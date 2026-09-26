from dementia_prevention import (
    JAPAN_DEMENTIA_PARTIAL_CALIBRATION,
    dementia_biomarker_hazard_ratio,
    dementia_curve,
    selected_dementia_evidence,
)


def test_bp_and_glp1_are_returned_as_supported_evidence():
    result = selected_dementia_evidence(
        bp_medications=[{"category": "ARB"}],
        lipid_medications=[],
        diabetes_medications=[{"category": "GLP-1受容体作動薬（皮下）"}],
    )
    assert [item.key for item in result["supported"]] == ["bp_lowering", "glp1_ra"]


def test_statin_is_counted_but_unsupported_dpp4_is_not():
    result = selected_dementia_evidence(
        bp_medications=[],
        lipid_medications=[{"category": "スタチン"}],
        diabetes_medications=[{"category": "DPP-4阻害薬"}],
    )
    assert [item.key for item in result["supported"]] == ["statin"]
    assert result["has_statin"] is True
    assert result["has_other_glucose_drug"] is True


def test_sglt2_and_metformin_are_returned_once_per_class():
    result = selected_dementia_evidence(
        bp_medications=[],
        lipid_medications=[],
        diabetes_medications=[
            {"category": "SGLT2阻害薬"},
            {"category": "SGLT2阻害薬"},
            {"category": "ビグアナイド"},
        ],
    )
    assert [item.key for item in result["supported"]] == ["sglt2", "metformin"]
    assert result["has_other_glucose_drug"] is False


def test_dual_gip_glp1_is_not_extrapolated_from_glp1_trials():
    result = selected_dementia_evidence(
        bp_medications=[],
        lipid_medications=[],
        diabetes_medications=[{"category": "GIP/GLP-1受容体作動薬"}],
    )
    assert result["supported"] == []


def test_dementia_curve_uses_age_specific_incidence_and_intervention_effect():
    untreated = dementia_curve(age=65, years=10)
    treated = dementia_curve(age=65, years=10, hazard_ratio=0.87)
    assert untreated["risk"][0] == 0
    assert 0 < float(untreated["risk"][-1]) < 0.148
    assert untreated["risk"][-1] > treated["risk"][-1] > 0


def test_dementia_curve_does_not_extrapolate_source_below_age_60():
    curve = dementia_curve(age=55, years=5)
    assert curve["risk"][-1] == 0


def test_dementia_curve_can_be_extrapolated_beyond_ten_years():
    curve = dementia_curve(age=65, years=50)
    assert curve["time"][-1] == 50
    assert len(curve["risk"]) == 51


def test_competing_mortality_reduces_elderly_risk_and_differs_by_sex():
    male = dementia_curve(age=85, years=10, sex="male")["risk"][-1]
    female = dementia_curve(age=85, years=10, sex="female")["risk"][-1]
    assert 0 < male < female < 0.631


def test_japanese_real_world_calibration_is_partial_not_full_replacement():
    assert JAPAN_DEMENTIA_PARTIAL_CALIBRATION == {"male": 0.75, "female": 0.78}
    male = dementia_curve(age=65, years=10, sex="male")["risk"][-1]
    female = dementia_curve(age=65, years=10, sex="female")["risk"][-1]
    assert 0.09 < male < 0.12
    assert 0.10 < female < 0.13


def test_biomarker_lowering_applies_without_requiring_medication():
    effect = dementia_biomarker_hazard_ratio(
        sbp_before=150, sbp_after=140, ldl_before=160, ldl_after=100,
    )
    assert round(effect["bp"], 2) == 0.87
    assert round(effect["ldl"], 2) == 0.74
    assert round(effect["combined"], 4) == round(0.87 * 0.74, 4)
