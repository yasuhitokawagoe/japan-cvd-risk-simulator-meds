from bone_health import bone_density_category, bone_health_flags, hip_fracture_risk


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


def test_hip_fracture_risk_increases_for_women_and_prior_fracture():
    male = hip_fracture_risk(age=75, sex="male")
    female = hip_fracture_risk(age=75, sex="female")
    previous = hip_fracture_risk(
        age=75, sex="female", prior_fragility_fracture=True,
    )
    assert 0 < male < female < previous < 1


def test_bone_density_category():
    assert bone_density_category(None) == "未測定"
    assert bone_density_category(-2.5) == "骨粗鬆症域"
    assert bone_density_category(-1.5) == "骨量減少域"
    assert bone_density_category(-0.5) == "正常域"
