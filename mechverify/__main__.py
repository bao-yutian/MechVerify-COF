"""Run `python -m mechverify --help`."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import load_json, verify_structured, majority_baseline
from .evaluation import metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="MechVerify COF mechanosynthesis pilot")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="List all pilot cases and gold labels")
    sub.add_parser("papers", help="Show bibliography and source scope")
    check = sub.add_parser("check", help="Inspect one structured-checker decision")
    check.add_argument("case_id", help="e.g. H-01")
    run = sub.add_parser("evaluate", help="Run and score a specified evaluator")
    run.add_argument("--strategy", choices=["structured", "always-supported", "llm"], default="structured")
    run.add_argument("--output", default=None, help="Optional JSON result path")
    args = parser.parse_args()
    cases = load_json("cases.json")
    facts = load_json("evidence.json")
    if args.command == "inspect":
        for c in cases:
            print(f"{c['id']:5} {c['gold_label']:15} {c['claim']}")
        return
    if args.command == "papers":
        for p in load_json("papers.json"):
            print(f"{p['id']}: {p['title']}\n  {p['url']} [{p['source_scope']}]")
        return
    if args.command == "check":
        item = next((c for c in cases if c["id"] == args.case_id), None)
        if item is None:
            parser.error("Unknown case_id. Run `python -m mechverify inspect`.")
        result = verify_structured(item, facts)
        print(json.dumps({"id": item["id"], "claim": item["claim"], "prediction": result.as_dict(),
                          "gold_label": item["gold_label"]}, indent=2, ensure_ascii=False))
        return
    predictions = {}
    output_rows = []
    for c in cases:
        if args.strategy == "structured":
            judgment = verify_structured(c, facts)
        elif args.strategy == "always-supported":
            judgment = majority_baseline(c)
        else:
            from .llm import judge_claim
            judgment = judge_claim(c, facts)
        predictions[c["id"]] = judgment.label
        output_rows.append({"id": c["id"], "predicted": judgment.label,
                            "gold_label": c["gold_label"], "reason": judgment.reason,
                            "evidence_ids": judgment.evidence_ids})
    summary = metrics(cases, predictions)
    result = {"strategy": args.strategy, "warning":
              ("This is a manually structured evidence-lookup sanity test, NOT a natural-language AI accuracy result."
               if args.strategy == "structured" else "Small pilot; performance is not statistically reliable."),
              "metrics": summary, "predictions": output_rows}
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved: {path}")
    print(json.dumps({"strategy": args.strategy, "warning": result["warning"],
                      "accuracy": summary["accuracy"], "macro_f1": summary["macro_f1"],
                      "n": summary["n"], "label_counts": summary["label_counts"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
