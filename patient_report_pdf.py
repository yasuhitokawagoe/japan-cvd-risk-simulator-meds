"""患者さん向けのリスク・療養目標レポートPDFを生成する。"""
from __future__ import annotations

import io
import os
from datetime import date
from typing import Iterable, Mapping

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT = "NotoSansJP"
_FONT_CANDIDATES = (
    os.environ.get("PATIENT_REPORT_JP_FONT", ""),
    "/usr/share/fonts/truetype/noto/NotoSansJP.ttf",
)
for _font_path in _FONT_CANDIDATES:
    if _font_path and os.path.exists(_font_path):
        pdfmetrics.registerFont(TTFont(FONT, _font_path, subfontIndex=0))
        break
else:
    # ローカル開発環境向けの後方互換。RailwayではNoto Sans CJKを必ず使用する。
    FONT = "HeiseiKakuGo-W5"
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))

NAVY = HexColor("#14324A")
BLUE = HexColor("#2878B5")
PALE_BLUE = HexColor("#EAF4FB")
TEAL = HexColor("#168C83")
PALE_TEAL = HexColor("#E8F6F3")
RED = HexColor("#D85A5A")
PALE_RED = HexColor("#FCEEEE")
GRAY = HexColor("#5F6B73")
LIGHT = HexColor("#EEF1F3")
TEXT = HexColor("#18242C")

OUTCOME_LABELS = {"mortality": "全死亡", "mi": "心筋梗塞", "stroke": "脳卒中"}
OUTCOME_LABELS_EN = {
    "mortality": "All-cause mortality",
    "mi": "Myocardial infarction",
    "stroke": "Stroke",
}


def _text(c: canvas.Canvas, x: float, y: float, value: str, size: float = 10,
          color=TEXT, align: str = "left") -> None:
    c.setFont(FONT, size)
    c.setFillColor(color)
    if align == "center":
        c.drawCentredString(x, y, value)
    elif align == "right":
        c.drawRightString(x, y, value)
    else:
        c.drawString(x, y, value)


