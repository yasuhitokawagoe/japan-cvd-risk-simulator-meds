from dementia_prevention import selected_dementia_evidence


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
