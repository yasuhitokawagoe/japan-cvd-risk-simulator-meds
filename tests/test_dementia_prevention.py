from dementia_prevention import dementia_curve, selected_dementia_evidence


def test_bp_and_glp1_are_returned_as_supported_evidence():
    result = selected_dementia_evidence(
        bp_medications=[{"category": "ARB"}],
        lipid_medications=[],
        diabetes_medications=[{"category": "GLP-1受容体作動薬（皮下）"}],
    )
    assert [item.key for item in result["supported"]] == ["bp_lowering", "glp1_ra"]


def test_statin_and_hba1c_lowering_are_not_counted_as_preventive_effects():
    result = selected_dementia_evidence(
        bp_medications=[],
        lipid_medications=[{"category": "スタチン"}],
        diabetes_medications=[{"category": "DPP-4阻害薬"}],
    )
    assert result["supported"] == []
    assert result["has_statin"] is True
    assert result["has_other_glucose_drug"] is True


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
    assert untreated["risk"][-1] > treated["risk"][-1] > 0


def test_dementia_curve_does_not_extrapolate_source_below_age_60():
    curve = dementia_curve(age=55, years=5)
    assert curve["risk"][-1] == 0


def test_dementia_curve_can_be_extrapolated_beyond_ten_years():
    curve = dementia_curve(age=65, years=50)
    assert curve["time"][-1] == 50
    assert len(curve["risk"]) == 51
