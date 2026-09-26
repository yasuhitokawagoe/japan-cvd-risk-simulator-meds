"""PC-only non-diabetes reference outcomes; never reuse the T2D baseline.

Sources, equations, applicability and modelling assumptions are recorded in
docs/non_diabetic_outcomes.md. These are not individual treatment predictions.
"""
from math import exp, expm1, isfinite, log, log1p

from dementia_prevention import annual_mortality_probability, dementia_biomarker_hazard_ratio


KFRE_URL = "https://jamanetwork.com/journals/jama/fullarticle/2481005"
JAGES_URL = "https://www.jstage.jst.go.jp/article/jmaj/8/3/8_766/_pdf"
GENERAL_STATIN_URL = "https://pubmed.ncbi.nlm.nih.gov/39822593/"

# Baseline-age strata, NOT attained-age rates. Table 2, Shimada et al. 2025.
JAGES_ANNUAL_RATES = (
    (65, 70, 0.006, 0.005),
    (70, 75, 0.014, 0.013),
    (75, 80, 0.031, 0.032),
    (80, 85, 0.054, 0.062),
    (85, 96, 0.096, 0.105),
)


def kfre_risks(*, age: float, sex: str, egfr: float, uacr_mg_g: float) -> dict:
    """Non-North American 4-variable KFRE, probabilities at ONLY 2 and 5 years.

Caller must confirm established CKD, CKD-EPI eGFR and no prior KRT.
    """
    values = (age, egfr, uacr_mg_g)
    if any(v is None or not isfinite(float(v)) for v in values):
        raise ValueError("年齢・eGFR・尿ACRの実測値が必要です。")
    if sex not in ("male", "female") or not 20 <= age <= 95:
        raise ValueError("この画面では20〜95歳・性別の入力が必要です。")
    if not 5 <= egfr < 60:
        raise ValueError("KFREはCKD G3〜G5（eGFR 5以上60未満）の場合のみ算出します。")
    if not 0 < uacr_mg_g <= 100000:
        raise ValueError("尿ACRは0より大きい実測値（mg/gCr）を入力してください。")
    linear_predictor = (
        -0.2201 * (age / 10 - 7.036)
        + 0.2467 * ((1 if sex == "male" else 0) - 0.5642)
        - 0.5567 * (egfr / 5 - 7.222)
        + 0.4510 * (log(uacr_mg_g) - 5.137)
    )
    return {f"risk_{year}y": -expm1(log(survival) * exp(linear_predictor))
            for year, survival in ((2, 0.9832), (5, 0.9365))}


def kidney_reference(*, age, sex, egfr, uacr_mg_g=None, ckd_confirmed=False,
                     egfr_method=None) -> dict:
    result = {"model": "kfre"}
    try:
        if not ckd_confirmed:
            raise ValueError("「喫煙・BMI・腎機能・尿アルブミン」でCKDの適用条件を確認してください。")
        if egfr_method != "CKD-EPI":
            raise ValueError("KFREにはCKD-EPI式のeGFRが必要です。日本人式・算出式不明の値では算出しません。")
        result.update(kfre_risks(age=age, sex=sex, egfr=egfr, uacr_mg_g=uacr_mg_g))
    except ValueError as error:
        result["unavailable_reason"] = str(error)
    return result


def general_dementia_effects(*, sbp_before, sbp_after, ldl_before, ldl_after,
                             has_statin=False) -> dict:
    """Exploratory translation, not causal estimates or trial Cox HRs.

Statin and LDL associations overlap: use the stronger, never their product.
BP and lipid effects are combined assuming independence (unvalidated).
    """
    biomarker = dementia_biomarker_hazard_ratio(
        sbp_before=sbp_before, sbp_after=sbp_after,
        ldl_before=ldl_before, ldl_after=ldl_after,
    )
    lipid = min(biomarker["ldl"], 0.86 if has_statin else 1.0)
    return {"bp": biomarker["bp"], "ldl": biomarker["ldl"],
            "statin_increment": lipid / biomarker["ldl"],
            "combined": biomarker["bp"] * lipid}


def general_dementia_curve(*, age: float, sex: str, years: int,
                           hazard_ratio: float = 1.0) -> dict:
    """JAGES age/sex incidence approximation with Japanese competing mortality.

Not a published/validated prediction equation; the age-band hazard is held
fixed because the observed cohort rate ALREADY includes aging over follow-up.
    """
    if not isfinite(age) or not 65 <= age <= 95 or sex not in ("male", "female"):
        raise ValueError("一般住民の認知症参考推定は現在65〜95歳が対象です。65歳未満は未算出です（0%ではありません）。")
    if not isfinite(hazard_ratio) or hazard_ratio <= 0 or not 0 <= years <= 50:
        raise ValueError("推定期間または相対効果が範囲外です。")
    rate = next(row[2 if sex == "male" else 3] for row in JAGES_ANNUAL_RATES
                if row[0] <= age < row[1])
    dementia_hazard = rate * hazard_ratio
    years = min(int(years), int(110 - age))
    event_free, cumulative = 1.0, 0.0
    risks = [0.0]
    for elapsed in range(years):
        death_hazard = -log1p(-annual_mortality_probability(age + elapsed, sex))
        total = dementia_hazard + death_hazard
        cumulative += event_free * -expm1(-total) * dementia_hazard / total
        event_free *= exp(-total)
        risks.append(cumulative)
    return {"time": list(range(years + 1)), "risk": risks}


def dementia_reference(*, age, sex, years, treatment_hr=1.0, continuing=False) -> dict:
    result = {"model": "jages", "has_uncertainty": False, "extrapolation_after": 9.0}
    try:
        untreated = general_dementia_curve(age=age, sex=sex, years=years)
        treated = general_dementia_curve(age=age, sex=sex, years=years, hazard_ratio=treatment_hr)
    except ValueError as error:
        return {**result, "unavailable_reason": str(error)}
    result["time"] = untreated["time"]
    baseline, target = (treated, untreated) if continuing else (untreated, treated)
    for name, curve in (("baseline", baseline), ("target", target)):
        risk = [value * 100 for value in curve["risk"]]
        result[f"{name}_cumulative"] = risk
        # Interface compatibility only; has_uncertainty=False suppresses CI display.
        result[f"{name}_ci_lower"] = risk.copy()
        result[f"{name}_ci_upper"] = risk.copy()
    return result
