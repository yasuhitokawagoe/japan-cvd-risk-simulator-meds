from lifestyle_interventions import EXERCISE_EFFECTS, apply_lifestyle_effects


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
    assert round(result["sbp"], 2) == 137.06
    assert round(result["ldl"], 2) == 128.01
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


def test_all_exercise_modalities_match_figure_3():
    expected = {
        "aerobic_moderate": (-1.24, -0.19, -0.62),
        "combined": (-2.94, -0.31, -0.74),
        "hiit": (-2.64, -0.29, -0.71),
    }
    for key, (sbp_delta, ldl_mmol, a1c_delta) in expected.items():
        effect = EXERCISE_EFFECTS[key]
        assert effect.sbp_delta == sbp_delta
        assert effect.ldl_delta_mg == round(ldl_mmol * 38.67, 2)
        assert effect.a1c_delta == a1c_delta
        result = apply_lifestyle_effects(
            sbp=140, ldl=140, a1c=7.5,
            exercise_key=key, diabetes_context=True,
        )
        assert round(result["sbp"], 2) == round(140 + sbp_delta, 2)
        assert round(result["ldl"], 2) == round(140 + effect.ldl_delta_mg, 2)
        assert round(result["a1c"], 2) == round(7.5 + a1c_delta, 2)
        assert effect.source_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC12859889/"


def test_exercise_and_diet_are_each_applied_once():
    result = apply_lifestyle_effects(
        sbp=140, ldl=140, a1c=7.5,
        diet_keys=["salt", "fat", "carb"], exercise_key="combined",
        diabetes_context=True,
    )
    assert round(result["sbp"], 2) == 132.80
    assert round(result["ldl"], 2) == 115.41
    assert round(result["a1c"], 2) == 6.40
    assert len(result["applied"]) == 4


def test_exercise_preserves_safety_floors():
    result = apply_lifestyle_effects(
        sbp=81, ldl=22, a1c=4.1,
        exercise_key="combined", diabetes_context=True,
    )
    assert (result["sbp"], result["ldl"], result["a1c"]) == (80, 20, 4)
