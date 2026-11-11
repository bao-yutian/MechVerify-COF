"""Run a local Hugging Face Qwen baseline against the COF pilot cases.

Intended for a Google Colab GPU runtime. Requires transformers, torch, accelerate.
No API key or model installed on the user's own computer is required.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .core import LABELS, load_json
from .evaluation import metrics

DEFAULT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
SYSTEM_PROMPT = """You are reviewing a scientific claim about mechanochemical COF synthesis.
Only the supplied evidence is available to you. Match the material, synthesis route,
experimental conditions, quantity, and comparison before making a decision.
Choose exactly one label:
SUPPORTED = claim follows from the provided evidence under matching conditions.
CONTRADICTED = evidence directly conflicts with the claim under matching conditions.
INSUFFICIENT = the evidence does not establish or contradict the claim.
Do not generalize to untested frequencies or materials. Faster reaction progress is
not the same as greater crystallinity. Do not use external information.
Return ONE valid JSON object with keys "label", "reason", "evidence_ids".
"""


def build_messages(case: dict, facts: list[dict]) -> list[dict[str, str]]:
    """Use raw claim/evidence text, never human gold labels or structured claims."""
    evidence = [
        {"id": f["id"], "statement": f["evidence_note"],
         "system": f["system"], "conditions": f["context"],
         "source_locator": f["locator"]}
        for f in facts if f["paper_id"] == case["paper_id"]
    ]
    payload = {"claim": case["claim"], "evidence": evidence}
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def parse_response(raw: str, known_ids: set[str]) -> dict | None:
    """Return a validated judgment, or None for malformed model output."""
    text = raw.strip()
    # Allow markdown fences, but never silently map parse failures to INSUFFICIENT.
    if text.startswith(chr(96) * 3):
        text = re.sub(r"^\x60{3}(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*\x60{3}$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        candidate = re.search(r"\{[\s\S]*?\}", text)
        if not candidate:
            return None
        try:
            data = json.loads(candidate.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    label = data.get("label")
    if not isinstance(label, str) or label.strip().upper() not in LABELS:
        return None
    ids = data.get("evidence_ids", [])
    if not isinstance(ids, list):
        ids = []
    return {
        "label": label.strip().upper(),
        "reason": str(data.get("reason", "")),
        "evidence_ids": [x for x in ids if isinstance(x, str) and x in known_ids],
    }


def run(args: argparse.Namespace) -> None:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("Install dependencies in Colab: pip install -q transformers accelerate torch") from exc

    if not torch.cuda.is_available():
        print("WARNING: No CUDA GPU detected; local Qwen inference may be very slow.")
    print(f"Loading model {args.model} ...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype="auto", device_map="auto"
    )
    model.eval()

    cases = load_json("cases.json")
    facts = load_json("evidence.json")
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No cases to evaluate")

    rows = []
    for index, case in enumerate(cases, start=1):
        messages = build_messages(case, facts)
        batch = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_tensors="pt", return_dict=True,
        ).to(model.device)
        with torch.inference_mode():
            generated = model.generate(
                **batch, do_sample=False,
                max_new_tokens=args.max_new_tokens,
                pad_token_id=tokenizer.eos_token_id,
            )
        raw = tokenizer.decode(
            generated[0][batch["input_ids"].shape[-1]:],
            skip_special_tokens=True,
        )
        known = {f["id"] for f in facts if f["paper_id"] == case["paper_id"]}
        parsed = parse_response(raw, known)
        predicted = parsed["label"] if parsed else "PARSE_ERROR"
        row = {
            "id": case["id"], "paper_id": case["paper_id"],
            "claim": case["claim"], "gold_label": case["gold_label"],
            "predicted": predicted, "correct": predicted == case["gold_label"],
            "reason": parsed["reason"] if parsed else "Model response not valid judgment JSON",
            "evidence_ids": parsed["evidence_ids"] if parsed else [],
            "raw_model_response": raw,
        }
        rows.append(row)
        print(f"[{index}/{len(cases)}] {case['id']}: predicted={predicted}, expected={case['gold_label']}", flush=True)

    valid = [r for r in rows if r["predicted"] in LABELS]
    # Distinguish model response failures from the scientific INSUFFICIENT label.
    scored = metrics(
        [c for c in cases if c["id"] in {r["id"] for r in valid}],
        {r["id"]: r["predicted"] for r in valid},
    ) if valid else None
    total = len(rows)
    summary = {
        "n": total,
        "accuracy_all_cases": round(sum(r["correct"] for r in rows) / total, 4),
        "parse_success_rate": round(len(valid) / total, 4),
        "parse_errors": total - len(valid),
        "predicted_counts": dict(Counter(r["predicted"] for r in rows)),
        "parsed_only_metrics": scored,
    }
    report = {
        "model": args.model,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "warning": "15 manually curated pilot cases, not an independent benchmark; paper U reviewed against abstract only.",
        "summary": summary,
        "predictions": rows,
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved: {destination}")


def main() -> None:
    p = argparse.ArgumentParser(description="Run Qwen locally (e.g. on Google Colab GPU) without an API key")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--limit", type=int, default=None, help="Only the first N cases for a smoke test")
    p.add_argument("--max-new-tokens", type=int, default=220)
    p.add_argument("--output", default="results/qwen_local.json")
    args = p.parse_args()
    if args.limit is not None and args.limit <= 0:
        p.error("--limit must be positive")
    run(args)


if __name__ == "__main__":
    main()
