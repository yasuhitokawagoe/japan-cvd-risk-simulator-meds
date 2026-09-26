"""文献に基づく食事・運動介入の効果量。

効果は血圧・LDL・HbA1c・BMIへ反映し、その後は既存のアウトカム計算エンジンを使う。
危険因子を介した効果と重複するハードエンドポイントRRは直接掛けない。
"""
from __future__ import annotations

from dataclasses import dataclass
import math
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
    bmi_delta: float = 0.0
    is_diet_pattern: bool = False
    minimum_bmi: float | None = None


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
    "dash": LifestyleEffect(
        key="dash", label="野菜・低脂肪乳製品を増やす減塩食",
        definition="塩分と脂身の多い食品を控え、野菜・果物・全粒穀物を増やす。牛乳やヨーグルトは低脂肪のものを選ぶ。",
        sbp_delta=-3.94, ldl_delta_mg=-3.53, bmi_delta=-0.64,
        is_diet_pattern=True, population="慢性疾患を有する成人（糖尿病に限定しない）",
        evidence_summary="研究上の名称：DASH食。54試験のRCTメタ解析（Lari 2021）。対照食との差：SBP -3.94 mmHg、LDL -3.53 mg/dL、BMI -0.64。HbA1c低下はこの設定には追加しない。",
        endpoint_evidence="各指標を既存モデルへ入力。減塩・飽和脂肪制限は別加算しない。BMIの自動低下は現在BMI 25以上に限定するモデル上の制約。",
        source_url="https://consensus.app/papers/the-effects-of-the-dietary-approaches-to-stop-hypertension-lari-sohouli/f326efe690415dc1b8024b7e83b1925a/?utm_source=chatgpt",
    ),
    "mediterranean": LifestyleEffect(
        key="mediterranean", label="魚・野菜中心で、油の質を見直す食事",
        definition="魚・豆・野菜を中心に、牛・豚などの肉や加工肉を控える。油はオリーブ油を使い、ナッツや全粒穀物も取り入れる（飲酒は勧めません）。",
        ldl_delta_mg=-8.06, a1c_delta=-0.307, bmi_delta=-0.828,
        is_diet_pattern=True, requires_diabetes=True, population="2型糖尿病成人",
        evidence_summary="研究上の名称：地中海食。11 RCT（10報）のメタ解析（Wu 2025）。対照食との差：HbA1c -0.307ポイント、LDL -8.06 mg/dL、BMI -0.828。SBP -5.13 mmHgの95%CIは -10.877〜+0.617で不確実なため、SBP係数は保守的に0とする。効果がないと証明された意味ではない。",
        endpoint_evidence="PREDIMEDの心血管複合イベントHRを各アウトカムへ一律に掛けない。BMIの自動低下は現在BMI 25以上に限定するモデル上の制約。",
        source_url="https://consensus.app/papers/impact-of-the-mediterranean-diet-on-glycemic-control-body-wu-hung/12975e39342b5761854a06648467de4b/?utm_source=chatgpt",
    ),
    "meal_replacement": LifestyleEffect(
        key="meal_replacement", label="専用の食品に置き換える減量食",
        definition="医師・管理栄養士と相談し、普段の食事を、必要な栄養を調整した専用の飲料に置き換える。単に食事量を減らす方法とは別の設定です。",
        sbp_delta=-4.97, a1c_delta=-0.43, bmi_delta=-0.87,
        is_diet_pattern=True, requires_diabetes=True, minimum_bmi=25.0,
        population="過体重・肥満を伴う2型糖尿病成人（アプリでは現在BMI 25以上）",
        evidence_summary="研究上の名称：液体食事置換（Liquid meal replacements）。9試験比較・961人、追跡中央値24週のRCTメタ解析（Noronha 2019）。従来の減量食との差：SBP -4.97 mmHg、HbA1c -0.43ポイント、BMI -0.87。脂質への明確な効果は採用しない。エビデンスの確実性は低〜中等度。",
        endpoint_evidence="数値は通常の減量食に対する追加差で、食事療法前からの総減量ではない。現在BMI 25未満には全係数を適用しない。薬の自己減量・中止には使わない。",
        source_url="https://consensus.app/papers/the-effect-of-liquid-meal-replacements-on-cardiometabolic-noronha-nishi/8df5b77d72f6530c8501c2d5a9341ffd/?utm_source=chatgpt",
    ),
}

DIET_COMPONENT_KEYS = tuple(k for k, e in DIET_EFFECTS.items() if not e.is_diet_pattern)
DIET_PATTERN_KEYS = tuple(k for k, e in DIET_EFFECTS.items() if e.is_diet_pattern)


def validate_diet_selection(diet_keys: Iterable[str]) -> list[str]:
    """Components may be combined; a whole-diet pattern must stand alone."""
    keys = list(dict.fromkeys(k for k in diet_keys if k in DIET_EFFECTS))
    if len(keys) > 1 and any(k in DIET_PATTERN_KEYS for k in keys):
        raise ValueError("食事パターンは1種類だけ選び、個別の減塩・糖質・脂肪制限とは重ねないでください。")
    return keys


