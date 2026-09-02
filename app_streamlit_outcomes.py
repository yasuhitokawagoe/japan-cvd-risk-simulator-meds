# app_streamlit_outcomes.py
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from access_analytics import record_visit, total_visits
from calc_engine_outcomes import OutcomesEngine
from dm_outcomes import ACR_CATEGORY_MG_G, DIABETES_OUTCOMES, DiabetesOutcomeModel
from lifestyle_interventions import DIET_EFFECTS, EXERCISE_EFFECTS, apply_lifestyle_effects
from meds_catalog import apply_meds_to_targets, load_meds_catalog
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

st.markdown(
    f"""
    <div class="app-hero">
      <div class="hero-icon" aria-hidden="true">♥</div>
      <div class="hero-copy">
        <div class="hero-kicker">DIABETES CARE &amp; COMPLICATION PREVENTION</div>
        <h1 class="hero-title">生活習慣病療養指導シュミレーター</h1>
        <p class="hero-subtitle">血糖・血圧・腎機能と治療による将来リスクの変化を可視化し、合併症予防の目標を一緒に考えます。教育・共有意思決定支援用。</p>
      </div>
      <div class="hero-badge" translate="no" data-count="{access_stats['total']:,}"></div>
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
OUTCOME_DISPLAY_ORDER = CARDIOVASCULAR_OUTCOMES + DIABETES_OUTCOME_KEYS
OUTCOME_META = {
    "mortality": {"label": "全死亡", "title": "全死亡", "color": "#d95656"},
    "mi": {"label": "心筋梗塞", "title": "心筋梗塞", "color": "#e07b39"},
    "stroke": {"label": "脳卒中", "title": "脳卒中", "color": "#7656c9"},
    "esrd": {"label": "透析", "title": "透析（末期腎不全）", "color": "#3f7f9f"},
    "amputation": {"label": "大切断", "title": "大切断", "color": "#9c6b3f"},
    "blindness": {"label": "失明", "title": "失明", "color": "#3e7c58"},
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


def plot_risk_curve(outcome: str, data: dict):
    t = np.asarray(data["time"], dtype=float)
    baseline = np.asarray(data["baseline_cumulative"], dtype=float)
    target = np.asarray(data["target_cumulative"], dtype=float)
    baseline_low = np.asarray(data["baseline_ci_lower"], dtype=float)
    baseline_high = np.asarray(data["baseline_ci_upper"], dtype=float)
    target_low = np.asarray(data["target_ci_lower"], dtype=float)
    target_high = np.asarray(data["target_ci_upper"], dtype=float)

    cutoff_year = max(0.0, 85.0 - float(age))
    cut_idx = int(np.searchsorted(t, cutoff_year, side="right"))
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
            name="現在 95%CI",
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
            name="全薬中止時 95%CI" if care_mode == "continue" else "目標達成時 95%CI",
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
            x=t[cut_idx:],
            y=baseline[cut_idx:],
            mode="lines",
            showlegend=False,
            opacity=0.35,
            line=dict(color=baseline_color, width=3),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[:cut_idx],
            y=target[:cut_idx],
            mode="lines",
            name="今日から全薬中止" if care_mode == "continue" else "薬剤／目標達成時",
            line=dict(color=target_color, width=3),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[cut_idx:],
            y=target[cut_idx:],
            mode="lines",
            showlegend=False,
            opacity=0.35,
            line=dict(color=target_color, width=3),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title=OUTCOME_META[outcome]["title"],
        xaxis_title="年数",
        yaxis_title="累積リスク（%）",
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    )
    return fig


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
            sbp_options = [med["key"] for med in meds_catalog["sbp"]]
            ldl_options = [med["key"] for med in meds_catalog["ldl"]]
            a1c_options = [med["key"] for med in meds_catalog["hba1c"]]
            med_label_prefix = "現在の" if care_mode == "continue" else ""
            sbp_keys = st.multiselect(f"{med_label_prefix}降圧薬", sbp_options, key="current_sbp_meds")
            ldl_keys = st.multiselect(f"{med_label_prefix}脂質薬", ldl_options, key="current_ldl_meds")
            a1c_keys = st.multiselect(f"{med_label_prefix}糖尿病薬", a1c_options, key="current_a1c_meds")
            selected_sbp_meds = [med for med in meds_catalog["sbp"] if med["key"] in sbp_keys]
            selected_ldl_meds = [med for med in meds_catalog["ldl"] if med["key"] in ldl_keys]
            selected_a1c_meds = [med for med in meds_catalog["hba1c"] if med["key"] in a1c_keys]
            if care_mode == "continue":
                untreated = reconstruct_untreated_values(
                    sbp_now=float(sbp_now), ldl_now=float(ldl_now), a1c_now=float(a1c_now),
                    sbp_meds=selected_sbp_meds, ldl_meds=selected_ldl_meds,
                    a1c_meds=selected_a1c_meds,
                )
                meds_summary = {
                    "sbp_target": untreated["sbp"],
                    "ldl_target": untreated["ldl"],
                    "a1c_target": untreated["a1c"],
                    "annual_cost_yen": sum(int(m.get("annual_cost_yen") or 0) for m in selected_sbp_meds + selected_ldl_meds + selected_a1c_meds),
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

        if use_meds and meds_summary is not None:
            sbp_tgt = float(meds_summary["sbp_target"])
            ldl_tgt = float(meds_summary["ldl_target"])
            a1c_tgt = float(meds_summary["a1c_target"])
            annual_cost_yen = int(meds_summary["annual_cost_yen"])
            side_effects_md = meds_summary["side_effects_md"]
            target_metrics = st.columns(3)
            metric_prefix = "中止時" if care_mode == "continue" else "目標"
            target_metrics[0].metric(f"SBP{metric_prefix}", f"{sbp_tgt:.0f}")
            target_metrics[1].metric(f"LDL{metric_prefix}", f"{ldl_tgt:.0f}")
            target_metrics[2].metric(f"HbA1c{metric_prefix}", f"{a1c_tgt:.1f}")
        else:
            sbp_tgt = float(sbp_tgt_manual)
            ldl_tgt = float(ldl_tgt_manual)
            a1c_tgt = float(a1c_tgt_manual)
            annual_cost_yen = 0
            side_effects_md = ""

        selected_meds = selected_sbp_meds + selected_ldl_meds + selected_a1c_meds
        if use_meds and meds_summary is not None and selected_meds:
            st.divider()
            st.metric("年間薬剤費（合計）", f"{annual_cost_yen:,} 円/年")
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
            st.caption("食事療法を選択すると、予測検査値と6アウトカムへ反映します。")

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
            with st.expander("効果量と根拠を確認", expanded=False):
                st.write(exercise_effect.evidence_summary)
                st.caption(exercise_effect.endpoint_evidence)
                st.link_button("根拠文献を開く", exercise_effect.source_url)
        else:
            st.caption("運動療法を選択すると、予測検査値と6アウトカムへ反映します。")
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

with result_col:
    st.markdown('<div class="result-anchor" aria-hidden="true"></div>', unsafe_allow_html=True)
    st.subheader("リアルタイム予測")
    selected_outcome = st.radio(
        "表示するアウトカム",
        OUTCOME_DISPLAY_ORDER,
        index=0,
        format_func=lambda value: OUTCOME_META[value]["label"],
        horizontal=True,
        key="display_outcome",
    )
    selected_data = cumulative_data[selected_outcome]
    baseline_risk = selected_data["baseline_cumulative"][-1]
    target_risk = selected_data["target_cumulative"][-1]
    arr = baseline_risk - target_risk

    metric_cols = st.columns(3)
    if care_mode == "continue":
        harm = target_risk - baseline_risk
        metric_cols[0].metric(f"{horizon}年・服薬継続", f"{baseline_risk:.1f}%")
        metric_cols[1].metric(f"{horizon}年・今日から全薬中止", f"{target_risk:.1f}%")
        metric_cols[2].metric("中止によるリスク増加", f"+{harm:.1f} pt")
    else:
        metric_cols[0].metric(f"{horizon}年・現在", f"{baseline_risk:.1f}%")
        metric_cols[1].metric(f"{horizon}年・目標達成時", f"{target_risk:.1f}%")
        metric_cols[2].metric("リスク減少幅", f"{arr:.1f} pt")

    st.plotly_chart(
        plot_risk_curve(selected_outcome, selected_data),
        width="stretch",
        config={"displayModeBar": False},
    )
    if selected_outcome == "mortality":
        st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)

    if care_mode != "continue":
        with st.container(border=True):
            st.markdown(
                f'<h4 class="arr-breakdown-title" translate="no" '
                f'data-title="各治療によるリスク減少（{horizon}年間）"></h4>',
                unsafe_allow_html=True,
            )
            contributions = build_medication_contributions(selected_outcome, horizon)
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
    elif selected_meds:
        st.success("現在の良好な検査値と低い将来リスクは、服薬継続で得られている効果です。自己判断で中止せず主治医と相談しましょう。")
    else:
        st.info("左側で現在服用中の薬を選ぶと、全薬中止との比較を表示します。")

    with st.container(border=True):
        st.markdown("#### 6アウトカムの比較")
        summary_cols = st.columns(3)
        for index, outcome in enumerate(OUTCOME_DISPLAY_ORDER):
            data = cumulative_data[outcome]
            outcome_arr = data["baseline_cumulative"][-1] - data["target_cumulative"][-1]
            if care_mode == "continue":
                stopping_harm = max(0.0, -outcome_arr)
                summary_cols[index % 3].metric(
                    f"{OUTCOME_META[outcome]['label']}（継続）",
                    f"{data['baseline_cumulative'][-1]:.1f}%",
                    delta=f"中止で +{stopping_harm:.1f} pt",
                    delta_color="inverse",
                )
            else:
                summary_cols[index % 3].metric(
                    OUTCOME_META[outcome]["label"],
                    f"{data['target_cumulative'][-1]:.1f}%",
                    delta=f"{outcome_arr:.1f} pt減少",
                    delta_color="normal",
                )

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
