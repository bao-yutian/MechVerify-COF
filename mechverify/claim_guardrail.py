"""V3 experiment: conservative rule-based claim/evidence guardrail.

This is an *early diagnostic prototype*, NOT a scientific AI judge.
It takes a natural-language claim and the existing curated evidence records.
It does NOT read the dataset's structured_claim or gold_label fields.

Currently supports only COF-1 frequency/crystallinity, frequency/reaction
progress, and simple milling-completion-time wording. It deliberately
abstains when the evidence gives an upper time bound rather than an exact
completion time, or when it cannot parse a claim.

An eventual Hybrid Auditor should learn to extract claim features with
an LLM, validate them separately, and apply independently tested rules.
"""
from __future__ import annotations

import re
from typing import Any

from .core import Judgment

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


def _range_from_text(text: str) -> tuple[int, int] | None:
    m = re.search(r"\b(\d+)\s*(?:to|[-–—])\s*(\d+)\s*Hz\b", text, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _frequency_from_text(text: str) -> int | None:
    # Explicit values only; do not invent missing conditions.
    m = re.search(
        r"\b(?:at|of)\s+(?:a\s+)?(?:previously\s+untested\s+)?"
        r"(?:milling\s+)?(?:frequency\s+of\s+)?(\d+)\s*Hz\b",
        text, re.I,
    )
    return int(m.group(1)) if m else None


def _as_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    return _range_from_text(value + " Hz")


def _completion_time(text: str) -> float | None:
    m = re.search(
        r"\b(?:completion|full conversion)\b"
        r"[\s\S]{0,80}?\b(?:in|within)\s+"
        r"(?:approximately\s+|about\s+|~\s*)?"
        r"(\d+(?:\.\d+)?)\s*(?:minutes|min)\b",
        text, re.I,
    )
    return float(m.group(1)) if m else None


def extract_claim_features(claim: str) -> dict[str, Any]:
    """Limited, inspectable extraction from claim text (NO gold annotations)."""
    text = claim.lower()
    subject = "COF-1" if re.search(r"\bcof-1\b", text, re.I) else None
    f = _frequency_from_text(claim)
    frange = _range_from_text(claim)
    features: dict[str, Any] = {
        "system": subject,
        "frequency_hz": f,
        "frequency_range_hz": frange,
        "property": None,
        "value": None,
    }

    if re.search(r"\bcrystallinity\b", text) and "frequen" in text:
        features["property"] = "frequency_effect_on_crystallinity"
        if re.search(r"\b(?:significantly\s+improv|improv\w*\s+significantly)\w*", text):
            features["value"] = "increased_significantly"
        elif re.search(r"\bno\s+significant\s+(?:change|improvement)\b", text):
            features["value"] = "no_significant_change"

    elif ("completion" in text or "full conversion" in text):
        features["property"] = "milling_completion_time_min"
        features["value"] = _completion_time(claim)

    elif "reaction progress" in text and "frequen" in text:
        features["property"] = "frequency_effect_on_reaction"
        if re.search(r"\baccelerat\w*\b", text):
            features["value"] = "accelerated"

    return features


def _same_conditions(features: dict[str, Any], context: dict[str, Any]) -> bool:
    frequency = features["frequency_hz"]
    frange = features["frequency_range_hz"]
    if frequency is not None:
        # Never infer an untested frequency from evidence at a different one.
        if context.get("frequency_hz") != frequency:
            return False
    if frange is not None:
        if _as_range(context.get("frequency_range_hz")) != frange:
            return False
    return True


def verify_claim_text(claim: str, paper_id: str, facts: list[dict]) -> Judgment:
    """Conservative rule check; never consult structured_claim or gold_label."""
    f = extract_claim_features(claim)
    if f["system"] is None or f["property"] is None or f["value"] is None:
        return Judgment(NOT_IMPLEMENTED, "Claim features not reliably parsed by current prototype.", [])

    candidates = [
        row for row in facts
        if row.get("paper_id") == paper_id
        and row.get("system") == f["system"]
        and row.get("property") == f["property"]
    ]
    matching = [row for row in candidates if _same_conditions(f, row.get("context", {}))]

    if not matching:
        return Judgment(
            "INSUFFICIENT",
            "No evidence for the claimed property under these exact experimental conditions.",
            [],
        )

    if len(matching) != 1:
        return Judgment(
            "INSUFFICIENT", "Multiple matching evidence records need further adjudication.",
            [row["id"] for row in matching],
        )

    fact = matching[0]
    claimed, observed = f["value"], fact.get("value")
    source_id = [fact["id"]]

    if f["property"] == "milling_completion_time_min":
        if not isinstance(claimed, (int, float)) or not isinstance(observed, (int, float)):
            return Judgment(NOT_IMPLEMENTED, "Completion-time quantity is not numeric.", source_id)
        tolerance = float(fact.get("tolerance", 0))
        if abs(float(claimed) - float(observed)) <= tolerance:
            return Judgment(
                "SUPPORTED", "Claim is approximately consistent with the reported completion-time bound.",
                source_id,
            )
        if claimed < observed - tolerance:
            # 'completed within 45 min' does NOT logically disprove 5 min.
            return Judgment(
                "INSUFFICIENT",
                "Evidence reports completion within an upper time bound; it cannot exclude earlier completion without time-resolved data.",
                source_id,
            )
        return Judgment(
            "CONTRADICTED", "Claimed completion time is later than the reported completion bound.",
            source_id,
        )

    if f["property"] == "frequency_effect_on_crystallinity":
        if claimed == observed:
            return Judgment("SUPPORTED", "Crystallinity trend matches evidence.", source_id)
        if claimed == "increased_significantly" and observed == "no_significant_change":
            return Judgment("CONTRADICTED", "Claimed improvement conflicts with unchanged crystallinity.", source_id)
        return Judgment(NOT_IMPLEMENTED, "Unrecognized crystallinity comparison.", source_id)

    if f["property"] == "frequency_effect_on_reaction":
        if claimed == observed:
            return Judgment("SUPPORTED", "Reaction-progress trend matches evidence.", source_id)
        return Judgment(NOT_IMPLEMENTED, "Unrecognized reaction-progress comparison.", source_id)

    return Judgment(NOT_IMPLEMENTED, "No checker implemented for parsed property.", source_id)