# Michielsen et al., Fig. 3 (DOI: 10.1186/s12933-025-03048-1).
# LDL: mmol/L * 38.67 -> mg/dL, rounded to two decimals.
# CAT SBP is -1.24 in Fig. 3 / abstract; the prose reports -1.14 (inconsistent).
EXERCISE_SOURCE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12859889/"

EXERCISE_EFFECTS = {
    "aerobic_moderate": LifestyleEffect(
        key="aerobic_moderate", label="中強度有酸素運動",
        definition="3.0-5.9 METs、週150-210分（速歩など）",
        sbp_delta=-1.24, ldl_delta_mg=-7.35, a1c_delta=-0.62,
        population="2型糖尿病成人", requires_diabetes=True,
        evidence_summary="100 RCT・7,195人の解析。運動種別の平均値：SBP -1.24 mmHg、LDL -7.35 mg/dL、HbA1c -0.62ポイント（図3）。個人の効果を保証する値ではない。",
        endpoint_evidence="死亡率データは主に観察研究のため直接RRは掛けない。",
        source_url=EXERCISE_SOURCE_URL,
    ),
    "combined": LifestyleEffect(
        key="combined", label="有酸素＋筋力トレーニング",
        definition="中強度有酸素運動＋週2-3回の筋力トレーニング、計150-210分/週",
        sbp_delta=-2.94, ldl_delta_mg=-11.99, a1c_delta=-0.74,
        population="2型糖尿病成人", requires_diabetes=True,
        evidence_summary="100 RCT・7,195人の解析。運動種別の平均値：SBP -2.94 mmHg、LDL -11.99 mg/dL、HbA1c -0.74ポイント（図3）。個人の効果を保証する値ではない。",
        endpoint_evidence="死亡率データは主に観察研究のため直接RRは掛けない。",
        source_url=EXERCISE_SOURCE_URL,
    ),
    "hiit": LifestyleEffect(
        key="hiit", label="高強度インターバル運動",
        definition="6 METs以上の高強度区間と回復区間を反復（医療者確認が必要）",
        sbp_delta=-2.64, ldl_delta_mg=-11.21, a1c_delta=-0.71,
        population="2型糖尿病成人", requires_diabetes=True,
        evidence_summary="100 RCT・7,195人の解析。運動種別の平均値：SBP -2.64 mmHg、LDL -11.21 mg/dL、HbA1c -0.71ポイント（図3）。個人の効果を保証する値ではない。",
        endpoint_evidence="中強度より死亡率をさらに下げる確証なし。直接RRは掛けない。",
        source_url=EXERCISE_SOURCE_URL,
    ),
}


def apply_lifestyle_effects(*, sbp: float, ldl: float, a1c: float | None,
                            diet_keys: Iterable[str] = (), exercise_key: str | None = None,
                            diabetes_context: bool = False, bmi: float | None = None) -> dict:
    selected = [DIET_EFFECTS[k] for k in validate_diet_selection(diet_keys)]
    if bmi is not None and (not math.isfinite(bmi) or bmi <= 0):
        raise ValueError("BMIは正の有限値で指定してください。")
    if exercise_key in EXERCISE_EFFECTS:
        selected.append(EXERCISE_EFFECTS[exercise_key])
    applied, skipped = [], []
    out_sbp, out_ldl = float(sbp), float(ldl)
    out_a1c = float(a1c) if a1c is not None else None
    out_bmi = float(bmi) if bmi is not None else None
    skip_reasons = []
    for effect in selected:
        if effect.requires_diabetes and not diabetes_context:
            skipped.append(effect)
            skip_reasons.append(f"{effect.label}：2型糖尿病の効果量のため、糖尿病以外には適用しません。")
            continue
        if effect.minimum_bmi is not None and (bmi is None or bmi < effect.minimum_bmi):
            skipped.append(effect)
            skip_reasons.append(f"{effect.label}：現在BMI {effect.minimum_bmi:g}以上を対象とする設定のため、効果は適用していません。")
            continue
        out_sbp += effect.sbp_delta
        out_ldl = out_ldl * (1.0 + effect.ldl_relative) + effect.ldl_delta_mg
        if out_a1c is not None:
            out_a1c += effect.a1c_delta
        # A conservative applicability guard, not a trial-derived dose response.
        # Do not automatically prescribe weight loss at a normal/low BMI.
        if effect.bmi_delta and out_bmi is not None and bmi >= 25.0:
            out_bmi = max(18.5, out_bmi + effect.bmi_delta)
        applied.append(effect)
    return {
        "sbp": max(80.0, out_sbp), "ldl": max(20.0, out_ldl),
        "a1c": max(4.0, out_a1c) if out_a1c is not None else None,
        "bmi": out_bmi, "applied": applied, "skipped": skipped, "skip_reasons": skip_reasons,
    }
