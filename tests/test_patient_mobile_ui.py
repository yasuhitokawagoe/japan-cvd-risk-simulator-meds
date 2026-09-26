from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app_patient_mobile.py"


class PatientMobileUITests(unittest.TestCase):
    def start(self, mode="without"):
        app = AppTest.from_file(str(APP), default_timeout=40).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key="entry_without").disabled)
        app.checkbox(key="pm_eligible").check().run()
        app.button(key=f"entry_{mode}").click().run()
        return app

    def enter_values(self, app):
        for key, value in (("age", 60), ("sbp", 140.), ("ldl", 130.), ("a1c", 7.5)):
            app.number_input(key=f"pmw_{key}").set_value(value)
        app.selectbox(key="pmw_sex").select("male")
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
        app.checkbox(key="pm_eligible").check().run()
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


if __name__ == "__main__":
    unittest.main()
