"""文献に基づく食事・運動介入の効果量。

効果は血圧・LDL・HbA1cへ反映し、その後は既存のアウトカム計算エンジンを使う。
危険因子を介した効果と重複するハードエンドポイントRRは直接掛けない。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class LifestyleEffect:
    key: str
    label: str
    definition: str
    sbp_delta: float = 0.0
    ldl_delta_mg: float = 0.0
    ldl_relative: float = 0.0
    a1c_delta: float = 0.0
    population: str = "成人"
    evidence_summary: str = ""
    endpoint_evidence: str = ""
    source_url: str = ""
    requires_diabetes: bool = False


DIET_EFFECTS = {
    "salt": LifestyleEffect(
        key="salt", label="減塩", definition="食塩摂取量を減らす（目安6g/日未満）",
        sbp_delta=-4.26,
        evidence_summary="133試験・12,197人のRCTメタ解析。平均SBP -4.26 mmHg、DBP -2.07 mmHg。",
        endpoint_evidence="イベントRCTは不足。血圧低下を介して既存モデルへ反映。",
        source_url="https://consensus.app/papers/effect-of-dose-and-duration-of-reduction-in-dietary-sodium-huang-trieu/372f847fb1c05c3fb3345df923ce3856/",
    ),
    "carb": LifestyleEffect(
        key="carb", label="糖質制限", definition="糖質130g/日未満または総エネルギーの26%未満を目安",
        a1c_delta=-0.36, requires_diabetes=True,
        population="過体重・肥満を伴う2型糖尿病",
        evidence_summary="17 RCT・1,197人のメタ解析。HbA1c -0.36%。LDLへの有意な効果なし。",
        endpoint_evidence="長期ハードエンドポイントの直接RCT根拠なし。HbA1c低下を介して反映。",
        source_url="https://consensus.app/papers/the-effects-of-lowcarbohydrate-diet-on-glucose-and-lipid-tian-cao/1e38e99b73365874ae76fa1c988623ba/",
    ),
    "fat": LifestyleEffect(
        key="fat", label="飽和脂肪制限", definition="飽和脂肪を総エネルギー7%未満とし、不飽和脂肪へ置換",
        ldl_relative=-0.09,
        evidence_summary="NHLBI TLCの推定範囲（LDL 8-10%低下）の中点9%を採用。",
        endpoint_evidence="低リスク一次予防では直接イベント利益は小さく不確実。LDL低下のみ反映。",
        source_url="https://www.nhlbi.nih.gov/sites/default/files/publications/Your_Guide_to_Lowering_Your_Cholesterol_with_TLC.pdf",
    ),
}


EXERCISE_EFFECTS = {
    "aerobic_moderate": LifestyleEffect(
        key="aerobic_moderate", label="中強度有酸素運動",
        definition="3.0-5.9 METs、週150-210分（速歩など）",
        sbp_delta=-1.24, ldl_delta_mg=-6.96, a1c_delta=-0.62,
        population="2型糖尿病成人", requires_diabetes=True,
        evidence_summary="100 RCT・7,195人。持続的有酸素運動でHbA1c -0.62%。SBP/LDLは保守的下限。",
        endpoint_evidence="死亡率データは主に観察研究のため直接RRは掛けない。",
        source_url="https://consensus.app/papers/the-effect-of-exercise-characteristics-on-hba1c-and-other-michielsen-yagiz/64edf5b242b4590abba16d5d9d958843/",
    ),
    "combined": LifestyleEffect(
        key="combined", label="有酸素＋筋力トレーニング",
        definition="中強度有酸素運動＋週2-3回の筋力トレーニング、計150-210分/週",
        sbp_delta=-1.24, ldl_delta_mg=-6.96, a1c_delta=-0.74,
        population="2型糖尿病成人", requires_diabetes=True,
        evidence_summary="100 RCT・7,195人。複合運動でHbA1c -0.74%（最も大きい）。SBP/LDLは保守的下限。",
        endpoint_evidence="死亡率データは主に観察研究のため直接RRは掛けない。",
        source_url="https://consensus.app/papers/the-effect-of-exercise-characteristics-on-hba1c-and-other-michielsen-yagiz/64edf5b242b4590abba16d5d9d958843/",
    ),
    "hiit": LifestyleEffect(
        key="hiit", label="高強度インターバル運動",
        definition="6 METs以上の高強度区間と回復区間を反復（医療者確認が必要）",
        sbp_delta=-1.24, ldl_delta_mg=-6.96, a1c_delta=-0.71,
        population="2型糖尿病成人", requires_diabetes=True,
        evidence_summary="100 RCT・7,195人。HIITでHbA1c -0.71%。SBP/LDLは保守的下限。",
        endpoint_evidence="中強度より死亡率をさらに下げる確証なし。直接RRは掛けない。",
        source_url="https://consensus.app/papers/do-vigorousintensity-and-moderateintensity-physical-lopez-sabag/23c6bd3a32d054b7bdebecfc8282dbb4/",
    ),
}


def apply_lifestyle_effects(*, sbp: float, ldl: float, a1c: float,
                            diet_keys: Iterable[str] = (), exercise_key: str | None = None,
                            diabetes_context: bool = False) -> dict:
    selected = [DIET_EFFECTS[k] for k in diet_keys if k in DIET_EFFECTS]
    if exercise_key in EXERCISE_EFFECTS:
        selected.append(EXERCISE_EFFECTS[exercise_key])
    applied, skipped = [], []
    out_sbp, out_ldl, out_a1c = float(sbp), float(ldl), float(a1c)
    for effect in selected:
        if effect.requires_diabetes and not diabetes_context:
            skipped.append(effect)
            continue
        out_sbp += effect.sbp_delta
        out_ldl = out_ldl * (1.0 + effect.ldl_relative) + effect.ldl_delta_mg
        out_a1c += effect.a1c_delta
        applied.append(effect)
    return {
        "sbp": max(80.0, out_sbp), "ldl": max(20.0, out_ldl), "a1c": max(4.0, out_a1c),
        "applied": applied, "skipped": skipped,
    }
