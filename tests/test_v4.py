"""V4 tests for condition matching and claim/evidence separation."""
import json
import unittest
from mechverify.core import load_json
from mechverify.v4_checker import compare_claim_to_evidence, extraction_schema
from mechverify.v4_qwen import extraction_messages, parse_extraction


class V4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = load_json("evidence.json")

    def check(self, paper, system, prop, context, value, unit, expected, ids=None):
        extracted = dict(system=system, property=prop, context=context, value=value, unit=unit)
        found = compare_claim_to_evidence(extracted, paper, self.facts)
        self.assertEqual(found.label, expected, found)
        if ids is not None:
            self.assertEqual(found.evidence_ids, ids)

    def test_route_aware_bet(self):
        self.check("B", "TFPPy-PDA", "BET_surface_area",
                   {"method": "COP_to_COF"}, 150, "m2/g", "CONTRADICTED", ["B-F03"])
        self.check("B", "TFPPy-PDA", "BET_surface_area",
                   {"method": "de_novo_mechanosynthesis"}, 150, "m2/g",
                   "SUPPORTED", ["B-F04"])

    def test_omitted_route_abstains(self):
        self.check("B", "TFPPy-PDA", "BET_surface_area",
                   {}, 150, "m2/g", "INSUFFICIENT", [])

    def test_wrong_frequency_abstains(self):
        self.check("B", "DBrTP-TPB", "crystallinity_change_with_frequency",
                   {"method": "COP_to_COF", "frequency_range_hz": "30-60"},
                   "increased", None, "INSUFFICIENT")
        self.check("H", "COF-1", "milling_completion_time_min",
                   {"method": "ball_milling", "frequency_hz": 50},
                   20, "min", "INSUFFICIENT")

    def test_frequency_trend_and_reversal(self):
        ctx = {"method": "COP_to_COF", "frequency_range_hz": "15-30"}
        self.check("B", "DBrTP-TPB", "crystallinity_change_with_frequency",
                   ctx, "increased", None, "SUPPORTED")
        self.check("B", "DBrTP-TPB", "crystallinity_change_with_frequency",
                   ctx, "decreased", None, "CONTRADICTED")

    def test_temporal_trend(self):
        self.check("B", "DBrTP-TPB", "crystallinity_2h_vs_1h",
                   {"method": "COP_to_COF", "duration_comparison_h": "2_vs_1"},
                   "lower_at_2h", None, "SUPPORTED")

    def test_u_kinetic_trend(self):
        ctx = {"method": "mechanochemical_model", "measurement": "time_resolved_1H_NMR"}
        self.check("U", "imine_model_reaction", "exchange_rate_relative_to_condensation",
                   ctx, "slower", None, "SUPPORTED")
        self.check("U", "imine_model_reaction", "exchange_rate_relative_to_condensation",
                   ctx, "faster", None, "CONTRADICTED")

    def test_u_route_and_scope(self):
        self.check("U", "reported_imine_COFs", "BET_area_comparison",
                   {"method": "exchange_vs_direct_condensation", "scope": "reported_COFS"},
                   "higher_for_exchange", None, "SUPPORTED")
        self.check("U", "reported_imine_COFs", "BET_area_comparison",
                   {"method": "exchange_vs_direct_condensation", "scope": "all_imine_COFs",
                    "frequency_hz": 60},
                   "higher_for_exchange", None, "INSUFFICIENT")
        self.check("U", "AIE_based_COF", "obtained_by_direct_condensation",
                   {"method": "mechanochemical_direct_condensation", "scope": "tested_conditions"},
                   True, None, "CONTRADICTED")

    def test_h04_crystallinity(self):
        self.check("H", "COF-1", "frequency_effect_on_crystallinity",
                   {"method": "ball_milling", "frequency_range_hz": "5-30"},
                   "increased_significantly", None, "CONTRADICTED", ["H-F03"])

    def test_h02_cautious_upper_bound(self):
        self.check("H", "COF-1", "milling_completion_time_min",
                   {"method": "ball_milling", "frequency_hz": 25},
                   5, "min", "INSUFFICIENT", ["H-F01"])

    def test_invalid_schema_and_property(self):
        self.assertEqual(compare_claim_to_evidence(
            {"system": "COF-1"}, "H", self.facts).label, "EXTRACTION_ERROR")
        self.check("H", "COF-1", "new_unimplemented_property", {},
                   "anything", None, "NOT_IMPLEMENTED")
        self.check("H", "COF-1", "frequency_effect_on_crystallinity",
                   {"frequency_range_hz": None}, "increased",
                   None, "EXTRACTION_ERROR")

    def test_ontology_does_not_expose_evidence_values(self):
        dumped = json.dumps(extraction_schema(self.facts))
        self.assertNotIn("850", dumped)
        self.assertNotIn("150", dumped)
        self.assertNotIn("gold_label", dumped)

    def test_prompt_no_gold_fields(self):
        case = load_json("cases.json")[8]
        full_text = json.dumps(extraction_messages(case["claim"], self.facts))
        self.assertIn(case["claim"], full_text)
        self.assertNotIn("gold_label", full_text)
        self.assertNotIn("structured_claim", full_text)
        self.assertNotIn("CONTRADICTED", full_text)

    def test_parse_json(self):
        payload = '{"system":"COF-1","property":"milling_completion_time_min","context":{},"value":5,"unit":"min"}'
        self.assertEqual(parse_extraction(payload)["value"], 5)
        self.assertIsNone(parse_extraction("not JSON"))


if __name__ == "__main__":
    unittest.main()
