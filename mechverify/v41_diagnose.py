"""V4.1 post-hoc audit of claim extraction, using only claim text and source ontology.

This does not repair model outputs or grade science. It marks cases whose
extracted structure is inconsistent with explicit terms in the claim, so a
failed extraction is not mistaken for genuinely insufficient paper evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from .core import load_json
from .v4_checker import extraction_schema


def number_tokens(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", text)]


def audit_extraction(claim: str, extracted: object, paper_facts: list[dict]) -> list[str]:
    problems: list[str] = []
    if not isinstance(extracted, dict):
        return ["Extraction is not a JSON object"]
    schema = extraction_schema(paper_facts)
    source_systems = set(schema["systems"])
    system = extracted.get("system")
    prop = extracted.get("property")
    context = extracted.get("context")

    if not isinstance(system, str):
        problems.append("No valid system name")
    elif system not in source_systems and system.lower() not in claim.lower():
        problems.append("Extracted system is neither a source system nor explicitly named in claim")

    # These material names are explicit lexical anchors, not gold annotations.
    for f in paper_facts:
        s = f["system"]
        if s in {"COF-1", "DBrTP-TPB", "TFPPy-PDA"} and s.lower() in claim.lower():
            if system != s:
                problems.append("Explicit material " + s + " replaced with " + str(system))
        if s == "AIE_based_COF" and re.search(r"\bAIE[- ]based COF\b", claim, re.I):
            if system != s:
                problems.append("Explicit AIE-based COF replaced with " + str(system))

    if prop not in schema["properties"]:
        problems.append("Property not in this paper's evidence ontology: " + str(prop))
    if prop == "crystallinity_2h_vs_1h" and not re.search(r"\bhours?\b", claim, re.I):
        problems.append("Hours-comparison property hallucinated without hour values in claim")
    if prop in {"frequency_effect_on_crystallinity", "crystallinity_change_with_frequency"}:
        if not re.search(r"\bcrystallinity\b", claim, re.I):
            problems.append("Crystallinity comparison property not mentioned in claim")
    if prop == "BET_surface_area" and not re.search(r"\b(?:BET|surface area)\b", claim, re.I):
        problems.append("BET/surface area property not mentioned in claim")

    if not isinstance(context, dict):
        problems.append("Context is not an object")
        return problems

    unexpected_keys = set(context) - set(schema["context_keys"])
    if unexpected_keys:
        problems.append("Context contains invalid keys: " + ", ".join(sorted(unexpected_keys)))

    claimed_numbers = number_tokens(claim)
    for k in ("frequency_hz", "duration_min"):
        v = context.get(k)
        if v is None:
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            problems.append(k + " must be a single numeric value")
        elif float(v) not in claimed_numbers:
            problems.append(k + " is not explicitly present in claim")

    v = context.get("frequency_range_hz")
    if v is not None:
        m = re.search(
            r"(\d+)\s*(?:Hz\s*)?(?:to|[-–—])\s*(\d+)\s*Hz", claim, re.I
        )
        expected = (int(m.group(1)), int(m.group(2))) if m else None
        formatted = str(v).replace("–", "-").replace(" ", "")
        if expected is None or formatted != f"{expected[0]}-{expected[1]}":
            problems.append("Frequency range does not match the claim")

    if "duration_comparison_h" in context and not re.search(r"\bhours?\b", claim, re.I):
        problems.append("Duration comparison hallucinated; claim has no hours")
    if "time_points_min" in context and not re.search(r"\b(?:min|minutes)\b", claim, re.I):
        problems.append("Minute time points hallucinated; claim has no minutes")
    if "measurement" in context and not re.search(r"\bNMR\b", claim, re.I):
        problems.append("Measurement added without NMR mention")
    if "scope" in context:
        scope = context["scope"]
        if scope == "all_imine_COFs" and not re.search(r"\b(?:every|all)\b", claim, re.I):
            problems.append("Universal scope added without all/every")
        if scope == "reported_COFS" and not re.search(r"\b(?:reported|compared)\b", claim, re.I):
            problems.append("Reported-products scope not explicitly grounded")
    if "method" in context and context["method"] not in schema["allowed_methods"]:
        problems.append("Method is not canonical for the paper")

    value = extracted.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) not in claimed_numbers:
            problems.append("Numeric claim value not present in raw claim text")
    if extracted.get("unit") == "null":
        problems.append("Unit is literal string 'null' rather than JSON null")
    return list(dict.fromkeys(problems))


def diagnose(report: dict) -> dict:
    facts = load_json("evidence.json")
    rows = []
    for r in report["predictions"]:
        source = [f for f in facts if f["paper_id"] == r["id"].split("-")[0]]
        errors = audit_extraction(r["claim"], r.get("extracted"), source)
        rows.append({
            "id": r["id"],
            "old_prediction": r["predicted"],
            "extraction_trustworthy_under_checks": not errors,
            "grounding_problems": errors,
            "note": "Not a corrected scientific verdict. Failure checks are necessary, not sufficient."
        })
    bad = [r for r in rows if r["grounding_problems"]]
    return {
        "source_version": report.get("version"),
        "warning": "Post-hoc development diagnostics only. No scientific labels were repaired or changed.",
        "summary": {
            "n": len(rows),
            "suspect_extractions": len(bad),
            "previous_scientific_labels_with_suspect_extraction": sum(
                r["old_prediction"] in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT") for r in bad
            ),
            "failure_reason_counts": dict(Counter(
                problem for row in rows for problem in row["grounding_problems"]
            )),
        },
        "diagnostics": rows,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit saved V4 Qwen extraction against raw claim")
    parser.add_argument("--input", required=True, help="Existing V4 run JSON")
    parser.add_argument("--output", default="results/v41_extraction_diagnostics.json")
    args = parser.parse_args()
    old = json.loads(Path(args.input).read_text(encoding="utf-8"))
    new = diagnose(old)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(new["summary"], indent=2, ensure_ascii=False))
    for row in new["diagnostics"]:
        print(row["id"], "SUSPECT" if row["grounding_problems"] else "NO_RED_FLAGS",
              "; ".join(row["grounding_problems"][:2]))
    print("Saved:", path)


if __name__ == "__main__":
    main()
