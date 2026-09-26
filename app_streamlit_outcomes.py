# app_streamlit_outcomes.py
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from access_analytics import record_visit, total_visits, visit_counts
from bone_health import (
    DIABETES_DRUG_FRACTURE_URL,
    DIABETES_FRACTURE_MODEL_URL,
    JAPAN_HIP_FRACTURE_URL,
    HIP_FRACTURE_TREATMENT_NMA_URL,
    OSTEOPOROSIS_DRUGS,
    OSTEOPOROSIS_TREATMENT_URL,
    bone_density_category,
    bone_health_flags,
    hip_fracture_risk,
)
from calc_engine_outcomes import OutcomesEngine
from dementia_prevention import (
    DSDRS_EVIDENCE_URL,
    JAPAN_DEMENTIA_COHORT_URL,
    LDL_LEVEL_EVIDENCE_URL,
    dementia_biomarker_hazard_ratio,
    dementia_curve,
    selected_dementia_evidence,
)
from dm_outcomes import ACR_CATEGORY_MG_G, DIABETES_OUTCOMES, DiabetesOutcomeModel
from lifestyle_interventions import DIET_EFFECTS, EXERCISE_EFFECTS, apply_lifestyle_effects
from exercise_fitness import (
    FITNESS_MORTALITY_SOURCE, FITNESS_TRAINING_SOURCE, fitness_scenario,
)
from meds_catalog import apply_meds_to_targets, load_meds_catalog
from medical_cost_ui import render_medication_costs
from risk_display import hazard_ratio_curve, format_hr, format_hazard_change
import pdf_plan_ui
from treatment_backcast import reconstruct_untreated_values


