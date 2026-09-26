import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class DietPatternUITests(unittest.TestCase):
    def make_app(self):
        # Probe actual app calculations without adding test state to production.
        source = (Path(__file__).resolve().parents[1] / "app_streamlit_outcomes.py").read_text()
        source += '''
st.session_state["diet_test_probe"] = {
    "targets": (sbp_tgt, ldl_tgt, a1c_tgt, bmi_target),
    "keys": diet_intervention_keys,
    "data": cumulative_data,
    "document_data": document_risk_curves,
    "contributions": build_medication_contributions("mortality", horizon),
}
'''
        app = AppTest.from_string(source, default_timeout=40).run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        return app

    def probe(self, app):
        self.assertFalse(app.exception, [e.message for e in app.exception])
        return app.session_state["diet_test_probe"]

    def number(self, app, label):
        return next(n for n in app.number_input if n.label == label)

    def test_selection_reset_no_stacking_and_restore(self):
        app = self.make_app()
        self.assertEqual(app.selectbox(key="diet_pattern").options, [
            "個別の食事介入", "野菜・低脂肪乳製品を増やす減塩食",
            "魚・野菜中心で、油の質を見直す食事", "専用の食品に置き換える減量食",
        ])
        self.number(app, "現在のBMI").set_value(30).run()
        self.number(app, "目標BMI").set_value(22).run()
        app.multiselect(key="diet_interventions").set_value(["salt", "carb", "fat"]).run()
        app.selectbox(key="diet_pattern").select("dash").run()
        first = self.probe(app)
        self.assertEqual(first["keys"], ["dash"])
        self.assertEqual(first["contributions"][0]["name"], "食事：野菜・低脂肪乳製品を増やす減塩食")
        self.assertTrue(any("研究上の名称：DASH食" in m.value for m in app.markdown))
        for actual, expected in zip(first["targets"], (146.06, 156.47, 8, 29.36)):
            self.assertAlmostEqual(actual, expected)
        self.assertTrue(self.number(app, "目標BMI").disabled)
        self.assertFalse(list(app.multiselect))
        app.run()
        self.assertEqual(self.probe(app)["targets"], first["targets"])
        for key, expected in (
            ("mediterranean", (150, 151.94, 7.693, 29.172)),
            ("meal_replacement", (145.03, 160, 7.57, 29.13)),
        ):
            app.selectbox(key="diet_pattern").select(key).run()
            probe = self.probe(app)
            for actual, value in zip(probe["targets"], expected):
                self.assertAlmostEqual(actual, value)
            curve = probe["data"]["mortality"]
            arr = curve["baseline_cumulative"][-1] - curve["target_cumulative"][-1]
            self.assertAlmostEqual(sum(c["delta"] for c in probe["contributions"]), arr)
            self.assertEqual(probe["data"], probe["document_data"])
        app.selectbox(key="exercise_intervention").select("combined").run()
        probe = self.probe(app)
        for actual, expected in zip(probe["targets"], (142.09, 148.01, 6.83, 29.13)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(len(probe["contributions"]), 2)
        app.checkbox(key="show_hazard_ratio").check().run()
        self.assertFalse(app.get("plotly_chart"))
        self.assertTrue(any(m.label == "全死亡 HR相当" for m in app.metric))
        app.selectbox(key="exercise_intervention").select(None).run()
        app.selectbox(key="diet_pattern").select(None).run()
        restored = self.probe(app)
        self.assertEqual(restored["keys"], [])
        self.assertEqual(restored["targets"], (130, 100, 7, 22))
        self.assertFalse(self.number(app, "目標BMI").disabled)

    def test_normal_bmi_guard_documents_and_continue_mode(self):
        app = self.make_app()
        app.selectbox(key="diet_pattern").select("meal_replacement").run()
        self.assertEqual(self.probe(app)["targets"], (150, 160, 8, 24))
        self.assertEqual(self.probe(app)["contributions"], [])
        self.assertTrue(any("効果は適用していません" in w.value for w in app.warning))
        with patch("pdf_plan_ui.render_plan_section") as render:
            app.button(key="open_document_creation").click().run()
            self.assertEqual(render.call_args.kwargs["lifestyle_interventions"], ())
        app.session_state["show_document_creation"] = False
        app.selectbox(key="diet_pattern").select("mediterranean").run()
        self.assertEqual(self.probe(app)["targets"][3], 24)
        self.number(app, "現在のBMI").set_value(30).run()
        with patch("pdf_plan_ui.render_plan_section") as render:
            app.button(key="open_document_creation").click().run()
            self.assertFalse(app.exception)
            args = render.call_args.kwargs
            self.assertAlmostEqual(args["bmi_target"], 29.172)
            self.assertAlmostEqual(args["a1c_after"], 7.693)
            self.assertEqual(args["lifestyle_interventions"], ("魚・野菜中心で、油の質を見直す食事",))
            self.assertEqual(args["risk_curves"], self.probe(app)["document_data"])
        app.session_state["show_document_creation"] = False
        app.session_state["care_mode"] = "continue"
        app.run()
        self.assertEqual(self.probe(app)["keys"], [])
        self.assertFalse(any(m.label == "食事介入後BMI（推定）" for m in app.metric))

    def test_drug_diet_exercise_share_targets_and_contributions(self):
        app = self.make_app()
        self.number(app, "現在のBMI").set_value(30).run()
        next(c for c in app.checkbox if c.label == "薬剤から目標値を自動計算する").check().run()
        next(g for g in app.get("button_group") if g.key == "current_ldl_meds_categories").set_value(["スタチン"]).run()
        drugs = next(g for g in app.get("button_group") if g.key == "current_ldl_meds_スタチン_drugs")
        drugs.set_value([drugs.options[0]]).run()
        drug_targets = self.probe(app)["targets"]
        app.selectbox(key="diet_pattern").select("dash").run()
        app.selectbox(key="exercise_intervention").select("combined").run()
        probe = self.probe(app)
        for actual, value in zip(probe["targets"], (
            drug_targets[0] - 3.94 - 2.94,
            drug_targets[1] - 3.53 - 11.99,
            drug_targets[2] - 0.74, 29.36,
        )):
            self.assertAlmostEqual(actual, value)
        self.assertEqual(len(probe["contributions"]), 3)
        curve = probe["data"]["mortality"]
        arr = curve["baseline_cumulative"][-1] - curve["target_cumulative"][-1]
        self.assertAlmostEqual(sum(c["delta"] for c in probe["contributions"]), arr)


if __name__ == "__main__":
    unittest.main()
