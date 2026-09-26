from dementia_prevention import selected_dementia_evidence, trial_arm_curve


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


def test_trial_arm_curves_match_published_endpoint_risks():
    bp = trial_arm_curve("bp_lowering")
    assert round(bp["control"][-1], 1) == 7.5
    assert round(bp["intervention"][-1], 1) == 7.0

    glp1 = trial_arm_curve("glp1_ra")
    assert round(glp1["control"][-1], 3) == round(32 / 7913 * 100, 3)
    assert round(glp1["intervention"][-1], 3) == round(15 / 7907 * 100, 3)
