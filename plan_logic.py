"""療養計画書UIで使う、PDFやStreamlitに依存しない判定・文面生成ロジック。"""
from __future__ import annotations

import unicodedata
from typing import Iterable


# 目標の文言は【①達成目標】欄(テキスト111)にそのまま印字される。
# 欄は1行・全角21.4字しか入らず、溢れた分は縮小されずに切れて消える
# （PLAN_GOAL_FIELD_CAPACITY 参照）。2件を「／」で連結して収めるため、
# 1件あたり全角10字以内に保つこと。文言を足すときも同じ制約が要る。
LIFESTYLE_GOALS = {
    "塩分が多い": ["汁物は1日1杯まで", "食塩1日6g未満"],
    "野菜が少ない": ["毎食野菜を1皿追加"],
    "間食・甘い飲料が多い": ["間食は1日1回まで", "甘い飲料は水・お茶に"],
    "運動不足": ["週5日30分歩く", "1日1000歩増やす"],
    "体重を減らしたい": ["毎日体重を測り記録", "3か月で体重3%減"],
    "喫煙している": ["禁煙開始日を決める", "禁煙外来を相談する"],
    "飲酒量が多い": ["休肝日を週2日設ける", "飲酒量を記録する"],
    "服薬を忘れる": ["食事・歯磨き時に服薬", "薬箱・アラームを使う"],
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


# --- 【①達成目標】欄(テキスト111)の容量制約 ---------------------------------
# ひな型実測: 幅228.5pt・改行フラグなし(1行のみ)・フォント10.5pt固定。
# サイズ0(自動縮小)ではないため、溢れた文字は縮まずに切れて消える。
# 内側余白を4pt見込むと (228.5 - 4) / 10.5 = 21.4 全角字。
PLAN_GOAL_FIELD_CAPACITY = 21.4
# 1欄に連結して入れる目標の上限。各10字以内なら 10 + 1(／) + 10 = 21字 で収まる。
PLAN_GOAL_MAX_ITEMS = 2
PLAN_GOAL_SEPARATOR = "／"


def goal_text_width(text: str) -> float:
    """帳票上の表示幅を全角字数で返す。全角=1.0、半角=0.5。"""
    return sum(
        1.0 if unicodedata.east_asian_width(ch) in "WFA" else 0.5 for ch in text
    )


def build_plan_goal_text(goals: Iterable[str]) -> tuple[str, list[str]]:
    """
    達成目標欄に印字する文字列と、入りきらず落とした目標を返す。

    欄は1行・自動縮小なしのため、そのまま渡すと溢れた分がPDF上で黙って消える。
    ここで先に落とし、UI側が「落ちたこと」を提示できるようにする。
    """
    kept: list[str] = []
    dropped: list[str] = []
    for goal in goals:
        goal = (goal or "").strip()
        if not goal:
            continue
        if len(kept) >= PLAN_GOAL_MAX_ITEMS:
            dropped.append(goal)
            continue
        candidate = PLAN_GOAL_SEPARATOR.join([*kept, goal])
        if goal_text_width(candidate) > PLAN_GOAL_FIELD_CAPACITY:
            dropped.append(goal)
            continue
        kept.append(goal)
    return PLAN_GOAL_SEPARATOR.join(kept), dropped


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
