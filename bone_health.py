"""骨粗鬆症・骨折のおまけ表示。"""
from __future__ import annotations

import math
from typing import Iterable, Mapping

from dementia_prevention import annual_mortality_probability


JAPAN_HIP_FRACTURE_URL = (
    "https://consensus.app/papers/trends-in-hip-fracture-incidence-in-japan-estimates-based-"
    "takusari-sakata/cc4a0b53336757fa9fdd09ee3e2ef9e0/"
)
DIABETES_FRACTURE_MODEL_URL = (
    "https://consensus.app/papers/major-osteoporosis-fracture-prediction-in-type-2-diabetes-"
    "kong-zhao/ab024f9bfd1552d8a948c9c9bf03a515/"
)
OSTEOPOROSIS_TREATMENT_URL = (
    "https://consensus.app/papers/fracture-risk-reduction-and-safety-by-osteoporosis-"
    "h%C3%A4ndel-cardoso/ed519e3e91b452beb364985de7d04176/"
)
DIABETES_DRUG_FRACTURE_URL = (
    "https://consensus.app/papers/risk-of-fracture-with-dipeptidyl-peptidase4-inhibitors-"
    "chai-liu/3c397c65e77d5d94b942366f34a47365/"
)

JAPAN_HIP_FRACTURE_INCIDENCE_2017 = {
    "male": ((0, 39, 3.3), (40, 49, 10.6), (50, 59, 26.9),
             (60, 69, 57.6), (70, 79, 156.5), (80, 89, 606.5),
             (90, 200, 1729.0)),
    "female": ((0, 39, 1.2), (40, 49, 7.6), (50, 59, 36.7),
               (60, 69, 94.9), (70, 79, 315.5), (80, 89, 1392.1),
               (90, 200, 3181.5)),
}
TYPE2_DIABETES_HIP_FRACTURE_RR = 1.33
PRIOR_FRAGILITY_FRACTURE_HIP_HR = 1.82


def annual_hip_fracture_incidence(age: float, sex: str) -> float:
    """2017年日本全国調査の年間発生率を確率で返す。"""
    bands = JAPAN_HIP_FRACTURE_INCIDENCE_2017[
        "male" if sex == "male" else "female"
    ]
    for lower, upper, incidence_per_100k in bands:
        if lower <= float(age) <= upper:
            return incidence_per_100k / 100_000.0
    return bands[-1][2] / 100_000.0


def hip_fracture_risk(
    *, age: float, sex: str, years: int = 10,
    prior_fragility_fracture: bool = False,
) -> float:
    """死亡を競合リスクとした2型糖尿病患者の大腿骨骨折参考確率。"""
    multiplier = TYPE2_DIABETES_HIP_FRACTURE_RR
    if prior_fragility_fracture:
        multiplier *= PRIOR_FRAGILITY_FRACTURE_HIP_HR
    event_free_survival = 1.0
    cumulative_fracture = 0.0
    for elapsed in range(max(0, int(years))):
        attained_age = float(age) + elapsed
        fracture_probability = min(
            0.999999, annual_hip_fracture_incidence(attained_age, sex) * multiplier,
        )
        fracture_hazard = -math.log1p(-fracture_probability)
        death_hazard = -math.log1p(
            -min(0.999999, annual_mortality_probability(attained_age, sex))
        )
        total_hazard = fracture_hazard + death_hazard
        annual_any_event = 1.0 - math.exp(-total_hazard)
        cumulative_fracture += (
            event_free_survival * annual_any_event * fracture_hazard / total_hazard
        )
        event_free_survival *= math.exp(-total_hazard)
    return cumulative_fracture


def bone_density_category(t_score: float | None) -> str:
    if t_score is None:
        return "未測定"
    if t_score <= -2.5:
        return "骨粗鬆症域"
    if t_score < -1.0:
        return "骨量減少域"
    return "正常域"


def bone_health_flags(
    *, age: float, sex: str, bmi: float, egfr: float,
    diabetes_medications: Iterable[Mapping],
    prior_fragility_fracture: bool = False, fall_history: bool = False,
    peripheral_neuropathy: bool = False, glucocorticoid_use: bool = False,
    t_score: float | None = None,
) -> list[str]:
    """数値予測ではなく、DXA・骨折歴確認を促す参考フラグを返す。"""
    flags: list[str] = []
    if (sex == "female" and age >= 65) or (sex == "male" and age >= 70):
        flags.append("年齢から骨密度検査（DXA）の適否を確認")
    if bmi < 18.5:
        flags.append("低BMIは骨折リスク因子")
    if egfr < 45:
        flags.append("腎機能低下があり、骨・ミネラル代謝の評価を検討")
    if prior_fragility_fracture:
        flags.append("脆弱性骨折歴があり、二次骨折予防の評価を優先")
    if fall_history:
        flags.append("過去1年の転倒歴があり、転倒予防介入を検討")
    if peripheral_neuropathy:
        flags.append("末梢神経障害があり、転倒・骨折リスク評価を検討")
    if glucocorticoid_use:
        flags.append("長期ステロイド使用があり、続発性骨粗鬆症を評価")
    if t_score is not None and t_score <= -2.5:
        flags.append("大腿骨頸部Tスコアが骨粗鬆症域（≤−2.5）")
    if any(
        "インスリン" in f"{med.get('key', '')} {med.get('category', '')}"
        for med in diabetes_medications
    ):
        flags.append("インスリン使用は糖尿病患者の骨折リスクモデルで確認項目")
    return flags
