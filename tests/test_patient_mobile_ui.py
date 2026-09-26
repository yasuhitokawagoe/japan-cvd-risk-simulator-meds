from pathlib import Path
import json
import unittest
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app_patient_mobile.py"


class PatientMobileUITests(unittest.TestCase):
    def start(self, mode="without"):
        app = AppTest.from_file(str(APP), default_timeout=40).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.button(key="entry_without").disabled)
        self.assertFalse(app.button(key="entry_with").disabled)
        self.assertFalse(app.checkbox)
        app.button(key=f"entry_{mode}").click().run()
        return app

    def enter_values(self, app, diabetes_status="type2", a1c=7.5):
        for key, value in (("age", 60), ("sbp", 140.), ("ldl", 130.), ("a1c", a1c)):
            app.number_input(key=f"pmw_{key}").set_value(value)
        app.selectbox(key="pmw_sex").select("male")
        app.selectbox(key="pmw_diabetes_status").select(diabetes_status)
        app.selectbox(key="pmw_smoking").select("never")
        app.button(key="measurements_next").click().run()
        self.assertFalse(app.exception)

    def test_empty_measurements_and_lifestyle_navigation_preserve_values(self):
        app = self.start()
        self.assertTrue(all(n.value is None for n in app.number_input))
        app.button(key="measurements_next").click().run()
        self.assertTrue(app.error)
        self.assertEqual(app.session_state["pm_step"], "measurements")
        self.enter_values(app)
        app.selectbox(key="pmw_diet_pattern").select("dash").run()
        app.selectbox(key="pmw_exercise").select("combined").run()
        app.button(key="lifestyle_next").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("plotly_chart")), 1)
        traces = json.loads(app.get("plotly_chart")[0].proto.spec)["data"]
        self.assertTrue(all(trace["mode"] == "lines" for trace in traces))
        self.assertAlmostEqual(app.session_state["pm_result"]["targets"]["sbp"], 133.12)
        app.checkbox(key="pmw_hr").check().run()
        self.assertFalse(app.get("plotly_chart"))
        app.button(key="results_measurements").click().run()
        self.assertEqual(app.number_input(key="pmw_age").value, 60)
        app.button(key="measurements_next").click().run()
        self.assertEqual(app.selectbox(key="pmw_diet_pattern").value, "dash")
        self.assertEqual(app.selectbox(key="pmw_exercise").value, "combined")

    def test_unknown_current_medication_route(self):
        app = self.start("with")
        app.button(key="meds_next").click().run()
        self.assertTrue(app.error)
        app.checkbox(key="pmw_current_unknown").check().run()
        app.button(key="meds_next").click().run()
        self.enter_values(app)
        self.assertFalse(any(c.key == "pmw_proposed_enabled" for c in app.checkbox))
        app.button(key="lifestyle_next").click().run()
        self.assertFalse(app.exception)
        self.assertIsNone(app.session_state["pm_result"]["medication"])
        self.assertFalse(app.radio)

    def test_known_drugs_no_default_dose_no_double_count_and_confirmation_reset(self):
        app = self.start("with")
        app.multiselect(key="pmw_current_sbp").set_value(["アムロジピン"]).run()
        dose_key = "pmw_current_dose_sbp_アムロジピン"
        self.assertIsNone(app.selectbox(key=dose_key).value)
        app.selectbox(key=dose_key).select("アムロジピン 2.5 mg").run()
        app.checkbox(key="pmw_current_confirmed").check().run()
        app.button(key="meds_next").click().run()
        self.enter_values(app)
        app.button(key="lifestyle_next").click().run()
        self.assertFalse(app.exception)
        result = app.session_state["pm_result"]
        self.assertEqual(result["targets"]["sbp"], 140)
        self.assertAlmostEqual(result["untreated"]["sbp"], 146.3)
        self.assertEqual(app.radio(key="pmw_comparison").value, "medication")
        app.button(key="results_medications").click().run()
        self.assertEqual(app.multiselect(key="pmw_current_sbp").value, ["アムロジピン"])
        self.assertTrue(app.checkbox(key="pmw_current_confirmed").value)
        app.selectbox(key=dose_key).select("アムロジピン 5 mg").run()
        self.assertFalse(app.checkbox(key="pmw_current_confirmed").value)

    def test_route_reset_removes_all_patient_and_drug_values(self):
        app = self.start("with")
        app.checkbox(key="pmw_current_unknown").check().run()
        app.button(key="meds_next").click().run()
        self.enter_values(app)
        app.button(key="reset_mobile").click().run()
        app.button(key="entry_without").click().run()
        self.assertIsNone(app.number_input(key="pmw_age").value)
        self.assertNotIn("current_meds", app.session_state["pm_data"])

    def test_proposed_medication_requires_explicit_dose_and_can_be_removed(self):
        app = self.start()
        self.enter_values(app)
        app.checkbox(key="pmw_proposed_enabled").check().run()
        app.multiselect(key="pmw_proposed_sbp").set_value(["アムロジピン"]).run()
        app.button(key="lifestyle_next").click().run()
        self.assertTrue(app.error)
        app.selectbox(key="pmw_proposed_dose_sbp_アムロジピン").select("アムロジピン 2.5 mg").run()
        app.button(key="lifestyle_next").click().run()
        self.assertAlmostEqual(app.session_state["pm_result"]["targets"]["sbp"], 133.7)
        app.button(key="results_lifestyle").click().run()
        app.checkbox(key="pmw_proposed_enabled").uncheck().run()
        app.button(key="lifestyle_next").click().run()
        self.assertEqual(app.session_state["pm_result"]["targets"]["sbp"], 140.)

    def test_non_diabetic_patient_reaches_results_without_hba1c(self):
        app = self.start()
        self.enter_values(app, diabetes_status="none", a1c=None)
        self.assertEqual(app.session_state["pm_step"], "lifestyle")
        app.selectbox(key="pmw_diet_pattern").select("dash").run()
        app.button(key="lifestyle_next").click().run()
        self.assertFalse(app.exception)
        result = app.session_state["pm_result"]
        self.assertEqual(set(result["lifestyle"]["curves"]), {"mi", "stroke", "mortality"})
        self.assertIsNone(result["targets"]["a1c"])
        self.assertAlmostEqual(result["targets"]["sbp"], 136.06)
        self.assertTrue(any("未入力" in m.value and "HbA1c" in m.value for m in app.markdown))
        app.button(key="results_lifestyle").click().run()
        app.selectbox(key="pmw_diet_pattern").select(None).run()
        app.selectbox(key="pmw_exercise").select("combined").run()
        app.button(key="lifestyle_next").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("数値化できません" in item.value for item in app.info))

    def test_change_diagnosis_resets_outcome_and_recalculates_without_old_effects(self):
        app = self.start()
        self.enter_values(app)
        app.selectbox(key="pmw_diet_pattern").select("mediterranean").run()
        app.selectbox(key="pmw_exercise").select("combined").run()
        app.button(key="lifestyle_next").click().run()
        app.selectbox(key="pmw_outcome").select("dementia").run()
        app.button(key="results_measurements").click().run()
        app.selectbox(key="pmw_diabetes_status").select("none").run()
        app.number_input(key="pmw_a1c").set_value(None).run()
        app.button(key="measurements_next").click().run()
        app.button(key="lifestyle_next").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="pmw_outcome").value, "mi")
        result = app.session_state["pm_result"]
        self.assertEqual(result["targets"]["sbp"], 140.)
        self.assertEqual(result["targets"]["ldl"], 130.)
        self.assertIsNone(result["targets"]["a1c"])
        self.assertFalse(result["applied"])

    def test_unknown_diagnosis_is_allowed_but_type2_requires_its_input(self):
        app = self.start()
        self.enter_values(app, diabetes_status="unknown", a1c=None)
        app.button(key="lifestyle_next").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["pm_result"]["lifestyle"]["curves"]), 3)
        app.button(key="results_measurements").click().run()
        app.selectbox(key="pmw_diabetes_status").select("type2").run()
        app.button(key="measurements_next").click().run()
        self.assertTrue(app.error)
        self.assertEqual(app.session_state["pm_step"], "measurements")


if __name__ == "__main__":
    unittest.main()
