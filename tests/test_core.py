import unittest
from mechverify.core import load_json, verify_structured, value_agrees
from mechverify.evaluation import metrics


class TestPilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_json("cases.json")
        cls.facts = load_json("evidence.json")

    def test_unique_case_ids(self):
        self.assertEqual(len(self.cases), 15)
        self.assertEqual(len({c["id"] for c in self.cases}), 15)

    def test_all_categories_present(self):
        self.assertEqual({c["gold_label"] for c in self.cases},
                         {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"})

    def test_pilot_structured_sanity(self):
        # Gold labels are curated from the SAME evidence registry. This only
        # tests bookkeeping and deterministic comparison, NOT LLM performance.
        for c in self.cases:
            with self.subTest(case=c["id"]):
                self.assertEqual(verify_structured(c, self.facts).label, c["gold_label"])

    def test_number_tolerance_and_bool_safety(self):
        self.assertTrue(value_agrees(44, 45, tolerance=5))
        self.assertFalse(value_agrees(20, 45, tolerance=5))
        self.assertFalse(value_agrees(True, 1))

    def test_unknown_context_abstains(self):
        item = next(c for c in self.cases if c["id"] == "B-05")
        self.assertEqual(verify_structured(item, self.facts).label, "INSUFFICIENT")

    def test_metrics(self):
        pred = {c["id"]: "SUPPORTED" for c in self.cases}
        m = metrics(self.cases, pred)
        self.assertEqual(m["n"], 15)
        self.assertAlmostEqual(m["accuracy"], 0.4)

    def test_no_gold_in_evidence(self):
        for f in self.facts:
            self.assertNotIn("gold_label", f)


if __name__ == "__main__":
    unittest.main()
