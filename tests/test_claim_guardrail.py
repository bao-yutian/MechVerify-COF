"""Focused tests for the raw-text guardrail, distinct from gold-labelled structured checks."""
import unittest

from mechverify.claim_guardrail import extract_claim_features, verify_claim_text
from mechverify.core import load_json


class TestClaimGuardrail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = load_json("evidence.json")

    def test_h02_temporal_ambiguity(self):
        claim = ("For COF-1 milled at 25 Hz in the reported experiment, "
                 "completion occurred in approximately 5 minutes.")
        found = extract_claim_features(claim)
        self.assertEqual(found["frequency_hz"], 25)
        self.assertEqual(found["value"], 5)
        verdict = verify_claim_text(claim, "H", self.facts)
        self.assertEqual(verdict.label, "INSUFFICIENT")
        self.assertEqual(verdict.evidence_ids, ["H-F01"])

    def test_h04_crystallinity_contradiction(self):
        claim = ("Across the reported 5 to 30 Hz ball-milling conditions for COF-1, "
                 "increasing frequency significantly improved the crystallinity.")
        found = extract_claim_features(claim)
        self.assertEqual(found["frequency_range_hz"], (5, 30))
        self.assertEqual(found["value"], "increased_significantly")
        verdict = verify_claim_text(claim, "H", self.facts)
        self.assertEqual(verdict.label, "CONTRADICTED")
        self.assertEqual(verdict.evidence_ids, ["H-F03"])

    def test_h05_out_of_range(self):
        claim = ("At a previously untested frequency of 50 Hz, "
                 "COF-1 reaches full conversion in 20 minutes.")
        found = extract_claim_features(claim)
        self.assertEqual(found["frequency_hz"], 50)
        self.assertEqual(found["value"], 20)
        verdict = verify_claim_text(claim, "H", self.facts)
        self.assertEqual(verdict.label, "INSUFFICIENT")

    def test_in_scope_completion_roughly_45_min(self):
        claim = ("For COF-1 milled at 25 Hz, reaction completion "
                 "occurred in approximately 45 minutes.")
        verdict = verify_claim_text(claim, "H", self.facts)
        self.assertEqual(verdict.label, "SUPPORTED")

    def test_unrecognized_scientific_property_abstains(self):
        verdict = verify_claim_text("COF-1 pressure decreases activation enthalpy", "H", self.facts)
        self.assertEqual(verdict.label, "NOT_IMPLEMENTED")

    def test_wrong_paper_does_not_match(self):
        claim = ("For COF-1 milled at 25 Hz, reaction completion "
                 "occurred in approximately 45 minutes.")
        verdict = verify_claim_text(claim, "B", self.facts)
        self.assertEqual(verdict.label, "INSUFFICIENT")


if __name__ == "__main__":
    unittest.main()
