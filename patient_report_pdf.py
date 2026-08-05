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


def _bar_chart(c: canvas.Canvas, x: float, y: float, w: float, h: float,
               risks: Mapping[str, Mapping[str, Iterable[float]]]) -> None:
    values = {key: _risk_values(risks[key]) for key in OUTCOME_LABELS}
    max_value = max([v for pair in values.values() for v in pair[:2]] + [1.0]) * 1.15
    c.setFillColor(white)
    c.roundRect(x, y, w, h, 7, fill=1, stroke=0)
    _text(c, x + 12, y + h - 19, "計画実行前後の累積リスク", 10, NAVY)
    row_h = 48
    for index, key in enumerate(OUTCOME_LABELS):
        cy = y + h - 46 - index * row_h
        _text(c, x + 12, cy + 12, OUTCOME_LABELS[key], 8.5)
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
        _text(c, x + w - 9, cy + 13, f"現在 {current:.1f}%", 7.5, RED, "right")
        _text(c, x + w - 9, cy - 2, f"実行後 {target:.1f}%", 7.5, TEAL, "right")


def _line_chart(c: canvas.Canvas, x: float, y: float, w: float, h: float,
                title: str, curve: Mapping[str, Iterable[float]]) -> None:
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
        return left + (right-left)*t/max(times), bottom + (top-bottom)*v/max_y
    for values, color in ((baseline, RED), (target, TEAL)):
        c.setStrokeColor(color)
        c.setLineWidth(2)
        pts = [point(t, v) for t, v in zip(times, values)]
        for a, b in zip(pts, pts[1:]):
            c.line(a[0], a[1], b[0], b[1])
    _text(c, left, y + 8, "0年", 6.5, GRAY)
    _text(c, right, y + 8, f"{max(times):.0f}年", 6.5, GRAY, "right")


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
) -> bytes:
    """A4 2ページの患者向け説明資料を返す。"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # 1ページ目: 現状・介入・メリット
    c.setFillColor(NAVY)
    c.rect(0, page_h - 92, page_w, 92, fill=1, stroke=0)
    _text(c, 30, page_h - 43, "あなたの健康づくりプラン", 20, white)
    _text(c, 30, page_h - 68, f"現在の状態と、計画を実行した場合の{horizon_years}年間の見通し", 10, white)
    _text(c, page_w - 30, page_h - 68, date.today().strftime("%Y.%m.%d"), 8, white, "right")

    y = page_h - 120
    y = _section_title(c, y, "1. 現在の状態")
    _text(c, 42, y, f"{age}歳・{sex_label}　身長 {height_cm:.1f} cm　体重 {weight_kg:.1f} kg（BMI {weight_kg/(height_cm/100)**2:.1f}）", 10)
    _text(c, 42, y - 18, "現在考えられる病気・管理対象: " + ("、".join(diagnoses) if list(diagnoses) else "該当なし／確認中"), 10)
    _text(c, 42, y - 36, "入力された服薬: " + ("、".join(medications) if list(medications) else "なし／未入力"), 9, GRAY)

    y -= 72
    y = _section_title(c, y, "2. 介入で目指す変化")
    card_y = y - 58
    _metric_card(c, 30, card_y, 170, "血圧", current_values["sbp"], target_values["sbp"], "mmHg")
    _metric_card(c, 212, card_y, 170, "LDLコレステロール", current_values["ldl"], target_values["ldl"], "mg/dL")
    _metric_card(c, 394, card_y, 171, "HbA1c", current_values["a1c"], target_values["a1c"], "%")

    y = card_y - 35
    y = _section_title(c, y, f"3. 計画を続けた場合のメリット（{horizon_years}年）")
    benefits_y = y - 72
    for index, key in enumerate(OUTCOME_LABELS):
        current, target, arr = _risk_values(risks[key])
        x = 30 + index * 182
        c.setFillColor(PALE_TEAL if arr > 0 else LIGHT)
        c.roundRect(x, benefits_y, 170, 70, 7, fill=1, stroke=0)
        _text(c, x + 10, benefits_y + 51, OUTCOME_LABELS[key], 9, NAVY)
        _text(c, x + 10, benefits_y + 29, f"{current:.1f}% → {target:.1f}%", 14, TEAL if arr > 0 else GRAY)
        _text(c, x + 10, benefits_y + 10, f"絶対リスク減少 {arr:.1f}ポイント", 8, GRAY)

    _bar_chart(c, 30, 112, 535, 265, risks)
    _text(c, 30, 42, "赤: 現在の状態が続いた場合　緑: 目標を実行した場合", 8, GRAY)
    _text(c, 30, 27, "推定値には不確実性があります。治療内容は主治医と相談して決めてください。", 7.5, GRAY)
    c.showPage()

    # 2ページ目: 経時グラフ・実行目標
    c.setFillColor(NAVY)
    c.rect(0, page_h - 65, page_w, 65, fill=1, stroke=0)
    _text(c, 30, page_h - 40, "リスクの変化と、いっしょに取り組む目標", 17, white)
    chart_y = page_h - 250
    chart_w = 170
    for index, key in enumerate(OUTCOME_LABELS):
        _line_chart(c, 30 + index * 182, chart_y, chart_w, 160, OUTCOME_LABELS[key], risks[key])
    _text(c, 30, chart_y - 16, "赤: 現在の状態が続いた場合　緑: 目標を実行した場合", 8, GRAY)

    y = chart_y - 50
    y = _section_title(c, y, "選んだ指導項目")
    instruction_lines = [f"□ {item}" for item in instructions] or ["□ 次回、相談して決める"]
    col_x = [42, 305]
    for idx, item in enumerate(instruction_lines[:8]):
        _text(c, col_x[idx % 2], y - (idx // 2) * 18, item, 9)

    y -= 98
    y = _section_title(c, y, "患者さんと相談して決めた行動目標")
    goal_y = y
    for goal in list(goals)[:6] or ["次回、相談して決める"]:
        for line_index, line in enumerate(_wrap(f"□ {goal}", 42)):
            _text(c, 42, goal_y, line, 10, NAVY if line_index == 0 else TEXT)
            goal_y -= 15
        goal_y -= 4

    c.setFillColor(PALE_BLUE)
    c.roundRect(30, 58, 535, 65, 7, fill=1, stroke=0)
    _text(c, 43, 101, "次回の振り返り", 10, NAVY)
    _text(c, 43, 82, "できたことを確認し、難しかった目標は無理のない内容へ調整しましょう。", 9)
    _text(c, 43, 65, "体調の変化や薬の副作用が気になる場合は、自己判断で中止せず医療者へ相談してください。", 8, GRAY)
    _text(c, page_w - 30, 27, "教育・共有意思決定用の推定資料（医療機器ではありません）", 7.5, GRAY, "right")
    c.save()
    return buf.getvalue()
