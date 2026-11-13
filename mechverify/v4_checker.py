"""V4: independent condition-aware comparison of LLM-extracted scientific claims.

Input is an extraction from *claim text*, not the manually annotated
structured_claim or gold_label. Evidence is curated from public papers.
This prototype is domain-limited and does not independently read full PDFs.
"""
from __future__ import annotations

import re
from typing import Any

from .core import Judgment

NON_VERDICTS = ("EXTRACTION_ERROR", "NOT_IMPLEMENTED")
FIELDS = {"system", "property", "context", "value", "unit"}
CRITICAL_CONTEXT = {
    "method", "frequency_hz", "frequency_range_hz",
    "duration_comparison_h", "scope", "measurement",
}


def extraction_schema(facts: list[dict]) -> dict[str, Any]:
    """Evidence-derived ontology, with NO case labels, claim structures, or fact values."""
    return {
        "systems": sorted({f["system"] for f in facts}),
        "properties": sorted({f["property"] for f in facts}),
        "context_keys": sorted({k for f in facts for k in f["context"]}),
        "allowed_methods": sorted({
            f["context"]["method"] for f in facts if "method" in f["context"]
        }),
    }


def normalize_unit(unit: Any) -> str | None:
    if unit is None:
        return None
    if not isinstance(unit, str):
        return "INVALID_UNIT"
    cleaned = unit.strip().lower().replace("²", "2").replace(" ", "")
    return {"minutes": "min", "minute": "min", "m^2/g": "m2/g",
            "m2g-1": "m2/g"}.get(cleaned, cleaned)


def normalize_condition(value: Any) -> Any:
    if isinstance(value, str):
        v = value.strip().lower().replace("–", "-").replace("—", "-")
        v = re.sub(r"\s+to\s+", "-", v)
        v = re.sub(r"\s+", "", v)
        return v
    if isinstance(value, list) and len(value) == 2:
        return "-".join(str(x) for x in value)
    return value


def compare_claim_to_evidence(extracted: Any, paper_id: str, facts: list[dict]) -> Judgment:
    """Verify one extracted claim against same-paper, same-system source records."""
    if not isinstance(extracted, dict) or not FIELDS.issubset(extracted):
        return Judgment("EXTRACTION_ERROR", "Missing required extraction fields.", [])
    system, prop, context = extracted["system"], extracted["property"], extracted["context"]
    value, unit = extracted["value"], normalize_unit(extracted["unit"])
    if not isinstance(system, str) or not system or not isinstance(prop, str) or not prop:
        return Judgment("EXTRACTION_ERROR", "System/property must be nonempty strings.", [])
    if not isinstance(context, dict) or not isinstance(paper_id, str):
        return Judgment("EXTRACTION_ERROR", "Context must be a JSON object.", [])
    if any(not isinstance(k, str) or isinstance(v, (dict, list)) or v is None
           for k, v in context.items()):
        return Judgment("EXTRACTION_ERROR", "Invalid or incomplete context entries.", [])
    if value is None or isinstance(value, (dict, list)) or unit == "INVALID_UNIT":
        return Judgment("EXTRACTION_ERROR", "Missing or invalid value/unit.", [])

    schema = extraction_schema(facts)
    if prop not in schema["properties"]:
        return Judgment("NOT_IMPLEMENTED", "Scientific property is not covered by current evidence schema.", [])
    if set(context) - set(schema["context_keys"]):
        return Judgment("EXTRACTION_ERROR", "Unrecognized context keys: " +
                        ", ".join(sorted(set(context) - set(schema["context_keys"]))), [])

    candidates = [
        f for f in facts if f["paper_id"] == paper_id
        and f["system"] == system and f["property"] == prop
    ]
    if not candidates:
        return Judgment("INSUFFICIENT", "No evidence for this system/property in the cited paper.", [])

    matching = []
    for f in candidates:
        source_ctx = f["context"]
        # Any stated condition must match; never borrow numbers from other routes.
        if any(k not in source_ctx or normalize_condition(v) != normalize_condition(source_ctx[k])
               for k, v in context.items()):
            continue
        # Do not silently generalize source-specific experiments to unspecified scope.
        if any(k in source_ctx and k not in context for k in CRITICAL_CONTEXT):
            continue
        matching.append(f)

    if not matching:
        return Judgment("INSUFFICIENT",
                        "No record matches all stated conditions (or essential source constraints are absent).", [])

    supported, contradicted, undecidable = [], [], []
    for f in matching:
        source_id = f["id"]
        actual = f["value"]
        if normalize_unit(f.get("unit")) != unit:
            undecidable.append((source_id, "Unit mismatch"))
            continue
        if isinstance(actual, bool):
            if not isinstance(value, bool):
                undecidable.append((source_id, "Boolean value was not extracted as boolean"))
            elif value == actual:
                supported.append(source_id)
            else:
                contradicted.append(source_id)
        elif isinstance(actual, (int, float)) and not isinstance(actual, bool):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                undecidable.append((source_id, "Numerical value was not extracted as a number"))
                continue
            tolerance = float(f.get("tolerance", 0))
            difference = float(value) - float(actual)
            if abs(difference) <= tolerance:
                supported.append(source_id)
            elif ("within" in f.get("evidence_note", "").lower()
                  and difference < -tolerance):
                # Upper bound cannot exclude earlier reaction completion.
                undecidable.append((source_id, "Earlier completion not ruled out by an upper bound"))
            else:
                contradicted.append(source_id)
        elif isinstance(actual, str):
            if not isinstance(value, str):
                undecidable.append((source_id, "Categorical value not extracted as a string"))
            elif normalize_condition(actual) == normalize_condition(value):
                supported.append(source_id)
            else:
                contradicted.append(source_id)
        else:
            undecidable.append((source_id, "Unsupported evidence value type"))

    all_ids = [f["id"] for f in matching]
    if undecidable or (supported and contradicted):
        explanation = "; ".join(msg for _, msg in undecidable) or "Conflicting evidence records"
        return Judgment("INSUFFICIENT", explanation, all_ids)
    if supported:
        return Judgment("SUPPORTED", "Claim agrees with evidence under matching conditions.", supported)
    if contradicted:
        return Judgment("CONTRADICTED",
                        "Claim conflicts with evidence for the same system/property/conditions.",
                        contradicted)
    return Judgment("INSUFFICIENT", "Comparison was not established.", all_ids)
