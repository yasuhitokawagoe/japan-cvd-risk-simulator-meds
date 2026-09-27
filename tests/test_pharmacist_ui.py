from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest
from pc_diabetes_selection import DIABETES_MODEL_KEY

ROOT = Path(__file__).resolve().parents[1]
HARNESS = '''
import streamlit as st
from pharmacist_ui import render_pharmacist_mode
render_pharmacist_mode(st.session_state.get("test_meds", []), st.session_state.get("test_bone", "none"))
'''


class PharmacistUITests(unittest.TestCase):
    def app(self):
        app = AppTest.from_string(HARNESS, default_timeout=20).run()
        self.assertFalse(app.exception)
        return app

    def checked(self, app):
        self.assertFalse(app.exception, [e.message for e in app.exception])
        return app.get("download_button")[0].proto.disabled

    def confirm(self, app, key="metformin"):
        app.text_input(key=f"pharm_regimen_{key}").input("架空テスト：薬袋の用法を確認").run()
        app.checkbox(key="pharm_actual_confirmed").check().run()
        app.checkbox(key="pharm_reviewed").check().run()

    def test_starts_empty_and_exposes_all_47_without_simulation_drugs(self):
        app = self.app()
        self.assertEqual(len(app.multiselect(key="pharm_selection").options), 47)
        self.assertEqual(app.multiselect(key="pharm_selection").value, [])
        self.assertTrue(app.button(key="pharm_import").disabled)
        self.assertFalse(app.get("download_button"))

    def test_confirmation_and_regimen_gate_download(self):
        app = self.app()
        app.multiselect(key="pharm_selection").set_value(["metformin"]).run()
        self.assertTrue(self.checked(app))
        app.checkbox(key="pharm_actual_confirmed").check().run()
        app.checkbox(key="pharm_reviewed").check().run()
        self.assertTrue(self.checked(app))  # Still lacks actual regimen.
        self.confirm(app)
        self.assertFalse(self.checked(app))

    def test_any_content_change_invalidates_both_checks(self):
        app = self.app()
        app.multiselect(key="pharm_selection").set_value(["metformin"]).run()
        self.confirm(app)
        for field, key in (("text_area", "pharm_note_metformin"), ("text_input", "pharm_contact"), ("text_input", "pharm_regimen_metformin")):
            getattr(app, field)(key=key).input("変更テスト").run()
            self.assertTrue(self.checked(app))
            self.assertFalse(app.checkbox(key="pharm_actual_confirmed").value)
            self.assertFalse(app.checkbox(key="pharm_reviewed").value)
            app.checkbox(key="pharm_actual_confirmed").check().run()
            app.checkbox(key="pharm_reviewed").check().run()
        app.multiselect(key="pharm_selection").set_value(["metformin", "amlodipine"]).run()
        self.assertTrue(self.checked(app))
        app.multiselect(key="pharm_selection").set_value(["metformin"]).run()
        self.assertFalse(app.checkbox(key="pharm_actual_confirmed").value)

    def test_import_includes_bone_but_does_not_invent_actual_regimen(self):
        app = self.app()
        app.session_state["test_meds"] = [{"drug_name": "メトホルミン", "key": "メトホルミン 1000mg"}]
        app.session_state["test_bone"] = "denosumab"
        app.run()
        app.button(key="pharm_import").click().run()
        self.assertEqual(app.multiselect(key="pharm_selection").value, ["metformin", "denosumab"])
        self.assertEqual(app.text_input(key="pharm_regimen_metformin").value, "")
        self.assertFalse(app.checkbox(key="pharm_actual_confirmed").value)
        self.assertTrue(self.checked(app))
        app.text_area(key="pharm_note_metformin").input("次の患者に残さない").run()
        app.button(key="pharm_clear").click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(app.multiselect(key="pharm_selection").value, [])
        app.multiselect(key="pharm_selection").set_value(["metformin"]).run()
        self.assertEqual(app.text_area(key="pharm_note_metformin").value, "")

    def test_contraindicated_combination_cannot_be_exported_even_if_checked(self):
        app = self.app()
        app.multiselect(key="pharm_selection").set_value(["enalapril", "sacubitril_valsartan"]).run()
        for key in ("enalapril", "sacubitril_valsartan"):
            app.text_input(key=f"pharm_regimen_{key}").input("架空テスト").run()
        app.checkbox(key="pharm_actual_confirmed").check().run()
        app.checkbox(key="pharm_reviewed").check().run()
        self.assertTrue(self.checked(app))
        self.assertTrue(any("併用禁忌" in element.value for element in app.error))

    def test_mode_and_guidance_selection_do_not_change_risk_curves(self):
        source = (ROOT / "app_streamlit_outcomes.py").read_text() + '''
st.session_state["pharm_test_risk"] = (cumulative_data, sbp_tgt, ldl_tgt, a1c_tgt, document_risk_curves)
'''
        app = AppTest.from_string(source, default_timeout=40).run()
        self.assertFalse(app.exception)
        before = app.session_state["pharm_test_risk"]
        app.checkbox(key="pharmacist_mode").check().run()
        app.multiselect(key="pharm_selection").set_value(["metformin", "denosumab"]).run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(before, app.session_state["pharm_test_risk"])
        app.checkbox(key=DIABETES_MODEL_KEY).uncheck().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        app.multiselect(key="pharm_selection").set_value(["empagliflozin"]).run()
        self.assertEqual(app.multiselect(key="pharm_selection").value, ["empagliflozin"])
        app.checkbox(key="pharmacist_mode").uncheck().run()
        self.assertFalse(app.exception)
        self.assertNotIn("pharm_selection", [widget.key for widget in app.multiselect])


if __name__ == "__main__":
    unittest.main()
