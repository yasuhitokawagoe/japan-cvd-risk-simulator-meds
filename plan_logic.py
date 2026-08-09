"""療養計画書UIで使う、PDFやStreamlitに依存しない判定・文面生成ロジック。"""
from __future__ import annotations

from typing import Iterable


# 達成目標欄は狭いため、短い見出し語にする（詳細は指導項目・手書きで補う）。
LIFESTYLE_GOALS = {
    "塩分が多い": ["減塩"],
    "野菜が少ない": ["食事の改善"],
    "間食・甘い飲料が多い": ["食事の改善"],
    "運動不足": ["運動"],
    "体重を減らしたい": ["減量"],
    "喫煙している": ["禁煙"],
    "飲酒量が多い": ["節酒"],
    "服薬を忘れる": ["服薬の継続"],
}

LIFESTYLE_INSTRUCTIONS = {
    "塩分が多い": ["食塩・調味料を控える"],
    "野菜が少ない": ["野菜・きのこ・海藻など食物繊維の摂取を増やす"],
    "間食・甘い飲料が多い": ["食事摂取量を適正にする", "間食を減らす"],
    "運動不足": ["運動処方", "日常生活の活動量を増やす"],
    "体重を減らしたい": ["減量する", "家庭で歩数・体重・血圧等を計測する"],
    "喫煙している": ["禁煙・節煙の有効性を説明する", "禁煙の実施方法を相談する"],
    "飲酒量が多い": ["節酒する"],
    "服薬を忘れる": ["家庭で歩数・体重・血圧等を計測する"],
}


def ideal_weight_kg(height_cm: float, target_bmi: float = 22.0) -> float:
    if height_cm <= 0:
        raise ValueError("height_cm must be positive")
    return round(target_bmi * (height_cm / 100.0) ** 2, 1)


def infer_diagnoses(
    *,
    sbp: float,
    dbp: float,
    ldl: float,
    a1c: float,
    has_bp_meds: bool = False,
    has_lipid_meds: bool = False,
    has_diabetes_meds: bool = False,
) -> dict[str, bool]:
    """検査値または対応薬から主病名の確認候補を返す（確定診断ではない）。"""
    return {
        "diabetes": a1c >= 6.5 or has_diabetes_meds,
        "hypertension": sbp >= 140 or dbp >= 90 or has_bp_meds,
        "dyslipidemia": ldl >= 140 or has_lipid_meds,
    }


def suggested_goals(lifestyle_items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in lifestyle_items:
        for goal in LIFESTYLE_GOALS.get(item, []):
            if goal not in result:
                result.append(goal)
    return result


def suggested_instructions(lifestyle_items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in lifestyle_items:
        for instruction in LIFESTYLE_INSTRUCTIONS.get(item, []):
            if instruction not in result:
                result.append(instruction)
    return result


def build_patient_handout(
    *,
    age: int,
    sex_label: str,
    height_cm: float,
    weight_kg: float,
    bp: str,
    ldl: float,
    a1c: float,
    medications: Iterable[str],
    goals: Iterable[str],
) -> str:
    meds = list(medications)
    selected_goals = list(goals)
    lines = [
        "生活習慣改善 いっしょに取り組む目標",
        "",
        f"年齢・性別: {age}歳・{sex_label}",
        f"身長・体重: {height_cm:.1f} cm・{weight_kg:.1f} kg",
        f"血圧: {bp} mmHg",
        f"LDLコレステロール: {ldl:.0f} mg/dL",
        f"HbA1c: {a1c:.1f} %",
        "",
        "服薬内容:",
        *([f"- {med}" for med in meds] or ["- なし／未入力"]),
        "",
        "相談して決めた目標:",
        *([f"□ {goal}" for goal in selected_goals] or ["□ 次回相談して決める"]),
        "",
        "無理のない範囲で取り組み、次回いっしょに振り返りましょう。",
    ]
    return "\n".join(lines)
