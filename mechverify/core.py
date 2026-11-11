"""Transparent structured fact checker for the pilot.

IMPORTANT: this checker consumes manually annotated, structured claims.
It does NOT parse unstructured scientific language or independently
understand mechanochemistry. Its current score is a software sanity check.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT")


def load_json(name: str) -> list[dict[str, Any]]:
    with (ROOT / "data" / name).open(encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class Judgment:
    label: str
    reason: str
    evidence_ids: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def value_agrees(claim_value: Any, evidence_value: Any, tolerance: float = 0) -> bool:
    # bool must not be conflated with 0 or 1
    if type(claim_value) is not type(evidence_value):
        return False
    if isinstance(claim_value, (int, float)) and not isinstance(claim_value, bool):
        return abs(claim_value - evidence_value) <= tolerance
    return claim_value == evidence_value


def verify_structured(case: dict[str, Any], evidence: list[dict[str, Any]]) -> Judgment:
    query = case["structured_claim"]
    same_subject = [
        f for f in evidence
        if f["paper_id"] == case["paper_id"]
        and f["system"] == query["system"]
        and f["property"] == query["property"]
    ]
    same_context = [f for f in same_subject if f["context"] == query["context"]]
    if not same_context:
        if same_subject:
            return Judgment("INSUFFICIENT", "Evidence exists for the property, but not under the stated conditions.", [])
        return Judgment("INSUFFICIENT", "No matching evidence record for this system and property.", [])

    consistent = []
    inconsistent = []
    for fact in same_context:
        if query.get("unit") != fact.get("unit"):
            return Judgment("INSUFFICIENT", "Unit differs; conversion has not been implemented for this field.", [fact["id"]])
        if value_agrees(query["value"], fact["value"], float(fact.get("tolerance", 0))):
            consistent.append(fact)
        else:
            inconsistent.append(fact)
    if consistent and inconsistent:
        return Judgment("INSUFFICIENT", "Conflicting evidence records require adjudication.", [f["id"] for f in same_context])
    if consistent:
        return Judgment("SUPPORTED", "Matches the curated measurement under the same experimental conditions.", [f["id"] for f in consistent])
    return Judgment("CONTRADICTED", "Conflicts with the curated measurement under the same experimental conditions.", [f["id"] for f in inconsistent])


def majority_baseline(_: dict[str, Any]) -> Judgment:
    return Judgment("SUPPORTED", "Naive always-supported baseline; for comparison only.", [])
