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


STATIN_EVIDENCE_URL = (
    "https://consensus.app/papers/association-of-lipidlowering-therapy-with-dementia-and-"
    "reddin-stankard/d0fb13490ace5644b6f64e7e9da308ae/"
)

GLUCOSE_CONTROL_EVIDENCE_URL = (
    "https://consensus.app/papers/intensive-glycaemic-control-and-cognitive-decline-in-"
    "tuligenga/f925f67fae395a138ee56e39d5972076/"
)


DSDRS_AGE_INCIDENCE_PER_10000 = (
    (60, 65, 82.9),
    (65, 70, 169.5),
    (70, 75, 294.1),
    (75, 80, 508.1),
    (80, 85, 815.9),
    (85, 90, 1001.1),
    (90, 200, 1152.6),
)

DSDRS_EVIDENCE_URL = (
    "https://consensus.app/papers/risk-score-for-prediction-of-10-year-dementia-risk-in-"
    "exalto-biessels/ba8f28761c10508a89fc8c000e3c93e3/"
)


def dementia_curve(*, age: float, years: int, hazard_ratio: float = 1.0) -> dict:
    """年齢別発症率を積算した10年以内の認知症曲線。"""
    validated_years = min(max(0, int(years)), 10)
    times = np.arange(0, validated_years + 1, dtype=float)
    survival = 1.0
    risks = [0.0]
    for elapsed in range(1, len(times)):
        attained_age = float(age) + elapsed - 1
        annual_rate = 0.0
        for lower, upper, rate in DSDRS_AGE_INCIDENCE_PER_10000:
            if lower <= attained_age < upper:
                annual_rate = rate / 10000.0
                break
        survival *= np.exp(-annual_rate * float(hazard_ratio))
        risks.append(1.0 - survival)
    return {"time": times, "risk": np.asarray(risks, dtype=float)}


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

    has_glp1 = any(
        str(med.get("category", "")).startswith("GLP-1受容体作動薬")
        for med in diabetes
    )
    if has_glp1:
        supported.append(GLP1_EVIDENCE)

    has_statin = any("スタチン" in str(med.get("category", "")) for med in lipid)
    has_other_glucose_drug = bool(diabetes) and not has_glp1

    return {
        "supported": supported,
        "has_statin": has_statin,
        "has_other_glucose_drug": has_other_glucose_drug,
    }
