"""Outpatient medication cost estimate, fixed August 2026–July 2027 rules.

Evidence and scope: docs/evidence_insurance_costs.md.
One patient, one prescribing institution plus its dispensing pharmacy.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

PERIOD_START = date(2026, 8, 1)
PERIOD_END = date(2027, 8, 1)
MONTHS = [(2026 + (7 + i) // 12, (7 + i) % 12 + 1) for i in range(12)]
SOURCE_URL = "https://www.kyoukaikenpo.or.jp/benefit/high_cost_medical_expenses/002/"

# base monthly cap, medical-cost threshold for 1%, repeated cap, annual cap
WORKING_LIMITS = {
    "a": (270300, 901000, 140100, 1680000),
    "b": (179100, 597000, 93000, 1110000),
    "c": (85800, 286000, 44400, 530000),
    "d": (61500, None, 44400, 530000),
    "d_low": (61500, None, 44400, 410000),
    "e": (36900, None, 24600, 290000),
}
# Elderly outpatient-only caps. These payments do not generate majority hits.
OUTPATIENT_LIMITS = {
    "general": (22000, 216000),
    "low2": (11000, 96000),
    "low1": (8000, None),
}
INCOME_LABELS = {
    "a": "区分ア：年収目安1,160万円以上（標準報酬月額83万円以上）",
    "b": "区分イ：年収目安770～1,160万円（標準報酬月額53～79万円）",
    "c": "区分ウ：年収目安370～770万円（標準報酬月額28～50万円）",
    "d": "区分エ：年収目安370万円以下（低所得区分・下記区分を除く）",
    "d_low": "区分エ・年間41万円対象：標準報酬月額15万円以下等（保険者確認済み）",
    "e": "区分オ：住民税非課税",
    "general": "一般所得",
    "low2": "低所得Ⅱ：住民税非課税世帯",
    "low1": "低所得Ⅰ：住民税非課税世帯で各種所得が一定以下",
}


def income_options(age: int, copay: int) -> list[str]:
    if copay == 10:
        return []
    if age < 70:
        return list(WORKING_LIMITS)
    if copay == 3:
        return ["a", "b", "c"]
    if age >= 75 and copay == 2:
        return ["general"]
    return list(OUTPATIENT_LIMITS)


def yen(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def medication_schedule(medications: list[dict], *, inclisiran_first_year=False) -> dict:
    """Calendar-month cost; periodic injections are never spread over 12 months.

    Daily therapy is monthly dispensing / consumption, weighted by calendar days.
    Weekly/fortnightly therapy starts August 1; year includes 53/27 injections.
    This is an explicit administration-month approximation for self-injections;
    actual multi-month dispensing can change insurance benefits.
    """
    totals = [0.0] * 12
    details = []
    days = (PERIOD_END - PERIOD_START).days
    for med in medications:
        annual = med.get("annual_cost_yen")
        if annual is None or not isfinite(float(annual)) or float(annual) < 0:
            raise ValueError(f"薬価を確認できません: {med.get('key', '')}")
        key = med["key"]
        amounts = [0.0] * 12
        if "インクリシラン" in key:
            indices = [0, 3, 9] if inclisiran_first_year else [0, 6]
            unit_cost = float(annual) / 2
            for i in indices:
                amounts[i] += unit_cost
            timing = "8・11・5月に投与（初年度）" if inclisiran_first_year else "8・2月に投与（維持期）"
        elif "隔週" in key or "/週" in key:
            interval, conventional_count = (14, 26) if "隔週" in key else (7, 52)
            unit_cost = float(annual) / conventional_count
            day = PERIOD_START
            count = 0
            while day < PERIOD_END:
                i = (day.year - 2026) * 12 + day.month - 8
                amounts[i] += unit_cost
                count += 1
                day += timedelta(days=interval)
            timing = f"8月1日から{interval}日間隔、期間内{count}回。投与月に費用計上"
        else:
            amounts = [float(annual) * monthrange(y, m)[1] / days for y, m in MONTHS]
            timing = "毎月処方・各月の日数で按分（注射ペンは消費量換算）"
        totals = [a + b for a, b in zip(totals, amounts)]
        details.append({"薬剤": key, "年間薬剤費（円）": yen(sum(amounts)), "計上方法": timing})
    return {"monthly_gross": totals, "details": details}


def estimate_outpatient_costs(monthly_gross: list[float], *, age: int, copay: int,
                              income: str | None, previous_hit_months=()) -> dict:
    """After-reimbursement estimate for one fixed benefit year.

    Prior months are offsets -11..-1 from Aug 2026; only true household hits,
    excluding elderly individual outpatient-only hits, from the same insurer.
    Year-end relief is returned separately, not a discount at the visit.
    """
    valid_rates = [3, 10] if age < 70 else ([2, 3, 10] if age < 75 else [1, 2, 3, 10])
    if copay not in valid_rates:
        raise ValueError("年齢と自己負担割合の組み合わせを確認してください")
    if len(monthly_gross) != 12 or any(not isfinite(v) or v < 0 for v in monthly_gross):
        raise ValueError("12か月の非負の医療費が必要です")
    if copay != 10 and income not in income_options(age, copay):
        raise ValueError("保険者の所得区分を選択してください")
    history = set(previous_hit_months)
    if any(not isinstance(i, int) or i < -11 or i > -1 for i in history):
        raise ValueError("過去の該当月は開始前11か月以内で指定してください")
    rows, eligible_annual = [], 0.0
    elderly_outpatient = copay != 10 and age >= 70 and income in OUTPATIENT_LIMITS
    annual_limit = None
    if copay != 10:
        annual_limit = OUTPATIENT_LIMITS[income][1] if elderly_outpatient else WORKING_LIMITS[income][3]
    for index, gross in enumerate(monthly_gross):
        before = gross * copay / 10
        limit, repeated = None, False
        if copay != 10:
            if elderly_outpatient:
                limit = OUTPATIENT_LIMITS[income][0]
            else:
                base, threshold, multiple, _ = WORKING_LIMITS[income]
                repeated = sum(index-11 <= i < index for i in history) >= 3
                limit = multiple if repeated else base + (max(0.0, gross-threshold) * .01 if threshold else 0)
        after = min(before, limit) if limit is not None else before
        if limit is not None and before > limit and not elderly_outpatient:
            history.add(index)
        # Under-70 annual aggregation also excludes <21,000-yen units.
        if copay != 10 and (age >= 70 or before >= 21000):
            eligible_annual += after
        year, month = MONTHS[index]
        rows.append({"month": f"{year}/{month:02d}", "gross": gross,
                     "before": before, "after_monthly": after,
                     "monthly_relief": before-after, "multiple": repeated and before > after})
    after_monthly = sum(r["after_monthly"] for r in rows)
    annual_relief = max(0.0, eligible_annual - annual_limit) if annual_limit is not None else 0.0
    after = max(0.0, after_monthly - annual_relief)
    before = sum(r["before"] for r in rows)
    return {"months": rows, "gross": sum(monthly_gross), "before": before,
            "after": after, "monthly_relief": before-after_monthly,
            "annual_relief": annual_relief, "total_relief": before-after}
