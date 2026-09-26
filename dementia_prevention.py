"""2型糖尿病患者の認知症基礎曲線と介入エビデンス。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class DementiaEvidence:
    key: str
    label: str
    relative_effect: str
    estimate: float
    estimate_type: str
    evidence_summary: str
    source_url: str


BP_LOWERING_EVIDENCE = DementiaEvidence(
    key="bp_lowering",
    label="降圧治療",
    relative_effect="認知症発症オッズ 約13%低下",
    estimate=0.87,
    estimate_type="OR",
    evidence_summary=(
        "二重盲検RCT 5試験・28,008人の個人データメタ解析。平均10/4 mmHgの降圧で、"
        "認知症発症 OR 0.87（95%CI 0.75–0.99、追跡中央値4.3年）。"
    ),
    source_url=(
        "https://consensus.app/papers/blood-pressure-lowering-and-prevention-of-dementia-an-"
        "peters-xu/80e4c462131a5a9da849201e137c347d/"
    ),
)


GLP1_EVIDENCE = DementiaEvidence(
    key="glp1_ra",
    label="GLP-1受容体作動薬",
    relative_effect="認知症発症ハザード 約10%低下（保守的推定）",
    estimate=0.90,
    estimate_type="HR",
    evidence_summary=(
        "2型糖尿病109,778人の観察コホートで認知症 HR 0.90（95%CI 0.83–0.97）。"
        "観察研究メタ解析ではOR 0.58、探索的RCT解析ではOR 0.55であり幅が大きいため、"
        "曲線には最も保守的な0.90を採用。"
    ),
    source_url=(
        "https://consensus.app/papers/impact-of-glucagon%E2%80%90like-peptide%E2%80%901-receptor-"
        "agonists-on-cheng-yang/89acae5b8222597b836f4beedcfe34d8/"
    ),
)

STATIN_EVIDENCE = DementiaEvidence(
    key="statin",
    label="スタチン",
    relative_effect="認知症発症ハザード 約13%低下（観察研究）",
    estimate=0.87,
    estimate_type="HR",
    evidence_summary=(
        "観察研究55件・700万人超のメタ解析。2型糖尿病サブグループで認知症 HR 0.87"
        "（95%CI 0.85–0.89）。RCTでは予防効果未確立のため観察研究由来として表示。"
    ),
    source_url=(
        "https://consensus.app/papers/statin-use-and-dementia-risk-a-systematic-review-and-"
        "westphal-lopes/ee237a45c6cc5bcd9113cdfa6f85426f/"
    ),
)

SGLT2_EVIDENCE = DementiaEvidence(
    key="sglt2",
    label="SGLT2阻害薬",
    relative_effect="認知症オッズ 約44%低下（観察研究）",
    estimate=0.56,
    estimate_type="OR",
    evidence_summary=(
        "2型糖尿病の観察研究ネットワークメタ解析（41研究・3,307,483人）で、"
        "非使用者に対する認知症 OR 0.56（95%CI 0.45–0.69）。RCTでは未確立。"
    ),
    source_url=(
        "https://consensus.app/papers/antidiabetic-agents-and-the-risks-of-dementia-in-patients-"
        "li-lin/9856bad4379c53e1acf01068f0233af3/"
    ),
)

METFORMIN_EVIDENCE = DementiaEvidence(
    key="metformin",
    label="ビグアナイド（メトホルミン）",
    relative_effect="認知症オッズ 約11%低下（観察研究）",
    estimate=0.89,
    estimate_type="OR",
    evidence_summary=(
        "2型糖尿病の観察研究ネットワークメタ解析で、非使用者に対する認知症 OR 0.89"
        "（95%CI 0.80–0.99）。別メタ解析ではHR 0.76だが異質性が高く、保守値を採用。"
    ),
    source_url=(
        "https://consensus.app/papers/antidiabetic-agents-and-the-risks-of-dementia-in-patients-"
        "li-lin/9856bad4379c53e1acf01068f0233af3/"
    ),
)


STATIN_EVIDENCE_URL = (
    "https://consensus.app/papers/statin-use-and-dementia-risk-a-systematic-review-and-"
    "westphal-lopes/ee237a45c6cc5bcd9113cdfa6f85426f/"
)

GLUCOSE_CONTROL_EVIDENCE_URL = (
    "https://consensus.app/papers/intensive-glycaemic-control-and-cognitive-decline-in-"
    "tuligenga/f925f67fae395a138ee56e39d5972076/"
)


# DSDRSの年齢点数だけを用いた場合に対応する観察10年リスク。
# 既往症など未入力の加点は行わず、基礎曲線の過大推定を避ける。
DSDRS_10_YEAR_RISK_BY_AGE = (
    (60, 65, 0.074),
    (65, 70, 0.148),
    (70, 75, 0.245),
    (75, 80, 0.403),
    (80, 85, 0.499),
    (85, 200, 0.631),
)

DSDRS_EVIDENCE_URL = (
    "https://consensus.app/papers/risk-score-for-prediction-of-10-year-dementia-risk-in-"
    "exalto-biessels/ba8f28761c10508a89fc8c000e3c93e3/"
)

LDL_LEVEL_EVIDENCE_URL = (
    "https://consensus.app/papers/lowdensity-lipoprotein-cholesterol-levels-and-risk-of-"
    "lee-lee/4bf9a1f3fed25c058b00c34b5a05de67/"
)

JAPAN_LIFE_TABLE_2024_URL = (
    "https://www.mhlw.go.jp/toukei/saikin/hw/life/life24/"
)

# 厚生労働省「令和6(2024)年簡易生命表」の1年死亡確率 nqx。
# 5歳刻みの公表値を保持し、中間年齢は対数線形補間する。
JAPAN_2024_MORTALITY_QX = {
    "male": (
        (20, 0.00042), (25, 0.00047), (30, 0.00053), (35, 0.00071),
        (40, 0.00097), (45, 0.00144), (50, 0.00238), (55, 0.00394),
        (60, 0.00639), (65, 0.01051), (70, 0.01724), (75, 0.02894),
        (80, 0.04861), (85, 0.08467), (90, 0.15175), (95, 0.24640),
        (100, 0.40384),
    ),
    "female": (
        (20, 0.00028), (25, 0.00029), (30, 0.00030), (35, 0.00041),
        (40, 0.00057), (45, 0.00087), (50, 0.00141), (55, 0.00209),
        (60, 0.00297), (65, 0.00446), (70, 0.00704), (75, 0.01224),
        (80, 0.02294), (85, 0.04602), (90, 0.09520), (95, 0.18355),
        (100, 0.33068),
    ),
}


def annual_mortality_probability(age: float, sex: str) -> float:
    """2024年簡易生命表の死亡確率を年齢間で対数線形補間する。"""
    points = JAPAN_2024_MORTALITY_QX["male" if sex == "male" else "female"]
    attained_age = float(age)
    if attained_age <= points[0][0]:
        return points[0][1]
    if attained_age >= points[-1][0]:
        return points[-1][1]
    for (age0, q0), (age1, q1) in zip(points, points[1:]):
        if age0 <= attained_age <= age1:
            weight = (attained_age - age0) / (age1 - age0)
            return float(np.exp(np.log(q0) + weight * (np.log(q1) - np.log(q0))))
    return points[-1][1]


def dementia_curve(
    *, age: float, years: int, hazard_ratio: float = 1.0, sex: str = "male",
) -> dict:
    """DSDRS発症ハザードに日本の性別死亡を競合リスクとして加えた曲線。"""
    times = np.arange(0, max(0, int(years)) + 1, dtype=float)
    baseline_age = max(60.0, float(age))
    ten_year_risk = DSDRS_10_YEAR_RISK_BY_AGE[-1][2]
    for lower, upper, risk in DSDRS_10_YEAR_RISK_BY_AGE:
        if lower <= baseline_age < upper:
            ten_year_risk = risk
            break
    annual_hazard = -np.log1p(-ten_year_risk) / 10.0
    event_free_survival = 1.0
    cumulative_dementia = 0.0
    risks = [0.0]
    for elapsed in range(1, len(times)):
        attained_age = float(age) + elapsed - 1
        dementia_hazard = (
            annual_hazard * float(hazard_ratio) if attained_age >= 60 else 0.0
        )
        death_probability = annual_mortality_probability(attained_age, sex)
        death_hazard = -np.log1p(-min(0.999999, death_probability))
        total_hazard = dementia_hazard + death_hazard
        if total_hazard > 0:
            annual_event_probability = 1.0 - np.exp(-total_hazard)
            cumulative_dementia += (
                event_free_survival
                * annual_event_probability
                * dementia_hazard / total_hazard
            )
            event_free_survival *= np.exp(-total_hazard)
        risks.append(cumulative_dementia)
    return {"time": times, "risk": np.asarray(risks, dtype=float)}


def dementia_biomarker_hazard_ratio(
    *, sbp_before: float, sbp_after: float, ldl_before: float, ldl_after: float,
) -> dict[str, float]:
    """血圧・LDL低下を方法に依存せず認知症曲線へ反映する探索的換算。"""
    sbp_drop = min(30.0, max(0.0, float(sbp_before) - float(sbp_after)))
    ldl_drop = min(60.0, max(0.0, float(ldl_before) - float(ldl_after)))
    bp_hr = 0.87 ** (sbp_drop / 10.0)
    ldl_hr = 0.74 ** (ldl_drop / 60.0)
    return {"bp": bp_hr, "ldl": ldl_hr, "combined": bp_hr * ldl_hr}


def selected_dementia_evidence(
    *,
    bp_medications: Iterable[Mapping],
    lipid_medications: Iterable[Mapping],
    diabetes_medications: Iterable[Mapping],
) -> dict:
    """選択薬に対応する採用エビデンスと、採用しない根拠を返す。"""
    bp = list(bp_medications)
    lipid = list(lipid_medications)
    diabetes = list(diabetes_medications)

    supported: list[DementiaEvidence] = []
    if bp:
        supported.append(BP_LOWERING_EVIDENCE)

    has_statin = any("スタチン" in str(med.get("category", "")) for med in lipid)
    if has_statin:
        supported.append(STATIN_EVIDENCE)

    has_glp1 = any(
        str(med.get("category", "")).startswith("GLP-1受容体作動薬")
        for med in diabetes
    )
    if has_glp1:
        supported.append(GLP1_EVIDENCE)

    has_sglt2 = any("SGLT2阻害薬" in str(med.get("category", "")) for med in diabetes)
    if has_sglt2:
        supported.append(SGLT2_EVIDENCE)

    has_metformin = any("ビグアナイド" in str(med.get("category", "")) for med in diabetes)
    if has_metformin:
        supported.append(METFORMIN_EVIDENCE)

    supported_glucose_categories = ("GLP-1受容体作動薬", "SGLT2阻害薬", "ビグアナイド")
    has_other_glucose_drug = any(
        not any(
            str(med.get("category", "")).startswith(category)
            for category in supported_glucose_categories
        )
        for med in diabetes
    )

    return {
        "supported": supported,
        "has_statin": has_statin,
        "has_other_glucose_drug": has_other_glucose_drug,
    }
