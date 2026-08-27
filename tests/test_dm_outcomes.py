import pytest

from dm_outcomes import DiabetesOutcomeModel


@pytest.mark.parametrize("outcome", ["esrd", "amputation", "blindness"])
def test_improving_dm_risk_factors_reduces_risk(outcome):
    model = DiabetesOutcomeModel()
    current = model.predict_risk(
        outcome, hba1c=9.0, age=65, egfr=45, acr=300,
        sbp=155, sex=1, years=10,
    )
    improved = model.predict_risk(
        outcome, hba1c=7.0, age=65, egfr=60, acr=30,
        sbp=130, sex=1, years=10,
    )
    assert 0 < improved < current < 1


def test_curve_starts_at_zero_and_ci_contains_valid_probabilities():
    curve = DiabetesOutcomeModel().predict_curve_with_ci(
        "esrd", hba1c=8.0, age=70, egfr=55, acr=100,
        sbp=140, sex=1, years=20,
    )
    assert curve["risk"][0] == 0
    assert len(curve["time"]) == 21
    assert all(0 <= value <= 1 for value in curve["lower"])
    assert all(0 <= value <= 1 for value in curve["upper"])
