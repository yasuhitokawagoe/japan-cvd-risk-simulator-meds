"""服薬中の現在値から、無治療だった場合の危険因子を逆算する。"""
from __future__ import annotations

from typing import Iterable, Mapping


def _by_key(items: Iterable[Mapping]) -> dict[str, Mapping]:
    return {str(item["key"]): item for item in items}


def reconstruct_untreated_values(
    *, sbp_now: float, ldl_now: float, a1c_now: float,
    sbp_meds: Iterable[Mapping] = (), ldl_meds: Iterable[Mapping] = (),
    a1c_meds: Iterable[Mapping] = (),
) -> dict[str, float]:
    """薬効を逆向きにたどり、薬を飲まなかった場合の値を推定する。"""
    sbp_effect = sum(float(m["effect"]["mean"]) for m in sbp_meds)
    a1c_effect = sum(float(m["effect"]["mean"]) for m in a1c_meds)
    ldl_factor = 1.0
    for med in ldl_meds:
        ldl_factor *= 1.0 - float(med["effect"]["mean"])
    return {
        "sbp": min(260.0, max(70.0, float(sbp_now) - sbp_effect)),
        "ldl": min(400.0, max(20.0, float(ldl_now) / max(ldl_factor, 0.05))),
        "a1c": min(20.0, max(4.0, float(a1c_now) - a1c_effect)),
    }


def exposure_adjusted_values(
    *, untreated: Mapping[str, float], current: Mapping[str, float],
    treatment_years: int, medication_years: Mapping[str, float],
    sbp_meds: Iterable[Mapping] = (), ldl_meds: Iterable[Mapping] = (),
    a1c_meds: Iterable[Mapping] = (),
) -> dict[str, float]:
    """服薬年数/観察年数で薬効を按分した、期間平均の危険因子を返す。"""
    if treatment_years <= 0:
        raise ValueError("treatment_years must be positive")

    def exposure(meds: Iterable[Mapping]) -> float:
        meds = list(meds)
        if not meds:
            return 0.0
        weighted = [
            min(1.0, max(0.0, float(medication_years.get(str(m["key"]), 0))) / treatment_years)
            for m in meds
        ]
        return sum(weighted) / len(weighted)

    return {
        "sbp": float(untreated["sbp"]) + (float(current["sbp"]) - float(untreated["sbp"])) * exposure(sbp_meds),
        "ldl": float(untreated["ldl"]) + (float(current["ldl"]) - float(untreated["ldl"])) * exposure(ldl_meds),
        "a1c": float(untreated["a1c"]) + (float(current["a1c"]) - float(untreated["a1c"])) * exposure(a1c_meds),
    }


def selected_medications(catalog: Mapping, domain: str, keys: Iterable[str]) -> list[Mapping]:
    lookup = _by_key(catalog.get(domain, []))
    return [lookup[key] for key in keys if key in lookup]
