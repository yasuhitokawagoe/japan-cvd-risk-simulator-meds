"""Optional non-causal CRF scenario; never modifies the standard risk curve."""
from math import isfinite

FITNESS_MORTALITY_SOURCE = "https://pubmed.ncbi.nlm.nih.gov/35562197/"
FITNESS_TRAINING_SOURCE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12859889/"
VO2_GAIN = {"aerobic_moderate": 2.77, "combined": 2.68, "hiit": 4.19}
MORTALITY_RR_PER_MET = 0.89


def fitness_scenario(risks_percent, exercise_key, *, enabled=False):
    """Use observational RR as a constant hazard multiplier (explicit assumption).

    Trial-average fitness gain is assumed achieved and maintained throughout
    follow-up, not accumulated annually. No combined confidence interval claimed.
    """
    if not enabled or exercise_key not in VO2_GAIN:
        return None
    risks = [float(value) for value in risks_percent]
    if any(not isfinite(value) or not 0 <= value <= 100 for value in risks):
        raise ValueError("Risk must be finite and between 0 and 100 percent")
    gain = VO2_GAIN[exercise_key]
    mets = gain / 3.5
    multiplier = MORTALITY_RR_PER_MET ** mets
    return {
        "vo2_gain": gain, "met_gain": mets, "hazard_multiplier": multiplier,
        "risk": [100 * (1 - (1 - value / 100) ** multiplier) for value in risks],
    }