st.set_page_config(
    page_title="生活習慣病療養指導シュミレーター",
    layout="wide",
    page_icon="♥",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1500px; padding-top: 1.5rem;}
    .app-hero {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1.3rem;
        border: 1px solid #d7e7e2;
        border-radius: 18px;
        background: linear-gradient(135deg, #f4fbf9 0%, #ffffff 58%, #f7faf9 100%);
        box-shadow: 0 8px 28px rgba(15, 92, 76, 0.07);
    }
    .hero-icon {
        width: 58px;
        height: 58px;
        flex: 0 0 58px;
        display: grid;
        place-items: center;
        border-radius: 16px;
        color: white;
        background: linear-gradient(145deg, #16876f, #0b6554);
        box-shadow: 0 8px 18px rgba(20, 134, 109, 0.24);
        font-size: 1.8rem;
        line-height: 1;
    }
    .hero-copy {min-width: 0;}
    .hero-kicker {
        margin-bottom: 0.2rem;
        color: #14745f;
        font-size: 0.78rem;
        font-weight: 750;
        letter-spacing: 0.1em;
    }
    .hero-title {
        margin: 0;
        color: #193b34;
        font-size: clamp(1.55rem, 3vw, 2.25rem);
        font-weight: 780;
        line-height: 1.2;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        margin: 0.4rem 0 0;
        color: #60736e;
        font-size: 0.92rem;
        line-height: 1.55;
    }
    .hero-badge {
        margin-left: auto;
        flex: 0 0 auto;
        padding: 0.42rem 0.72rem;
        border-radius: 999px;
        color: #0d6d59;
        background: #e4f4ef;
        font-size: 0.78rem;
        font-weight: 700;
        white-space: nowrap;
    }
    .hero-badge::before {
        content: "● 累計 " attr(data-count) " アクセス";
    }
    [data-testid="stMetric"] {
        background: #f7faf9;
        border: 1px solid #dce8e4;
        border-radius: 14px;
        padding: 0.75rem 1rem;
    }
    .live-note {
        color: #37665a;
        background: #eef8f5;
        border: 1px solid #cfe6df;
        border-radius: 12px;
        padding: 0.65rem 0.85rem;
        margin-bottom: 0.8rem;
    }
    .sex-field-label::before {
        content: "性別";
        font-weight: 700;
    }
    .arr-breakdown-title {
        margin: 0 0 0.5rem;
        font-size: 1.25rem;
        font-weight: 700;
        line-height: 1.4;
    }
    .arr-breakdown-title::before {content: attr(data-title);}
    .fixed-field-label::before {
        content: attr(data-title);
        font-size: 1rem;
    }
    div[role="radiogroup"][aria-label="表示するアウトカム"]
    label:has(input[value="0"]) [data-testid="stMarkdownContainer"] p {
        font-size: 0;
    }
    div[role="radiogroup"][aria-label="表示するアウトカム"]
    label:has(input[value="0"]) [data-testid="stMarkdownContainer"] p::before {
        content: "全死亡";
        font-size: 1rem;
    }
    .contribution-row {
        display: grid;
        grid-template-columns: minmax(150px, 1.5fr) 2fr 70px;
        gap: 10px;
        align-items: center;
        margin: 8px 0;
    }
    .contribution-track {height: 9px; border-radius: 99px; background: #e7eeec; overflow: hidden;}
    .contribution-fill {height: 100%; border-radius: 99px; background: #14866d;}
    .contribution-value {text-align: right; color: #0d725c; font-weight: 700;}
    div[data-testid="stHorizontalBlock"]:has(.live-note):has(.result-anchor) > div:nth-child(2) {
        position: sticky;
        top: 1rem;
        align-self: flex-start;
        max-height: calc(100vh - 2rem);
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: #c9d8d4 transparent;
    }
    .result-anchor {height: 0; overflow: hidden;}
    @media (max-width: 900px) {
        .contribution-row {grid-template-columns: 1fr 70px;}
        .contribution-track {grid-column: 1 / -1; grid-row: 2;}
        .app-hero {align-items: flex-start; padding: 1rem;}
        .hero-icon {width: 48px; height: 48px; flex-basis: 48px; border-radius: 14px;}
        .hero-badge {display: none;}
        div[data-testid="stHorizontalBlock"]:has(.live-note):has(.result-anchor) > div:nth-child(2) {
            position: static;
            max-height: none;
            overflow-y: visible;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "access_stats" not in st.session_state:
    try:
        request_headers = dict(st.context.headers)
        st.session_state.access_stats = record_visit(request_headers)
    except Exception:
        st.session_state.access_stats = {
            "total": total_visits(),
            "prefecture": "不明",
            "country_code": "不明",
        }
access_stats = st.session_state.access_stats
try:
    # Refresh the cumulative count without creating another visit on widget reruns.
    access_stats = {**access_stats, **visit_counts()}
except Exception:
    pass
access_count_label = ("約 " if access_stats.get("historical_estimate", 0) else "") + f"{access_stats['total']:,}"

st.markdown(
    f"""
    <div class="app-hero">
      <div class="hero-icon" aria-hidden="true">♥</div>
      <div class="hero-copy">
        <div class="hero-kicker">DIABETES CARE &amp; COMPLICATION PREVENTION</div>
        <h1 class="hero-title">生活習慣病療養指導シュミレーター</h1>
        <p class="hero-subtitle">血糖・血圧・腎機能と治療による将来リスクの変化を可視化し、合併症予防の目標を一緒に考えます。教育・共有意思決定支援用。</p>
      </div>
      <div class="hero-badge" translate="no" data-count="{access_count_label}"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

engine = OutcomesEngine("config.yaml")
dm_engine = DiabetesOutcomeModel()

MORTALITY_ALL_CAUSE_DEATH_CAPTION = (
    "※全死亡は、心血管疾患に限らず、がんや他の病気を含むすべての死亡を対象としています。"
)
CARDIOVASCULAR_OUTCOMES = ("mortality", "mi", "stroke")
DIABETES_OUTCOME_KEYS = tuple(DIABETES_OUTCOMES)
OUTCOME_DISPLAY_ORDER = CARDIOVASCULAR_OUTCOMES + DIABETES_OUTCOME_KEYS + ("dementia",)
OUTCOME_META = {
    "mortality": {"label": "全死亡", "title": "全死亡", "color": "#d95656"},
    "mi": {"label": "心筋梗塞", "title": "心筋梗塞", "color": "#e07b39"},
    "stroke": {"label": "脳卒中", "title": "脳卒中", "color": "#7656c9"},
    "esrd": {"label": "透析", "title": "透析（末期腎不全）", "color": "#3f7f9f"},
    "amputation": {"label": "大切断", "title": "大切断", "color": "#9c6b3f"},
    "blindness": {"label": "失明", "title": "失明", "color": "#3e7c58"},
    "dementia": {"label": "認知症", "title": "認知症", "color": "#66558f"},
}

BP_XLSX_PATH = "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx"
LIPID_GLU_XLSX_PATH = "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx"


@st.cache_data(show_spinner=False)
def _cached_catalog(bp_path: str, lipid_glu_path: str):
    return load_meds_catalog(bp_path, lipid_glu_path)


try:
    meds_catalog = _cached_catalog(BP_XLSX_PATH, LIPID_GLU_XLSX_PATH)
    catalog_error = None
except Exception as exc:
    meds_catalog = None
    catalog_error = str(exc)


def medication_selector(label: str, medications: list[dict], key_prefix: str) -> list[dict]:
    """薬剤クラス → 種類（複数可） → 薬剤ごとの用量の順で選ぶ。"""
    categories = list(dict.fromkeys(med["category"] for med in medications))
    selected_categories = st.pills(
        "1. 薬剤クラス",
        categories,
        selection_mode="multi",
        key=f"{key_prefix}_categories",
    )
    selected: list[dict] = []
    for category in selected_categories:
        class_meds = [med for med in medications if med["category"] == category]
        drug_names = list(dict.fromkeys(med["drug_name"] for med in class_meds))
        with st.container(border=True):
            st.markdown(f"**{category}**")
            selected_drug_names = st.pills(
                "2. 種類（複数選択可）",
                drug_names,
                selection_mode="multi",
                key=f"{key_prefix}_{category}_drugs",
            )
            for drug_name in selected_drug_names:
                matching_meds = [
                    med for med in class_meds if med["drug_name"] == drug_name
                ]
                dose_labels = [med["dose_label"] for med in matching_meds]
                dose_label = st.selectbox(
                    f"3. {drug_name}の用量",
                    dose_labels,
                    key=f"{key_prefix}_{category}_{drug_name}_dose",
                )
                selected.append(
                    next(med for med in matching_meds if med["dose_label"] == dose_label)
                )
    return selected


def _years_from_choice(choice: str) -> int:
    return {"5-year": 5, "10-year": 10, "20-year": 20, "30-year": 30, "50-year": 50}[choice]


def _nudge_slider(state_key: str, delta: float, minimum: float, maximum: float, digits: int):
    current = float(st.session_state[state_key])
    st.session_state[state_key] = round(min(max(current + delta, minimum), maximum), digits)


def slider_with_nudges(
    label: str,
    minimum,
    maximum,
    initial,
    *,
    key: str,
    nudge: float,
    step=None,
    fixed_label: str | None = None,
):
    slider_kwargs = {"key": key}
    if step is not None:
        slider_kwargs["step"] = step
    if fixed_label:
        st.markdown(
            f'<div class="fixed-field-label" translate="no" '
            f'data-title="{fixed_label}"></div>',
            unsafe_allow_html=True,
        )
        slider_kwargs["label_visibility"] = "collapsed"
    st.slider(label, minimum, maximum, initial, **slider_kwargs)
    decrease, increase = st.columns(2)
    digits = 1 if isinstance(initial, float) else 0
    display_nudge = f"{nudge:.1f}" if digits else f"{int(nudge)}"
    decrease.button(
        f"−{display_nudge}",
        key=f"{key}_decrease",
        on_click=_nudge_slider,
        args=(key, -nudge, float(minimum), float(maximum), digits),
        use_container_width=True,
    )
    increase.button(
        f"＋{display_nudge}",
        key=f"{key}_increase",
        on_click=_nudge_slider,
        args=(key, nudge, float(minimum), float(maximum), digits),
        use_container_width=True,
    )
    return st.session_state[key]


def calculate_cumulative_risk_curves(years: int):
    cumulative_data = {}
    for outcome in CARDIOVASCULAR_OUTCOMES:
        cumulative_data[outcome] = {
            "baseline_cumulative": [0.0],
            "target_cumulative": [0.0],
            "baseline_ci_lower": [0.0],
            "baseline_ci_upper": [0.0],
            "target_ci_lower": [0.0],
            "target_ci_upper": [0.0],
            "time": [0.0],
        }
        for year in np.arange(1, years + 1, 1):
            if age + year > 110:
                break
            result = engine.cumulative_incidence_with_ci(
                outcome,
                sex,
                age,
                int(year),
                sbp_now,
                sbp_tgt,
                ldl_now,
                ldl_tgt,
                a1c_now,
                a1c_tgt,
                smoking_status,
                cigs_per_day,
                years_smoked,
                years_since_quit,
                quit_today,
                bmi_now=bmi_now,
                bmi_target=bmi_target if bmi_target != bmi_now else None,
                egfr_now=egfr_now,
                egfr_target=egfr_target if egfr_target != egfr_now else None,
                acr_now=acr_now,
                acr_target=acr_target if acr_target != acr_now else None,
            )
            cumulative_data[outcome]["time"].append(float(year))
            for scenario in ("baseline", "target"):
                cumulative_data[outcome][f"{scenario}_cumulative"].append(
                    result["point"][scenario] * 100.0
                )
                cumulative_data[outcome][f"{scenario}_ci_lower"].append(
                    result["lower"][scenario] * 100.0
                )
                cumulative_data[outcome][f"{scenario}_ci_upper"].append(
                    result["upper"][scenario] * 100.0
                )
    dm_common = {
        "age": float(age),
        "sex": 1 if sex == "male" else 0,
        "years": years,
    }
    for outcome in DIABETES_OUTCOME_KEYS:
        current = dm_engine.predict_curve_with_ci(
            outcome, hba1c=float(a1c_now), egfr=float(egfr_now),
            acr=ACR_CATEGORY_MG_G[acr_now], sbp=float(sbp_now), **dm_common,
        )
        target = dm_engine.predict_curve_with_ci(
            outcome, hba1c=float(a1c_tgt), egfr=float(egfr_target),
            acr=ACR_CATEGORY_MG_G[acr_target], sbp=float(sbp_tgt), **dm_common,
        )
        cumulative_data[outcome] = {
            "time": current["time"].tolist(),
            "baseline_cumulative": (current["risk"] * 100.0).tolist(),
            "target_cumulative": (target["risk"] * 100.0).tolist(),
            "baseline_ci_lower": (current["lower"] * 100.0).tolist(),
            "baseline_ci_upper": (current["upper"] * 100.0).tolist(),
            "target_ci_lower": (target["lower"] * 100.0).tolist(),
            "target_ci_upper": (target["upper"] * 100.0).tolist(),
        }

    dementia_evidence = selected_dementia_evidence(
        bp_medications=selected_sbp_meds,
        lipid_medications=selected_ldl_meds,
        diabetes_medications=selected_a1c_meds,
    )
    medication_hr = float(np.prod([
        item.estimate for item in dementia_evidence["supported"]
        if item.key != "bp_lowering"
    ]))
    if care_mode == "continue":
        biomarker_hr = dementia_biomarker_hazard_ratio(
            sbp_before=float(sbp_tgt), sbp_after=float(sbp_now),
            ldl_before=float(ldl_tgt), ldl_after=float(ldl_now),
        )["combined"]
        current_hr, target_hr = medication_hr * biomarker_hr, 1.0
    else:
        biomarker_hr = dementia_biomarker_hazard_ratio(
            sbp_before=float(sbp_now), sbp_after=float(sbp_tgt),
            ldl_before=float(ldl_now), ldl_after=float(ldl_tgt),
        )["combined"]
        current_hr, target_hr = 1.0, medication_hr * biomarker_hr
    dementia_current = dementia_curve(
        age=float(age), years=years, hazard_ratio=current_hr, sex=sex,
    )
    dementia_target = dementia_curve(
        age=float(age), years=years, hazard_ratio=target_hr, sex=sex,
    )
    current_risk = dementia_current["risk"] * 100.0
    target_risk = dementia_target["risk"] * 100.0
    cumulative_data["dementia"] = {
        "time": dementia_current["time"].tolist(),
        "baseline_cumulative": current_risk.tolist(),
        "target_cumulative": target_risk.tolist(),
        "baseline_ci_lower": current_risk.tolist(),
        "baseline_ci_upper": current_risk.tolist(),
        "target_ci_lower": target_risk.tolist(),
        "target_ci_upper": target_risk.tolist(),
    }
    return cumulative_data


def calculate_past_treatment_benefit(years: int) -> dict:
    """治療開始から現在までの、無治療との累積リスク差を推定する。"""
    start_age = max(20, int(age) - int(years))
    result = {}
    for outcome in CARDIOVASCULAR_OUTCOMES:
        untreated_curve = [0.0]
        treated_curve = [0.0]
        for elapsed in range(1, int(years) + 1):
            risk = engine.cumulative_incidence(
                outcome, sex, start_age, elapsed,
                float(sbp_tgt), float(sbp_now),
                float(ldl_tgt), float(ldl_now),
                float(a1c_tgt), float(a1c_now),
                smoking_status, cigs_per_day, years_smoked, years_since_quit,
                assume_quit_today_in_target=False,
            )
            untreated_curve.append(float(risk["baseline"]) * 100.0)
            treated_curve.append(float(risk["target"]) * 100.0)
        result[outcome] = {
            "time": list(range(-int(years), 1)),
            "untreated": untreated_curve,
            "treated": treated_curve,
            "avoided": max(0.0, untreated_curve[-1] - treated_curve[-1]),
        }

    dm_common = {
        "age": float(start_age), "sex": 1 if sex == "male" else 0,
        "years": int(years),
    }
    for outcome in DIABETES_OUTCOME_KEYS:
        untreated_dm = dm_engine.predict_curve_with_ci(
            outcome, hba1c=float(a1c_tgt), egfr=float(egfr_now),
            acr=ACR_CATEGORY_MG_G[acr_now], sbp=float(sbp_tgt), **dm_common,
        )
        treated_dm = dm_engine.predict_curve_with_ci(
            outcome, hba1c=float(a1c_now), egfr=float(egfr_now),
            acr=ACR_CATEGORY_MG_G[acr_now], sbp=float(sbp_now), **dm_common,
        )
        untreated_curve = (untreated_dm["risk"] * 100.0).tolist()
        treated_curve = (treated_dm["risk"] * 100.0).tolist()
        result[outcome] = {
            "time": list(range(-int(years), 1)),
            "untreated": untreated_curve,
            "treated": treated_curve,
            "avoided": max(0.0, untreated_curve[-1] - treated_curve[-1]),
        }

    dementia_evidence = selected_dementia_evidence(
        bp_medications=selected_sbp_meds,
        lipid_medications=selected_ldl_meds,
        diabetes_medications=selected_a1c_meds,
    )
    medication_hr = float(np.prod([
        item.estimate for item in dementia_evidence["supported"]
        if item.key != "bp_lowering"
    ]))
    biomarker_hr = dementia_biomarker_hazard_ratio(
        sbp_before=float(sbp_tgt), sbp_after=float(sbp_now),
        ldl_before=float(ldl_tgt), ldl_after=float(ldl_now),
    )["combined"]
    treatment_hr = medication_hr * biomarker_hr
    untreated_dementia_result = dementia_curve(
        age=float(start_age), years=int(years), sex=sex,
    )
    treated_dementia_result = dementia_curve(
        age=float(start_age), years=int(years), hazard_ratio=treatment_hr, sex=sex,
    )
    untreated_dementia = untreated_dementia_result["risk"] * 100.0
    treated_dementia = treated_dementia_result["risk"] * 100.0
    dementia_years = len(untreated_dementia) - 1
    result["dementia"] = {
        "time": list(range(-dementia_years, 1)),
        "untreated": untreated_dementia.tolist(),
        "treated": treated_dementia.tolist(),
        "avoided": max(0.0, untreated_dementia[-1] - treated_dementia[-1]),
    }

    mortality = result["mortality"]
    survival_gain = np.asarray(mortality["untreated"]) - np.asarray(mortality["treated"])
    result["estimated_life_years_gained"] = max(
        0.0, float(np.trapezoid(survival_gain / 100.0, dx=1.0))
    )
    return result


def risk_at_horizon(outcome: str, horizon: int, targets: dict) -> float:
    if outcome in DIABETES_OUTCOME_KEYS:
        return dm_engine.predict_risk(
            outcome, hba1c=float(targets["a1c_target"]), age=float(age),
            egfr=float(egfr_target), acr=ACR_CATEGORY_MG_G[acr_target],
            sbp=float(targets["sbp_target"]), sex=1 if sex == "male" else 0,
            years=horizon,
        )
    result = engine.cumulative_incidence_with_ci(
        outcome,
        sex,
        age,
        horizon,
        sbp_now,
        targets["sbp_target"],
        ldl_now,
        targets["ldl_target"],
        a1c_now,
        targets["a1c_target"],
        smoking_status,
        cigs_per_day,
        years_smoked,
        years_since_quit,
        quit_today,
        bmi_now=bmi_now,
        bmi_target=bmi_target if bmi_target != bmi_now else None,
        egfr_now=egfr_now,
        egfr_target=egfr_target if egfr_target != egfr_now else None,
        acr_now=acr_now,
        acr_target=acr_target if acr_target != acr_now else None,
    )
    return float(result["point"]["target"])


def build_medication_contributions(outcome: str, horizon: int):
    ordered_meds = selected_sbp_meds + selected_ldl_meds + selected_a1c_meds
    if outcome == "dementia":
        running_risk = dementia_curve(
            age=float(age), years=horizon, sex=sex,
        )["risk"][-1]
        running_hr = 1.0
        contributions = []
        evidence_set = selected_dementia_evidence(
            bp_medications=selected_sbp_meds,
            lipid_medications=selected_ldl_meds,
            diabetes_medications=selected_a1c_meds,
        )
        biomarker_effects = dementia_biomarker_hazard_ratio(
            sbp_before=float(sbp_now), sbp_after=float(sbp_tgt),
            ldl_before=float(ldl_now), ldl_after=float(ldl_tgt),
        )
        for label, effect in (
            ("血圧低下（方法を問わず）", biomarker_effects["bp"]),
            ("LDL低下（方法を問わず）", biomarker_effects["ldl"]),
        ):
            if effect >= 0.999999:
                continue
            next_hr = running_hr * effect
            next_risk = dementia_curve(
                age=float(age), years=horizon, hazard_ratio=next_hr, sex=sex,
            )["risk"][-1]
            contributions.append({
                "name": label,
                "delta": max(0.0, (running_risk - next_risk) * 100.0),
            })
            running_risk, running_hr = next_risk, next_hr
        for evidence in evidence_set["supported"]:
            if evidence.key == "bp_lowering":
                continue
            next_hr = running_hr * evidence.estimate
            next_risk = dementia_curve(
                age=float(age), years=horizon, hazard_ratio=next_hr, sex=sex,
            )["risk"][-1]
            contributions.append({
                "name": evidence.label,
                "delta": max(0.0, (running_risk - next_risk) * 100.0),
            })
            running_risk, running_hr = next_risk, next_hr
        return contributions

    if not ordered_meds and not diet_intervention_keys and exercise_intervention_key is None:
        return []

    selected = {"sbp": [], "ldl": [], "hba1c": []}
    current_targets = {
        "sbp_target": float(sbp_now),
        "ldl_target": float(ldl_now),
        "a1c_target": float(a1c_now),
    }
    running_risk = risk_at_horizon(outcome, horizon, current_targets)
    contributions = []

    for medication in ordered_meds:
        selected[medication["domain"]].append(medication)
        next_targets = apply_meds_to_targets(
            sbp_now=float(sbp_now),
            ldl_now_mg=float(ldl_now),
            a1c_now=float(a1c_now),
            selected_sbp=selected["sbp"],
            selected_ldl=selected["ldl"],
            selected_a1c=selected["hba1c"],
        )
        next_risk = risk_at_horizon(outcome, horizon, next_targets)
        contributions.append(
            {
                "name": medication["key"],
                "delta": max(0.0, (running_risk - next_risk) * 100.0),
            }
        )
        running_risk = next_risk
        current_targets = next_targets

    for diet_key in diet_intervention_keys:
        diet_targets = apply_lifestyle_effects(
            sbp=current_targets["sbp_target"],
            ldl=current_targets["ldl_target"],
            a1c=current_targets["a1c_target"],
            diet_keys=[diet_key],
            diabetes_context=True,
        )
        next_targets = {
            "sbp_target": diet_targets["sbp"],
            "ldl_target": diet_targets["ldl"],
            "a1c_target": diet_targets["a1c"],
        }
        next_risk = risk_at_horizon(outcome, horizon, next_targets)
        contributions.append(
            {
                "name": f"食事：{DIET_EFFECTS[diet_key].label}",
                "delta": max(0.0, (running_risk - next_risk) * 100.0),
            }
        )
        running_risk = next_risk
        current_targets = next_targets

    if exercise_intervention_key is not None:
        exercise_targets = apply_lifestyle_effects(
            sbp=current_targets["sbp_target"],
            ldl=current_targets["ldl_target"],
            a1c=current_targets["a1c_target"],
            exercise_key=exercise_intervention_key,
            diabetes_context=True,
        )
        next_targets = {
            "sbp_target": exercise_targets["sbp"],
            "ldl_target": exercise_targets["ldl"],
            "a1c_target": exercise_targets["a1c"],
        }
        next_risk = risk_at_horizon(outcome, horizon, next_targets)
        contributions.append(
            {
                "name": f"運動：{EXERCISE_EFFECTS[exercise_intervention_key].label}",
                "delta": max(0.0, (running_risk - next_risk) * 100.0),
            }
        )
    return contributions


def plot_risk_curve(outcome: str, data: dict, hr_mode: bool = False):
    if hr_mode:
        data = hazard_ratio_curve(data)
    fitness_active = outcome == "mortality" and "fitness_scenario" in data
    t = np.asarray(data["time"], dtype=float)
    baseline = np.asarray(data["baseline_cumulative"], dtype=float)
    target = np.asarray(data["target_cumulative"], dtype=float)
    baseline_low = np.asarray(data["baseline_ci_lower"], dtype=float)
    baseline_high = np.asarray(data["baseline_ci_upper"], dtype=float)
    target_low = np.asarray(data["target_ci_lower"], dtype=float)
    target_high = np.asarray(data["target_ci_upper"], dtype=float)

    cutoff_year = 10.0 if outcome == "dementia" else max(0.0, 85.0 - float(age))
    cut_idx = int(np.searchsorted(t, cutoff_year, side="right"))
    post_idx = max(0, cut_idx - 1)
    post_dash = "dot" if outcome == "dementia" else "solid"
    post_opacity = 0.62 if outcome == "dementia" else 0.35
    baseline_color = "#14866d" if care_mode == "continue" else "#d34b4b"
    target_color = "#d34b4b" if care_mode == "continue" else "#14866d"
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=t,
            y=baseline_high,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t,
            y=baseline_low,
            mode="lines",
            fill="tonexty",
            line=dict(width=0),
            name="基準（1.00）" if hr_mode else "現在 95%CI",
            showlegend=not hr_mode,
            hoverinfo="skip",
            fillcolor="rgba(211, 75, 75, 0.10)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t,
            y=target_high,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t,
            y=target_low,
            mode="lines",
            fill="tonexty",
            line=dict(width=0),
            name=("HR相当の参考幅" if hr_mode else "心肺体力込み・95%推定幅" if fitness_active else
                  "全薬中止時 95%CI" if care_mode == "continue" else "目標達成時 95%CI"),
            hoverinfo="skip",
            fillcolor="rgba(20, 134, 109, 0.11)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[:cut_idx],
            y=baseline[:cut_idx],
            mode="lines",
            name="服薬を継続" if care_mode == "continue" else "現在のリスク因子",
            line=dict(color=baseline_color, width=3),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[post_idx:],
            y=baseline[post_idx:],
            mode="lines",
            showlegend=False,
            opacity=post_opacity,
            line=dict(color=baseline_color, width=3, dash=post_dash),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[:cut_idx],
            y=target[:cut_idx],
            mode="lines",
            name=("目標達成時・心肺体力込み（推定）" if fitness_active else
                  "今日から全薬中止" if care_mode == "continue" else "薬剤／目標達成時"),
            line=dict(color=target_color, width=3),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[post_idx:],
            y=target[post_idx:],
            mode="lines",
            showlegend=False,
            opacity=post_opacity,
            line=dict(color=target_color, width=3, dash=post_dash),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    if hr_mode:
        for trace in fig.data:
            if trace.hoverinfo != "skip":
                trace.hovertemplate = "%{x:.0f}年：HR相当 %{y:.2f}<extra></extra>"
    fig.update_layout(
        title=OUTCOME_META[outcome]["title"],
        xaxis_title="年数",
        yaxis_title="HR相当（累積ハザード比・基準=1）" if hr_mode else "累積リスク（%）",
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    )
    return fig


include_fitness = False
input_col, result_col = st.columns([0.38, 0.62], gap="large")

with input_col:
    st.subheader("入力")
    st.markdown('<div class="live-note">入力を変更すると、右のグラフがすぐに更新されます。</div>', unsafe_allow_html=True)

    care_mode = st.segmented_control(
        "診療モード",
        ["start", "continue"],
        default="start",
        format_func=lambda value: {
            "start": "治療を始める",
            "continue": "現在の治療を続ける",
        }[value],
        key="care_mode",
    ) or "start"
    if care_mode == "continue":
        st.caption("現在の服薬をすべて中止した場合と比べ、続ける意味を確認します。")

    with st.container(border=True):
        st.markdown("#### 患者プロフィール")
        profile_left, profile_right = st.columns(2)
        with profile_left:
            st.markdown(
                '<div class="sex-field-label" translate="no" aria-label="性別"></div>',
                unsafe_allow_html=True,
            )
            sex_label = st.selectbox(
                "性別",
                ["男性", "女性"],
                label_visibility="collapsed",
            )
            sex = "male" if sex_label == "男性" else "female"
        with profile_right:
            age = st.number_input("年齢（歳）", 20, 95, 60, step=1)

    with st.container(border=True):
        st.markdown("#### 現在の検査値" if care_mode == "continue" else "#### リスク因子（現在 → 目標）")
        if care_mode == "continue":
            st.caption("服薬中の直近値を入力してください。薬を中止した場合の値を薬効から逆算します。")
        else:
            st.caption("手入力した目標値はすぐにグラフへ反映されます。薬剤モードでは目標値を薬効から自動計算します。")
        now_col, target_col = st.columns(2)
        with now_col:
            st.markdown("**現在**")
            sbp_now = slider_with_nudges(
                "収縮期血圧 (mmHg)", 90, 200, 150,
                key="sbp_now", nudge=10, fixed_label="収縮期血圧 (mmHg)",
            )
            ldl_now = slider_with_nudges(
                "LDL (mg/dL)", 50, 250, 160,
                key="ldl_now", nudge=10,
            )
            a1c_now = slider_with_nudges(
                "HbA1c (%)", 5.0, 12.0, 8.0,
                key="a1c_now", nudge=0.5, step=0.1,
            )
        with target_col:
            if care_mode == "continue":
                st.markdown("**全薬中止時（自動推定）**")
                st.info("下で現在の薬を選ぶと表示されます。")
                sbp_tgt_manual = float(sbp_now)
                ldl_tgt_manual = float(ldl_now)
                a1c_tgt_manual = float(a1c_now)
            else:
                st.markdown("**目標**")
                sbp_tgt_manual = slider_with_nudges(
                    "収縮期血圧 (mmHg)", 90, 160, 130,
                    key="sbp_target", nudge=10, fixed_label="収縮期血圧 (mmHg)",
                )
                ldl_tgt_manual = slider_with_nudges(
                    "LDL (mg/dL)", 50, 160, 100,
                    key="ldl_target", nudge=10,
                )
                a1c_tgt_manual = slider_with_nudges(
                    "HbA1c (%)", 5.0, 9.0, 7.0,
                    key="a1c_target", nudge=0.5, step=0.1,
                )

    with st.expander("喫煙・BMI・腎機能・尿アルブミン", expanded=False):
        smoking_status = st.selectbox(
            "喫煙状況",
            ["never", "current", "former"],
            format_func=lambda value: {
                "never": "非喫煙者",
                "current": "現在喫煙者",
                "former": "元喫煙者",
            }[value],
        )
        if smoking_status != "never":
            cigs_per_day = st.slider("1日あたりの喫煙本数", 0, 40, 20)
            years_smoked = st.slider("喫煙年数", 0, 60, 20)
        else:
            cigs_per_day = 0
            years_smoked = 0
        if smoking_status == "former":
            years_since_quit = st.slider("禁煙からの年数", 0, 40, 5)
        else:
            years_since_quit = 0
        quit_today = st.checkbox("今日禁煙したと仮定（目標シナリオ）")

        bmi_left, bmi_right = st.columns(2)
        with bmi_left:
            bmi_now = st.number_input("現在のBMI", 10.0, 50.0, 24.0, 0.1)
        with bmi_right:
            bmi_target = st.number_input("目標BMI", 10.0, 50.0, 24.0, 0.1)

        st.markdown("**書類作成に使用する身体情報**")
        body_left, body_middle, body_right = st.columns(3)
        with body_left:
            height_cm = st.number_input("身長 (cm)", 100.0, 220.0, 170.0, 0.1)
        with body_middle:
            weight_kg = st.number_input(
                "体重 (kg)", 20.0, 250.0,
                round(float(bmi_now) * (float(height_cm) / 100.0) ** 2, 1), 0.1,
            )
        with body_right:
            dbp_now = st.number_input("拡張期血圧 (mmHg)", 40, 140, 90, 1)

        st.markdown("**糖尿病合併症予測に使用する腎指標**")
        egfr_left, egfr_right = st.columns(2)
        with egfr_left:
            egfr_now = st.number_input("現在のeGFR", 5.0, 120.0, 80.0, 1.0)
            acr_now = st.selectbox(
                "尿アルブミン（現在）", ["A1", "A2", "A3"],
                format_func=lambda value: {"A1": "A1（正常〜軽度）", "A2": "A2（中等度）", "A3": "A3（高度）"}[value],
            )
        with egfr_right:
            egfr_target = st.number_input("目標eGFR", 5.0, 120.0, 80.0, 1.0)
            acr_target = st.selectbox(
                "尿アルブミン（目標）", ["A1", "A2", "A3"],
                format_func=lambda value: {"A1": "A1（正常〜軽度）", "A2": "A2（中等度）", "A3": "A3（高度）"}[value],
            )

    with st.container(border=True):
        st.markdown("#### 💊 現在服用中の薬" if care_mode == "continue" else "#### 💊 薬剤")
        use_meds = True if care_mode == "continue" else st.checkbox("薬剤から目標値を自動計算する", value=False)
        selected_sbp_meds = []
        selected_ldl_meds = []
        selected_a1c_meds = []
        meds_summary = None

        if catalog_error:
            st.warning("薬剤カタログの読み込みに失敗しました。")
            st.caption(catalog_error)
            use_meds = False
        elif use_meds and meds_catalog:
            med_label_prefix = "現在の" if care_mode == "continue" else ""
            with st.container():
                st.markdown(f"##### {med_label_prefix}降圧薬")
                selected_sbp_meds = medication_selector(
                    "降圧薬", meds_catalog["sbp"], "current_sbp_meds",
                )
            st.divider()
            with st.container():
                st.markdown(f"##### {med_label_prefix}脂質薬")
                selected_ldl_meds = medication_selector(
                    "脂質薬", meds_catalog["ldl"], "current_ldl_meds",
                )
            st.divider()
            with st.container():
                st.markdown(f"##### {med_label_prefix}糖尿病薬")
                selected_a1c_meds = medication_selector(
                    "糖尿病薬", meds_catalog["hba1c"], "current_a1c_meds",
                )
            all_selected_labels = [med["key"] for med in (
                selected_sbp_meds + selected_ldl_meds + selected_a1c_meds
            )]
            if all_selected_labels:
                st.caption("選択中: " + " / ".join(all_selected_labels))
            if care_mode == "continue":
                all_selected_meds = selected_sbp_meds + selected_ldl_meds + selected_a1c_meds
                missing_cost_labels = [m.get("key", "") for m in all_selected_meds if m.get("annual_cost_yen") is None]
                untreated = reconstruct_untreated_values(
                    sbp_now=float(sbp_now), ldl_now=float(ldl_now), a1c_now=float(a1c_now),
                    sbp_meds=selected_sbp_meds, ldl_meds=selected_ldl_meds,
                    a1c_meds=selected_a1c_meds,
                )
                meds_summary = {
                    "sbp_target": untreated["sbp"],
                    "ldl_target": untreated["ldl"],
                    "a1c_target": untreated["a1c"],
                    "annual_cost_yen": sum(int(m.get("annual_cost_yen") or 0) for m in all_selected_meds),
                    "cost_complete": not missing_cost_labels,
                    "missing_cost_labels": missing_cost_labels,
                    "side_effects_md": "",
                }
                st.caption("選択薬の平均効果を逆算し、全薬中止時の検査値を推定します。")
            else:
                meds_summary = apply_meds_to_targets(
                    sbp_now=float(sbp_now),
                    ldl_now_mg=float(ldl_now),
                    a1c_now=float(a1c_now),
                    selected_sbp=selected_sbp_meds,
                    selected_ldl=selected_ldl_meds,
                    selected_a1c=selected_a1c_meds,
                )
                st.caption("SBPは加算 / LDLは%低下を乗算 / HbA1cは加算")

        selected_meds = selected_sbp_meds + selected_ldl_meds + selected_a1c_meds
        if care_mode == "continue" and use_meds and meds_summary is not None:
            sbp_tgt = float(meds_summary["sbp_target"])
            ldl_tgt = float(meds_summary["ldl_target"])
            a1c_tgt = float(meds_summary["a1c_target"])
            annual_cost_yen = int(meds_summary["annual_cost_yen"])
            side_effects_md = meds_summary["side_effects_md"]
            target_metrics = st.columns(3)
            target_metrics[0].metric("SBP中止時", f"{sbp_tgt:.0f}")
            target_metrics[1].metric("LDL中止時", f"{ldl_tgt:.0f}")
            target_metrics[2].metric("HbA1c中止時", f"{a1c_tgt:.1f}")
        elif selected_meds and use_meds and meds_summary is not None:
            sbp_tgt = float(meds_summary["sbp_target"])
            ldl_tgt = float(meds_summary["ldl_target"])
            a1c_tgt = float(meds_summary["a1c_target"])
            annual_cost_yen = int(meds_summary["annual_cost_yen"])
            side_effects_md = meds_summary["side_effects_md"]
            target_metrics = st.columns(3)
            target_metrics[0].metric("薬剤介入後SBP", f"{sbp_tgt:.0f}")
            target_metrics[1].metric("薬剤介入後LDL", f"{ldl_tgt:.0f}")
            target_metrics[2].metric("薬剤介入後HbA1c", f"{a1c_tgt:.1f}")
        else:
            sbp_tgt = float(sbp_tgt_manual)
            ldl_tgt = float(ldl_tgt_manual)
            a1c_tgt = float(a1c_tgt_manual)
            annual_cost_yen = 0
            side_effects_md = ""

        if use_meds and meds_summary is not None and selected_meds:
            st.divider()
            cost_complete = bool(meds_summary.get("cost_complete", True))
            if not cost_complete:
                st.caption("薬価未登録: " + " / ".join(meds_summary.get("missing_cost_labels", [])))
            render_medication_costs(selected_meds, age=int(age), continuing=care_mode == "continue")
            with st.expander("主な副作用を確認", expanded=False):
                if side_effects_md.strip():
                    st.markdown(side_effects_md)
                else:
                    st.info("副作用情報は登録されていません。")
        elif use_meds:
            st.caption("薬剤を選択すると、年間費用と主な副作用をここに表示します。")

    if care_mode != "continue":
      with st.container(border=True):
        st.markdown("#### 🥗 食事療法")
        diet_intervention_keys = st.multiselect(
            "食事プログラム",
            list(DIET_EFFECTS),
            format_func=lambda key: DIET_EFFECTS[key].label,
            key="diet_interventions",
            placeholder="食事介入を選択",
        )
        if diet_intervention_keys:
            if not selected_meds:
                sbp_tgt = float(sbp_now)
                ldl_tgt = float(ldl_now)
                a1c_tgt = float(a1c_now)
            diet_result = apply_lifestyle_effects(
                sbp=sbp_tgt,
                ldl=ldl_tgt,
                a1c=a1c_tgt,
                diet_keys=diet_intervention_keys,
                diabetes_context=True,
            )
            sbp_tgt = float(diet_result["sbp"])
            ldl_tgt = float(diet_result["ldl"])
            a1c_tgt = float(diet_result["a1c"])
            diet_metrics = st.columns(3)
            diet_metrics[0].metric("介入後SBP", f"{sbp_tgt:.1f}")
            diet_metrics[1].metric("介入後LDL", f"{ldl_tgt:.1f}")
            diet_metrics[2].metric("介入後HbA1c", f"{a1c_tgt:.2f}%")
            with st.expander("効果量と根拠を確認", expanded=False):
                for diet_key in diet_intervention_keys:
                    diet_effect = DIET_EFFECTS[diet_key]
                    st.markdown(f"**{diet_effect.label}** — {diet_effect.definition}")
                    st.write(diet_effect.evidence_summary)
                    st.caption(diet_effect.endpoint_evidence)
                    st.link_button(
                        f"{diet_effect.label}の根拠文献を開く",
                        diet_effect.source_url,
                        key=f"diet_source_{diet_key}",
                    )
        else:
            st.caption("食事療法を選択すると、予測検査値と各アウトカムへ反映します。")

      with st.container(border=True):
        st.markdown("#### 🏃 運動療法")
        exercise_intervention_key = st.selectbox(
            "運動プログラム",
            [None, *EXERCISE_EFFECTS],
            format_func=lambda key: (
                "選択しない" if key is None else EXERCISE_EFFECTS[key].label
            ),
            key="exercise_intervention",
        )
        if exercise_intervention_key is not None:
            if not selected_meds and not diet_intervention_keys:
                sbp_tgt = float(sbp_now)
                ldl_tgt = float(ldl_now)
                a1c_tgt = float(a1c_now)
            exercise_effect = EXERCISE_EFFECTS[exercise_intervention_key]
            st.caption(exercise_effect.definition)
            exercise_result = apply_lifestyle_effects(
                sbp=sbp_tgt,
                ldl=ldl_tgt,
                a1c=a1c_tgt,
                exercise_key=exercise_intervention_key,
                diabetes_context=True,
            )
            sbp_tgt = float(exercise_result["sbp"])
            ldl_tgt = float(exercise_result["ldl"])
            a1c_tgt = float(exercise_result["a1c"])
            exercise_metrics = st.columns(3)
            exercise_metrics[0].metric("介入後SBP", f"{sbp_tgt:.1f}")
            exercise_metrics[1].metric("介入後LDL", f"{ldl_tgt:.1f}")
            exercise_metrics[2].metric("介入後HbA1c", f"{a1c_tgt:.2f}%")
            include_fitness = st.checkbox(
                "心肺体力の改善も考慮する（探索的推定・全死亡のみ）",
                value=False, key="include_exercise_fitness",
            )
            if include_fitness:
                fitness_info = fitness_scenario([0], exercise_intervention_key, enabled=True)
                st.caption(
                    f"心肺体力の平均改善：VO₂peak +{fitness_info['vo2_gain']:.2f} mL/kg/分"
                    f"（+{fitness_info['met_gain']:.2f} MET）。"
                    "この改善を達成し、予測期間中維持する仮定です。毎年加算はしません。"
                )
                st.warning(
                    "観察研究の関連を上乗せした探索的シナリオです。"
                    "運動による追加の死亡予防効果が証明された値ではありません。"
                    "血圧・血糖等の改善との重複により、利益を過大評価する可能性があります。"
                    "全死亡の介入後曲線・数値を心肺体力込みに置き換え、95%推定幅を表示します。"
                )
                st.link_button("心肺体力と死亡の関連（観察研究）", FITNESS_MORTALITY_SOURCE)
                st.link_button("運動による心肺体力改善（RCT解析）", FITNESS_TRAINING_SOURCE)
            with st.expander("効果量と根拠を確認", expanded=False):
                st.write(exercise_effect.evidence_summary)
                st.caption(exercise_effect.endpoint_evidence)
                st.link_button("根拠文献を開く", exercise_effect.source_url)
        else:
            st.caption("運動療法を選択すると、予測検査値と各アウトカムへ反映します。")
      if selected_meds or diet_intervention_keys or exercise_intervention_key is not None:
        st.info("介入を選択中は、手入力した目標値を使わず、現在値に選択した効果だけを反映しています。")
    else:
        diet_intervention_keys = []
        exercise_intervention_key = None

    if care_mode == "continue":
        with st.container(border=True):
            st.markdown("#### ⏪ これまでの治療期間")
            treatment_years = st.number_input(
                "治療を開始したのは何年前ですか？",
                min_value=1,
                max_value=max(1, int(age) - 20),
                value=min(10, max(1, int(age) - 20)),
                step=1,
                key="treatment_years",
            )
            st.caption("この期間、現在選択した薬を継続していたと仮定して累積利益を推定します。")
    else:
        treatment_years = 0

    horizon_choice = st.selectbox(
        "予測期間",
        ["5-year", "10-year", "20-year", "30-year", "50-year"],
        index=2,
        format_func=lambda value: f"{_years_from_choice(value)}年",
    )

horizon = _years_from_choice(horizon_choice)
cumulative_data = calculate_cumulative_risk_curves(horizon)
# Preserve ordinary results only for document export; the screen uses the selected scenario.
document_risk_curves = {key: dict(value) for key, value in cumulative_data.items()}
fitness_projection = fitness_scenario(
    cumulative_data["mortality"]["target_cumulative"], exercise_intervention_key,
    enabled=include_fitness and care_mode != "continue",
    lower_percent=cumulative_data["mortality"]["target_ci_lower"],
    upper_percent=cumulative_data["mortality"]["target_ci_upper"],
)
if fitness_projection is not None:
    mortality_data = cumulative_data["mortality"]
    fitness_projection["additional_arr"] = mortality_data["target_cumulative"][-1] - fitness_projection["risk"][-1]
    mortality_data["fitness_scenario"] = fitness_projection
    mortality_data["target_cumulative"] = fitness_projection["risk"]
    mortality_data["target_ci_lower"] = fitness_projection["lower"]
    mortality_data["target_ci_upper"] = fitness_projection["upper"]

with result_col:
    st.markdown('<div class="result-anchor" aria-hidden="true"></div>', unsafe_allow_html=True)
    st.subheader("リアルタイム予測")
    hr_mode = st.checkbox("HR表示に切り替える（累積ハザード比の推定）", key="show_hazard_ratio")
    if hr_mode:
        st.caption(
            "現在（継続モードでは服薬継続）を1とした期間平均のHR相当値です。"
            "−log(1−介入後リスク) / −log(1−現在リスク) で換算しています。"
            "瞬間的なHRや臨床試験のCox HRではなく、比例ハザードが成り立つ場合にHRと一致します。"
            "参考幅は元の上下限から換算した範囲で、HRの95%信頼区間ではありません。"
            "0年やリスクが0%・100%で計算できない箇所は表示しません。書類は絶対リスク表示のままです。"
        )
    selected_outcome = st.radio(
        "表示するアウトカム",
        OUTCOME_DISPLAY_ORDER,
        index=0,
        format_func=lambda value: OUTCOME_META[value]["label"],
        horizontal=True,
        key="display_outcome",
    )
    selected_data = cumulative_data[selected_outcome]
    if fitness_projection is not None and selected_outcome != "mortality":
        st.info("心肺体力の推定上乗せは「全死亡」で確認できます。このアウトカムには上乗せしていません。")
    baseline_risk = selected_data["baseline_cumulative"][-1]
    target_risk = selected_data["target_cumulative"][-1]
    arr = baseline_risk - target_risk
    displayed_horizon = int(selected_data["time"][-1])

    metric_cols = st.columns(3)
    if hr_mode:
        ratio_data = hazard_ratio_curve(selected_data)
        ratio = ratio_data["target_cumulative"][-1]
        metric_cols[0].metric("服薬継続（基準）" if care_mode == "continue" else "現在（基準）", "1.00")
        metric_cols[1].metric(
            f"{displayed_horizon}年・{'全薬中止' if care_mode == 'continue' else '目標達成時'} HR相当"
            + ("（心肺体力込み・推定）" if selected_outcome == "mortality" and fitness_projection is not None else ""),
            format_hr(ratio),
        )
        metric_cols[2].metric("ハザードの変化（推定）", format_hazard_change(ratio))
        st.caption(
            f"HR相当の参考幅：{format_hr(ratio_data['target_ci_lower'][-1])}–"
            f"{format_hr(ratio_data['target_ci_upper'][-1])}"
        )
    elif care_mode == "continue":
        harm = target_risk - baseline_risk
        metric_cols[0].metric(f"{displayed_horizon}年・服薬継続", f"{baseline_risk:.1f}%")
        metric_cols[1].metric(f"{displayed_horizon}年・今日から全薬中止", f"{target_risk:.1f}%")
        metric_cols[2].metric("中止によるリスク増加", f"+{harm:.1f} pt")
    else:
        metric_cols[0].metric(f"{displayed_horizon}年・現在", f"{baseline_risk:.1f}%")
        target_label = f"{displayed_horizon}年・目標達成時"
        if selected_outcome == "mortality" and fitness_projection is not None:
            target_label += "（心肺体力込み・推定）"
        metric_cols[1].metric(target_label, f"{target_risk:.1f}%")
        metric_cols[2].metric("リスク減少幅", f"{arr:.1f} pt")

    if not hr_mode:
        st.plotly_chart(
            plot_risk_curve(selected_outcome, selected_data),
            width="stretch",
            config={"displayModeBar": False},
        )
    if selected_outcome == "mortality":
        st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)
        if fitness_projection is not None:
            st.caption(
                ("" if hr_mode else f"{displayed_horizon}年・全死亡の95%推定幅："
                 f"{fitness_projection['lower'][-1]:.2f}–{fitness_projection['upper'][-1]:.2f}%。") +
                "モデル上の仮定を含む元の予測幅・心肺体力改善量・観察研究のRRの不確実性を独立と仮定して合成した近似幅です。"
                "検証済みの95%信頼区間ではなく、交絡や効果重複による偏りは含みません。"
                "グラフ・全死亡の数値・減少幅・治療内訳に反映しています。書類は通常推計です。"
            )
    elif selected_outcome == "dementia":
        st.caption(
            "2型糖尿病患者（60歳以上）の年齢別発症率を、日本の実測コホートへ部分較正した参考推定です。"
            "10年までは実線、10年超は同じ年齢別発症率と治療効果が続く仮定の外挿を点線で表示します。"
            "血圧・LDL低下は薬剤、食事、運動、手入力のいずれでも低下量から反映します。"
            "介入併用時は相対効果の乗算を仮定しています。"
        )
        dementia_links = st.columns(3)
        dementia_links[0].link_button("認知症基礎曲線の根拠", DSDRS_EVIDENCE_URL)
        dementia_links[1].link_button("日本実測の根拠", JAPAN_DEMENTIA_COHORT_URL)
        dementia_links[2].link_button("LDL値と認知症の根拠", LDL_LEVEL_EVIDENCE_URL)

    if care_mode != "continue" and not hr_mode:
        with st.container(border=True):
            st.markdown(
                f'<h4 class="arr-breakdown-title" translate="no" '
                f'data-title="各治療によるリスク減少（{displayed_horizon}年間）"></h4>',
                unsafe_allow_html=True,
            )
            contributions = build_medication_contributions(selected_outcome, horizon)
            if selected_outcome == "mortality" and fitness_projection is not None:
                contributions.append({
                    "name": "運動：心肺体力の追加効果（探索的推定）",
                    "delta": fitness_projection["additional_arr"],
                })
            if not contributions:
                st.info("薬剤・食事療法・運動療法を選ぶと、追加によるリスク低下幅をここに表示します。")
            else:
                max_delta = max(max(item["delta"] for item in contributions), 0.01)
                for item in contributions:
                    width = min(100.0, item["delta"] / max_delta * 100.0)
                    st.markdown(
                        f"""
                        <div class="contribution-row">
                          <div>{item['name']}</div>
                          <div class="contribution-track"><div class="contribution-fill" style="width:{width:.1f}%"></div></div>
                          <div class="contribution-value">−{item['delta']:.2f} pt</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                st.caption("表示順に治療を追加したときのリスク減少幅です。併用順によって内訳は変わります。")
    elif care_mode == "continue" and selected_meds:
        st.success("現在の良好な検査値と低い将来リスクは、服薬継続で得られている効果です。自己判断で中止せず主治医と相談しましょう。")
    elif care_mode == "continue":
        st.info("左側で現在服用中の薬を選ぶと、全薬中止との比較を表示します。")

    with st.container(border=True):
        st.markdown("#### 7アウトカムの比較")
        summary_cols = st.columns(3)
        for index, outcome in enumerate(OUTCOME_DISPLAY_ORDER):
            data = cumulative_data[outcome]
            outcome_arr = data["baseline_cumulative"][-1] - data["target_cumulative"][-1]
            if hr_mode:
                outcome_hr = hazard_ratio_curve(data)["target_cumulative"][-1]
                summary_cols[index % 3].metric(
                    OUTCOME_META[outcome]["label"] + " HR相当" + (
                        "（心肺体力込み・推定）" if outcome == "mortality" and fitness_projection is not None else ""
                    ),
                    format_hr(outcome_hr),
                    delta=format_hazard_change(outcome_hr),
                    delta_color="off",
                )
            elif care_mode == "continue":
                stopping_harm = max(0.0, -outcome_arr)
                summary_cols[index % 3].metric(
                    f"{OUTCOME_META[outcome]['label']}（継続）",
                    f"{data['baseline_cumulative'][-1]:.1f}%",
                    delta=f"中止で +{stopping_harm:.1f} pt",
                    delta_color="inverse",
                )
            else:
                summary_cols[index % 3].metric(
                    OUTCOME_META[outcome]["label"] + (
                        "（心肺体力込み・推定）" if outcome == "mortality" and fitness_projection is not None else ""
                    ),
                    f"{data['target_cumulative'][-1]:.1f}%",
                    delta=f"{outcome_arr:.1f} pt減少",
                    delta_color="normal",
                )

    with st.container(border=True):
        st.markdown("#### 🦴 骨の健康（参考）")
        st.caption(
            "主要アウトカムには含めない、おまけのスクリーニング機能です。"
            "日本の年齢・性別別発生率から大腿骨近位部骨折の10年参考確率を計算します。"
        )
        with st.expander("骨折リスクを詳しく確認", expanded=False):
            bone_col1, bone_col2 = st.columns(2)
            with bone_col1:
                prior_fragility_fracture = st.checkbox("脆弱性骨折歴あり")
                peripheral_neuropathy = st.checkbox("糖尿病性末梢神経障害あり")
            with bone_col2:
                glucocorticoid_use = st.checkbox("長期ステロイド使用あり")
                has_t_score = st.checkbox("大腿骨頸部Tスコアが分かる")
                t_score = (
                    st.number_input("大腿骨頸部Tスコア", -6.0, 3.0, -1.0, 0.1)
                    if has_t_score else None
                )
            fracture_risk_10y = hip_fracture_risk(
                age=float(age), sex=sex, years=10,
                prior_fragility_fracture=prior_fragility_fracture,
            )
            st.markdown("**薬物介入（参考試算）**")
            osteoporosis_drug_key = st.selectbox(
                "骨粗鬆症薬",
                list(OSTEOPOROSIS_DRUGS),
                format_func=lambda key: OSTEOPOROSIS_DRUGS[key]["label"],
                key="osteoporosis_drug",
            )
            drug_effect = OSTEOPOROSIS_DRUGS[osteoporosis_drug_key]
            max_treatment_years = int(drug_effect["max_years"])
            if osteoporosis_drug_key == "none":
                treatment_duration = 0
            elif max_treatment_years == 1:
                treatment_duration = 1
                st.caption("モデル上の投与期間: 12か月")
            else:
                treatment_duration = st.slider(
                    "治療を継続する期間", 1, max_treatment_years,
                    min(3, max_treatment_years), 1, format="%d年",
                )
            treated_fracture_risk_10y = hip_fracture_risk(
                age=float(age), sex=sex, years=10,
                prior_fragility_fracture=prior_fragility_fracture,
                treatment_rr=float(drug_effect["hip_rr"]),
                treatment_years=(
                    int(treatment_duration) if osteoporosis_drug_key != "none" else 0
                ),
            )
            bone_metrics = st.columns(3)
            bone_metrics[0].metric(
                "薬物介入なし・10年", f"{fracture_risk_10y * 100:.1f}%",
            )
            bone_metrics[1].metric(
                "選択薬で介入・10年", f"{treated_fracture_risk_10y * 100:.1f}%",
                delta=f"−{(fracture_risk_10y - treated_fracture_risk_10y) * 100:.1f} pt",
                delta_color="inverse",
            )
            bone_metrics[2].metric("DXA区分", bone_density_category(t_score))
            if osteoporosis_drug_key != "none":
                st.caption(
                    f"{drug_effect['label']}: 股関節骨折RR {drug_effect['hip_rr']:.2f}／"
                    f"{drug_effect['certainty']}。選択期間中のみ効果が続くと仮定しています。"
                )
                if sex == "male":
                    st.warning("効果量の中心的な根拠は閉経後女性です。男性への適用は外挿です。")
                if osteoporosis_drug_key == "denosumab":
                    st.warning("デノスマブは中断・終了時に反跳性骨折を避ける後続治療が必要です。")
                if osteoporosis_drug_key == "romosozumab_alendronate":
                    st.warning("ロモソズマブは12か月まで。終了後の抗吸収薬と心血管リスク評価が必要です。")
                if (
                    osteoporosis_drug_key in {"alendronate", "risedronate", "zoledronate"}
                    and egfr_now < 35
                ):
                    st.warning("高度腎機能低下ではビスホスホネートの適否を個別に確認してください。")
            st.caption(
                "2型糖尿病RR 1.33と、骨折歴がある場合は既往骨折HR 1.82を反映。"
                "神経障害・ステロイドは注意喚起だけに使い、未検証の上乗せはしません。"
            )
        bone_flags = bone_health_flags(
            age=float(age), sex=sex, bmi=float(bmi_now), egfr=float(egfr_now),
            diabetes_medications=selected_a1c_meds,
            prior_fragility_fracture=prior_fragility_fracture,
            peripheral_neuropathy=peripheral_neuropathy,
            glucocorticoid_use=glucocorticoid_use,
            t_score=t_score,
        )
        if bone_flags:
            st.markdown("**診察時に確認したい項目**")
            for flag in bone_flags:
                st.markdown(f"- {flag}")
        else:
            st.info("現在の入力項目から追加の確認フラグはありません。骨折歴や骨密度は別途評価が必要です。")
        st.write(
            "参考確率は日本版FRAXや骨粗鬆症診断の代替ではありません。"
            "骨粗鬆症治療薬には骨折予防のRCT根拠があります。"
        )
        bone_links = st.columns(5)
        bone_links[0].link_button("日本の骨折疫学", JAPAN_HIP_FRACTURE_URL)
        bone_links[1].link_button("糖尿病骨折モデル", DIABETES_FRACTURE_MODEL_URL)
        bone_links[2].link_button("骨粗鬆症治療", OSTEOPOROSIS_TREATMENT_URL)
        bone_links[3].link_button("糖尿病薬と骨折", DIABETES_DRUG_FRACTURE_URL)
        bone_links[4].link_button("薬剤別股関節骨折効果", HIP_FRACTURE_TREATMENT_NMA_URL)

    if care_mode == "continue" and selected_meds and treatment_years > 0:
        past_benefit = calculate_past_treatment_benefit(int(treatment_years))
        st.markdown("## ⏪ これまでの治療で得られた利益")
        st.caption(
            f"治療開始から現在までの{int(treatment_years)}年間を、最初から薬を使わなかった場合と比較した推定です。"
        )
        life_years = past_benefit["estimated_life_years_gained"]
        life_days = life_years * 365.25
        st.metric(
            "推定で保持できた生存期間",
            f"約{life_days:.0f}日",
            delta=f"{life_years:.3f}年相当",
        )
        st.caption("全死亡の生存曲線差を治療期間内で積分した集団平均のモデル推定です。個人の寿命を断定する値ではありません。")

        benefit_cols = st.columns(3)
        for index, outcome in enumerate(OUTCOME_DISPLAY_ORDER):
            benefit = past_benefit[outcome]
            benefit_cols[index % 3].metric(
                OUTCOME_META[outcome]["label"],
                f"{benefit['avoided']:.2f} pt回避",
                delta=f"無治療 {benefit['untreated'][-1]:.1f}% → 治療あり {benefit['treated'][-1]:.1f}%",
                delta_color="normal",
            )

        past_outcome = st.selectbox(
            "過去の累積利益を表示するアウトカム",
            OUTCOME_DISPLAY_ORDER,
            format_func=lambda value: OUTCOME_META[value]["label"],
            key="past_benefit_outcome",
        )
        past = past_benefit[past_outcome]
        past_fig = go.Figure()
        past_fig.add_trace(go.Scatter(
            x=past["time"], y=past["untreated"], mode="lines",
            name="最初から薬なし", line=dict(color="#d34b4b", dash="dash", width=3),
        ))
        past_fig.add_trace(go.Scatter(
            x=past["time"], y=past["treated"], mode="lines",
            name="治療あり", line=dict(color="#14866d", width=3),
        ))
        past_fig.add_vline(x=0, line_dash="dot", line_color="#374151", annotation_text="現在")
        past_fig.update_layout(
            title=f"{OUTCOME_META[past_outcome]['label']}：これまでの累積リスク",
            xaxis_title="現在を0とした年数", yaxis_title="累積リスク（%）",
            height=390, hovermode="x unified",
            legend=dict(orientation="h", y=1.12),
        )
        if not hr_mode:
            st.plotly_chart(past_fig, width="stretch", config={"displayModeBar": False})

st.caption(
    "※ 治療ごとのリスク減少幅は、既存の薬効・食事・運動効果量・リスクモデルを用い、"
    "選択した介入を順に加えた際の表示上の差を分解したものです。"
)
st.caption(
    "※ 透析・大切断・失明はDM-modelのWeibullモデルを用いた2型糖尿病患者向け推定です。"
    "個人の発症を断定するものではなく、1型糖尿病には適用しません。"
)
st.caption(
    "※ アクセス解析では訪問日時を保存します。都道府県解析を有効にした場合も、"
    "保存するのはIPから概算した国・都道府県のみで、IPアドレスそのものは保存しません。"
    "位置情報は実際の所在地と異なる場合があります。"
)

if access_stats.get("historical_estimate", 0):
    st.caption(f"※ 累計アクセスは過去約{access_stats['historical_estimate']:,}件への概算補正を含みます。補正後の訪問は別途実測で加算しています。")

st.divider()
if st.button(
    "📄 書類作成へ進む",
    type="primary",
    use_container_width=True,
    key="open_document_creation",
):
    st.session_state["show_document_creation"] = True

if st.session_state.get("show_document_creation"):
    if fitness_projection is not None:
        st.info("書類には通常推計を出力します。心肺体力の探索的上乗せは書類に含めません。")
    if st.button("書類作成を閉じる", key="close_document_creation"):
        st.session_state["show_document_creation"] = False
        st.rerun()

    lifestyle_labels = [DIET_EFFECTS[key].label for key in diet_intervention_keys]
    if exercise_intervention_key is not None:
        lifestyle_labels.append(EXERCISE_EFFECTS[exercise_intervention_key].label)

    pdf_plan_ui.render_plan_section(
        sex=sex,
        age=age,
        height_cm=height_cm,
        weight_kg=weight_kg,
        sbp_now=sbp_now,
        dbp_now=dbp_now,
        ldl_now=ldl_now,
        a1c_now=a1c_now,
        sbp_tgt_manual=sbp_tgt_manual,
        a1c_tgt_manual=a1c_tgt_manual,
        bmi_target=bmi_target,
        bp_medications=tuple(med["key"] for med in selected_sbp_meds),
        lipid_medications=tuple(med["key"] for med in selected_ldl_meds),
        diabetes_medications=tuple(med["key"] for med in selected_a1c_meds),
        lifestyle_interventions=tuple(lifestyle_labels),
        risk_curves=document_risk_curves,
        risk_horizon_years=horizon,
        sbp_after=sbp_tgt,
        ldl_after=ldl_tgt,
        a1c_after=a1c_tgt,
        key_prefix="dm_care",
    )
