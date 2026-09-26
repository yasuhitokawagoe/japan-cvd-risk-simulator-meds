from pathlib import Path
import json
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from pc_diabetes_selection import DIABETES_MODEL_KEY


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app_streamlit_outcomes.py").read_text() + '''
st.session_state["pc_diabetes_probe"] = {
    "enabled": has_type2_diabetes,
    "curves": cumulative_data,
    "documents": document_risk_curves,
    "past": calculate_past_treatment_benefit(3, has_type2_diabetes=has_type2_diabetes),
    "targets": (sbp_tgt, ldl_tgt, a1c_tgt),
    "contributions": build_medication_contributions("mortality", horizon),
    "fitness": fitness_projection,
    "selected_a1c_meds": selected_a1c_meds,
    "dementia_contributions": build_medication_contributions("dementia", horizon),
}
'''


class PCDiabetesUITests(unittest.TestCase):
    def make_app(self, a1c=None):
        app = AppTest.from_string(SOURCE, default_timeout=40)
        if a1c is not None:
            app.session_state["a1c_now"] = a1c
        app.run()
        self.probe(app)
        return app

    def probe(self, app):
        self.assertFalse(app.exception, [e.message for e in app.exception])
        return app.session_state["pc_diabetes_probe"]

    def toggle(self, app, checked):
        app.checkbox(key=DIABETES_MODEL_KEY).set_value(checked).run()
        return self.probe(app)

    def test_default_high_value_auto_checks_and_discloses_type1_exclusion(self):
        app = self.make_app()
        self.assertTrue(app.checkbox(key=DIABETES_MODEL_KEY).value)
        self.assertEqual(len(self.probe(app)["curves"]), 7)
        self.assertTrue(any("1型糖尿病はこのアプリの推定対象外" in c.value for c in app.caption))
        self.assertTrue(any("確定診断ではありません" in c.value for c in app.caption))

    def test_threshold_slider_and_nudge_and_targets(self):
        app = self.make_app(6.4)
        self.assertFalse(self.probe(app)["enabled"])
        app.slider(key="a1c_target").set_value(8.0).run()
        self.assertFalse(self.probe(app)["enabled"])
        app.slider(key="a1c_now").set_value(6.5).run()
        self.assertTrue(self.probe(app)["enabled"])
        app.slider(key="a1c_now").set_value(5.0).run()
        self.assertTrue(self.probe(app)["enabled"])
        second = self.make_app(6.0)
        second.button(key="a1c_now_increase").click().run()
        self.assertTrue(self.probe(second)["enabled"])

    def test_manual_override_stays_off_despite_reruns_and_high_a1c(self):
        app = self.make_app()
        self.toggle(app, False)
        app.run()
        for current in (9.0, 5.5, 7.0):
            app.slider(key="a1c_now").set_value(current).run()
            self.assertFalse(self.probe(app)["enabled"])
        app.slider(key="sbp_now").set_value(160).run()
        self.assertFalse(self.probe(app)["enabled"])
        app.slider(key="a1c_now").set_value(5.5).run()
        self.toggle(app, True)
        app.slider(key="a1c_target").set_value(5.0).run()
        self.assertTrue(self.probe(app)["enabled"])

    def test_off_filters_curves_summary_hr_documents_and_restores_valid_selection(self):
        app = self.make_app()
        app.radio(key="display_outcome").set_value("blindness").run()
        app.session_state["past_benefit_outcome"] = "dementia"
        with patch("dm_outcomes.DiabetesOutcomeModel.predict_curve_with_ci", side_effect=AssertionError("DM model called")), \
                patch("dementia_prevention.dementia_curve", side_effect=AssertionError("DM dementia called")):
            probe = self.toggle(app, False)
        self.assertEqual(set(probe["curves"]), {"mortality", "mi", "stroke", "esrd", "dementia"})
        self.assertIn("unavailable_reason", probe["curves"]["esrd"])
        self.assertIn("unavailable_reason", probe["curves"]["dementia"])
        self.assertEqual(probe["curves"], probe["documents"])
        self.assertEqual(set(probe["past"]), {"mortality", "mi", "stroke", "estimated_life_years_gained"})
        self.assertEqual(app.radio(key="display_outcome").value, "mortality")
        self.assertTrue(any("5アウトカム" in m.value for m in app.markdown))
        app.checkbox(key="show_hazard_ratio").check().run()
        self.probe(app)
        self.assertFalse(app.get("plotly_chart"))
        self.assertEqual(len([m for m in app.metric if "HR相当" in m.label]), 4)
        self.toggle(app, True)
        self.assertEqual(len(self.probe(app)["curves"]), 7)

    def test_non_diabetes_hba1c_does_not_change_future_past_or_contributions(self):
        app = self.make_app()
        reference = self.toggle(app, False)
        app.slider(key="a1c_now").set_value(5.0).run()
        app.slider(key="a1c_target").set_value(5.0).run()
        probe = self.probe(app)
        self.assertEqual(probe["curves"], reference["curves"])
        self.assertEqual(probe["past"], reference["past"])
        self.assertEqual(probe["contributions"], reference["contributions"])

    def test_lifestyle_and_fitness_do_not_apply_diabetes_only_effects(self):
        app = self.make_app()
        self.toggle(app, False)
        app.selectbox(key="diet_pattern").select("dash").run()
        probe = self.probe(app)
        self.assertAlmostEqual(probe["targets"][0], 146.06)
        self.assertEqual(len(probe["contributions"]), 1)
        app.selectbox(key="diet_pattern").select("mediterranean").run()
        self.assertEqual(self.probe(app)["targets"], (150.0, 160.0, 8.0))
        self.assertEqual(self.probe(app)["contributions"], [])
        app.selectbox(key="exercise_intervention").select("combined").run()
        self.assertTrue(app.checkbox(key="include_exercise_fitness").disabled)
        self.assertIsNone(self.probe(app)["fitness"])
        self.assertTrue(any("数値化は対象外" in w.value for w in app.warning))
        with patch("pdf_plan_ui.render_plan_section") as render:
            app.button(key="open_document_creation").click().run()
            self.probe(app)
            self.assertFalse(render.call_args.kwargs["diabetes_model_enabled"])
            self.assertEqual(render.call_args.kwargs["lifestyle_interventions"], ())

    def test_document_diabetes_suggestion_respects_manual_off_at_high_a1c(self):
        app = self.make_app()
        self.toggle(app, False)
        app.button(key="open_document_creation").click().run()
        self.probe(app)
        self.assertFalse(app.checkbox(key="dm_care_dx_dm").value)
        app.slider(key="a1c_now").set_value(9.0).run()
        self.probe(app)
        self.assertFalse(app.checkbox(key="dm_care_dx_dm").value)
        self.toggle(app, True)
        self.assertTrue(app.checkbox(key="dm_care_dx_dm").value)

    def test_continuing_drugs_past_outcomes_and_stale_selections(self):
        app = self.make_app()
        app.session_state["care_mode"] = "continue"
        app.run()
        next(g for g in app.get("button_group") if g.key == "current_ldl_meds_categories").set_value(["スタチン"]).run()
        drugs = next(g for g in app.get("button_group") if g.key == "current_ldl_meds_スタチン_drugs")
        drugs.set_value([drugs.options[0]]).run()
        glucose_classes = next(g for g in app.get("button_group") if g.key == "current_a1c_meds_categories")
        glucose_class = glucose_classes.options[0]
        glucose_classes.set_value([glucose_class]).run()
        glucose_drugs = next(g for g in app.get("button_group") if g.key == f"current_a1c_meds_{glucose_class}_drugs")
        glucose_drugs.set_value([glucose_drugs.options[0]]).run()
        self.assertTrue(self.probe(app)["selected_a1c_meds"])
        app.selectbox(key="past_benefit_outcome").select("amputation").run()
        self.toggle(app, False)
        self.assertEqual(app.selectbox(key="past_benefit_outcome").value, "mortality")
        self.assertEqual(app.selectbox(key="past_benefit_outcome").options, ["全死亡", "心筋梗塞", "脳卒中"])
        self.assertFalse(any(g.key == "current_a1c_meds_categories" for g in app.get("button_group")))
        self.assertEqual(self.probe(app)["selected_a1c_meds"], [])

    def test_general_dementia_curve_hr_and_contributions(self):
        app = self.make_app(5.5)
        next(n for n in app.number_input if n.label == "年齢（歳）").set_value(70).run()
        app.radio(key="display_outcome").set_value("dementia").run()
        probe = self.probe(app)
        dementia = probe["curves"]["dementia"]
        self.assertEqual(dementia["model"], "jages")
        self.assertFalse(dementia["has_uncertainty"])
        self.assertAlmostEqual(
            sum(c["delta"] for c in probe["dementia_contributions"]),
            dementia["baseline_cumulative"][-1] - dementia["target_cumulative"][-1],
        )
        figure = json.loads(app.get("plotly_chart")[0].proto.spec)
        self.assertEqual(len(figure["data"]), 4)
        self.assertTrue(any(t["line"].get("dash") == "dot" for t in figure["data"]))
        self.assertFalse(any("95%" in t.get("name", "") for t in figure["data"]))
        self.assertTrue(any("非糖尿病の人だけで検証された個人予測ではありません" in w.value for w in app.warning))
        app.checkbox(key="show_hazard_ratio").check().run()
        self.probe(app)
        self.assertFalse(app.get("plotly_chart"))
        self.assertFalse(any("HR相当の参考幅：" in c.value for c in app.caption))
        self.assertEqual(len([m for m in app.metric if "HR相当" in m.label]), 5)
        next(n for n in app.number_input if n.label == "年齢（歳）").set_value(64).run()
        self.assertIn("unavailable_reason", self.probe(app)["curves"]["dementia"])
        self.assertEqual(app.radio(key="display_outcome").value, "dementia")
        self.assertTrue(any("65歳未満は未算出" in i.value for i in app.info))

    def test_kfre_requires_real_inputs_and_has_no_intervention_or_hr(self):
        app = self.make_app(5.5)
        app.radio(key="display_outcome").set_value("esrd").run()
        self.assertIn("unavailable_reason", self.probe(app)["curves"]["esrd"])
        next(n for n in app.number_input if n.label == "現在のeGFR").set_value(25.0).run()
        app.number_input(key="pc_kfre_uacr").set_value(300.0).run()
        app.checkbox(key="pc_kfre_ckd_confirmed").check().run()
        self.assertIn("unavailable_reason", self.probe(app)["curves"]["esrd"])
        app.selectbox(key="pc_kfre_egfr_method").select("CKD-EPI").run()
        renal = self.probe(app)["curves"]["esrd"]
        self.assertIn("risk_2y", renal)
        self.assertNotIn("target_cumulative", renal)
        self.assertFalse(app.get("plotly_chart"))
        next(n for n in app.number_input if n.label == "目標eGFR").set_value(55.0).run()
        next(s for s in app.selectbox if s.label == "予測期間").select("50-year").run()
        self.assertEqual(self.probe(app)["curves"]["esrd"], renal)
        app.checkbox(key="show_hazard_ratio").check().run()
        self.probe(app)
        self.assertFalse(app.get("plotly_chart"))
        self.assertTrue(any("比較する介入HRは算出しません" in i.value for i in app.info))
        next(n for n in app.number_input if n.label == "現在のeGFR").set_value(60.0).run()
        self.assertIn("unavailable_reason", self.probe(app)["curves"]["esrd"])


if __name__ == "__main__":
    unittest.main()
