# app_streamlit_outcomes.py
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from calc_engine_outcomes import OutcomesEngine
from meds_catalog import apply_meds_to_targets, load_meds_catalog


st.set_page_config(
    page_title="JP Outcomes Prevention Simulator (MVP)",
    layout="wide",
    page_icon="🫐",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1500px; padding-top: 1.5rem;}
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
    @media (max-width: 900px) {
        .contribution-row {grid-template-columns: 1fr 70px;}
        .contribution-track {grid-column: 1 / -1; grid-row: 2;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🫐📈 アウトカムベース一次予防シミュレーター（MVP）")
st.caption("教育・共有意思決定のため。医療機器ではありません。")

engine = OutcomesEngine("config.yaml")

MORTALITY_ALL_CAUSE_DEATH_CAPTION = (
    "※全死亡は、心血管疾患に限らず、がんや他の病気を含むすべての死亡を対象としています。"
)
OUTCOME_DISPLAY_ORDER = ("mortality", "mi", "stroke")
OUTCOME_META = {
    "mortality": {"label": "全死亡", "title": "💀 全死亡", "color": "#d95656"},
    "mi": {"label": "心筋梗塞", "title": "🫐 心筋梗塞", "color": "#e07b39"},
    "stroke": {"label": "脳卒中", "title": "🧠 脳卒中", "color": "#7656c9"},
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


def calculate_cumulative_risk_curves(years: int):
    cumulative_data = {}
    for outcome in OUTCOME_DISPLAY_ORDER:
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
    return cumulative_data


def risk_at_horizon(outcome: str, horizon: int, targets: dict) -> float:
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
    if not ordered_meds:
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
            name="目標達成時 95%CI",
            hoverinfo="skip",
            fillcolor="rgba(20, 134, 109, 0.11)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[:cut_idx],
            y=baseline[:cut_idx],
            mode="lines",
            name="現在のリスク因子",
            line=dict(color="#d34b4b", width=3),
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
            line=dict(color="#d34b4b", width=3),
            hovertemplate="%{x:.0f}年：%{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t[:cut_idx],
            y=target[:cut_idx],
            mode="lines",
            name="薬剤／目標達成時",
            line=dict(color="#14866d", width=3),
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
            line=dict(color="#14866d", width=3),
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

    with st.container(border=True):
        st.markdown("#### 患者プロフィール")
        profile_left, profile_right = st.columns(2)
        with profile_left:
            sex = st.selectbox(
                "性別",
                ["male", "female"],
                format_func=lambda value: "男性" if value == "male" else "女性",
            )
        with profile_right:
            age = st.number_input("年齢（歳）", 20, 95, 60, step=1)

    with st.container(border=True):
        st.markdown("#### リスク因子（現在 → 目標）")
        st.caption("薬剤を選択する場合、血圧・LDL・HbA1cの目標値は自動計算されます。")
        now_col, target_col = st.columns(2)
        with now_col:
            st.markdown("**現在**")
            sbp_now = st.slider("収縮期血圧 (mmHg)", 90, 200, 150, key="sbp_now")
            ldl_now = st.slider("LDL (mg/dL)", 50, 250, 160, key="ldl_now")
            a1c_now = st.slider("HbA1c (%)", 5.0, 12.0, 8.0, step=0.1, key="a1c_now")
        with target_col:
            st.markdown("**目標**")
            sbp_tgt_manual = st.slider("収縮期血圧 (mmHg)", 90, 160, 130, key="sbp_target")
            ldl_tgt_manual = st.slider("LDL (mg/dL)", 50, 160, 100, key="ldl_target")
            a1c_tgt_manual = st.slider("HbA1c (%)", 5.0, 9.0, 7.0, step=0.1, key="a1c_target")

    with st.expander("喫煙・BMI・CKD", expanded=False):
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

        egfr_left, egfr_right = st.columns(2)
        with egfr_left:
            egfr_now = st.number_input("現在のeGFR", 5.0, 120.0, 80.0, 1.0)
            acr_now = st.selectbox("尿アルブミン／蛋白（現在）", ["A1", "A2", "A3"])
        with egfr_right:
            egfr_target = st.number_input("目標eGFR", 5.0, 120.0, 80.0, 1.0)
            acr_target = st.selectbox("尿アルブミン／蛋白（目標）", ["A1", "A2", "A3"])

    with st.container(border=True):
        st.markdown("#### 💊 薬剤")
        use_meds = st.checkbox("薬剤から目標値を自動計算する", value=True)
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
            sbp_keys = st.multiselect("降圧薬（SBPに反映）", sbp_options)
            ldl_keys = st.multiselect("脂質薬（LDLに反映）", ldl_options)
            a1c_keys = st.multiselect("糖尿病薬（HbA1cに反映）", a1c_options)
            selected_sbp_meds = [med for med in meds_catalog["sbp"] if med["key"] in sbp_keys]
            selected_ldl_meds = [med for med in meds_catalog["ldl"] if med["key"] in ldl_keys]
            selected_a1c_meds = [med for med in meds_catalog["hba1c"] if med["key"] in a1c_keys]
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
            target_metrics[0].metric("SBP目標", f"{sbp_tgt:.0f}")
            target_metrics[1].metric("LDL目標", f"{ldl_tgt:.0f}")
            target_metrics[2].metric("HbA1c目標", f"{a1c_tgt:.1f}")
        else:
            sbp_tgt = float(sbp_tgt_manual)
            ldl_tgt = float(ldl_tgt_manual)
            a1c_tgt = float(a1c_tgt_manual)
            annual_cost_yen = 0
            side_effects_md = ""

    display_left, display_right = st.columns(2)
    with display_left:
        selected_outcome = st.selectbox(
            "右に表示するアウトカム",
            OUTCOME_DISPLAY_ORDER,
            format_func=lambda value: OUTCOME_META[value]["label"],
        )
    with display_right:
        horizon_choice = st.selectbox(
            "予測期間",
            ["5-year", "10-year", "20-year", "30-year", "50-year"],
            index=2,
            format_func=lambda value: f"{_years_from_choice(value)}年",
        )

horizon = _years_from_choice(horizon_choice)
cumulative_data = calculate_cumulative_risk_curves(horizon)

with result_col:
    st.subheader("リアルタイム予測")
    selected_data = cumulative_data[selected_outcome]
    baseline_risk = selected_data["baseline_cumulative"][-1]
    target_risk = selected_data["target_cumulative"][-1]
    arr = baseline_risk - target_risk

    metric_cols = st.columns(3)
    metric_cols[0].metric(f"{horizon}年・現在", f"{baseline_risk:.1f}%")
    metric_cols[1].metric(f"{horizon}年・目標達成時", f"{target_risk:.1f}%")
    metric_cols[2].metric("絶対リスク減少（ARR）", f"{arr:.1f} pt")

    st.plotly_chart(
        plot_risk_curve(selected_outcome, selected_data),
        width="stretch",
        config={"displayModeBar": False},
    )
    if selected_outcome == "mortality":
        st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)

    with st.container(border=True):
        st.markdown(f"#### 何がどれくらい下げているか（{horizon}年ARR）")
        contributions = build_medication_contributions(selected_outcome, horizon)
        if not contributions:
            st.info("薬剤を選ぶと、各薬剤の追加によるリスク低下幅をここに表示します。")
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
            st.caption("表示順に1剤ずつ追加したときの追加ARRです。併用順によって内訳は変わります。")

    with st.container(border=True):
        st.markdown("#### 3アウトカムの比較")
        summary_cols = st.columns(3)
        for index, outcome in enumerate(OUTCOME_DISPLAY_ORDER):
            data = cumulative_data[outcome]
            outcome_arr = data["baseline_cumulative"][-1] - data["target_cumulative"][-1]
            summary_cols[index].metric(
                OUTCOME_META[outcome]["label"],
                f"{data['target_cumulative'][-1]:.1f}%",
                delta=f"ARR {outcome_arr:.1f} pt",
                delta_color="normal",
            )

    with st.expander("💴 費用と主な副作用"):
        if use_meds and meds_summary is not None:
            st.metric("年間薬剤費（合計）", f"{annual_cost_yen:,} 円/年")
            if side_effects_md.strip():
                st.markdown("**主な副作用（薬剤ごと）**")
                st.markdown(side_effects_md)
        else:
            st.info("薬剤を選択していないため、費用・副作用は表示しません。")

st.caption(
    "※ 薬剤ごとのARRは、既存の薬効・用量・リスクモデルをそのまま使い、"
    "選択した薬剤を順に加えた際の表示上の差を分解したものです。"
)
