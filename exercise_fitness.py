"""Optional non-causal CRF scenario with an approximate model uncertainty band."""
from math import exp, expm1, isfinite, log, log1p, sqrt

FITNESS_MORTALITY_SOURCE = "https://pubmed.ncbi.nlm.nih.gov/35562197/"
FITNESS_TRAINING_SOURCE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12859889/"
VO2_GAIN = {"aerobic_moderate": 2.77, "combined": 2.68, "hiit": 4.19}
VO2_GAIN_CI = {"aerobic_moderate": (1.98, 3.56), "combined": (1.66, 3.70), "hiit": (2.59, 5.79)}
MORTALITY_RR_PER_MET = 0.89
MORTALITY_RR_CI = (0.86, 0.92)


def fitness_scenario(risks_percent, exercise_key, *, enabled=False,
                     lower_percent=None, upper_percent=None):
    """Use observational RR as a constant hazard multiplier (explicit assumption).

    Trial-average fitness gain is assumed achieved and maintained throughout
    follow-up, not accumulated annually. The approximate 95% band assumes
    independent errors on log cumulative hazard / VO2 / log RR; not a validated CI.
    """
    if not enabled or exercise_key not in VO2_GAIN:
        return None
    risks = [float(value) for value in risks_percent]
    if any(not isfinite(value) or not 0 <= value <= 100 for value in risks):
        raise ValueError("Risk must be finite and between 0 and 100 percent")
    if (lower_percent is None) != (upper_percent is None):
        raise ValueError("Both risk bounds must be provided together")
    lower = risks if lower_percent is None else [float(v) for v in lower_percent]
    upper = risks if upper_percent is None else [float(v) for v in upper_percent]
    if len(lower) != len(risks) or len(upper) != len(risks):
        raise ValueError("Risk and bound lengths must match")
    if any(not isfinite(lo) or not isfinite(hi) or not 0 <= lo <= p <= hi <= 100
           for p, lo, hi in zip(risks, lower, upper)):
        raise ValueError("Bounds must be finite, ordered and contain the point risk")
    gain = VO2_GAIN[exercise_key]
    mets = gain / 3.5
    multiplier = MORTALITY_RR_PER_MET ** mets
    se_mets = (VO2_GAIN_CI[exercise_key][1] - VO2_GAIN_CI[exercise_key][0]) / (3.92 * 3.5)
    se_log_rr = (log(MORTALITY_RR_CI[1]) - log(MORTALITY_RR_CI[0])) / 3.92
    effect_variance = (log(MORTALITY_RR_PER_MET) * se_mets) ** 2 + (mets * se_log_rr) ** 2

    def transform(p):
        return 100.0 if p == 100 else -100 * expm1(log1p(-p / 100) * multiplier)

    def bound(p, endpoint, direction):
        # Boundary hazards cannot be log-transformed; preserve valid endpoints.
        if endpoint in (0, 100) or p in (0, 100):
            return transform(endpoint)
        log_h = log(-log1p(-p / 100))
        log_endpoint_h = log(-log1p(-endpoint / 100))
        base_se = abs(log_endpoint_h - log_h) / 1.96
        log_adjusted_h = log_h + log(multiplier) + direction * 1.96 * sqrt(base_se ** 2 + effect_variance)
        return -100 * expm1(-exp(log_adjusted_h))

    return {
        "vo2_gain": gain, "met_gain": mets, "hazard_multiplier": multiplier,
        "risk": [transform(p) for p in risks],
        "lower": [bound(p, lo, -1) for p, lo in zip(risks, lower)],
        "upper": [bound(p, hi, 1) for p, hi in zip(risks, upper)],
    }
