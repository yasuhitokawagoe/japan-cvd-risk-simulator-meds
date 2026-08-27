from treatment_backcast import combine_cumulative_risk, reconstruct_untreated_values


def _med(key, effect):
    return {"key": key, "effect": {"mean": effect}}


def test_reverse_all_medication_effects():
    untreated = reconstruct_untreated_values(
        sbp_now=130, ldl_now=70, a1c_now=6.5,
        sbp_meds=[_med("bp", -10)],
        ldl_meds=[_med("ldl", 0.5)],
        a1c_meds=[_med("dm", -1.0)],
    )
    assert untreated == {"sbp": 140.0, "ldl": 140.0, "a1c": 7.5}


def test_past_and_future_risk_are_joined_on_survival_scale():
    assert abs(combine_cumulative_risk(0.10, 0.20) - 0.28) < 1e-12
