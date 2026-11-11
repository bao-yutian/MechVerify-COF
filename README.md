# MechVerify · COF Mechanosynthesis Pilot

**A reproducible starter project for evaluating whether AI-generated explanations of mechanochemical COF synthesis are supported by experimental evidence.**

## What is in this repository?

- `data/papers.json` — bibliographic records for three peer-reviewed COF mechanosynthesis papers.
- `data/evidence.json` — manually curated, structured experimental evidence (11 facts), with source locators.
- `data/cases.json` — **15 pilot claims**, including supported, contradicted, and insufficient-evidence examples.
- `mechverify/core.py` — transparent condition-matching and structured-value checking (a *software sanity test*, not an AI judge).
- `mechverify/llm.py` — optional zero-shot baseline that sends *claim text + evidence text* to a user-configured OpenAI-compatible LLM API.
- `mechverify/evaluation.py` — classification accuracy, class precision/recall/F1 and confusion matrices.
- `tests/` — repeatable unit tests.

## Quick start (Python 3.10+; stdlib only)

```bash
python -m mechverify papers
python -m mechverify inspect
python -m mechverify check H-04
python -m mechverify evaluate --strategy always-supported --output results/always_supported.json
python -m mechverify evaluate --strategy structured --output results/structured_sanity.json
python -m unittest discover -s tests -v
```

### Optional: run a *real LLM* baseline

Configure your own OpenAI-compatible endpoint and key (for example, one from a model provider you already use):

```bash
export LLM_BASE_URL="https://YOUR_PROVIDER/v1"
export LLM_MODEL="YOUR_MODEL"
export LLM_API_KEY="YOUR_KEY"
python -m mechverify evaluate --strategy llm --output results/llm_baseline.json
```

**Privacy:** this sends the claim text and curated evidence to your chosen third-party API. Use only public-source data and check your institution's requirements. Do not put keys in your Git repository. An API costs money depending on provider.

## Why this matters

Mechanical milling conditions do not map trivially to molecular forces; faster bond formation does not guarantee improved crystallinity. We test claims that confuse **reaction progress**, **crystallinity**, **route comparisons**, and **untested milling parameters**.

## Important scientific limitations

1. **The structured checker is not an LLM.** A human has already mapped each claim to a system, property, conditions, and value. It compares these to the curated evidence registry. It is expected to match the curated gold labels and cannot measure generalization. Its 15/15 on this data, if observed, is *not* AI accuracy or a research contribution.
2. **This is a pilot, not an independent benchmark.** There are only 15 cases from three papers. Claims are manually paraphrased. The third paper (`U`) has been checked against the **publisher abstract only**; its full text and SI require further review before publication-ready labels.
3. **Insufficient evidence is not necessarily falsity.** A claim about an untested milling frequency could be true, but cannot be inferred from reported conditions.
4. **No general claim that faster milling improves crystallinity.** Hamzehpoor et al. report faster reaction without a significant crystallinity change for COF-1 over their tested frequency range; Brown et al. report improved crystallinity for a *different* imine COF made from a COP precursor. These are different systems/routes.
5. **No author-independent annotations yet.** Before research use, have at least one independent expert verify each label and its paper/SI locator, freeze document-level splits, and expand the dataset.
6. **Structured claims are human annotations.** To make a complete Auditor, implement text-to-structured-claim extraction (LLM) and evaluate extraction errors separately, ideally with an independent retrieval stage and a tool-based numeric checker.

## Next experiments

- Run real LLM zero-shot baseline, storing raw model output and cost.
- Add an automated claim extractor; report end-to-end scores distinct from oracle-structured checks.
- Add document-level train/validation/test splits to prevent leakage.
- Expand to 20–30 papers and ~100+ independently reviewed claims.
- Compare LLM only, LLM + evidence, condition-aware checking, and physics checking using a held-out set.
- Include a clear taxonomy: force/energy confusion, condition mismatch, conversion/crystallinity confusion, kinetics/generalization, and unsupported causal inference.

## Primary papers

1. Hamzehpoor, E. et al. *Mechanochemical Synthesis of Boroxine-linked Covalent Organic Frameworks.* **Angew. Chem. Int. Ed.** (2024). https://doi.org/10.1002/anie.202404539  
   Evidence: publisher full text (Results, Fig. 3) on COF-1 25 Hz/45 min and milling-frequency effects.
2. Brown, N. et al. *Amorphous-to-crystalline transformation: a mechanochemical pathway to imine-linked covalent organic frameworks.* **RSC Mechanochem.** (2026). https://doi.org/10.1039/D5MR00161G  
   Evidence: publisher HTML full text, Figs. 1 and 5.
3. Uddin, M. H. et al. *A Mechanochemical Imine Exchange Route to 2D Imine-Linked Covalent Organic Frameworks.* **ACS Mater. Lett.** (2026). https://doi.org/10.1021/acsmaterialslett.6c00282  
   Evidence: publisher abstract only so far.

## Suggested portfolio statement (only after a true evaluation)

> Developed a condition-aware scientific verification benchmark for mechanochemical COF synthesis and evaluated LLM judgments against curated evidence, tracking unsupported extrapolations and confusion between reaction rate and crystallinity.

Do **not** claim an accuracy improvement until a real LLM experiment on a sufficiently large independently checked evaluation set is complete.

## Chinese quick guide

See `PILOT_STATUS_CN.md` for a concise Chinese project overview and GitHub upload instructions. Open `data/pilot_cases_for_review.csv` to review and annotate all 15 pilot cases in Excel or Google Sheets.