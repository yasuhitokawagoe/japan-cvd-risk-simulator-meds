"""PC dementia bands: conditional, approximate 95% model uncertainty, NOT CIs.

Point predictions are preserved. See docs/dementia_uncertainty.md for sources,
unavailable uncertainties, fixed assumptions and the limitations of reconstruction.
"""
from math import exp, log, log1p, sqrt

from dementia_prevention import (
    DSDRS_10_YEAR_RISK_BY_AGE, dementia_curve, dementia_biomarker_hazard_ratio,
    STATIN_EVIDENCE, GLP1_EVIDENCE, SGLT2_EVIDENCE, METFORMIN_EVIDENCE,
)
from non_diabetic_outcomes import JAGES_ANNUAL_RATES, general_dementia_curve, general_dementia_effects


# Exalto et al. 2013, appendix Table 6; matches existing age-only scores 0,3,5,7,8,10.
DSDRS_10_YEAR_CI = ((.061, .086), (.132, .163), (.227, .263),
                    (.379, .427), (.466, .532), (.580, .682))

# Shimada et al. 2025, Table 1 (sum of income strata) and Table 2.
# N is after multiple imputation; D=N*p is approximate, NOT observed event counts.
# Female N sums to 23450 vs reported total 23449 because published cells are rounded.
JAGES_APPROX_COUNTS = {
    "male": ((6196, .053), (6241, .109), (4552, .218), (2597, .333), (1048, .460)),
    "female": ((6868, .043), (6937, .104), (5288, .241), (2922, .406), (1435, .544)),
}

# Published intervals for the effects already used in this app, not new effects.
EFFECT_CI = {
    "bp": (.75, .99), "statin_general": (.82, .91), "statin": (.85, .89),
    "glp1_ra": (.83, .97), "sglt2": (.45, .69), "metformin": (.80, .99),
}
MEDICATION_ESTIMATES = {e.key: e.estimate for e in (
    STATIN_EVIDENCE, GLP1_EVIDENCE, SGLT2_EVIDENCE, METFORMIN_EVIDENCE,
)}


def log_effect_variance(key: str, power: float = 1.0) -> float:
    lo, hi = EFFECT_CI[key]
    return (power * (log(hi) - log(lo)) / 3.92) ** 2


def baseline_log_se(*, age: float, sex: str, has_type2_diabetes: bool) -> tuple[float, float]:
    """Lower/upper log-hazard SEs. Japanese calibration/mortality held fixed."""
    if has_type2_diabetes:
        index = next(i for i, (lo, hi, _) in enumerate(DSDRS_10_YEAR_RISK_BY_AGE)
                     if lo <= max(age, 60) < hi)
        point = DSDRS_10_YEAR_RISK_BY_AGE[index][2]
        low, high = DSDRS_10_YEAR_CI[index]
        h = -log1p(-point)
        return (log(h / -log1p(-low)) / 1.96, log(-log1p(-high) / h) / 1.96)
    index = next(i for i, row in enumerate(JAGES_ANNUAL_RATES) if row[0] <= age < row[1])
    n, incidence = JAGES_APPROX_COUNTS[sex][index]
    # Conditional Poisson approximation; not a Rubin-pooled MI confidence interval.
    se = 1 / sqrt(n * incidence)
    return se, se


def treatment_uncertainty(*, has_type2_diabetes, sbp_before, sbp_after,
                          ldl_before, ldl_after, medication_keys=()) -> dict:
    keys = set(medication_keys)  # Same-class selections must not narrow or duplicate CIs.
    bp_power = min(30.0, max(0.0, sbp_before - sbp_after)) / 10.0
    biomarker = dementia_biomarker_hazard_ratio(
        sbp_before=sbp_before, sbp_after=sbp_after, ldl_before=ldl_before, ldl_after=ldl_after,
    )
    variance = log_effect_variance("bp", bp_power)
    omitted = []
    if has_type2_diabetes:
        multiplier = biomarker["combined"]
        for key in sorted(keys & MEDICATION_ESTIMATES.keys()):
            multiplier *= MEDICATION_ESTIMATES[key]
            variance += log_effect_variance(key)
        uses_ldl = biomarker["ldl"] < 1.0
    else:
        multiplier = general_dementia_effects(
            sbp_before=sbp_before, sbp_after=sbp_after, ldl_before=ldl_before, ldl_after=ldl_after,
            has_statin="statin" in keys,
        )["combined"]
        # Match the existing stronger-of-LDL/statin branch, not their product.
        uses_statin = "statin" in keys and .86 < biomarker["ldl"]
        if uses_statin:
            variance += log_effect_variance("statin_general")
        uses_ldl = not uses_statin and biomarker["ldl"] < 1.0
    if uses_ldl:
        # Full source table unavailable in this audit: never invent a standard error.
        omitted.append("LDL関連効果の不確実性（原著CI未確認のため倍率を固定）")
    return {"multiplier": multiplier, "log_variance": variance, "omitted": omitted}


def add_dementia_uncertainty(data: dict, *, age: float, sex: str,
                             has_type2_diabetes: bool, sbp_before: float,
                             sbp_after: float, ldl_before: float, ldl_after: float,
                             medication_keys=(), continuing=False) -> dict:
    """Decorate only PC output, preserving points, exclusions and mobile behavior."""
    if "unavailable_reason" in data:
        return dict(data)
    effect = treatment_uncertainty(
        has_type2_diabetes=has_type2_diabetes, sbp_before=sbp_before, sbp_after=sbp_after,
        ldl_before=ldl_before, ldl_after=ldl_after, medication_keys=medication_keys,
    )
    low_se, high_se = baseline_log_se(age=age, sex=sex, has_type2_diabetes=has_type2_diabetes)
    curve = dementia_curve if has_type2_diabetes else general_dementia_curve
    years = int(data["time"][-1])
    result = dict(data)
    for scenario, treated in (("baseline", continuing), ("target", not continuing)):
        hr = effect["multiplier"] if treated else 1.0
        variance = effect["log_variance"] if treated else 0.0
        for side, se, sign in (("lower", low_se, -1), ("upper", high_se, 1)):
            multiplier = hr * exp(sign * 1.96 * sqrt(se ** 2 + variance))
            bound = curve(age=age, sex=sex, years=years, hazard_ratio=multiplier)["risk"]
            result[f"{scenario}_ci_{side}"] = [float(r) * 100 for r in bound]
    result.update({
        "has_uncertainty": True, "uncertainty_label": "95%推定幅（近似）",
        "uncertainty_omitted": effect["omitted"],
        "uncertainty_method": "conditional_log_hazard_propagation",
    })
    return result
