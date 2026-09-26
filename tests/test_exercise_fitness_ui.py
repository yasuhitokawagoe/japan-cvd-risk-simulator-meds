"""Integration test: python -m unittest tests.test_exercise_fitness_ui -v."""
import json
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class FitnessUITests(unittest.TestCase):
    def test_opt_in_curve_and_transitions(self):
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "app_streamlit_outcomes.py"),
            default_timeout=40,
        ).run()

        def traces():
            self.assertFalse(app.exception, [e.message for e in app.exception])
            return json.loads(app.get("plotly_chart")[0].proto.spec)["data"]

        def fitness_traces():
            return [t for t in traces() if "心肺体力" in t.get("name", "")]

        next(c for c in app.checkbox if c.label == "薬剤から目標値を自動計算する").check().run()
        app.selectbox(key="exercise_intervention").select("combined").run()
        self.assertFalse(app.checkbox(key="include_exercise_fitness").value)
        ordinary = traces()
        ordinary_value = next(m.value for m in app.metric if m.label == "全死亡")
        ordinary_arr = next(m.value for m in app.metric if m.label == "リスク減少幅")
        self.assertFalse(fitness_traces())
        app.checkbox(key="include_exercise_fitness").check().run()
        self.assertEqual(len(traces()), len(ordinary))  # replacement, not a third curve
        self.assertEqual(traces()[:2], ordinary[:2])  # baseline band unchanged
        self.assertEqual(traces()[4:6], ordinary[4:6])  # baseline curve unchanged
        self.assertNotEqual(traces()[6]["y"], ordinary[6]["y"])
        self.assertNotEqual(traces()[2]["y"], ordinary[2]["y"])
        self.assertEqual(traces()[6]["line"], ordinary[6]["line"])  # same style
        self.assertTrue(any("95%推定幅" in t.get("name", "") for t in traces()))
        new_value = next(m.value for m in app.metric if m.label == "全死亡（心肺体力込み・推定）")
        self.assertLess(float(new_value.rstrip("%")), float(ordinary_value.rstrip("%")))
        self.assertNotEqual(next(m.value for m in app.metric if m.label == "リスク減少幅"), ordinary_arr)
        self.assertEqual(next(m.value for m in app.metric if "目標達成時（心肺体力込み" in m.label), new_value)
        self.assertTrue(any("心肺体力の追加効果" in m.value for m in app.markdown))
        app.radio(key="display_outcome").set_value("mi").run()
        self.assertFalse(fitness_traces())
        self.assertTrue(any("このアウトカムには上乗せしていません" in i.value for i in app.info))
        app.radio(key="display_outcome").set_value("mortality").run()
        app.selectbox(key="exercise_intervention").select("hiit").run()
        self.assertEqual(len(fitness_traces()), 2)  # band + selected target curve
        self.assertTrue(any("+4.19" in c.value for c in app.caption))
        app.checkbox(key="include_exercise_fitness").uncheck().run()
        self.assertFalse(fitness_traces())
        app.selectbox(key="exercise_intervention").select("combined").run()
        self.assertEqual(traces(), ordinary)
        self.assertEqual(next(m.value for m in app.metric if m.label == "全死亡"), ordinary_value)
        app.checkbox(key="include_exercise_fitness").check().run()
        app.selectbox(key="exercise_intervention").select(None).run()
        self.assertFalse(fitness_traces())
        app.selectbox(key="exercise_intervention").select("combined").run()
        app.checkbox(key="include_exercise_fitness").check().run()
        app.session_state["care_mode"] = "continue"
        app.run()
        self.assertFalse(fitness_traces())


if __name__ == "__main__":
    unittest.main()
