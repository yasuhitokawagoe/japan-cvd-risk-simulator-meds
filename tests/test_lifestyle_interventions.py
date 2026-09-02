from lifestyle_interventions import apply_lifestyle_effects


def test_diet_effects_are_applied_to_supported_markers():
    result = apply_lifestyle_effects(
        sbp=150, ldl=160, a1c=8.0,
        diet_keys=["salt", "carb", "fat"], diabetes_context=True,
    )
    assert round(result["sbp"], 2) == 145.74
    assert round(result["ldl"], 1) == 145.6
    assert round(result["a1c"], 2) == 7.64


def test_combined_exercise_uses_meta_analysis_coefficients():
    result = apply_lifestyle_effects(
        sbp=140, ldl=140, a1c=7.5,
        exercise_key="combined", diabetes_context=True,
    )
    assert round(result["sbp"], 2) == 138.76
    assert round(result["ldl"], 2) == 133.04
    assert round(result["a1c"], 2) == 6.76


def test_diabetes_exercise_is_not_extrapolated_without_context():
    result = apply_lifestyle_effects(
        sbp=130, ldl=120, a1c=5.5,
        exercise_key="combined", diabetes_context=False,
    )
    assert result["sbp"] == 130
    assert result["ldl"] == 120
    assert result["a1c"] == 5.5
    assert len(result["skipped"]) == 1
