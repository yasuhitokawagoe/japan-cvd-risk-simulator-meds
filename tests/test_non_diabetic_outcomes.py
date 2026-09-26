import math
import unittest
from unittest.mock import patch

from non_diabetic_outcomes import (
    dementia_reference, general_dementia_curve, general_dementia_effects,
    JAGES_ANNUAL_RATES, kidney_reference, kfre_risks,
)


class KidneyReferenceTests(unittest.TestCase):
    def test_published_equation_and_unit_centering(self):
        # Set LP to zero independently using the published centering constants.
        uacr = math.exp(5.137 - 0.2467 * (1 - 0.5642) / 0.4510)
        result = kfre_risks(age=70.36, sex="male", egfr=36.11, uacr_mg_g=uacr)
        self.assertAlmostEqual(result["risk_2y"], 0.0168, places=12)
        self.assertAlmostEqual(result["risk_5y"], 0.0635, places=12)
        self.assertEqual(set(result), {"risk_2y", "risk_5y"})

    def test_risk_gradients_and_fixed_horizons(self):
        base = dict(age=65, sex="male", egfr=25, uacr_mg_g=300)
        risk = kfre_risks(**base)
        self.assertTrue(0 < risk["risk_2y"] < risk["risk_5y"] < 1)
        for change in ({"egfr": 20}, {"uacr_mg_g": 600}):
            self.assertGreater(kfre_risks(**(base | change))["risk_5y"], risk["risk_5y"])
        self.assertLess(kfre_risks(**(base | {"sex": "female"}))["risk_5y"], risk["risk_5y"])

    def test_rejects_missing_invalid_and_out_of_scope_inputs(self):
        base = dict(age=65, sex="male", egfr=25, uacr_mg_g=300)
        for change in ({"uacr_mg_g": None}, {"uacr_mg_g": 0}, {"uacr_mg_g": -1},
                       {"uacr_mg_g": math.nan}, {"egfr": math.inf}, {"egfr": 60},
                       {"egfr": 120}, {"egfr": 4}, {"age": 19}, {"sex": "unknown"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                kfre_risks(**(base | change))

    def test_no_imputation_or_silent_use_of_japanese_egfr(self):
        base = dict(age=65, sex="male", egfr=25, uacr_mg_g=300,
                    ckd_confirmed=True, egfr_method="CKD-EPI")
        for change in ({"ckd_confirmed": False}, {"egfr_method": None},
                       {"egfr_method": "不明・日本人式"}, {"uacr_mg_g": None}):
            result = kidney_reference(**(base | change))
            self.assertIn("unavailable_reason", result)
            self.assertNotIn("risk_5y", result)
        self.assertNotIn("unavailable_reason", kidney_reference(**base))


class GeneralDementiaTests(unittest.TestCase):
    def test_rates_are_baseline_age_strata_not_attained_age(self):
        with patch("non_diabetic_outcomes.annual_mortality_probability", return_value=0):
            for lower, upper, male, female in JAGES_ANNUAL_RATES:
                for sex, rate in (("male", male), ("female", female)):
                    curve = general_dementia_curve(age=lower, sex=sex, years=10)
                    self.assertAlmostEqual(curve["risk"][-1], 1 - math.exp(-rate * 10))
            # Crossing 70 does not apply a second aging effect to a cohort average.
            curve = general_dementia_curve(age=69, sex="male", years=10)
            self.assertAlmostEqual(curve["risk"][-1], 1 - math.exp(-0.006 * 10))

    def test_competing_death_and_long_horizon(self):
        curve = general_dementia_curve(age=85, sex="female", years=50)
        self.assertEqual(curve["time"][-1], 25)
        self.assertTrue(all(a <= b < 1 for a, b in zip(curve["risk"], curve["risk"][1:])))
        self.assertLess(curve["risk"][-1], 1 - math.exp(-0.105 * 25))
        treated = general_dementia_curve(age=85, sex="female", years=50, hazard_ratio=0.8)
        self.assertLess(treated["risk"][-1], curve["risk"][-1])

    def test_under_65_is_unavailable_not_zero_and_no_fake_ci(self):
        invalid = dementia_reference(age=60, sex="male", years=20)
        self.assertIn("unavailable_reason", invalid)
        self.assertNotIn("baseline_cumulative", invalid)
        valid = dementia_reference(age=70, sex="male", years=20, treatment_hr=0.8)
        self.assertFalse(valid["has_uncertainty"])
        self.assertEqual(valid["extrapolation_after"], 9)
        self.assertLess(valid["target_cumulative"][-1], valid["baseline_cumulative"][-1])
        continued = dementia_reference(age=70, sex="male", years=20, treatment_hr=0.8, continuing=True)
        self.assertEqual(continued["baseline_cumulative"], valid["target_cumulative"])
        self.assertEqual(continued["target_cumulative"], valid["baseline_cumulative"])

    def test_no_double_counting_of_statin_and_ldl(self):
        base = dict(sbp_before=140, sbp_after=140, ldl_before=160, ldl_after=160)
        self.assertEqual(general_dementia_effects(**base)["combined"], 1)
        self.assertEqual(general_dementia_effects(**base, has_statin=True)["combined"], 0.86)
        with_ldl = general_dementia_effects(**(base | {"ldl_after": 100}), has_statin=True)
        self.assertEqual(with_ldl["combined"], 0.74)
        self.assertEqual(with_ldl["statin_increment"], 1)
        with_bp = general_dementia_effects(**(base | {"sbp_after": 130, "ldl_after": 100}), has_statin=True)
        self.assertAlmostEqual(with_bp["combined"], 0.87 * 0.74)


if __name__ == "__main__":
    unittest.main()
