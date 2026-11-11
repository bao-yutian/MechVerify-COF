"""Evaluation of prediction files against independently recorded gold labels."""
from __future__ import annotations
from collections import Counter
from typing import Any
from .core import LABELS


def metrics(cases: list[dict[str, Any]], predictions: dict[str, str]) -> dict[str, Any]:
    case_ids = {c["id"] for c in cases}
    if set(predictions) != case_ids:
        missing, extra = case_ids - set(predictions), set(predictions) - case_ids
        raise ValueError(f"Prediction IDs mismatch (missing={sorted(missing)}, extra={sorted(extra)}).")
    matrix = {gold: {pred: 0 for pred in LABELS} for gold in LABELS}
    for case in cases:
        gold, pred = case["gold_label"], predictions[case["id"]]
        if gold not in LABELS or pred not in LABELS:
            raise ValueError(f"Invalid class: {gold}, {pred}")
        matrix[gold][pred] += 1
    per_class = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        fn = sum(matrix[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "count": sum(matrix[label].values())}
    return {
        "n": len(cases),
        "accuracy": round(sum(matrix[l][l] for l in LABELS) / len(cases), 4),
        "macro_f1": round(sum(v["f1"] for v in per_class.values()) / len(LABELS), 4),
        "label_counts": dict(Counter(c["gold_label"] for c in cases)),
        "confusion": matrix,
        "per_class": per_class,
    }
