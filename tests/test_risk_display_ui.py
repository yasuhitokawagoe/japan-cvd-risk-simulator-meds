import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class RiskDisplayUITests(unittest.TestCase):
    def test_toggle_all_outcomes_and_fitness(self):
        a = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app_streamlit_outcomes.py"), default_timeout=40).run()
        next(c for c in a.checkbox if c.label == "薬剤から目標値を自動計算する").check().run()
        a.selectbox(key="exercise_intervention").select("combined").run()
        absolute = next(m.value for m in a.metric if m.label == "全死亡")
        a.checkbox(key="show_hazard_ratio").check().run()
        self.assertFalse(a.exception)
        ratios = [m for m in a.metric if "HR相当" in m.label]
        self.assertEqual(len(ratios), 8)  # one selected + seven outcomes
        self.assertTrue(all("%" not in m.value for m in ratios))
        mortality_hr = next(m.value for m in ratios if m.label == "全死亡 HR相当")
        for outcome in ("mortality", "mi", "stroke", "esrd", "amputation", "blindness", "dementia"):
            a.radio(key="display_outcome").set_value(outcome).run()
            self.assertFalse(a.exception)
            self.assertEqual(len(a.get("plotly_chart")), 0)
        a.radio(key="display_outcome").set_value("mortality").run()
        a.checkbox(key="include_exercise_fitness").check().run()
        self.assertEqual(len(a.get("plotly_chart")), 0)
        self.assertLess(float(next(m.value for m in a.metric if m.label == "全死亡 HR相当（心肺体力込み・推定）")), float(mortality_hr))
        a.checkbox(key="include_exercise_fitness").uncheck().run()
        a.checkbox(key="show_hazard_ratio").uncheck().run()
        self.assertEqual(next(m.value for m in a.metric if m.label == "全死亡"), absolute)
        self.assertGreater(len(a.get("plotly_chart")), 0)
        a.checkbox(key="show_hazard_ratio").check().run()
        a.session_state["care_mode"] = "continue"
        a.run()
        self.assertFalse(a.exception)
        self.assertEqual(len(a.get("plotly_chart")), 0)
        self.assertTrue(any(m.label == "服薬継続（基準）" and m.value == "1.00" for m in a.metric))


if __name__ == "__main__":
    unittest.main()
