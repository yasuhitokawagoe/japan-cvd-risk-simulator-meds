import math

from calc_engine_outcomes import OutcomesEngine
from patient_mode.calculator import PatientInputs, InterventionPlan, calculate_snapshot


def _inputs():
    return PatientInputs(
        sex="male", age=60, sbp=150, ldl=160, hba1c=8.0,
        smoking_status="current", cigs_per_day=20, years_smoked=20,
        years_since_quit=0, bmi=24.2, egfr=80, acr="A1",
        diabetes_context=True,
    )


def test_patient_baseline_is_exactly_existing_engine_result():
    engine = OutcomesEngine("config.yaml")
    inputs = _inputs()
    patient = calculate_snapshot(engine, inputs, InterventionPlan(), horizons=(10,))
    direct = engine.cumulative_incidence_with_ci(
        "mi", inputs.sex, inputs.age, 10,
        inputs.sbp, inputs.sbp, inputs.ldl, inputs.ldl,
        inputs.hba1c, inputs.hba1c, inputs.smoking_status,
        inputs.cigs_per_day, inputs.years_smoked, inputs.years_since_quit,
        False, bmi_now=inputs.bmi, bmi_target=inputs.bmi,
        egfr_now=inputs.egfr, egfr_target=inputs.egfr,
        acr_now=inputs.acr, acr_target=inputs.acr,
    )
    assert patient["outcomes"]["mi"][10] == direct


def test_patient_intervention_uses_same_engine_target_result():
    engine = OutcomesEngine("config.yaml")
    inputs = _inputs()
    plan = InterventionPlan(target_sbp=130, target_ldl=100, quit_smoking=True)
    patient = calculate_snapshot(engine, inputs, plan, horizons=(10,))
    direct = engine.cumulative_incidence_with_ci(
        "stroke", inputs.sex, inputs.age, 10,
        150, 130, 160, 100, 8.0, 8.0, "current", 20, 20, 0, True,
        bmi_now=inputs.bmi, bmi_target=inputs.bmi,
        egfr_now=80, egfr_target=80, acr_now="A1", acr_target="A1",
    )
    assert patient["outcomes"]["stroke"][10] == direct
