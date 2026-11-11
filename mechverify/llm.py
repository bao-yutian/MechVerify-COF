"""OPTIONAL raw-text LLM judge using a user-configured OpenAI-compatible endpoint.

Requires user-provided LLM_BASE_URL, LLM_API_KEY, LLM_MODEL.
Never includes gold labels or manually annotated structured claims in prompts.
"""
from __future__ import annotations
import json
import os
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from .core import Judgment, LABELS

PROMPT = """You are auditing a claim about mechanochemical COF synthesis.
Use ONLY the provided evidence. Check whether the statement follows under the
stated conditions. Do not generalize findings to untested milling settings.
Return exactly one JSON object with keys label, reason, evidence_ids.
label MUST be SUPPORTED, CONTRADICTED, or INSUFFICIENT.
SUPPORTED: explicitly follows from the evidence.
CONTRADICTED: explicitly conflicts with evidence under matching conditions.
INSUFFICIENT: evidence does not establish or contradict this claim.
"""


def judge_claim(case: dict, facts: list[dict]) -> Judgment:
    base_url = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("LLM_MODEL", "").strip()
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not (base_url and model and key):
        raise RuntimeError("Set LLM_BASE_URL, LLM_MODEL and LLM_API_KEY first (see README).")
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise ValueError("For safety LLM_BASE_URL must use HTTPS.")
    # This is a deliberate external API call. Do not send private unpublished data.
    papers_facts = [
        {"evidence_id": f["id"], "statement": f["evidence_note"],
         "system": f["system"], "conditions": f["context"], "locator": f["locator"]}
        for f in facts if f["paper_id"] == case["paper_id"]
    ]
    payload = {
        "model": model, "temperature": 0,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps({"claim": case["claim"], "evidence": papers_facts}, ensure_ascii=False)},
        ],
    }
    req = request.Request(
        base_url + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=75) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    content = answer["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    out = json.loads(content)
    if out["label"] not in LABELS:
        raise ValueError(f"Unrecognized model label: {out['label']}")
    return Judgment(out["label"], str(out.get("reason", "")), list(out.get("evidence_ids", [])))
