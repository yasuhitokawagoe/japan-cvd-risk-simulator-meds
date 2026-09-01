import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plan_logic import (
    LIFESTYLE_GOALS, PLAN_GOAL_FIELD_CAPACITY, PLAN_GOAL_MAX_ITEMS,
    build_patient_handout, build_plan_goal_text, goal_text_width,
    ideal_weight_kg, infer_diagnoses, suggested_goals, suggested_instructions,
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


def _all_goal_texts():
    """帳票の達成目標欄に印字されうる目標文言をすべて集める。"""
    from pdf_plan_ui import _INTERVENTION_PLAN_ITEMS, _TREATMENT_BENEFIT_PLAN_GOAL

    texts = [g for goals in LIFESTYLE_GOALS.values() for g in goals]
    texts += [g for _, goals in _INTERVENTION_PLAN_ITEMS.values() for g in goals]
    texts.append(_TREATMENT_BENEFIT_PLAN_GOAL)
    return texts


def test_goal_text_width_counts_halfwidth_as_half():
    assert goal_text_width("あいう") == 3.0
    assert goal_text_width("1日1000歩増やす") == 7.5


def test_every_goal_fits_when_two_are_joined():
    """
    達成目標欄は1行・全角21.4字で、溢れた分は縮小されず消える。
    2件を「／」で連結して収めるため、各目標は10字以内でなければならない。
    """
    too_long = [t for t in _all_goal_texts() if goal_text_width(t) > 10.0]
    assert not too_long, f"10字を超える目標文言: {too_long}"


def test_any_two_goals_fit_in_the_field():
    texts = _all_goal_texts()
    for a in texts:
        for b in texts:
            text, dropped = build_plan_goal_text([a, b])
            assert not dropped, f"2件が収まらない: {a} / {b}"
            assert goal_text_width(text) <= PLAN_GOAL_FIELD_CAPACITY


def test_third_goal_is_dropped_not_silently_truncated():
    goals = ["週5日30分歩く", "1日1000歩増やす", "飲酒量を記録する"]
    text, dropped = build_plan_goal_text(goals)
    assert text == "週5日30分歩く／1日1000歩増やす"
    assert dropped == ["飲酒量を記録する"]
    assert len(goals) - len(dropped) == PLAN_GOAL_MAX_ITEMS


def test_overlong_freetext_is_dropped_and_reported():
    text, dropped = build_plan_goal_text(
        ["週5日30分歩く", "毎日決まった時間に体重と血圧を測って記録する"]
    )
    assert text == "週5日30分歩く"
    assert dropped == ["毎日決まった時間に体重と血圧を測って記録する"]


def test_blank_goals_are_ignored():
    assert build_plan_goal_text(["", "  ", "飲酒量を記録する"]) == ("飲酒量を記録する", [])


if __name__ == "__main__":
    test_ideal_weight()
    test_diagnosis_candidates_from_values()
    test_diagnosis_candidates_from_medications()
    test_goals_and_handout_share_selected_text()
    test_goal_text_width_counts_halfwidth_as_half()
    test_every_goal_fits_when_two_are_joined()
    test_any_two_goals_fit_in_the_field()
    test_third_goal_is_dropped_not_silently_truncated()
    test_overlong_freetext_is_dropped_and_reported()
    test_blank_goals_are_ignored()
    print("OK: plan_logic tests passed")
