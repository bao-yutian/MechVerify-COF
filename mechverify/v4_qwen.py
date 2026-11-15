"""V4: API-free Qwen claim extraction + independent source-condition checking.

Run on Google Colab with a GPU for Qwen; replay mode is CPU-only.
Never passes gold labels or manually structured claims to Qwen or verifier.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import LABELS, load_json
from .evaluation import metrics
from .v4_checker import extraction_schema, compare_claim_to_evidence

DEFAULT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
SYSTEM_PROMPT = """You are a scientific claim STRUCTURE EXTRACTOR, not a judge.
Your ONLY task is to parse the claim text. Do not assess whether it is true.
Do not take any values or experimental conditions from an evidence document.
Do not infer missing experimental conditions. An unmentioned condition should
be omitted from context, not invented. Keep the claim's original polarity.
Return ONLY a JSON object with exactly these fields:
{"system": string, "property": string, "context": object, "value": number|string|boolean, "unit": string|null}

Use one of the provided canonical system and property names if applicable.
Use only the provided context keys. Normalize experimental method when
explicitly stated or unambiguously described in the claim:
- milling an amorphous polymer precursor to make a COF: COP_to_COF
- de novo direct mechanosynthesis: de_novo_mechanosynthesis
- ordinary ball milling: ball_milling
- mechanochemical model reaction: mechanochemical_model
- comparing imine exchange and direct condensation: exchange_vs_direct_condensation
- mechanochemical direct imine condensation: mechanochemical_direct_condensation
Represent a frequency comparison as context.frequency_range_hz = "15-30"
(not separate start/end) and a specific frequency as frequency_hz = 25.
Represent 2 hours compared with 1 hour as duration_comparison_h = "2_vs_1".
When stated, use scope: reported_COFS, all_imine_COFs, or tested_conditions.
When stated, time-resolved proton NMR is measurement = time_resolved_1H_NMR.
For crystallinity trends use: increased, decreased,
increased_significantly, no_significant_change.
For milling frequency and reaction progress use: accelerated or decelerated.
For crystallinity lower after 2h vs 1h use: lower_at_2h.
For imine exchange rate vs direct condensation use: slower or faster.
For higher BET of imine exchange vs direct condensation use: higher_for_exchange,
or lower_for_exchange for lower.
For whether a COF can be made by direct condensation use JSON true/false.
For numerical BET area, use a number and unit "m2/g".
For completion time, use a number and unit "min".
For qualitative properties, use unit null.
If an entity/property cannot be mapped, use the literal words from the claim.
"""


def extraction_messages(claim: str, facts: list[dict]) -> list[dict[str, str]]:
    schema = extraction_schema(facts)
    # The ontology contains allowed terms, NOT evidence values, gold labels,
    # source records, or manually pre-annotated claim structures.
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(
            {"claim": claim, "allowed_ontology": schema}, ensure_ascii=False,
        )},
    ]


def parse_extraction(text: str) -> dict | None:
    """Parse a JSON object from Qwen output; malformed JSON is a model error."""
    raw = text.strip()
    if raw.startswith(chr(96) * 3):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit(chr(96) * 3, 1)[0].strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        if start < 0:
            return None
        try:
            result, _ = json.JSONDecoder().raw_decode(raw[start:])
        except json.JSONDecodeError:
            return None
    return result if isinstance(result, dict) else None


def _summarize(cases: list[dict], rows: list[dict]) -> dict[str, Any]:
    valid = [r for r in rows if r["predicted"] in LABELS]
    valid_ids = {r["id"] for r in valid}
    eligible = [c for c in cases if c["id"] in valid_ids]
    correct = sum(r["predicted"] == r["gold_label"] for r in rows)
    return {
        "total_cases": len(rows),
        "coverage": round(len(valid) / len(rows), 4) if rows else 0,
        "correct_vs_provisional_gold_all_cases": correct,
        "overall_provisional_accuracy": round(correct / len(rows), 4) if rows else None,
        "prediction_counts": dict(Counter(r["predicted"] for r in rows)),
        "conditional_metrics_covered_only": (
            metrics(eligible, {r["id"]: r["predicted"] for r in valid})
            if eligible else None
        ),
    }


def _checkpoint(destination: Path, rows: list[dict], args: argparse.Namespace,
                complete: bool, cases: list[dict]) -> None:
    report = {
        "version": "v4_qwen_extraction_plus_evidence_checker",
        "model": args.model if not args.replay else "replay:" + args.replay,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed" if complete else "in_progress",
        "warning": (
            "Development-set diagnostic, not a held-out scientific benchmark. "
            "Source U is abstract-only. H-02 gold label is not independently confirmed. "
            "No claim structured annotations or gold labels used by the extractor/checker."
        ),
        "summary": _summarize(cases, rows),
        "predictions": rows,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(destination)


def run(args: argparse.Namespace) -> None:
    cases = load_json("cases.json")
    facts = load_json("evidence.json")
    if args.limit is not None:
        cases = cases[:args.limit]
    if not cases:
        raise SystemExit("No cases selected")
    destination = Path(args.output)
    if args.replay and Path(args.replay).resolve() == destination.resolve():
        raise SystemExit("--output must be a different path than --replay")

    if args.replay:
        previous = json.loads(Path(args.replay).read_text(encoding="utf-8"))
        cached = {r["id"]: r for r in previous.get("predictions", [])}
        missing = {c["id"] for c in cases} - set(cached)
        if missing:
            raise SystemExit(f"Replay file missing cases: {sorted(missing)}")
        model, tokenizer, torch = None, None, None
    else:
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
        except ImportError as exc:
            raise SystemExit(
                "Install dependencies in Colab: pip install -q transformers accelerate torch"
            ) from exc
        if not torch.cuda.is_available():
            print("WARNING: No CUDA GPU. Inference may be very slow.", flush=True)
        print(f"Loading {args.model} ...", flush=True)
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForCausalLM.from_pretrained(
            args.model, dtype="auto", device_map="auto"
        )
        model.eval()

    rows = []
    for i, case in enumerate(cases, start=1):
        if args.replay:
            row_cache = cached[case["id"]]
            extracted = row_cache.get("extracted")
            raw = row_cache.get("raw_model_response", "")
        else:
            messages = extraction_messages(
                case["claim"],
                [f for f in facts if f["paper_id"] == case["paper_id"]],
            )
            batch = tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
                return_tensors="pt", return_dict=True,
            ).to(model.device)
            with torch.inference_mode():
                generated = model.generate(
                    **batch, do_sample=False, max_new_tokens=args.max_new_tokens,
                    pad_token_id=tokenizer.eos_token_id,
                )
            raw = tokenizer.decode(
                generated[0][batch["input_ids"].shape[-1]:],
                skip_special_tokens=True,
            )
            extracted = parse_extraction(raw)

        judgment = compare_claim_to_evidence(extracted, case["paper_id"], facts)
        row = {
            "id": case["id"],
            "claim": case["claim"],
            "gold_label": case["gold_label"],  # reporting only; NEVER sent to model/checker
            "predicted": judgment.label,
            "reason": judgment.reason,
            "evidence_ids": judgment.evidence_ids,
            "extracted": extracted,
            "raw_model_response": raw,
            "correct_against_provisional_gold": judgment.label == case["gold_label"],
        }
        rows.append(row)
        _checkpoint(destination, rows, args, complete=False, cases=cases)
        print(
            f"[{i}/{len(cases)}] {case['id']}: {judgment.label}; "
            f"gold (provisional): {case['gold_label']}; saved {destination}",
            flush=True,
        )

    _checkpoint(destination, rows, args, complete=True, cases=cases)
    print("\n" + json.dumps(_summarize(cases, rows), ensure_ascii=False, indent=2))
    print(f"Saved: {destination}")


def main() -> None:
    p = argparse.ArgumentParser(description="MechVerify V4: Qwen extraction -> independent evidence check")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--limit", type=int, default=None, help="Run first N cases")
    p.add_argument("--max-new-tokens", type=int, default=320)
    p.add_argument("--output", default="results/v4_qwen.json")
    p.add_argument("--replay", default=None,
                   help="Recheck stored Qwen extraction JSON with current checker (CPU only)")
    args = p.parse_args()
    if args.limit is not None and args.limit < 1:
        p.error("--limit must be >=1")
    run(args)


if __name__ == "__main__":
    main()
