# Qwen2.5-1.5B-Instruct baseline: first diagnostic findings

## Observed run

User ran the `mechverify.qwen_local` baseline over all 15 pilot COF mechanosynthesis claims (CPU execution).

- `n=15`, `accuracy_all_cases=0.40`, `macro_f1=0.1905`, `parse_success_rate=1.0`
- Predictions: `SUPPORTED` for **all 15 cases**
- Gold labels: 6 `SUPPORTED`, 6 `CONTRADICTED`, 3 `INSUFFICIENT`
- This is identical to an always-supported majority baseline on this set. It does **not** establish reliable model performance outside the pilot.
- No evidence of an improvement from tool-based checking is yet available: structured checker uses human-provided claim structure.

## Three raw-output failure investigations

### H-02 — Numerical claim / potential annotation ambiguity

- Claim: COF-1 25 Hz milling completed in *approximately 5 min*.
- Qwen label: `SUPPORTED`.
- Model rationale: evidence says reaction completed *within 45 min*, 'which matches the claim'.
- Observation: model failed to distinguish 5 vs 45 min.
- **Gold-label caution:** source fact `H-F01` says **within approximately 45 min** rather than directly 'not complete at 5 min'. This wording alone is not logically enough to contradict completion at 5 min. Before treating H-02 as a strong contradiction test, review paper time-resolved data/Fig. 3 and either document noncompletion at 5 min or revise label to `INSUFFICIENT`.

### H-04 — Property conflation / internally contradictory rationale

- Claim: higher milling frequency significantly improved crystallinity (COF-1, 5–30 Hz).
- Qwen: `SUPPORTED` but its rationale says *no significant change in crystallinity*.
- The stronger matching evidence is `H-F03` (frequency did not significantly affect crystallinity), which model did not cite; it cited `H-F01` and `H-F02`.
- This is a clear explanation-verdict mismatch and an evidence-selection problem.

### H-05 — Unsupported extrapolation

- Claim: at 50 Hz (untested), COF-1 fully converts in 20 min.
- Evidence covers 5–30 Hz and/or 25 Hz, **not 50 Hz or the stated 20 min completion**.
- Qwen called the claim `SUPPORTED` and incorrectly stated that 25→50 Hz acceleration was evidenced.
- Correct evidence-grounded verdict: `INSUFFICIENT`.

## Next controlled experiment (avoid benchmark leakage)

1. Preserve current unmodified baseline output as `results/qwen_local_baseline_v1.json`; record exact commit/model/prompt/runtime and raw outputs. Do not overwrite it accidentally.
2. Independently recheck ambiguous annotations (especially H-02) with paper text, figures, supplementary information.
3. Implement a new **evidence-first** text extraction stage, with outputs such as `system`, `property`, `conditions`, `claim_value`, `evidence_value`, `comparison`, `source_id`. For mixed numeric/qualitative evidence, include exact citations and uncertainty.
4. Add Python comparisons and a distinct `EXTRACTION_ERROR` status. Never convert parser errors to `INSUFFICIENT` without evidence.
5. Report extraction accuracy, scientific-verdict accuracy, abstention rates, evidence-citation accuracy, and confusion matrix **separately**.
6. Treat these 15 cases as *development examples*. Freeze code/prompts before independent **paper-held-out** test cases. Do not claim performance improvements based on retuning to the same examples.

## The main research hypothesis

Evidence-grounded, condition-aware verification might catch numerical mismatch, property conflation, and unsupported extrapolation that a small zero-shot LLM misses. This is a hypothesis, not yet an empirical finding.
