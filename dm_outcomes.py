"""糖尿病合併症アウトカムモデル。

yasuhitokawagoe/DM-model の Weibull パラメータと回帰係数を、既存の
心血管アウトカムエンジンから独立して利用できる形にしたもの。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DiabetesOutcome:
    label: str
    weibull_lambda: float
    weibull_shape: float
    beta: tuple[float, float, float, float, float, float]
    se: tuple[float, float, float, float, float, float]
    source: str


DIABETES_OUTCOMES = {
    "esrd": DiabetesOutcome(
        "透析（末期腎不全）", 0.0012, 1.5,
        (0.152, 0.086, -0.245, 0.401, 0.071, 0.125),
        (0.022, 0.010, 0.027, 0.036, 0.012, 0.017),
        "NZ Renal Risk Model (Elley et al., 2013)",
    ),
    "amputation": DiabetesOutcome(
        "大切断", 0.0015, 1.5,
        (0.145, 0.081, -0.213, 0.386, 0.065, 0.118),
        (0.016, 0.008, 0.025, 0.031, 0.009, 0.015),
        "RECODe (Basu et al., 2017); Ishii & Kumada (2012)",
    ),
    "blindness": DiabetesOutcome(
        "失明", 0.0009, 1.4,
        (0.181, 0.080, -0.220, 0.420, 0.070, 0.120),
        (0.030, 0.010, 0.035, 0.040, 0.012, 0.018),
        "DCCT/EDIC (2003); EURODIAB (2014)",
    ),
}

ACR_CATEGORY_MG_G = {"A1": 15.0, "A2": 100.0, "A3": 500.0}


class DiabetesOutcomeModel:
    """2型糖尿病患者の合併症リスクを推定する Weibull モデル。"""

    @staticmethod
    def alpha_age(age: float) -> float:
        if age <= 60:
            return 1.0
        if age <= 80:
            return 1.0 - 0.015 * (age - 60)
        return 0.7

    def _features(self, *, hba1c, age, egfr, acr, sbp, sex) -> np.ndarray:
        if acr <= 0:
            raise ValueError("ACRは0より大きい値が必要です")
        return np.asarray([
            (hba1c - 6.5) * self.alpha_age(age),
            (age - 60.0) / 10.0,
            (egfr - 60.0) / 10.0,
            math.log(acr / 30.0),
            (sbp - 130.0) / 10.0,
            int(sex),
        ], dtype=float)

    def predict_curve_with_ci(
        self, outcome: str, *, hba1c: float, age: float, egfr: float,
        acr: float, sbp: float, sex: int, years: int, n_sim: int = 200,
    ) -> dict[str, np.ndarray]:
        if outcome not in DIABETES_OUTCOMES:
            raise ValueError(f"未知の糖尿病アウトカムです: {outcome}")
        spec = DIABETES_OUTCOMES[outcome]
        times = np.arange(0, max(0, years) + 1, dtype=float)
        features = self._features(
            hba1c=hba1c, age=age, egfr=egfr, acr=acr, sbp=sbp, sex=sex,
        )
        beta = np.asarray(spec.beta, dtype=float)
        point_xb = float(beta @ features)
        point = 1.0 - np.exp(
            -spec.weibull_lambda * np.power(times, spec.weibull_shape) * np.exp(point_xb)
        )

        rng = np.random.default_rng(42)
        samples = rng.normal(beta, np.asarray(spec.se), size=(n_sim, len(beta)))
        sampled_xb = samples @ features
        simulated = 1.0 - np.exp(
            -spec.weibull_lambda
            * np.power(times[:, None], spec.weibull_shape)
            * np.exp(sampled_xb[None, :])
        )
        return {
            "time": times,
            "risk": np.clip(point, 0.0, 1.0),
            "lower": np.clip(np.percentile(simulated, 2.5, axis=1), 0.0, 1.0),
            "upper": np.clip(np.percentile(simulated, 97.5, axis=1), 0.0, 1.0),
        }

    def predict_risk(self, outcome: str, *, years: int, **patient) -> float:
        return float(self.predict_curve_with_ci(outcome, years=years, n_sim=1, **patient)["risk"][-1])

