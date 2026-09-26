"""Display-only cumulative hazard ratios; not a fitted Cox/instantaneous HR."""
from math import isfinite, log1p


def hazard_ratio(target_percent, baseline_percent):
    """H_target(t)/H_baseline(t); undefined at zero baseline or saturated risks."""
    t, b = float(target_percent), float(baseline_percent)
    if not (isfinite(t) and isfinite(b) and 0 <= t < 100 and 0 < b < 100):
        return None
    return -log1p(-t / 100) / -log1p(-b / 100)


def hazard_ratio_curve(data):
    """Reference envelope from absolute bounds, not a joint 95% HR interval."""
    result = dict(data)
    baseline = data["baseline_cumulative"]
    result["baseline_cumulative"] = [1.0] * len(baseline)
    result["baseline_ci_lower"] = [1.0] * len(baseline)
    result["baseline_ci_upper"] = [1.0] * len(baseline)
    result["target_cumulative"] = [hazard_ratio(t, b) for t, b in zip(data["target_cumulative"], baseline)]
    result["target_ci_lower"] = [
        hazard_ratio(t, b) for t, b in zip(data["target_ci_lower"], data["baseline_ci_upper"])
    ]
    result["target_ci_upper"] = [
        hazard_ratio(t, b) for t, b in zip(data["target_ci_upper"], data["baseline_ci_lower"])
    ]
    return result


def format_hr(value):
    return "算出不可" if value is None else f"{value:.2f}"


def format_hazard_change(value):
    if value is None:
        return "算出不可"
    change = (1 - value) * 100
    return f"{abs(change):.1f}%{'減少' if change >= 0 else '増加'}"
