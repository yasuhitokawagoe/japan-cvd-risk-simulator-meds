import copy
import math
import unittest

from dementia_prevention import dementia_curve
from dementia_uncertainty import (
    add_dementia_uncertainty, baseline_log_se, DSDRS_10_YEAR_CI,
    JAGES_APPROX_COUNTS, log_effect_variance, treatment_uncertainty,
)
from non_diabetic_outcomes import dementia_reference


class DementiaUncertaintyTests(unittest.TestCase):
    def inputs(self, **changes):
        return dict(age=70., sex="male", has_type2_diabetes=False,
                    sbp_before=150., sbp_after=130., ldl_before=160., ldl_after=100.) | changes

    def scenario(self, **changes):
        args = self.inputs(**changes)
        effects = treatment_uncertainty(**{k: v for k, v in args.items()
                                         if k not in ("age", "sex", "continuing")})
        if not args["has_type2_diabetes"]:
            data = dementia_reference(age=args["age"], sex=args["sex"], years=20,
                                      treatment_hr=effects["multiplier"],
                                      continuing=args.get("continuing", False))
        else:
            data = {"time": list(range(21))}
            for side, treated in (("baseline", args.get("continuing", False)),
                                  ("target", not args.get("continuing", False))):
                risk = dementia_curve(age=args["age"], sex=args["sex"], years=20,
                                      hazard_ratio=effects["multiplier"] if treated else 1)["risk"]
                for suffix in ("cumulative", "ci_lower", "ci_upper"):
                    data[f"{side}_{suffix}"] = [r * 100 for r in risk]
        return data, args

    def test_original_ci_transforms_to_log_hazard_se(self):
        lo, hi = baseline_log_se(age=70, sex="male", has_type2_diabetes=True)
        h = -math.log1p(-.245)
        self.assertAlmostEqual(h * math.exp(-1.96 * lo), -math.log1p(-.227))
        self.assertAlmostEqual(h * math.exp(1.96 * hi), -math.log1p(-.263))
        self.assertEqual(DSDRS_10_YEAR_CI[-1], (.580, .682))

    def test_general_baseline_is_explicit_count_approximation(self):
        lo, hi = baseline_log_se(age=70, sex="male", has_type2_diabetes=False)
        self.assertEqual(lo, hi)
        self.assertAlmostEqual(lo, 1 / math.sqrt(6241 * .109))
        self.assertEqual(sum(n for n, _ in JAGES_APPROX_COUNTS["female"]), 23450)

    def test_points_untouched_and_bounds_ordered_over_all_ages(self):
        for dm, ages in ((False, (65, 69, 70, 75, 80, 85, 95)),
                         (True, (55, 60, 65, 70, 75, 80, 85, 95))):
            for sex in ("male", "female"):
                for age in ages:
                    data, args = self.scenario(has_type2_diabetes=dm, age=float(age), sex=sex)
                    original = copy.deepcopy(data)
                    result = add_dementia_uncertainty(data, **args)
                    self.assertEqual(data, original)
                    for side in ("baseline", "target"):
                        point = result[f"{side}_cumulative"]
                        self.assertEqual(point, original[f"{side}_cumulative"])
                        lower, upper = (result[f"{side}_ci_{key}"] for key in ("lower", "upper"))
                        self.assertEqual(len(lower), len(point))
                        self.assertTrue(all(0 <= lo <= p <= hi <= 100 for lo, p, hi in zip(lower, point, upper)))
                        self.assertTrue(all(a <= b for a, b in zip(lower, lower[1:])))
                        self.assertTrue(all(a <= b for a, b in zip(upper, upper[1:])))
                        self.assertEqual((lower[0], upper[0]), (0, 0))
                        self.assertGreater(upper[-1], lower[-1])
                    self.assertEqual(result["uncertainty_label"], "95%推定幅（近似）")

    def test_continuation_swaps_full_intervals_not_only_point(self):
        for dm in (False, True):
            data, args = self.scenario(has_type2_diabetes=dm, medication_keys=("statin",))
            reference = add_dementia_uncertainty(data, **args)
            data, args = self.scenario(has_type2_diabetes=dm, continuing=True, medication_keys=("statin",))
            continued = add_dementia_uncertainty(data, **args)
            for suffix in ("cumulative", "ci_lower", "ci_upper"):
                self.assertEqual(reference[f"baseline_{suffix}"], continued[f"target_{suffix}"])
                self.assertEqual(reference[f"target_{suffix}"], continued[f"baseline_{suffix}"])

    def test_no_intervention_means_same_bounds_and_no_effect_variance(self):
        data, args = self.scenario(sbp_after=150, ldl_after=160)
        result = add_dementia_uncertainty(data, **args)
        for suffix in ("cumulative", "ci_lower", "ci_upper"):
            self.assertEqual(result[f"baseline_{suffix}"], result[f"target_{suffix}"])
        self.assertEqual(result["uncertainty_omitted"], [])

    def test_unavailable_stays_unavailable(self):
        data, args = self.scenario(age=60)
        self.assertEqual(add_dementia_uncertainty(data, **args), data)
        self.assertNotIn("baseline_ci_lower", data)

    def test_bp_variance_scales_with_squared_power_and_caps(self):
        base = dict(has_type2_diabetes=False, sbp_before=160, sbp_after=150,
                    ldl_before=160, ldl_after=160)
        one = treatment_uncertainty(**base)["log_variance"]
        two = treatment_uncertainty(**(base | {"sbp_after": 140}))["log_variance"]
        capped = treatment_uncertainty(**(base | {"sbp_after": 100}))["log_variance"]
        self.assertAlmostEqual(one, ((math.log(.99) - math.log(.75)) / 3.92) ** 2)
        self.assertAlmostEqual(two, 4 * one)
        self.assertAlmostEqual(capped, 9 * one)

    def test_statin_ldl_branch_and_missing_ldl_uncertainty_are_honest(self):
        base = dict(has_type2_diabetes=False, sbp_before=150, sbp_after=150,
                    ldl_before=160, ldl_after=160, medication_keys=("statin",))
        statin = treatment_uncertainty(**base)
        self.assertEqual(statin["multiplier"], .86)
        self.assertEqual(statin["log_variance"], log_effect_variance("statin_general"))
        ldl = treatment_uncertainty(**(base | {"ldl_after": 100}))
        self.assertEqual(ldl["multiplier"], .74)
        self.assertEqual(ldl["log_variance"], 0)
        self.assertIn("LDL", ldl["omitted"][0])

    def test_medication_ci_class_dedup_and_no_diabetes_leak(self):
        base = dict(has_type2_diabetes=True, sbp_before=150, sbp_after=150,
                    ldl_before=160, ldl_after=160)
        one = treatment_uncertainty(**base, medication_keys=("sglt2", "metformin", "glp1_ra"))
        dup = treatment_uncertainty(**base, medication_keys=("sglt2", "sglt2", "metformin", "glp1_ra", "bp_lowering"))
        self.assertEqual(one, dup)
        self.assertAlmostEqual(one["log_variance"], sum(log_effect_variance(k) for k in ("sglt2", "metformin", "glp1_ra")))
        general = treatment_uncertainty(**(base | {"has_type2_diabetes": False}), medication_keys=("sglt2", "metformin", "glp1_ra"))
        self.assertEqual(general["log_variance"], 0)
        self.assertEqual(general["multiplier"], 1)


if __name__ == "__main__":
    unittest.main()
