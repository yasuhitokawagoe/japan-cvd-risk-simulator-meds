import math
import unittest

from lifestyle_interventions import (
    DIET_COMPONENT_KEYS, DIET_EFFECTS, DIET_PATTERN_KEYS,
    apply_lifestyle_effects, validate_diet_selection,
)


class DietPatternTests(unittest.TestCase):
    def apply(self, key, **kwargs):
        return apply_lifestyle_effects(
            sbp=150, ldl=160, a1c=8, diet_keys=[key],
            diabetes_context=kwargs.pop("diabetes_context", True),
            bmi=kwargs.pop("bmi", 30), **kwargs,
        )

    def test_source_coefficients(self):
        expected = {
            "dash": (146.06, 156.47, 8, 29.36),
            "mediterranean": (150, 151.94, 7.693, 29.172),
            "meal_replacement": (145.03, 160, 7.57, 29.13),
        }
        for key, values in expected.items():
            with self.subTest(key=key):
                result = self.apply(key)
                for field, value in zip(("sbp", "ldl", "a1c", "bmi"), values):
                    self.assertAlmostEqual(result[field], value)
                self.assertEqual(len(result["applied"]), 1)
                self.assertFalse(result["skipped"])
                self.assertIn("consensus.app/papers/", DIET_EFFECTS[key].source_url)

    def test_exclusive_patterns_and_components(self):
        self.assertEqual(DIET_COMPONENT_KEYS, ("salt", "carb", "fat"))
        for pattern in DIET_PATTERN_KEYS:
            for other in DIET_EFFECTS:
                if other != pattern:
                    with self.subTest(pattern=pattern, other=other), self.assertRaises(ValueError):
                        apply_lifestyle_effects(sbp=150, ldl=160, a1c=8, diet_keys=[pattern, other])

    def test_duplicate_keys_are_applied_only_once(self):
        self.assertEqual(validate_diet_selection(["dash", "dash"]), ["dash"])
        result = apply_lifestyle_effects(sbp=150, ldl=160, a1c=8, diet_keys=["salt", "salt"])
        self.assertAlmostEqual(result["sbp"], 145.74)

    def test_no_automatic_weight_loss_at_normal_or_low_bmi(self):
        for bmi in (10, 18.5, 24.9):
            for key in ("dash", "mediterranean"):
                self.assertEqual(self.apply(key, bmi=bmi)["bmi"], bmi)
            result = self.apply("meal_replacement", bmi=bmi)
            self.assertEqual((result["sbp"], result["ldl"], result["a1c"], result["bmi"]), (150, 160, 8, bmi))
            self.assertEqual(len(result["skip_reasons"]), 1)
        self.assertAlmostEqual(self.apply("meal_replacement", bmi=25)["bmi"], 24.13)

    def test_missing_bmi_does_not_apply_weight_program(self):
        result = self.apply("meal_replacement", bmi=None)
        self.assertIsNone(result["bmi"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["skip_reasons"])

    def test_diabetes_population_guard(self):
        for key in ("mediterranean", "meal_replacement"):
            result = self.apply(key, diabetes_context=False)
            self.assertEqual((result["sbp"], result["ldl"], result["a1c"], result["bmi"]), (150, 160, 8, 30))
            self.assertFalse(result["applied"])
        self.assertTrue(self.apply("dash", diabetes_context=False)["applied"])

    def test_exercise_preserves_diet_bmi_and_adds_markers_once(self):
        result = self.apply("dash", exercise_key="combined")
        self.assertAlmostEqual(result["sbp"], 143.12)
        self.assertAlmostEqual(result["ldl"], 144.48)
        self.assertAlmostEqual(result["a1c"], 7.26)
        self.assertAlmostEqual(result["bmi"], 29.36)
        self.assertEqual(len(result["applied"]), 2)

    def test_invalid_bmi_rejected(self):
        for bmi in (0, -1, math.nan, math.inf):
            with self.subTest(bmi=bmi), self.assertRaises(ValueError):
                self.apply("dash", bmi=bmi)


if __name__ == "__main__":
    unittest.main()
