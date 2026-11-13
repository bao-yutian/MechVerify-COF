"""Evaluate the V3 text-only guardrail on all curated COF pilot claims.

Important: this is a development-set diagnostic, NOT an independent
benchmark. The checker reads only case claim + paper ID, not structured_claim
or gold labels. Gold labels are used here only to summarize predictions.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .claim_guardrail import NOT_IMPLEMENTED, verify_claim_text
from .core import LABELS, load_json
from .evaluation import metrics


def evaluate() -> dict:
    cases = load_json("cases.json")
    evidence = load_json("evidence.json")
    rows = []
    for case in cases:
        verdict = verify_claim_text(case["claim"], case["paper_id"], evidence)
        rows.append({
            "id": case["id"],
            "claim": case["claim"],
            "prediction": verdict.label,
            "gold_label": case["gold_label"],
            "reason": verdict.reason,
            "evidence_ids": verdict.evidence_ids,
            "correct_against_provisional_gold": verdict.label == case["gold_label"],
            "annotation_caution": (
                "H-02 is flagged for source-figure review; completion within 45 min "
                "does not by itself disprove completion at 5 min."
                if case["id"] == "H-02" else None
            ),
        })

    covered = [r for r in rows if r["prediction"] in LABELS]
    parsed_cases = [c for c in cases if c["id"] in {r["id"] for r in covered}]
    provisional_metrics = (
        metrics(parsed_cases, {r["id"]: r["prediction"] for r in covered})
        if covered else None
    )
    return {
        "version": "v3_text_rule_guardrail_development_diagnostic",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "warning": (
            "Not a complete hybrid Auditor. Regex supports only a few COF-1 "
            "claim patterns; this is the same development set used to create "
            "tests. Gold labels have not been independently validated. "
            "H-02 is annotation-ambiguous; do not count it as an established error."
        ),
        "summary": {
            "n": len(rows),
            "covered": len(covered),
            "coverage": round(len(covered) / len(rows), 4),
            "not_implemented": sum(r["prediction"] == NOT_IMPLEMENTED for r in rows),
            "prediction_counts": dict(Counter(r["prediction"] for r in rows)),
            "provisional_accuracy_on_covered": (
                round(sum(r["correct_against_provisional_gold"] for r in covered) / len(covered), 4)
                if covered else None
            ),
            "provisional_metrics_on_covered": provisional_metrics,
        },
        "predictions": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate text-only V3 COF guardrail on pilot examples")
    p.add_argument("--output", default="results/v3_guardrail_dev.json")
    args = p.parse_args()
    report = evaluate()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in report["predictions"]:
        print(
            f"{row['id']}: {row['prediction']:<15} "
            f"(provisional gold: {row['gold_label']})"
        )
    print("\n" + json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
