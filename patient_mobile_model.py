"""Patient-facing scenarios using the existing PC engines, with no new coefficients."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, prod
from pathlib import Path

from calc_engine_outcomes import OutcomesEngine
from dementia_prevention import (
    dementia_biomarker_hazard_ratio, dementia_curve, selected_dementia_evidence,
)
from dm_outcomes import ACR_CATEGORY_MG_G, DIABETES_OUTCOMES, DiabetesOutcomeModel
from lifestyle_interventions import apply_lifestyle_effects, validate_diet_selection
from meds_catalog import apply_meds_to_targets
from treatment_backcast import reconstruct_untreated_values


OUTCOME_LABELS = {
    "mi": "心筋梗塞", "stroke": "脳卒中", "mortality": "死亡（すべての原因）",
    "dementia": "認知症（参考推定）", "esrd": "透析",
    "amputation": "足の大きな切断", "blindness": "失明",
}
BP_CATALOG = "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx"
LIPID_CATALOG = "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx"
DIABETES_STATUS_LABELS = {
    "unknown": "分からない・未確認", "none": "糖尿病とは診断されていない",
    "type2": "2型糖尿病と診断されている", "other": "1型・その他の糖尿病／型が分からない",
}


@dataclass(frozen=True)
class PatientInputs:
    age: int
    sex: str
    sbp: float
    ldl: float
    a1c: float | None = None
    bmi: float | None = None
    egfr: float | None = None
    acr: str | None = None
    smoking_status: str = "never"
    cigs_per_day: int = 0
    years_smoked: int = 0
    years_since_quit: int = 0
    diabetes_status: str = "unknown"

    def __post_init__(self):
        if self.diabetes_status not in DIABETES_STATUS_LABELS:
            raise ValueError("糖尿病の診断状況を確認してください。")
        limits = {"age": (20, 95), "sbp": (90, 200), "ldl": (50, 250)}
        if self.has_type2_diabetes or self.a1c is not None:
            limits["a1c"] = (5 if self.has_type2_diabetes else 4, 12)
        for key, (low, high) in limits.items():
            value = getattr(self, key)
            if value is None or not isfinite(value) or not low <= value <= high:
                raise ValueError(f"{key}が計算範囲外です（{low}〜{high}）。")
        if int(self.age) != self.age or self.sex not in ("male", "female"):
            raise ValueError("年齢・性別を確認してください。")
        for key, low, high in (("bmi", 10, 50), ("egfr", 5, 120)):
            value = getattr(self, key)
            if value is not None and (not isfinite(value) or not low <= value <= high):
                raise ValueError(f"{key}が計算範囲外です（{low}〜{high}）。")
        if self.acr is not None and self.acr not in ACR_CATEGORY_MG_G:
            raise ValueError("尿アルブミンの区分を確認してください。")
        if self.smoking_status not in ("never", "current", "former"):
            raise ValueError("喫煙状況を選んでください。")
        for value, upper in ((self.cigs_per_day, 40), (self.years_smoked, 80), (self.years_since_quit, 80)):
            if not isfinite(value) or not 0 <= value <= upper:
                raise ValueError("喫煙の本数・年数を確認してください。")

    @property
    def has_type2_diabetes(self):
        return self.diabetes_status == "type2"

    @property
    def markers(self):
        return {"sbp": float(self.sbp), "ldl": float(self.ldl),
                "a1c": float(self.a1c) if self.a1c is not None else None, "bmi": self.bmi}


def group_medications(medications):
    result = {"sbp": [], "ldl": [], "hba1c": []}
    names = set()
    for med in medications:
        identity = (med["domain"], med.get("drug_name", med["key"]))
        if identity in names:
            raise ValueError("同じ薬の量を重複して選ばないでください。")
        names.add(identity)
        result[med["domain"]].append(med)
    return result


def _medication_dementia_hr(grouped):
    evidence = selected_dementia_evidence(
        bp_medications=grouped["sbp"], lipid_medications=grouped["ldl"],
        diabetes_medications=grouped["hba1c"],
    )
    return prod(e.estimate for e in evidence["supported"] if e.key != "bp_lowering")


def _biomarker_hr(before, after):
    return dementia_biomarker_hazard_ratio(
        sbp_before=before["sbp"], sbp_after=after["sbp"],
        ldl_before=before["ldl"], ldl_after=after["ldl"],
    )["combined"]


def _empty_curve():
    return {key: [0.0] for key in (
        "time", "baseline_cumulative", "target_cumulative", "baseline_ci_lower",
        "baseline_ci_upper", "target_ci_lower", "target_ci_upper",
    )}


def predict_pair(patient, target, years, *, engine, dementia_hr=(1.0, 1.0)):
    """Same inputs, conventions and CI calls as the PC application."""
    curves = {}
    for outcome in ("mi", "stroke", "mortality"):
        data = _empty_curve()
        for year in range(1, years + 1):
            result = engine.cumulative_incidence_with_ci(
                outcome, patient.sex, patient.age, year,
                patient.sbp, target["sbp"], patient.ldl, target["ldl"],
                patient.a1c, target["a1c"], patient.smoking_status,
                patient.cigs_per_day, patient.years_smoked, patient.years_since_quit, False,
                bmi_now=patient.bmi, bmi_target=target["bmi"],
                egfr_now=patient.egfr, egfr_target=patient.egfr,
                acr_now=patient.acr, acr_target=patient.acr,
                apply_hba1c_effect=patient.has_type2_diabetes,
            )
            data["time"].append(float(year))
            for scenario in ("baseline", "target"):
                for field, source in (("cumulative", "point"), ("ci_lower", "lower"), ("ci_upper", "upper")):
                    data[f"{scenario}_{field}"].append(float(result[source][scenario]) * 100)
        curves[outcome] = data
    # Unknown kidney results are not silently filled with healthy default values.
    if patient.has_type2_diabetes and patient.egfr is not None and patient.acr is not None:
        dm_engine = DiabetesOutcomeModel()
        for outcome in DIABETES_OUTCOMES:
            common = dict(age=patient.age, egfr=patient.egfr, acr=ACR_CATEGORY_MG_G[patient.acr],
                          sex=1 if patient.sex == "male" else 0, years=years)
            baseline = dm_engine.predict_curve_with_ci(outcome, hba1c=patient.a1c, sbp=patient.sbp, **common)
            improved = dm_engine.predict_curve_with_ci(outcome, hba1c=target["a1c"], sbp=target["sbp"], **common)
            data = {"time": baseline["time"].tolist()}
            for scenario, values in (("baseline", baseline), ("target", improved)):
                for field, source in (("cumulative", "risk"), ("ci_lower", "lower"), ("ci_upper", "upper")):
                    data[f"{scenario}_{field}"] = (values[source] * 100).tolist()
            curves[outcome] = data
    # The current dementia baseline is calibrated for type 2 diabetes as well.
    if not patient.has_type2_diabetes:
        return curves
    baseline = dementia_curve(age=patient.age, years=years, hazard_ratio=dementia_hr[0], sex=patient.sex)
    improved = dementia_curve(age=patient.age, years=years, hazard_ratio=dementia_hr[1], sex=patient.sex)
    data = {"time": baseline["time"].tolist()}
    for scenario, values in (("baseline", baseline), ("target", improved)):
        for field in ("cumulative", "ci_lower", "ci_upper"):
            data[f"{scenario}_{field}"] = (values["risk"] * 100).tolist()
    curves["dementia"] = data
    return curves


def swap_sides(curves):
    return {
        outcome: {
            "time": list(data["time"]),
            **{f"{side}_{field}": list(data[f"{other}_{field}"])
               for side, other in (("baseline", "target"), ("target", "baseline"))
               for field in ("cumulative", "ci_lower", "ci_upper")},
        }
        for outcome, data in curves.items()
    }


def calculate_mobile_scenarios(patient: PatientInputs, *, mode: str,
                               current_medications=(), proposed_medications=(),
                               medications_complete=False, diet_keys=(), exercise_key=None,
                               years=10, engine=None):
    if mode not in ("without", "with"):
        raise ValueError("薬を使っているか選んでください。")
    if mode == "without" and current_medications:
        raise ValueError("薬なしの入口に現在の薬を引き継げません。")
    if mode == "with" and proposed_medications:
        raise ValueError("薬ありの入口では新たな薬の試算を混ぜません。")
    if years not in (5, 10, 20):
        raise ValueError("予測期間は5・10・20年から選んでください。")
    years = min(years, 110 - int(patient.age))
    if engine is None:
        engine = OutcomesEngine(str(Path(__file__).with_name("config.yaml")))
    diet_keys = validate_diet_selection(diet_keys)
    current = group_medications(current_medications)
    proposed = group_medications(proposed_medications)
    type2 = patient.has_type2_diabetes
    current_has_unmodeled_drugs = bool(current["hba1c"] and not type2)
    proposed_has_unmodeled_drugs = bool(proposed["hba1c"] and not type2)
    starting = patient.markers
    warnings = []
    if not type2:
        warnings.append("糖尿病がなくても、血圧・脂質などから心筋梗塞・脳卒中・全死亡を試算できます。HbA1cによる効果補正は行いません。")
        warnings.append("透析・足の切断・失明と、現在の認知症の基礎曲線は2型糖尿病向けのため、今回は表示しません。")
        if current_has_unmodeled_drugs or proposed_has_unmodeled_drugs:
            warnings.append("血糖に作用する薬の登録効果量は2型糖尿病向けのため反映しません。別の病気に対する薬効は未評価です。")
        # A prescription or an HbA1c value is not a diagnosis of type 2 diabetes.
        current["hba1c"] = []
        proposed["hba1c"] = []
    if patient.bmi is None:
        warnings.append("身長・体重が未入力のため、BMIによる補正・減量の反映はしていません。")
    if patient.egfr is None or patient.acr is None:
        warnings.append("腎機能の情報が不足しています。未入力項目の腎機能補正は行いません。" +
                        ("透析・足の切断・失明の推定も表示しません。" if type2 else ""))

    untreated = None
    med_comparison = None
    dementia_base_hr = 1.0
    if mode == "without" and proposed_medications:
        medications = apply_meds_to_targets(
            patient.sbp, patient.ldl, patient.a1c, proposed["sbp"], proposed["ldl"], proposed["hba1c"],
        )
        starting = {"sbp": medications["sbp_target"], "ldl": medications["ldl_target"],
                    "a1c": medications["a1c_target"] if type2 else patient.a1c, "bmi": patient.bmi}
    elif mode == "with":
        if medications_complete and current_medications and not current_has_unmodeled_drugs:
            untreated = reconstruct_untreated_values(
                sbp_now=patient.sbp, ldl_now=patient.ldl, a1c_now=patient.a1c,
                sbp_meds=current["sbp"], ldl_meds=current["ldl"], a1c_meds=current["hba1c"],
            )
            untreated["bmi"] = patient.bmi
            if not type2:
                untreated["a1c"] = patient.a1c
            if type2:
                dementia_base_hr = _medication_dementia_hr(current) * _biomarker_hr(untreated, patient.markers)
            # Reverse the PC "continue vs stop" display, not its calculation.
            med_comparison = {
                "before_label": "薬がなかった場合（推定）", "after_label": "今の薬を続ける",
                "curves": swap_sides(predict_pair(patient, untreated, years, engine=engine,
                                                   dementia_hr=(dementia_base_hr, 1.0))),
            }
        else:
            reason = "対象外の効果量を使う薬が含まれる" if current_has_unmodeled_drugs else "薬の情報が未確認の"
            warnings.append(f"{reason}ため、薬がなかった場合との比較は表示しません。生活改善は今の治療を続ける前提で試算します。")

    # Current treated values are the starting point: never apply current drugs again.
    diet = apply_lifestyle_effects(**{k: starting[k] for k in ("sbp", "ldl", "a1c", "bmi")},
                                  diet_keys=diet_keys, diabetes_context=type2)
    target = apply_lifestyle_effects(**{k: diet[k] for k in ("sbp", "ldl", "a1c", "bmi")},
                                    exercise_key=exercise_key, diabetes_context=type2)
    warnings.extend(diet["skip_reasons"] + target["skip_reasons"])
    dementia_target_hr = 1.0
    if type2 and mode == "with" and untreated is not None:
        dementia_target_hr = _medication_dementia_hr(current) * _biomarker_hr(untreated, target)
    elif type2:
        dementia_target_hr = _medication_dementia_hr(proposed) * _biomarker_hr(patient.markers, target)
    lifestyle = {
        "before_label": "今の治療を続ける" if mode == "with" else "今の状態が続く",
        "after_label": "生活改善も加える" if mode == "with" else "選んだ改善を続ける",
        "curves": predict_pair(patient, target, years, engine=engine,
                               dementia_hr=(dementia_base_hr, dementia_target_hr)),
    }
    if proposed_has_unmodeled_drugs or diet["skipped"] or target["skipped"]:
        lifestyle["after_label"] = "計算できる改善だけを反映（参考）"
    return {"years": years, "lifestyle": lifestyle, "medication": med_comparison,
            "targets": {k: target[k] for k in ("sbp", "ldl", "a1c", "bmi")},
            "untreated": untreated, "warnings": warnings,
            "applied": [e.key for e in diet["applied"] + target["applied"]],
            "has_requested_changes": bool(diet_keys or exercise_key or proposed_medications),
            "has_changes": bool(diet["applied"] or target["applied"] or any(proposed.values()))}
