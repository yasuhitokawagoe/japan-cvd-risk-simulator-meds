import ast
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from calc_engine_outcomes import OutcomesEngine
from dementia_prevention import dementia_biomarker_hazard_ratio, dementia_curve, selected_dementia_evidence
from dm_outcomes import ACR_CATEGORY_MG_G, DIABETES_OUTCOMES, DiabetesOutcomeModel
from meds_catalog import load_meds_catalog
from meds_catalog import apply_meds_to_targets
from treatment_backcast import reconstruct_untreated_values
from patient_mobile_model import (
    BP_CATALOG, LIPID_CATALOG, PatientInputs, calculate_mobile_scenarios, group_medications, swap_sides,
)


ROOT = Path(__file__).resolve().parents[1]


class PatientMobileModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = OutcomesEngine(str(ROOT / "config.yaml"))
        cls.catalog = load_meds_catalog(str(ROOT / BP_CATALOG), str(ROOT / LIPID_CATALOG))

    def patient(self, **kwargs):
        return PatientInputs(**(dict(age=60, sex="male", sbp=140., ldl=130., a1c=7.5, bmi=27., egfr=80., acr="A1", diabetes_status="type2") | kwargs))

    def calc(self, patient=None, **kwargs):
        return calculate_mobile_scenarios(patient or self.patient(), engine=self.engine, **kwargs)

    def test_no_selection_does_not_use_pc_manual_targets(self):
        patient = self.patient()
        result = self.calc(patient, mode="without")
        self.assertEqual(result["targets"], patient.markers)
        for curve in result["lifestyle"]["curves"].values():
            self.assertEqual(curve["baseline_cumulative"], curve["target_cumulative"])

    def test_current_drugs_not_applied_twice(self):
        meds = [self.catalog[d][0] for d in ("sbp", "ldl", "hba1c")]
        patient = self.patient()
        result = self.calc(patient, mode="with", current_medications=meds, medications_complete=True,
                           diet_keys=["salt"], exercise_key="combined")
        self.assertAlmostEqual(result["targets"]["sbp"], 140 - 4.26 - 2.94)
        self.assertAlmostEqual(result["targets"]["ldl"], 130 - 11.99)
        self.assertAlmostEqual(result["targets"]["a1c"], 7.5 - .74)
        self.assertGreater(result["untreated"]["sbp"], patient.sbp)
        for key, curve in result["medication"]["curves"].items():
            self.assertEqual(curve["target_cumulative"], result["lifestyle"]["curves"][key]["baseline_cumulative"])

    def test_unknown_drug_information_cannot_create_drug_comparison(self):
        for meds, complete in (([], True), ([self.catalog["ldl"][0]], False)):
            result = self.calc(mode="with", current_medications=meds, medications_complete=complete)
            self.assertIsNone(result["medication"])
            self.assertEqual(result["targets"], self.patient().markers)
            self.assertTrue(any("未確認" in w for w in result["warnings"]))

    def test_proposed_drugs_apply_once_and_routes_do_not_mix(self):
        drug = self.catalog["sbp"][0]
        result = self.calc(mode="without", proposed_medications=[drug], diet_keys=["salt"])
        self.assertAlmostEqual(result["targets"]["sbp"], 140 + drug["effect"]["mean"] - 4.26)
        for args in (dict(mode="without", current_medications=[drug]), dict(mode="with", proposed_medications=[drug])):
            with self.assertRaises(ValueError):
                self.calc(**args)

    def test_unknown_kidney_and_bmi_not_filled(self):
        result = self.calc(self.patient(bmi=None, egfr=None, acr=None), mode="without", diet_keys=["meal_replacement"])
        self.assertEqual(set(result["lifestyle"]["curves"]), {"mi", "stroke", "mortality", "dementia"})
        self.assertIsNone(result["targets"]["bmi"])
        self.assertFalse(result["has_changes"])
        self.assertEqual(len(result["warnings"]), 3)

    def test_exclusive_food_patterns_and_same_class_drugs(self):
        with self.assertRaises(ValueError):
            self.calc(mode="without", diet_keys=["dash", "salt"])
        drug = self.catalog["ldl"][0]
        with self.assertRaises(ValueError):
            group_medications([drug, drug])
        second = next(m for m in self.catalog["ldl"] if m["category"] == drug["category"] and m["drug_name"] != drug["drug_name"])
        self.assertEqual(len(group_medications([drug, second])["ldl"]), 2)

    def test_input_validation_and_age_cap(self):
        for kwargs in (dict(age=19), dict(sbp=float("nan")), dict(a1c=None), dict(acr="unknown"), dict(bmi=0)):
            with self.assertRaises(ValueError):
                self.patient(**kwargs)
        result = self.calc(self.patient(age=95), mode="without", years=20)
        self.assertEqual(result["years"], 15)
        for curve in result["lifestyle"]["curves"].values():
            self.assertEqual(curve["time"][-1], 15)

    def pc_function(self, patient, target, meds, care_mode):
        # Execute the actual PC calculation function without importing its UI.
        tree = ast.parse((ROOT / "app_streamlit_outcomes.py").read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "calculate_cumulative_risk_curves")
        namespace = dict(np=np, engine=self.engine, dm_engine=DiabetesOutcomeModel(),
                         CARDIOVASCULAR_OUTCOMES=("mi", "stroke", "mortality"),
                         DIABETES_OUTCOME_KEYS=DIABETES_OUTCOMES, ACR_CATEGORY_MG_G=ACR_CATEGORY_MG_G,
                         selected_dementia_evidence=selected_dementia_evidence,
                         dementia_biomarker_hazard_ratio=dementia_biomarker_hazard_ratio, dementia_curve=dementia_curve,
                         age=patient.age, sex=patient.sex, care_mode=care_mode,
                         sbp_now=patient.sbp, ldl_now=patient.ldl, a1c_now=patient.a1c, bmi_now=patient.bmi,
                         sbp_tgt=target["sbp"], ldl_tgt=target["ldl"], a1c_tgt=target["a1c"], bmi_target=target["bmi"],
                         egfr_now=patient.egfr, egfr_target=patient.egfr, acr_now=patient.acr, acr_target=patient.acr,
                         smoking_status=patient.smoking_status, cigs_per_day=patient.cigs_per_day,
                         years_smoked=patient.years_smoked, years_since_quit=patient.years_since_quit, quit_today=False,
                         selected_sbp_meds=meds["sbp"], selected_ldl_meds=meds["ldl"], selected_a1c_meds=meds["hba1c"])
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(ROOT / "app_streamlit_outcomes.py"), "exec"), namespace)
        return namespace["calculate_cumulative_risk_curves"](10)

    def test_exact_pc_parity_lifestyle_and_medication_comparisons(self):
        patient = self.patient()
        meds = [self.catalog[d][0] for d in ("sbp", "ldl", "hba1c")]
        result = self.calc(patient, mode="without", proposed_medications=meds,
                           diet_keys=["mediterranean"], exercise_key="combined")
        pc = self.pc_function(patient, result["targets"], group_medications(meds), "start")
        self.assertEqual(result["lifestyle"]["curves"], pc)
        result = self.calc(patient, mode="with", current_medications=meds, medications_complete=True)
        pc = self.pc_function(patient, result["untreated"], group_medications(meds), "continue")
        self.assertEqual(result["medication"]["curves"], swap_sides(pc))

    def test_non_diabetes_unknown_and_other_do_not_call_diabetes_engines(self):
        for status in ("none", "unknown", "other"):
            with self.subTest(status=status), patch("patient_mobile_model.DiabetesOutcomeModel", side_effect=AssertionError), \
                    patch("patient_mobile_model.dementia_curve", side_effect=AssertionError):
                result = self.calc(self.patient(diabetes_status=status, a1c=None), mode="without", diet_keys=["dash"])
            self.assertEqual(set(result["lifestyle"]["curves"]), {"mi", "stroke", "mortality"})
            self.assertIsNone(result["targets"]["a1c"])
            self.assertAlmostEqual(result["targets"]["sbp"], 136.06)
            self.assertEqual(result["applied"], ["dash"])

    def test_non_diabetes_low_hba1c_does_not_cause_artificial_risk_increase(self):
        reference = None
        for a1c in (None, 4.8, 5.5, 7.5):
            result = self.calc(self.patient(diabetes_status="none", a1c=a1c), mode="without")
            for curve in result["lifestyle"]["curves"].values():
                self.assertEqual(curve["baseline_cumulative"], curve["target_cumulative"])
            if reference is not None:
                self.assertEqual(result["lifestyle"]["curves"], reference)
            reference = result["lifestyle"]["curves"]
            self.assertEqual(result["targets"]["a1c"], a1c)

    def test_non_diabetes_bp_lipid_medications_work_without_hba1c(self):
        patient = self.patient(diabetes_status="none", a1c=None)
        meds = [self.catalog[d][0] for d in ("sbp", "ldl")]
        result = self.calc(patient, mode="with", current_medications=meds, medications_complete=True, diet_keys=["salt"])
        self.assertIsNotNone(result["medication"])
        self.assertIsNone(result["untreated"]["a1c"])
        self.assertAlmostEqual(result["targets"]["sbp"], 135.74)
        for key, curve in result["medication"]["curves"].items():
            self.assertEqual(curve["target_cumulative"], result["lifestyle"]["curves"][key]["baseline_cumulative"])
        result = self.calc(patient, mode="without", proposed_medications=meds)
        self.assertIsNone(result["targets"]["a1c"])
        self.assertLess(result["targets"]["sbp"], patient.sbp)
        self.assertLess(result["targets"]["ldl"], patient.ldl)

    def test_diabetes_diet_exercise_and_drug_coefficients_do_not_leak(self):
        patient = self.patient(diabetes_status="none", a1c=None)
        for diet, exercise in ((["carb"], None), (["mediterranean"], None), (["meal_replacement"], None), ([], "combined")):
            result = self.calc(patient, mode="without", diet_keys=diet, exercise_key=exercise)
            self.assertEqual(result["targets"], patient.markers)
            self.assertFalse(result["has_changes"])
            self.assertTrue(result["has_requested_changes"])
            self.assertTrue(any("適用しません" in w for w in result["warnings"]))
        meds = [self.catalog["hba1c"][0]]
        result = self.calc(patient, mode="with", current_medications=meds, medications_complete=True)
        self.assertIsNone(result["medication"])
        result = self.calc(patient, mode="without", proposed_medications=meds)
        self.assertEqual(result["targets"], patient.markers)
        self.assertFalse(result["has_changes"])
        self.assertNotIn("dementia", result["lifestyle"]["curves"])

    def test_unknown_is_default_not_inferred_from_hba1c_or_medications(self):
        patient = PatientInputs(age=60, sex="male", sbp=140, ldl=130, a1c=9)
        self.assertEqual(patient.diabetes_status, "unknown")
        result = self.calc(patient, mode="without", proposed_medications=[self.catalog["hba1c"][0]])
        self.assertEqual(result["targets"]["a1c"], 9)
        self.assertEqual(len(result["lifestyle"]["curves"]), 3)
        with self.assertRaises(ValueError):
            self.patient(diabetes_status="invalid")
        with self.assertRaises(ValueError):
            self.patient(diabetes_status="type2", a1c=None)

    def test_missing_hba1c_is_not_imputed_by_shared_medication_helpers(self):
        drug = self.catalog["hba1c"][0]
        with self.assertRaises(ValueError):
            apply_meds_to_targets(140, 130, None, [], [], [drug])
        with self.assertRaises(ValueError):
            reconstruct_untreated_values(sbp_now=140, ldl_now=130, a1c_now=None, a1c_meds=[drug])


if __name__ == "__main__":
    unittest.main()
