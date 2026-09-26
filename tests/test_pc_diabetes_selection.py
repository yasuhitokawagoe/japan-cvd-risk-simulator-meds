import unittest

from bone_health import hip_fracture_risk
from calc_engine_outcomes import OutcomesEngine
from pc_diabetes_selection import (
    DIABETES_MANUAL_KEY, DIABETES_MODEL_KEY,
    mark_diabetes_selection_manual, sync_diabetes_selection,
)


class DiabetesSelectionTests(unittest.TestCase):
    def test_threshold_is_inclusive(self):
        for a1c, expected in ((5.5, False), (6.4, False), (6.5, True), (8.0, True)):
            state = {}
            sync_diabetes_selection(state, a1c)
            self.assertEqual(state[DIABETES_MODEL_KEY], expected)

    def test_rising_current_value_enables_but_falling_does_not_clear(self):
        state = {}
        sync_diabetes_selection(state, 6.4)
        sync_diabetes_selection(state, 6.5)
        self.assertTrue(state[DIABETES_MODEL_KEY])
        sync_diabetes_selection(state, 5.5)
        self.assertTrue(state[DIABETES_MODEL_KEY])

    def test_manual_on_and_off_persist_at_any_current_value(self):
        for choice in (True, False):
            state = {DIABETES_MODEL_KEY: choice}
            mark_diabetes_selection_manual(state)
            self.assertTrue(state[DIABETES_MANUAL_KEY])
            for a1c in (5.0, 6.5, 9.0, 5.5, 8.0):
                sync_diabetes_selection(state, a1c)
                self.assertEqual(state[DIABETES_MODEL_KEY], choice)

    def test_sessions_do_not_share_overrides(self):
        first = {DIABETES_MODEL_KEY: False, DIABETES_MANUAL_KEY: True}
        second = {}
        sync_diabetes_selection(first, 8.0)
        sync_diabetes_selection(second, 8.0)
        self.assertFalse(first[DIABETES_MODEL_KEY])
        self.assertTrue(second[DIABETES_MODEL_KEY])

    def test_non_diabetes_has_no_glucose_effect_in_past_or_future(self):
        engine = OutcomesEngine("config.yaml")
        for method in (engine.cumulative_incidence, engine.cumulative_incidence_with_ci):
            for outcome in ("mi", "stroke", "mortality"):
                expected = None
                for current, target in ((8.0, 7.0), (5.0, 5.0), (5.0, 9.0)):
                    actual = method(outcome, "male", 60, 10, 140, 130, 130, 100,
                                    current, target, "never", 0, 0, 0,
                                    apply_hba1c_effect=False)
                    if expected is None:
                        expected = actual
                    self.assertEqual(actual, expected)

    def test_bone_multiplier_only_applied_when_enabled(self):
        ordinary = hip_fracture_risk(age=70, sex="female", has_type2_diabetes=False)
        diabetes = hip_fracture_risk(age=70, sex="female", has_type2_diabetes=True)
        self.assertGreater(diabetes, ordinary)
        self.assertEqual(diabetes, hip_fracture_risk(age=70, sex="female"))


if __name__ == "__main__":
    unittest.main()
