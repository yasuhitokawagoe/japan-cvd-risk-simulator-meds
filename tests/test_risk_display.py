import copy
import math
import unittest

from risk_display import hazard_ratio, hazard_ratio_curve, format_hr


class RiskDisplayTests(unittest.TestCase):
    def test_proportional_hazards_and_not_risk_ratio(self):
        baseline = 50
        target = 100 * (1 - .5 ** .7)
        self.assertAlmostEqual(hazard_ratio(target, baseline), .7)
        self.assertNotAlmostEqual(target / baseline, .7)
        self.assertEqual(hazard_ratio(20, 20), 1)
        self.assertGreater(hazard_ratio(30, 20), 1)

    def test_boundaries(self):
        for t, b in [(0, 0), (20, 0), (100, 20), (20, 100), (-1, 20), (math.nan, 20)]:
            self.assertIsNone(hazard_ratio(t, b))
        self.assertEqual(hazard_ratio(0, 20), 0)
        self.assertEqual(format_hr(None), "算出不可")

    def test_non_mutating_curve_and_reference_band(self):
        data = {"time": [0, 1], "baseline_cumulative": [0, 20],
                "target_cumulative": [0, 10], "baseline_ci_lower": [0, 18],
                "baseline_ci_upper": [0, 22], "target_ci_lower": [0, 8],
                "target_ci_upper": [0, 12]}
        original = copy.deepcopy(data)
        result = hazard_ratio_curve(data)
        self.assertEqual(data, original)
        self.assertIsNone(result["target_cumulative"][0])
        self.assertEqual(result["baseline_cumulative"], [1, 1])
        self.assertLess(result["target_ci_lower"][1], result["target_cumulative"][1])
        self.assertGreater(result["target_ci_upper"][1], result["target_cumulative"][1])


if __name__ == "__main__":
    unittest.main()
