import math
import unittest

from exercise_fitness import fitness_scenario


class FitnessScenarioTests(unittest.TestCase):
    def test_off_or_no_exercise(self):
        for key in (None, "unknown", "combined"):
            self.assertIsNone(fitness_scenario([0, 20], key))
        self.assertIsNone(fitness_scenario([0, 20], None, enabled=True))

    def test_modality_gains_and_formula(self):
        for key, gain in [("aerobic_moderate", 2.77), ("combined", 2.68), ("hiit", 4.19)]:
            risks = [0, 10, 30, 80, 100]
            result = fitness_scenario(risks, key, enabled=True)
            multiplier = .89 ** (gain / 3.5)
            self.assertAlmostEqual(result["met_gain"], gain / 3.5)
            self.assertAlmostEqual(result["hazard_multiplier"], multiplier)
            self.assertAlmostEqual(result["risk"][2], 100 * (1 - .7 ** multiplier))
            self.assertEqual(result["risk"][0], 0)
            self.assertEqual(result["risk"][-1], 100)
            self.assertEqual(sorted(result["risk"]), result["risk"])
            self.assertTrue(all(0 <= new <= old for new, old in zip(result["risk"], risks)))
            self.assertEqual(risks, [0, 10, 30, 80, 100])

    def test_no_annual_accumulation(self):
        result = fitness_scenario([10, 10, 10], "hiit", enabled=True)
        self.assertEqual(len(set(result["risk"])), 1)

    def test_invalid_risks(self):
        for value in (-1, 101, math.nan, math.inf):
            with self.assertRaises(ValueError):
                fitness_scenario([value], "combined", enabled=True)

    def test_band_combines_base_and_effect_uncertainty(self):
        for key in ("aerobic_moderate", "combined", "hiit"):
            result = fitness_scenario([0, 10, 30, 80, 100], key, enabled=True,
                                      lower_percent=[0, 8, 25, 70, 100],
                                      upper_percent=[0, 12, 35, 90, 100])
            effect_only = fitness_scenario([0, 10, 30, 80, 100], key, enabled=True)
            self.assertEqual(result["risk"], effect_only["risk"])
            for lo, point, hi in zip(result["lower"], result["risk"], result["upper"]):
                self.assertTrue(0 <= lo <= point <= hi <= 100)
            self.assertLess(result["lower"][2], effect_only["lower"][2])
            self.assertGreater(result["upper"][2], effect_only["upper"][2])
            self.assertLess(effect_only["lower"][2], effect_only["risk"][2])
            self.assertGreater(effect_only["upper"][2], effect_only["risk"][2])

    def test_invalid_bounds(self):
        for lower, upper in [([5], None), ([5, 6], [15]), ([11], [15]),
                             ([5], [9]), ([math.nan], [15]), ([5], [101])]:
            with self.assertRaises(ValueError):
                fitness_scenario([10], "combined", enabled=True,
                                 lower_percent=lower, upper_percent=upper)


if __name__ == "__main__":
    unittest.main()
