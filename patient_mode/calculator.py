from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from calc_engine_outcomes import OutcomesEngine
from lifestyle_interventions import apply_lifestyle_effects
from meds_catalog import apply_meds_to_targets


OUTCOMES = ("mortality", "mi", "stroke")


@dataclass(frozen=True)
class PatientInputs:
    sex: str
    age: int
    sbp: float
    ldl: float
    hba1c: float
    smoking_status: str
    cigs_per_day: int
    years_smoked: int
    years_since_quit: int
    bmi: float
    egfr: float = 80.0
    acr: str = "A1"
    diabetes_context: bool = False


@dataclass
class InterventionPlan:
    target_sbp: float | None = None
    target_ldl: float | None = None
    quit_smoking: bool = False
    diet_keys: list[str] = field(default_factory=list)
    exercise_key: str | None = None
    selected_sbp_meds: list[dict[str, Any]] = field(default_factory=list)
    selected_ldl_meds: list[dict[str, Any]] = field(default_factory=list)
    selected_a1c_meds: list[dict[str, Any]] = field(default_factory=list)


def intervention_targets(inputs: PatientInputs, plan: InterventionPlan) -> dict[str, Any]:
    """Use existing medication/lifestyle functions; do not reproduce their logic."""
    meds = apply_meds_to_targets(
        inputs.sbp,
        inputs.ldl,
        inputs.hba1c,
        plan.selected_sbp_meds,
        plan.selected_ldl_meds,
        plan.selected_a1c_meds,
    )
    sbp = meds["sbp_target"] if plan.selected_sbp_meds else inputs.sbp
    ldl = meds["ldl_target"] if plan.selected_ldl_meds else inputs.ldl
    a1c = meds["a1c_target"] if plan.selected_a1c_meds else inputs.hba1c
    if plan.target_sbp is not None:
        sbp = float(plan.target_sbp)
    if plan.target_ldl is not None:
        ldl = float(plan.target_ldl)
    lifestyle = apply_lifestyle_effects(
        sbp=sbp,
        ldl=ldl,
        a1c=a1c,
        diet_keys=plan.diet_keys,
        exercise_key=plan.exercise_key,
        diabetes_context=inputs.diabetes_context,
    )
    return {
        "sbp": lifestyle["sbp"],
        "ldl": lifestyle["ldl"],
        "hba1c": lifestyle["a1c"],
        "annual_cost_yen": meds["annual_cost_yen"],
        "side_effects_md": meds["side_effects_md"],
        "lifestyle_applied": lifestyle["applied"],
        "lifestyle_skipped": lifestyle["skipped"],
    }


def calculate_snapshot(
    engine: OutcomesEngine,
    inputs: PatientInputs,
    plan: InterventionPlan | None,
    horizons: tuple[int, ...] = (10, 20, 30),
) -> dict[str, Any]:
    targets = intervention_targets(inputs, plan or InterventionPlan())
    quit_today = bool(plan and plan.quit_smoking and inputs.smoking_status == "current")
    results: dict[str, Any] = {"targets": targets, "outcomes": {}}
    for outcome in OUTCOMES:
        results["outcomes"][outcome] = {}
        for years in horizons:
            results["outcomes"][outcome][years] = engine.cumulative_incidence_with_ci(
                outcome,
                inputs.sex,
                inputs.age,
                years,
                inputs.sbp,
                targets["sbp"],
                inputs.ldl,
                targets["ldl"],
                inputs.hba1c,
                targets["hba1c"],
                inputs.smoking_status,
                inputs.cigs_per_day,
                inputs.years_smoked,
                inputs.years_since_quit,
                quit_today,
                bmi_now=inputs.bmi,
                bmi_target=inputs.bmi,
                egfr_now=inputs.egfr,
                egfr_target=inputs.egfr,
                acr_now=inputs.acr,
                acr_target=inputs.acr,
            )
    return results
