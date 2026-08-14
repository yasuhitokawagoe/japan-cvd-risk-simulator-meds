import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from treatment_backcast import (
    available_future_horizons,
    combine_cumulative_risk,
    exposure_adjusted_values,
    reconstruct_untreated_values,
)


def test_combine_cumulative_risk_connects_past_and_future_survival():
    assert abs(combine_cumulative_risk(0.10, 0.20) - 0.28) < 1e-12


def test_available_future_horizons_respects_age_cap():
    assert available_future_horizons(60) == (5, 10, 20, 30, 40, 50)
    assert available_future_horizons(85) == (5, 10, 20)


def med(key, effect):
    return {"key": key, "effect": {"mean": effect}}


def test_reverse_medication_effects():
    untreated = reconstruct_untreated_values(
        sbp_now=130, ldl_now=70, a1c_now=6.5,
        sbp_meds=[med("bp", -10)], ldl_meds=[med("ldl", 0.5)],
        a1c_meds=[med("dm", -1.0)],
    )
    assert untreated == {"sbp": 140.0, "ldl": 140.0, "a1c": 7.5}


def test_exposure_years_weight_the_achieved_effect():
    current = {"sbp": 130, "ldl": 70, "a1c": 6.5}
    untreated = {"sbp": 140, "ldl": 140, "a1c": 7.5}
    adjusted = exposure_adjusted_values(
        untreated=untreated, current=current, treatment_years=10,
        medication_years={"bp": 5, "ldl": 10, "dm": 2},
        sbp_meds=[med("bp", -10)], ldl_meds=[med("ldl", 0.5)], a1c_meds=[med("dm", -1)],
    )
    assert adjusted == {"sbp": 135.0, "ldl": 70.0, "a1c": 7.3}


if __name__ == "__main__":
    test_combine_cumulative_risk_connects_past_and_future_survival()
    test_available_future_horizons_respects_age_cap()
    test_reverse_medication_effects()
    test_exposure_years_weight_the_achieved_effect()
    print("OK: treatment backcast tests passed")
