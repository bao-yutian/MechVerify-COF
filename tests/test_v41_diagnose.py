"""Tests for V4.1 post-hoc claim grounding warnings."""
import unittest
from mechverify.core import load_json
from mechverify.v41_diagnose import audit_extraction


class TestV41Diagnose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = load_json("evidence.json")
        cls.cases = {c["id"]: c for c in load_json("cases.json")}

    def source(self, paper):
        return [f for f in self.facts if f["paper_id"] == paper]

    def test_h04_detects_wrong_material_and_frequency_range(self):
        case = self.cases["H-04"]
        extracted = {
            "system": "mechanical_milling",
            "property": "frequency_effect_on_crystallinity",
            "context": {"method": "ball_milling", "frequency_range_hz": "15-30"},
            "value": 25,
            "unit": "Hz",
        }
        errors = audit_extraction(case["claim"], extracted, self.source("H"))
        self.assertTrue(any("COF-1 replaced" in e for e in errors))
        self.assertTrue(any("Frequency range does not match" in e for e in errors))

    def test_b04_detects_extraneous_context_and_wrong_material(self):
        case = self.cases["B-04"]
        extracted = {
            "system": "mechanical_exfoliation",
            "property": "BET_surface_area",
            "context": {"duration_comparison_h": "2_vs_1", "frequency_range_hz": "15-30"},
            "value": 150,
            "unit": "m2/g",
        }
        errors = audit_extraction(case["claim"], extracted, self.source("B"))
        self.assertTrue(any("TFPPy-PDA replaced" in e for e in errors))
        self.assertTrue(any("Duration comparison hallucinated" in e for e in errors))

    def test_correct_b04_extraction_is_not_flagged(self):
        case = self.cases["B-04"]
        extracted = {
            "system": "TFPPy-PDA",
            "property": "BET_surface_area",
            "context": {"method": "COP_to_COF"},
            "value": 150,
            "unit": "m2/g",
        }
        self.assertEqual(audit_extraction(case["claim"], extracted, self.source("B")), [])

    def test_u05_literal_null_unit_is_flagged(self):
        case = self.cases["U-05"]
        extracted = {
            "system": "reported_imine_COFs",
            "property": "BET_area_comparison",
            "context": {"frequency_hz": 60},
            "value": "higher_for_exchange",
            "unit": "null",
        }
        errors = audit_extraction(case["claim"], extracted, self.source("U"))
        self.assertTrue(any("literal string" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
