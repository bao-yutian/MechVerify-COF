# V3 claim guardrail: first 15-case development diagnostic

Date: 2026-11-13

## Reproduced run (user's Colab)

Command:

```bash
python -m mechverify.guardrail_eval
```

- Test suite: 13/13 passed (`python -m unittest discover -s tests -v`)
- Cases: 15
- V3 predictions on *supported scope* (H cases): 5/15 = 33.33% coverage
- 10/15 returned NOT_IMPLEMENTED (all five B and all five U cases)
- Agreement with **provisional** labels on covered cases: 4/5 = 80.0%
- Covered macro F1 vs provisional labels: 0.7778
- Predictions:
  - H-01 SUPPORTED (provisional gold SUPPORTED)
  - H-02 INSUFFICIENT (provisional gold CONTRADICTED) — **ambiguous evidence/label**
  - H-03 SUPPORTED (provisional gold SUPPORTED)
  - H-04 CONTRADICTED (provisional gold CONTRADICTED)
  - H-05 INSUFFICIENT (provisional gold INSUFFICIENT)
  - All B-01...B-05 and U-01...U-05 NOT_IMPLEMENTED

## Interpretation

This run confirms **code coverage limitations**, not superiority over Qwen.
- Qwen-only had 6/15 = 40.0% accuracy (all SUPPORTED) on the complete set.
- V3's 4/5 is a *different denominator* and the same examples were used to design its rules.
- No evidence that V3 generalizes, no independent-held-out result, no fair 15-case head-to-head yet.
- Structured baseline uses manually curated claim structures and is an oracle/sanity check, not a real automated Auditor.
- H-02 should not be used as an unambiguous contradicted example: 'completed within ~45 min' by itself does not rule out completion at 5 min. The kinetic figure/SI needs review.

## What to add next and why

Build **general claim-to-evidence feature extraction** that reads only
`case['claim']` plus source evidence; do NOT supply
`case['gold_label']` or `case['structured_claim']` to the model.

Prioritize **B papers** before adding hand-written patterns to every case:

- B-04: Same TFPPy-PDA material, different synthesis route. Claim uses ~150 m2/g for COP-to-COF, but that value belongs to the *de novo* route; COP-to-COF reported ~850 m2/g. Requires **route-aware numerical matching** rather than number-only matching.
- B-05: extrapolating frequency from tested 15–30 Hz to 60 Hz. Requires **out-of-distribution condition detection**.
- B-01/B-02: trend reversal under the same stated route/range.
- U-01/U-02: imine exchange vs condensation rate reversal, conditional on measurement.
- U-03/U-04/U-05: route-specific BET, failed direct condensation, universal claim extrapolation.

Design:
1. LLM extracts `system`, `property`, `method`, `conditions`, `value`, `unit` and relevant source IDs from **raw claim text** (not gold metadata).
2. Python checks against curated evidence, with explicit conflicts, mismatched contexts, out-of-range claims, and **EXTRACTION_ERROR/NOT_IMPLEMENTED** separate from **INSUFFICIENT**.
3. Score separately: extraction success, coverage, evidence citation, label accuracy on all cases, and abstention rate.
4. Freeze prompt/code before testing on papers not previously seen.

## Important caveat

The 15 cases are a **development set**, not publishable model evaluation. Third paper U is based on abstract-only source review; revise labels after full text/SI verification.
