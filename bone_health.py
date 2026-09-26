"""骨粗鬆症・骨折の補足表示。

骨密度、既往骨折、末梢神経障害などが未入力のため、絶対リスクは計算せず、
現在得られる情報から骨折リスク評価を検討すべき項目だけを返す。
"""
from __future__ import annotations

from typing import Iterable, Mapping


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


def bone_health_flags(
    *, age: float, sex: str, bmi: float, egfr: float,
    diabetes_medications: Iterable[Mapping],
) -> list[str]:
    """数値予測ではなく、DXA・骨折歴確認を促す参考フラグを返す。"""
    flags: list[str] = []
    if (sex == "female" and age >= 65) or (sex == "male" and age >= 70):
        flags.append("年齢から骨密度検査（DXA）の適否を確認")
    if bmi < 18.5:
        flags.append("低BMIは骨折リスク因子")
    if egfr < 45:
        flags.append("腎機能低下があり、骨・ミネラル代謝の評価を検討")
    if any(
        "インスリン" in f"{med.get('key', '')} {med.get('category', '')}"
        for med in diabetes_medications
    ):
        flags.append("インスリン使用は糖尿病患者の骨折リスクモデルで確認項目")
    return flags