def _wrap(value: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for raw in value.splitlines() or [""]:
        while len(raw) > max_chars:
            lines.append(raw[:max_chars])
            raw = raw[max_chars:]
        lines.append(raw)
    return lines


def _section_title(c: canvas.Canvas, y: float, title: str) -> float:
    c.setFillColor(NAVY)
    c.roundRect(30, y - 5, 535, 25, 5, fill=1, stroke=0)
    _text(c, 42, y + 2, title, 12, white)
    return y - 18


def _metric_card(c: canvas.Canvas, x: float, y: float, w: float, title: str,
                 current: float, target: float, unit: str) -> None:
    c.setFillColor(PALE_BLUE)
    c.roundRect(x, y, w, 58, 7, fill=1, stroke=0)
    _text(c, x + 10, y + 41, title, 8.5, GRAY)
    _text(c, x + 10, y + 20, f"{current:g} → {target:g} {unit}", 13, NAVY)


def _risk_values(curve: Mapping[str, Iterable[float]]) -> tuple[float, float, float]:
    baseline = list(curve["baseline_cumulative"])
    target = list(curve["target_cumulative"])
    current_value = float(baseline[-1])
    target_value = float(target[-1])
    return current_value, target_value, max(0.0, current_value - target_value)


def _bar_chart(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    risks: Mapping[str, Mapping[str, Iterable[float]]],
    *,
    labels: Mapping[str, str] | None = None,
    title: str = "計画実行前後の累積リスク",
    current_fmt: str = "現在 {v:.1f}%",
    after_fmt: str = "実行後 {v:.1f}%",
) -> None:
    labels = labels or OUTCOME_LABELS
    values = {key: _risk_values(risks[key]) for key in labels}
    max_value = max([v for pair in values.values() for v in pair[:2]] + [1.0]) * 1.15
    c.setFillColor(white)
    c.roundRect(x, y, w, h, 7, fill=1, stroke=0)
    _text(c, x + 12, y + h - 19, title, 10, NAVY)
    row_h = 48
    for index, key in enumerate(labels):
        cy = y + h - 46 - index * row_h
        _text(c, x + 12, cy + 12, labels[key], 8.5)
        bx = x + 84
        available = w - 104
        current, target, _ = values[key]
        c.setFillColor(PALE_RED)
        c.roundRect(bx, cy + 12, available, 10, 3, fill=1, stroke=0)
        c.setFillColor(RED)
        c.roundRect(bx, cy + 12, available * current / max_value, 10, 3, fill=1, stroke=0)
        c.setFillColor(PALE_TEAL)
        c.roundRect(bx, cy - 3, available, 10, 3, fill=1, stroke=0)
        c.setFillColor(TEAL)
        c.roundRect(bx, cy - 3, available * target / max_value, 10, 3, fill=1, stroke=0)
        _text(c, x + w - 9, cy + 13, current_fmt.format(v=current), 7.5, RED, "right")
        _text(c, x + w - 9, cy - 2, after_fmt.format(v=target), 7.5, TEAL, "right")


def _line_chart(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    curve: Mapping[str, Iterable[float]],
    *,
    yr0: str = "0年",
    yr_n_fmt: str = "{n:.0f}年",
) -> None:
    times = [float(v) for v in curve["time"]]
    baseline = [float(v) for v in curve["baseline_cumulative"]]
    target = [float(v) for v in curve["target_cumulative"]]
    max_y = max(baseline + target + [1.0]) * 1.15
    left, bottom, right, top = x + 34, y + 25, x + w - 12, y + h - 25
    c.setFillColor(white)
    c.roundRect(x, y, w, h, 7, fill=1, stroke=0)
    _text(c, x + 10, y + h - 17, title, 9, NAVY)
    c.setStrokeColor(LIGHT)
    for i in range(4):
        gy = bottom + (top - bottom) * i / 3
        c.line(left, gy, right, gy)
        _text(c, left - 4, gy - 2, f"{max_y*i/3:.0f}%", 6.5, GRAY, "right")
    if len(times) < 2 or max(times) <= 0:
        return

    def point(t: float, v: float) -> tuple[float, float]:
        return left + (right - left) * t / max(times), bottom + (top - bottom) * v / max_y

    for values, color in ((baseline, RED), (target, TEAL)):
        c.setStrokeColor(color)
        c.setLineWidth(2)
        pts = [point(t, v) for t, v in zip(times, values)]
        for a, b in zip(pts, pts[1:]):
            c.line(a[0], a[1], b[0], b[1])
    _text(c, left, y + 8, yr0, 6.5, GRAY)
    _text(c, right, y + 8, yr_n_fmt.format(n=max(times)), 6.5, GRAY, "right")


def _backcast_line_chart(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    curve: Mapping[str, Iterable[float]],
    *,
    now_label: str = "現在",
    year_suffix: str = "年",
) -> None:
    times = [float(v) for v in curve["time"]]
    untreated = [float(v) for v in curve["untreated"]]
    treated = [float(v) for v in curve["treated"]]
    min_t, max_t = min(times), max(times)
    max_y = max(untreated + treated + [1.0]) * 1.15
    left, bottom, right, top = x + 42, y + 28, x + w - 14, y + h - 28
    c.setFillColor(white)
    c.roundRect(x, y, w, h, 7, fill=1, stroke=0)
    _text(c, x + 12, y + h - 18, title, 10, NAVY)
    for i in range(4):
        gy = bottom + (top - bottom) * i / 3
        c.setStrokeColor(LIGHT)
        c.line(left, gy, right, gy)
        _text(c, left - 5, gy - 2, f"{max_y*i/3:.0f}%", 6.5, GRAY, "right")
    span = max(max_t - min_t, 1.0)

    def point(t: float, v: float) -> tuple[float, float]:
        return left + (right - left) * (t - min_t) / span, bottom + (top - bottom) * v / max_y

    for values, color, dashed in ((untreated, RED, True), (treated, TEAL, False)):
        c.setStrokeColor(color)
        c.setLineWidth(2)
        if dashed:
            c.setDash(5, 3)
        else:
            c.setDash()
        pts = [point(t, v) for t, v in zip(times, values)]
        for a, b in zip(pts, pts[1:]):
            c.line(a[0], a[1], b[0], b[1])
    c.setDash()
    now_x, _ = point(0, 0)
    c.setStrokeColor(GRAY)
    c.setDash(2, 2)
    c.line(now_x, bottom, now_x, top)
    c.setDash()
    _text(c, left, y + 10, f"{min_t:.0f}{year_suffix}", 6.5, GRAY)
    _text(c, now_x, y + 10, now_label, 6.5, NAVY, "center")
    _text(c, right, y + 10, f"+{max_t:.0f}{year_suffix}", 6.5, GRAY, "right")


def generate_patient_report_pdf(
    *,
    age: int,
    sex_label: str,
    height_cm: float,
    weight_kg: float,
    current_values: Mapping[str, float],
    target_values: Mapping[str, float],
    diagnoses: Iterable[str],
    medications: Iterable[str],
    instructions: Iterable[str],
    goals: Iterable[str],
    risks: Mapping[str, Mapping[str, Iterable[float]]],
    horizon_years: int,
    lifestyle_interventions: Iterable[str] = (),
    treatment_benefit: Mapping | None = None,
    lang: str = "ja",
) -> bytes:
    """Return an A4 2-page patient education PDF."""
    en = lang == "en"
    outcome_labels = OUTCOME_LABELS_EN if en else OUTCOME_LABELS
    joiner = ", " if en else "、"
    t = {
        "title_benefit": "Benefit from continuing medicines" if en else "お薬を続けて得られている成果",
        "subtitle_benefit": (
            "Estimated comparison versus not taking medicines over the past {years} years"
            if en else "現在までの{years}年間を、薬を飲まなかった場合と比べた推定"
        ),
        "sec_status": "1. Current status and medicines" if en else "1. 現在の状態と服薬",
        "profile": (
            f"{age} y · {sex_label} · Ht {height_cm:.1f} cm · Wt {weight_kg:.1f} kg"
            if en else f"{age}歳・{sex_label}　身長 {height_cm:.1f} cm　体重 {weight_kg:.1f} kg"
        ),
        "meds_prefix": "Current medicines: " if en else "現在服用中: ",
        "meds_none": "None / not entered" if en else "なし／未入力",
        "life_prefix": "Diet / exercise: " if en else "食事・運動: ",
        "life_none": "None selected" if en else "選択なし",
        "sec_compare": "2. Estimated comparison if medicines had not been taken" if en else "2. 薬を飲まなかった場合との推定比較",
        "card_sbp": "Systolic BP (no meds → current)" if en else "収縮期血圧（薬なし推定→現在）",
        "card_ldl": "LDL (no meds → current)" if en else "LDL（薬なし推定→現在）",
        "card_a1c": "HbA1c (no meds → current)" if en else "HbA1c（薬なし推定→現在）",
        "sec_events": (
            "3. Events that may have been avoided over these {years} years"
            if en else "3. この{years}年間に回避できた可能性があるイベント"
        ),
        "points": "percentage points avoided" if en else "ポイント回避",
        "no_drug": "Without medication" if en else "薬なし",
        "on_drug": "On medication" if en else "服薬",
        "sec_interpret": "4. How to interpret these results" if en else "4. この結果の受け止め方",
        "msg1": (
            "Current labs and avoided events include benefit from continuing medicines."
            if en else "現在の検査値とイベント回避効果には、服薬を続けてきた成果が含まれています。"
        ),
        "msg2": (
            "No-medicine values are estimates from average effects. Do not stop on your own."
            if en else "薬なしの数値は平均効果からの推定です。自己判断で中止しないことが大切です。"
        ),
        "msg3": (
            "If adverse effects or burden are a concern, discuss adjustments with the clinician."
            if en else "副作用や負担が気になる場合は、主治医と相談して調整しましょう。"
        ),
        "sec_plan": "5. Next steps" if en else "5. 今後の方針",
        "default_status": "Continue current treatment" if en else "現在の治療を継続する",
        "uncertainty": (
            "Estimates are uncertain. Discuss treatment changes with the clinician."
            if en else "推定値には不確実性があります。治療変更は主治医と相談してください。"
        ),
        "footer_benefit": (
            "For patient education and shared decision-making (not a medical device)"
            if en else "患者教育・共有意思決定用（医療機器ではありません）"
        ),
        "p2_title": "Benefit so far and outlook ahead" if en else "これまでの利益と、これからの見通し",
        "p2_sub": (
            "Red dashed: no meds · Green solid: continue meds · Vertical dotted: now"
            if en else "赤点線: 薬なし推定　緑実線: 服薬継続　縦点線: 現在"
        ),
        "p2_foot": (
            "Past and future both use average medication effects."
            if en else "過去と将来はいずれも薬剤の平均効果を用いた推定です。"
        ),
        "title": "Your health action plan" if en else "あなたの健康づくりプラン",
        "subtitle": (
            f"Current status and a {horizon_years}-year outlook if the plan is followed"
            if en else f"現在の状態と、計画を実行した場合の{horizon_years}年間の見通し"
        ),
        "s1": "1. Current status" if en else "1. 現在の状態",
        "profile_bmi": (
            f"{age} y · {sex_label} · Ht {height_cm:.1f} cm · Wt {weight_kg:.1f} kg (BMI {weight_kg/(height_cm/100)**2:.1f})"
            if en else f"{age}歳・{sex_label}　身長 {height_cm:.1f} cm　体重 {weight_kg:.1f} kg（BMI {weight_kg/(height_cm/100)**2:.1f}）"
        ),
        "dx_prefix": "Possible conditions / management targets: " if en else "現在考えられる病気・管理対象: ",
        "dx_none": "None / under review" if en else "該当なし／確認中",
        "entered_meds": "Entered medicines: " if en else "入力された服薬: ",
        "selected_life": "Selected diet / exercise: " if en else "選択した食事・運動: ",
        "s2": "2. Changes the plan aims for" if en else "2. 介入で目指す変化",
        "bp": "Blood pressure" if en else "血圧",
        "ldl": "LDL cholesterol" if en else "LDLコレステロール",
        "s3": (
            f"3. Benefit if the plan continues ({horizon_years} years)"
            if en else f"3. 計画を続けた場合のメリット（{horizon_years}年）"
        ),
        "arr": "Absolute risk reduction {arr:.1f} percentage points" if en else "絶対リスク減少 {arr:.1f}ポイント",
        "bar_title": "Cumulative risk before vs after the plan" if en else "計画実行前後の累積リスク",
        "legend": (
            "Red: if current status continues · Green: if targets are achieved"
            if en else "赤: 現在の状態が続いた場合　緑: 目標を実行した場合"
        ),
        "foot": (
            "Estimates are uncertain. Decide treatment with the clinician."
            if en else "推定値には不確実性があります。治療内容は主治医と相談して決めてください。"
        ),
        "p2_main": "Risk change and goals to work on together" if en else "リスクの変化と、いっしょに取り組む目標",
        "instr": "Selected counseling items" if en else "選んだ指導項目",
        "instr_default": "□ Decide together at the next visit" if en else "□ 次回、相談して決める",
        "goals": "Action goals agreed with the patient" if en else "患者さんと相談して決めた行動目標",
        "goals_default": "Decide together at the next visit" if en else "次回、相談して決める",
        "benefit_title": "Estimated benefit from continuing medicines" if en else "これまで薬を続けて積み上げた推定成果",
        "benefit1": (
            "Over {years} years, about {avoided:.1f} MI/stroke events per 100 people may have been avoided."
            if en else "{years}年間で、心筋梗塞・脳卒中を100人あたり約{avoided:.1f}件回避した可能性があります。"
        ),
        "benefit2": (
            "All-cause mortality difference ≈ {mortality:.1f} per 100. Continue current treatment."
            if en else "全死亡の推定差は100人あたり約{mortality:.1f}件。現在の治療を継続しましょう。"
        ),
        "benefit3": (
            "Estimates only. Do not stop medicines on your own; discuss changes with the clinician."
            if en else "推定値です。薬を自己判断で中止せず、変更は主治医と相談してください。"
        ),
        "review_title": "Next review" if en else "次回の振り返り",
        "review1": (
            "Confirm what went well, and ease goals that were hard to keep."
            if en else "できたことを確認し、難しかった目標は無理のない内容へ調整しましょう。"
        ),
        "review2": (
            "If symptoms or adverse effects appear, do not stop on your own—contact the care team."
            if en else "体調の変化や薬の副作用が気になる場合は、自己判断で中止せず医療者へ相談してください。"
        ),
        "footer": (
            "Educational estimate for shared decision-making (not a medical device)"
            if en else "教育・共有意思決定用の推定資料（医療機器ではありません）"
        ),
        "current_pct": "Current {v:.1f}%" if en else "現在 {v:.1f}%",
        "after_pct": "After plan {v:.1f}%" if en else "実行後 {v:.1f}%",
        "yr0": "0 y" if en else "0年",
        "yr_n": "{n:.0f} y" if en else "{n:.0f}年",
        "now": "Now" if en else "現在",
        "plus_y": "+{n:.0f} y" if en else "+{n:.0f}年",
    }

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    lifestyle_interventions = tuple(lifestyle_interventions)
    if treatment_benefit:
        years = int(treatment_benefit.get("treatment_years", 0))
        c.setFillColor(NAVY)
        c.rect(0, page_h - 92, page_w, 92, fill=1, stroke=0)
        _text(c, 30, page_h - 43, t["title_benefit"], 20, white)
        _text(c, 30, page_h - 68, t["subtitle_benefit"].format(years=years), 10, white)
        _text(c, page_w - 30, page_h - 68, date.today().strftime("%Y.%m.%d"), 8, white, "right")

        y = page_h - 120
        y = _section_title(c, y, t["sec_status"])
        _text(c, 42, y, t["profile"], 10)
        _text(
            c, 42, y - 22,
            t["meds_prefix"] + (joiner.join(medications) if list(medications) else t["meds_none"]),
            9, GRAY,
        )
        _text(
            c, 42, y - 38,
            t["life_prefix"] + (joiner.join(lifestyle_interventions) if lifestyle_interventions else t["life_none"]),
            9, GRAY,
        )

        y -= 66
        y = _section_title(c, y, t["sec_compare"])
        card_y = y - 62
        _metric_card(c, 30, card_y, 170, t["card_sbp"], float(treatment_benefit["untreated_sbp"]), float(treatment_benefit["current_sbp"]), "mmHg")
        _metric_card(c, 212, card_y, 170, t["card_ldl"], float(treatment_benefit["untreated_ldl"]), float(treatment_benefit["current_ldl"]), "mg/dL")
        _metric_card(c, 394, card_y, 171, t["card_a1c"], float(treatment_benefit["untreated_a1c"]), float(treatment_benefit["current_a1c"]), "%")

        y = card_y - 42
        y = _section_title(c, y, t["sec_events"].format(years=years))
        event_card_y = y - 68
        event_effects = treatment_benefit.get("event_effects", {})
        for index, key in enumerate(("mortality", "mi", "stroke")):
            effect = event_effects.get(key, {})
            x = 30 + index * 182
            avoided = float(effect.get("avoided", 0.0))
            untreated = float(effect.get("untreated", 0.0))
            treated = float(effect.get("treated", 0.0))
            c.setFillColor(PALE_TEAL if avoided > 0 else LIGHT)
            c.roundRect(x, event_card_y, 170, 62, 7, fill=1, stroke=0)
            _text(c, x + 10, event_card_y + 44, outcome_labels[key], 9, NAVY)
            _text(c, x + 10, event_card_y + 25, f"{avoided:.1f} {t['points']}", 12, TEAL)
            _text(c, x + 10, event_card_y + 9, f"{t['no_drug']} {untreated:.1f}% → {t['on_drug']} {treated:.1f}%", 7.5, GRAY)

        y = event_card_y - 38
        y = _section_title(c, y, t["sec_interpret"])
        c.setFillColor(PALE_TEAL)
        c.roundRect(30, y - 92, 535, 82, 7, fill=1, stroke=0)
        _text(c, 44, y - 32, t["msg1"], 9.5, NAVY)
        _text(c, 44, y - 54, t["msg2"], 8.5)
        _text(c, 44, y - 75, t["msg3"], 8.5)

        y -= 128
        y = _section_title(c, y, t["sec_plan"])
        status = str(treatment_benefit.get("plan_status", t["default_status"]))
        for index, line in enumerate(_wrap(status, 45)):
            _text(c, 44, y - index * 18, "□ " + line if index == 0 else line, 11, NAVY)
        _text(c, 30, 42, t["uncertainty"], 8, GRAY)
        _text(c, page_w - 30, 27, t["footer_benefit"], 7.5, GRAY, "right")

        event_curves = treatment_benefit.get("event_curves", {})
        if event_curves:
            c.showPage()
            c.setFillColor(NAVY)
            c.rect(0, page_h - 72, page_w, 72, fill=1, stroke=0)
            _text(c, 30, page_h - 40, t["p2_title"], 18, white)
            _text(c, 30, page_h - 58, t["p2_sub"], 8.5, white)
            for index, key in enumerate(("mortality", "mi", "stroke")):
                _backcast_line_chart(
                    c, 30, page_h - 285 - index * 235, 535, 205,
                    outcome_labels[key], event_curves[key], now_label=t["now"], year_suffix=(" y" if en else "年"),
                )
            _text(c, 30, 27, t["p2_foot"], 7.5, GRAY)
        c.save()
        return buf.getvalue()

    c.setFillColor(NAVY)
    c.rect(0, page_h - 92, page_w, 92, fill=1, stroke=0)
    _text(c, 30, page_h - 43, t["title"], 20, white)
    _text(c, 30, page_h - 68, t["subtitle"], 10, white)
    _text(c, page_w - 30, page_h - 68, date.today().strftime("%Y.%m.%d"), 8, white, "right")

    y = page_h - 120
    y = _section_title(c, y, t["s1"])
    _text(c, 42, y, t["profile_bmi"], 10)
    _text(c, 42, y - 18, t["dx_prefix"] + (joiner.join(diagnoses) if list(diagnoses) else t["dx_none"]), 10)
    _text(c, 42, y - 36, t["entered_meds"] + (joiner.join(medications) if list(medications) else t["meds_none"]), 9, GRAY)
    _text(c, 42, y - 52, t["selected_life"] + (joiner.join(lifestyle_interventions) if lifestyle_interventions else t["life_none"]), 9, GRAY)

    y -= 72
    y = _section_title(c, y, t["s2"])
    card_y = y - 58
    _metric_card(c, 30, card_y, 170, t["bp"], current_values["sbp"], target_values["sbp"], "mmHg")
    _metric_card(c, 212, card_y, 170, t["ldl"], current_values["ldl"], target_values["ldl"], "mg/dL")
    _metric_card(c, 394, card_y, 171, "HbA1c", current_values["a1c"], target_values["a1c"], "%")

    y = card_y - 35
    y = _section_title(c, y, t["s3"])
    benefits_y = y - 72
    for index, key in enumerate(outcome_labels):
        current, target, arr = _risk_values(risks[key])
        x = 30 + index * 182
        c.setFillColor(PALE_TEAL if arr > 0 else LIGHT)
        c.roundRect(x, benefits_y, 170, 70, 7, fill=1, stroke=0)
        _text(c, x + 10, benefits_y + 51, outcome_labels[key], 9, NAVY)
        _text(c, x + 10, benefits_y + 29, f"{current:.1f}% → {target:.1f}%", 14, TEAL if arr > 0 else GRAY)
        _text(c, x + 10, benefits_y + 10, t["arr"].format(arr=arr), 8, GRAY)

    _bar_chart(c, 30, 112, 535, 265, risks, labels=outcome_labels, title=t["bar_title"],
               current_fmt=t["current_pct"], after_fmt=t["after_pct"])
    _text(c, 30, 42, t["legend"], 8, GRAY)
    _text(c, 30, 27, t["foot"], 7.5, GRAY)
    c.showPage()

    c.setFillColor(NAVY)
    c.rect(0, page_h - 65, page_w, 65, fill=1, stroke=0)
    _text(c, 30, page_h - 40, t["p2_main"], 17, white)
    chart_y = page_h - 250
    chart_w = 170
    for index, key in enumerate(outcome_labels):
        _line_chart(
            c, 30 + index * 182, chart_y, chart_w, 160, outcome_labels[key], risks[key],
            yr0=t["yr0"], yr_n_fmt=t["yr_n"],
        )
    _text(c, 30, chart_y - 16, t["legend"], 8, GRAY)

    y = chart_y - 50
    y = _section_title(c, y, t["instr"])
    instruction_lines = [f"□ {item}" for item in instructions] or [t["instr_default"]]
    col_x = [42, 305]
    for idx, item in enumerate(instruction_lines[:8]):
        _text(c, col_x[idx % 2], y - (idx // 2) * 18, item, 9)

    y -= 98
    y = _section_title(c, y, t["goals"])
    goal_y = y
    for goal in list(goals)[:6] or [t["goals_default"]]:
        for line_index, line in enumerate(_wrap(f"□ {goal}", 42)):
            _text(c, 42, goal_y, line, 10, NAVY if line_index == 0 else TEXT)
            goal_y -= 15
        goal_y -= 4

    c.setFillColor(PALE_BLUE)
    c.roundRect(30, 58, 535, 85 if treatment_benefit else 65, 7, fill=1, stroke=0)
    if treatment_benefit:
        years = int(treatment_benefit.get("treatment_years", 0))
        avoided = float(treatment_benefit.get("mi_stroke_avoided", 0.0))
        mortality = float(treatment_benefit.get("mortality_avoided", 0.0))
        _text(c, 43, 121, t["benefit_title"], 10, NAVY)
        _text(c, 43, 102, t["benefit1"].format(years=years, avoided=avoided), 9)
        _text(c, 43, 84, t["benefit2"].format(mortality=mortality), 9)
        _text(c, 43, 65, t["benefit3"], 8, GRAY)
    else:
        _text(c, 43, 101, t["review_title"], 10, NAVY)
        _text(c, 43, 82, t["review1"], 9)
        _text(c, 43, 65, t["review2"], 8, GRAY)
    _text(c, page_w - 30, 27, t["footer"], 7.5, GRAY, "right")
    c.save()
    return buf.getvalue()
