"""認知症予防に関する介入エビデンスの表示判定。

患者別の認知症絶対リスクを推定するモジュールではない。無作為化試験で
認知症発症との関連が示された介入だけを、研究集団での相対効果として返す。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


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
    relative_effect="認知症・認知障害オッズ 約45%低下",
    estimate=0.55,
    estimate_type="OR",
    evidence_summary=(
        "心血管保護作用を持つ糖尿病薬のRCTメタ解析（26試験・164,531人）。"
        "GLP-1受容体作動薬では認知症・認知障害 OR 0.55（95%CI 0.35–0.86）。"
        "認知症を主要評価項目とした試験ではないため、確認試験が必要。"
    ),
    source_url=(
        "https://consensus.app/papers/cardioprotective-glucoselowering-agents-and-dementia-"
        "seminer-mulihano/bb7ccbb1ba7158fbb51ab40119bb5f8b/"
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
