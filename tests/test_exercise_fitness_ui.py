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
        self.assertFalse(fitness_traces())
        app.checkbox(key="include_exercise_fitness").check().run()
        self.assertEqual(traces()[:-1], ordinary)
        self.assertEqual(fitness_traces()[0]["line"]["dash"], "dot")
        self.assertTrue(any("探索的推定" in m.label for m in app.metric))
        app.radio(key="display_outcome").set_value("mi").run()
        self.assertFalse(fitness_traces())
        self.assertTrue(any("このアウトカムには上乗せしていません" in i.value for i in app.info))
        app.radio(key="display_outcome").set_value("mortality").run()
        app.selectbox(key="exercise_intervention").select("hiit").run()
        self.assertEqual(len(fitness_traces()), 1)
        self.assertTrue(any("+4.19" in c.value for c in app.caption))
        app.checkbox(key="include_exercise_fitness").uncheck().run()
        self.assertFalse(fitness_traces())
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
