import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plan_logic import (
    build_patient_handout, ideal_weight_kg, infer_diagnoses,
    suggested_goals, suggested_instructions,
)


def test_ideal_weight():
    assert ideal_weight_kg(165) == 59.9


def test_diagnosis_candidates_from_values():
    result = infer_diagnoses(sbp=140, dbp=80, ldl=140, a1c=6.5)
    assert result == {"diabetes": True, "hypertension": True, "dyslipidemia": True}


def test_diagnosis_candidates_from_medications():
    result = infer_diagnoses(
        sbp=120, dbp=70, ldl=100, a1c=5.5,
        has_bp_meds=True, has_lipid_meds=True, has_diabetes_meds=True,
    )
    assert all(result.values())


def test_goals_and_handout_share_selected_text():
    goals = suggested_goals(["運動不足"])
    handout = build_patient_handout(
        age=60, sex_label="男性", height_cm=165, weight_kg=65,
        bp="140/90", ldl=140, a1c=6.5, medications=["薬A"], goals=goals,
    )
    assert goals
    assert all(goal in handout for goal in goals)
    assert "薬A" in handout
    assert "運動処方" in suggested_instructions(["運動不足"])


if __name__ == "__main__":
    test_ideal_weight()
    test_diagnosis_candidates_from_values()
    test_diagnosis_candidates_from_medications()
    test_goals_and_handout_share_selected_text()
    print("OK: plan_logic tests passed")
