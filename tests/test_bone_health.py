from bone_health import bone_health_flags


def test_bone_health_flags_age_low_bmi_kidney_and_insulin():
    flags = bone_health_flags(
        age=72, sex="female", bmi=17.9, egfr=38,
        diabetes_medications=[{"key": "基礎インスリン", "category": "インスリン"}],
    )
    assert len(flags) == 4


def test_bone_health_flags_do_not_claim_risk_for_low_flag_profile():
    flags = bone_health_flags(
        age=55, sex="male", bmi=24.0, egfr=75,
        diabetes_medications=[],
    )
    assert flags == []
