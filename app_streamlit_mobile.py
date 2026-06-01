import hashlib

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from calc_engine_outcomes import OutcomesEngine
from meds_catalog import load_meds_catalog, apply_meds_to_targets

st.set_page_config(
    page_title="一次予防リスク（モバイル）",
    layout="centered",
    page_icon="🫀",
)

st.title("🫀 一次予防リスクシミュレーター")
st.subheader("（モバイル版）")
st.caption("将来の心血管リスクと、改善した場合の変化を簡単に確認できます。")
st.link_button("💻 詳細版（PC版）はこちら", "https://japan-cvd-risk-simulator.streamlit.app/")

engine = OutcomesEngine("config.yaml")

# ====== 薬剤Excelのパス ======
BP_XLSX_PATH = "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx"
LIPID_GLU_XLSX_PATH = "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx"

@st.cache_data(show_spinner=False)
def _cached_catalog(bp_path: str, lipid_glu_path: str):
    return load_meds_catalog(bp_path, lipid_glu_path)

meds_catalog = None
catalog_error = None
try:
    meds_catalog = _cached_catalog(BP_XLSX_PATH, LIPID_GLU_XLSX_PATH)
except Exception as e:
    catalog_error = str(e)

if "calculated" not in st.session_state:
    st.session_state.calculated = False
    st.session_state.cumulative_data = None
    st.session_state.params_hash = None


def calculate_cumulative_curves():
    if which == "5-year":
        years = 5
    elif which == "10-year":
        years = 10
    elif which == "20-year":
        years = 20
    elif which == "30-year":
        years = 30
    elif which == "50-year":
        years = 50

    calc_years = np.arange(1, years + 1, 1)
    cumulative_data = {}

    for outcome in ["mi", "stroke", "mortality"]:
        cumulative_data[outcome] = {
            "baseline_cumulative": [],
            "target_cumulative": [],
            "baseline_ci_lower": [],
            "baseline_ci_upper": [],
            "target_ci_lower": [],
            "target_ci_upper": [],
        }
        cumulative_data[outcome]["time"] = [0.0]
        cumulative_data[outcome]["baseline_cumulative"] = [0.0]
        cumulative_data[outcome]["target_cumulative"] = [0.0]
        cumulative_data[outcome]["baseline_ci_lower"] = [0.0]
        cumulative_data[outcome]["baseline_ci_upper"] = [0.0]
        cumulative_data[outcome]["target_ci_lower"] = [0.0]
        cumulative_data[outcome]["target_ci_upper"] = [0.0]

        AGE_CAP = 110
        for y in calc_years:
            age_at_t = age + y
            if age_at_t > AGE_CAP:
                break

            res = engine.cumulative_incidence_with_ci(
                outcome,
                sex,
                age,
                int(y),
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
                bmi_now=None,
                bmi_target=None,
                egfr_now=None,
                egfr_target=None,
                acr_now=None,
                acr_target=None,
            )
            cumulative_data[outcome]["time"].append(float(y))
            cumulative_data[outcome]["baseline_cumulative"].append(res["point"]["baseline"] * 100.0)
            cumulative_data[outcome]["target_cumulative"].append(res["point"]["target"] * 100.0)
            cumulative_data[outcome]["baseline_ci_lower"].append(res["lower"]["baseline"] * 100.0)
            cumulative_data[outcome]["baseline_ci_upper"].append(res["upper"]["baseline"] * 100.0)
            cumulative_data[outcome]["target_ci_lower"].append(res["lower"]["target"] * 100.0)
            cumulative_data[outcome]["target_ci_upper"].append(res["upper"]["target"] * 100.0)

    from scipy.interpolate import make_interp_spline

    for outcome in ["mi", "stroke", "mortality"]:
        ts = np.array(cumulative_data[outcome]["time"], dtype=float)
        base = np.array(cumulative_data[outcome]["baseline_cumulative"], dtype=float)
        targ = np.array(cumulative_data[outcome]["target_cumulative"], dtype=float)
        bl_l = np.array(cumulative_data[outcome]["baseline_ci_lower"], dtype=float)
        bl_u = np.array(cumulative_data[outcome]["baseline_ci_upper"], dtype=float)
        tg_l = np.array(cumulative_data[outcome]["target_ci_lower"], dtype=float)
        tg_u = np.array(cumulative_data[outcome]["target_ci_upper"], dtype=float)

        if len(ts) >= 4:
            dense_times = np.linspace(ts[0], ts[-1], max(101, int((ts[-1] - ts[0]) * 20)))
            base_s = make_interp_spline(ts, base, k=3)(dense_times)
            targ_s = make_interp_spline(ts, targ, k=3)(dense_times)
            bl_l_s = np.interp(dense_times, ts, bl_l)
            bl_u_s = np.interp(dense_times, ts, bl_u)
            tg_l_s = np.interp(dense_times, ts, tg_l)
            tg_u_s = np.interp(dense_times, ts, tg_u)

            cumulative_data[outcome]["time"] = dense_times
            cumulative_data[outcome]["baseline_cumulative"] = base_s
            cumulative_data[outcome]["target_cumulative"] = targ_s
            cumulative_data[outcome]["baseline_ci_lower"] = bl_l_s
            cumulative_data[outcome]["baseline_ci_upper"] = bl_u_s
            cumulative_data[outcome]["target_ci_lower"] = tg_l_s
            cumulative_data[outcome]["target_ci_upper"] = tg_u_s

    return cumulative_data


def _smooth_main_lines(fig):
    for trace in fig.data:
        if (
            trace.mode == "lines"
            and hasattr(trace, "name")
            and trace.name
            and "95%CI" not in trace.name
        ):
            trace.update(line=dict(smoothing=1.0, shape="spline"))


def figure_mi(cumulative_data, age):
    fig = go.Figure()
    _t = np.array(cumulative_data["mi"]["time"], dtype=float)
    _b = np.array(cumulative_data["mi"]["baseline_cumulative"], dtype=float)
    _tg = np.array(cumulative_data["mi"]["target_cumulative"], dtype=float)
    cutoff_year = max(0.0, 85.0 - float(age))
    cut_idx = int(np.searchsorted(_t, cutoff_year, side="right"))

    fig.add_trace(
        go.Scatter(
            x=_t[:cut_idx],
            y=_b[:cut_idx],
            mode="lines",
            name="現在のリスク因子",
            line=dict(color="#ff6b6b", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[cut_idx:],
            y=_b[cut_idx:],
            mode="lines",
            name="現在のリスク因子（≥85歳推定域）",
            line=dict(color="rgba(255,107,107,0.45)", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[:cut_idx],
            y=_tg[:cut_idx],
            mode="lines",
            name="目標達成時",
            line=dict(color="#10B981", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[cut_idx:],
            y=_tg[cut_idx:],
            mode="lines",
            name="目標達成時（≥85歳推定域）",
            line=dict(color="rgba(16, 185, 129, 0.45)", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mi"]["time"],
            y=cumulative_data["mi"]["baseline_ci_upper"],
            fill=None,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mi"]["time"],
            y=cumulative_data["mi"]["baseline_ci_lower"],
            fill="tonexty",
            mode="lines",
            line=dict(width=0),
            name="現在のリスク因子 95%CI",
            fillcolor="rgba(255,107,107,0.2)",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mi"]["time"],
            y=cumulative_data["mi"]["target_ci_upper"],
            fill=None,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mi"]["time"],
            y=cumulative_data["mi"]["target_ci_lower"],
            fill="tonexty",
            mode="lines",
            line=dict(width=0),
            name="目標達成時 95%CI",
            fillcolor="rgba(16, 185, 129, 0.2)",
            showlegend=False,
        )
    )
    fig.update_layout(
        xaxis_title="年数",
        yaxis_title="累積リスク（%）",
        height=320,
        showlegend=False,
        hovermode="x unified",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    _smooth_main_lines(fig)
    return fig


def figure_stroke(cumulative_data, age):
    fig = go.Figure()
    _t = np.array(cumulative_data["stroke"]["time"], dtype=float)
    _b = np.array(cumulative_data["stroke"]["baseline_cumulative"], dtype=float)
    _tg = np.array(cumulative_data["stroke"]["target_cumulative"], dtype=float)
    cutoff_year = max(0.0, 85.0 - float(age))
    cut_idx = int(np.searchsorted(_t, cutoff_year, side="right"))

    fig.add_trace(
        go.Scatter(
            x=_t[:cut_idx],
            y=_b[:cut_idx],
            mode="lines",
            name="現在のリスク因子",
            line=dict(color="#ff6b6b", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[cut_idx:],
            y=_b[cut_idx:],
            mode="lines",
            name="現在のリスク因子（≥85歳推定域）",
            line=dict(color="rgba(255,107,107,0.45)", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[:cut_idx],
            y=_tg[:cut_idx],
            mode="lines",
            name="目標達成時",
            line=dict(color="#10B981", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[cut_idx:],
            y=_tg[cut_idx:],
            mode="lines",
            name="目標達成時（≥85歳推定域）",
            line=dict(color="rgba(16, 185, 129, 0.45)", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["stroke"]["time"],
            y=cumulative_data["stroke"]["baseline_ci_upper"],
            fill=None,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["stroke"]["time"],
            y=cumulative_data["stroke"]["baseline_ci_lower"],
            fill="tonexty",
            mode="lines",
            line=dict(width=0),
            name="現在のリスク因子 95%CI",
            fillcolor="rgba(255,107,107,0.2)",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["stroke"]["time"],
            y=cumulative_data["stroke"]["target_ci_upper"],
            fill=None,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["stroke"]["time"],
            y=cumulative_data["stroke"]["target_ci_lower"],
            fill="tonexty",
            mode="lines",
            line=dict(width=0),
            name="目標達成時 95%CI",
            fillcolor="rgba(16, 185, 129, 0.2)",
            showlegend=False,
        )
    )
    fig.update_layout(
        xaxis_title="年数",
        yaxis_title="累積リスク（%）",
        height=320,
        showlegend=False,
        hovermode="x unified",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    _smooth_main_lines(fig)
    return fig


def figure_mortality(cumulative_data, age):
    fig = go.Figure()
    _t = np.array(cumulative_data["mortality"]["time"], dtype=float)
    _b = np.array(cumulative_data["mortality"]["baseline_cumulative"], dtype=float)
    _tg = np.array(cumulative_data["mortality"]["target_cumulative"], dtype=float)
    cutoff_year = max(0.0, 85.0 - float(age))
    cut_idx = int(np.searchsorted(_t, cutoff_year, side="right"))

    fig.add_trace(
        go.Scatter(
            x=_t[:cut_idx],
            y=_b[:cut_idx],
            mode="lines",
            name="現在のリスク因子",
            line=dict(color="#ef5350", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[cut_idx:],
            y=_b[cut_idx:],
            mode="lines",
            name="現在のリスク因子（≥85歳推定域）",
            line=dict(color="rgba(239,83,80,0.45)", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[:cut_idx],
            y=_tg[:cut_idx],
            mode="lines",
            name="目標達成時",
            line=dict(color="#10B981", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_t[cut_idx:],
            y=_tg[cut_idx:],
            mode="lines",
            name="目標達成時（≥85歳推定域）",
            line=dict(color="rgba(16, 185, 129, 0.45)", width=2),
            showlegend=False,
            hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mortality"]["time"],
            y=cumulative_data["mortality"]["baseline_ci_upper"],
            fill=None,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mortality"]["time"],
            y=cumulative_data["mortality"]["baseline_ci_lower"],
            fill="tonexty",
            mode="lines",
            line=dict(width=0),
            name="現在のリスク因子 95%CI",
            fillcolor="rgba(239,83,80,0.2)",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mortality"]["time"],
            y=cumulative_data["mortality"]["target_ci_upper"],
            fill=None,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=cumulative_data["mortality"]["time"],
            y=cumulative_data["mortality"]["target_ci_lower"],
            fill="tonexty",
            mode="lines",
            line=dict(width=0),
            name="目標達成時 95%CI",
            fillcolor="rgba(16, 185, 129, 0.2)",
            showlegend=False,
        )
    )
    fig.update_layout(
        xaxis_title="年数",
        yaxis_title="累積リスク（%）",
        height=320,
        showlegend=False,
        hovermode="x unified",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    _smooth_main_lines(fig)
    return fig


st.subheader("入力")

with st.expander("基本情報", expanded=True):
    sex = st.selectbox(
        "性別",
        ["male", "female"],
        format_func=lambda x: "男性" if x == "male" else "女性",
    )
    age = st.number_input("年齢（歳）", 20, 95, 60, step=1)

with st.expander("検査値", expanded=True):
    sbp_now = st.slider("収縮期血圧 現在 (mmHg)", 90, 200, 150)
    sbp_tgt = st.slider("収縮期血圧 目標 (mmHg)", 90, 160, 130)

    ldl_now = st.slider("LDLコレステロール 現在 (mg/dL)", 50, 250, 160)
    ldl_tgt = st.slider("LDLコレステロール 目標 (mg/dL)", 50, 160, 100)

    a1c_now = st.slider("HbA1c 現在 (%)", 5.0, 12.0, 8.0, step=0.1)
    a1c_tgt = st.slider("HbA1c 目標 (%)", 5.0, 9.0, 7.0, step=0.1)

with st.expander("生活習慣その他", expanded=True):
    smoking_status = st.selectbox(
        "喫煙状況",
        ["never", "current", "former"],
        format_func=lambda x: {"never": "非喫煙者", "current": "現在喫煙者", "former": "元喫煙者"}[x],
    )
    if smoking_status == "never":
        cigs_per_day = 0
        years_smoked = 0.0
        years_since_quit = 0.0
        quit_today = False
    elif smoking_status == "current":
        cigs_per_day = st.slider("1日あたりの喫煙本数", 0, 40, 20)
        years_smoked = st.slider("喫煙年数", 0, 60, 20)
        years_since_quit = 0.0
        quit_today = st.checkbox("今日禁煙したと仮定（目標シナリオ）")
    else:
        cigs_per_day = st.slider("1日あたりの喫煙本数", 0, 40, 20)
        years_smoked = st.slider("喫煙年数", 0, 60, 20)
        years_since_quit = st.slider("禁煙からの年数（元喫煙者の場合）", 0, 40, 5)
        quit_today = False

# ====== 薬剤選択 ======
selected_sbp_meds = []
selected_ldl_meds = []
selected_a1c_meds = []
meds_summary = None
use_meds = False

with st.expander("💊 薬剤で目標値を自動生成", expanded=True):
    use_meds = st.checkbox("薬剤を選んで目標値を自動計算する", value=True)

    if catalog_error:
        st.warning("薬剤カタログ読み込みに失敗。Excelのパス/シート名/列名を確認してください。")
        st.caption(catalog_error)
        use_meds = False

    if use_meds and meds_catalog:
        sbp_options = [m["key"] for m in meds_catalog["sbp"]]
        sbp_sel_keys = st.multiselect("降圧薬（SBPに反映）", options=sbp_options)
        selected_sbp_meds = [m for m in meds_catalog["sbp"] if m["key"] in sbp_sel_keys]

        ldl_options = [m["key"] for m in meds_catalog["ldl"]]
        ldl_sel_keys = st.multiselect("脂質薬（LDLに反映）", options=ldl_options)
        selected_ldl_meds = [m for m in meds_catalog["ldl"] if m["key"] in ldl_sel_keys]

        a1c_options = [m["key"] for m in meds_catalog["hba1c"]]
        a1c_sel_keys = st.multiselect("糖尿病薬（HbA1cに反映）", options=a1c_options)
        selected_a1c_meds = [m for m in meds_catalog["hba1c"] if m["key"] in a1c_sel_keys]

        meds_summary = apply_meds_to_targets(
            sbp_now=float(sbp_now),
            ldl_now_mg=float(ldl_now),
            a1c_now=float(a1c_now),
            selected_sbp=selected_sbp_meds,
            selected_ldl=selected_ldl_meds,
            selected_a1c=selected_a1c_meds,
        )

        st.caption("合成ルール：SBPは足し算 / LDLは%低下を掛け算 / HbA1cは足し算")
        st.metric("年間薬剤費（合計）", f"{meds_summary['annual_cost_yen']:,} 円/年")
        st.markdown("**自動計算された目標値（この値でリスク計算）**")
        st.write(f"- SBP 目標: **{meds_summary['sbp_target']:.0f} mmHg**")
        st.write(f"- LDL 目標: **{meds_summary['ldl_target']:.0f} mg/dL**")
        st.write(f"- HbA1c 目標: **{meds_summary['a1c_target']:.1f} %**")

        if meds_summary["side_effects_md"].strip():
            with st.expander("主な副作用（薬剤ごと）"):
                st.markdown(meds_summary["side_effects_md"])
    else:
        st.caption("薬剤を使わない場合は、上の手動目標値で計算します。")

# ====== 実際に使う目標値 ======
if use_meds and meds_summary is not None:
    sbp_tgt = float(meds_summary["sbp_target"])
    ldl_tgt = float(meds_summary["ldl_target"])
    a1c_tgt = float(meds_summary["a1c_target"])
    annual_cost_yen = int(meds_summary["annual_cost_yen"])
    side_effects_md = meds_summary["side_effects_md"]
else:
    sbp_tgt = float(sbp_tgt)
    ldl_tgt = float(ldl_tgt)
    a1c_tgt = float(a1c_tgt)
    annual_cost_yen = 0
    side_effects_md = ""

which = st.radio(
    "予測期間",
    ["5-year", "10-year", "20-year", "30-year", "50-year"],
    index=2,
    format_func=lambda x: {
        "5-year": "5年",
        "10-year": "10年",
        "20-year": "20年",
        "30-year": "30年",
        "50-year": "50年",
    }[x],
)

# ---- パラメータ変更検知と自動計算 ----
current_params = {
    "sex": sex, "age": age,
    "sbp_now": sbp_now, "sbp_tgt": sbp_tgt,
    "ldl_now": ldl_now, "ldl_tgt": ldl_tgt,
    "a1c_now": a1c_now, "a1c_tgt": a1c_tgt,
    "smoking_status": smoking_status, "cigs_per_day": cigs_per_day,
    "years_smoked": years_smoked, "years_since_quit": years_since_quit,
    "quit_today": quit_today,
    "which": which,
    "sbp_meds": tuple(sbp_sel_keys) if use_meds and meds_catalog else (),
    "ldl_meds": tuple(ldl_sel_keys) if use_meds and meds_catalog else (),
    "a1c_meds": tuple(a1c_sel_keys) if use_meds and meds_catalog else (),
    "use_meds": use_meds,
}
params_hash = hashlib.md5(str(sorted(current_params.items())).encode()).hexdigest()

params_changed = st.session_state.params_hash != params_hash
should_auto_calculate = params_changed and st.session_state.calculated

manual_button_clicked = st.button("🔄 リスク計算を実行", type="primary")
if manual_button_clicked or should_auto_calculate:
    with st.spinner("リスク計算中..."):
        st.session_state.cumulative_data = calculate_cumulative_curves()
        st.session_state.calculated = True
        st.session_state.params_hash = params_hash

if not st.session_state.calculated:
    st.info("👆 上記のパラメータを設定して「リスク計算を実行」を押してください")
    st.stop()

cumulative_data = st.session_state.cumulative_data

if which == "5-year":
    horizons = [5]
elif which == "10-year":
    horizons = [10]
elif which == "20-year":
    horizons = [20]
elif which == "30-year":
    horizons = [30]
else:
    horizons = [50]

h = horizons[0]
# labels = {"mi": "心筋梗塞", "stroke": "脳卒中", "mortality": "全死亡"}

labels = {
    "mi": "心筋梗塞",
    "stroke": "脳卒中",
    "mortality": "全死亡 <span style='font-size: 11px; font-weight: normal; color: #6b7280; margin-left: 8px;'>※死亡は癌や寿命など全ての疾患を含みます</span>"
}

r_by_outcome = {}
for outcome in ["mi", "stroke", "mortality"]:
    r_by_outcome[outcome] = engine.cumulative_incidence(
        outcome,
        sex,
        age,
        h,
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
        assume_quit_today_in_target=quit_today,
    )

st.markdown(f"#### 結果サマリー（{h}年）")

for outcome in ["mortality", "mi", "stroke"]:
    r = r_by_outcome[outcome]
    diff = r["baseline"] - r["target"]
    st.markdown(f"""
    <div style="background-color: #ffffff; border-radius: 8px; box-s
    hadow: 0 2px 4px rgba(0,0,0,0.05); padding: 15px; margin-bottom: 10px; border: 1px solid #e5e7eb;">
        <strong style="font-size: 16px; color: #374151; display: block; margin-bottom: 12px;">{labels[outcome]}</strong>
        <div style="display: flex; justify-content: space-around;">
            <div style="text-align: center;">
                <p style="margin: 0; font-size: 14px; color: #6b7280; font-weight: bold;">現在</p>
                <p style="margin: 0; font-size: 20px; font-weight: bold; color: {'#ff6b6b' if outcome != 'stroke' else '#ff6b6b'};">{100 * r['baseline']:.1f}%</p>
            </div>
            <div style="text-align: center;">
                <p style="margin: 0; font-size: 14px; color: #6b7280; font-weight: bold;">目標</p>
                <p style="margin: 0; font-size: 20px; font-weight: bold; color: #10B981;">{100 * r['target']:.1f}%</p>
            </div>
            <div style="text-align: center;">
                <p style="margin: 0; font-size: 14px; color: #6b7280; font-weight: bold;">差</p>
                <p style="margin: 0; font-size: 20px; font-weight: bold; color: #F59E0B;">{100 * diff:+.1f}%</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

st.markdown("## 💴 費用と副作用（薬剤選択時）")
if use_meds and meds_summary is not None:
    st.metric("年間薬剤費（合計）", f"{annual_cost_yen:,} 円/年")
    if side_effects_md.strip():
        st.markdown("**主な副作用（薬剤ごと）**")
        st.markdown(side_effects_md)
else:
    st.info("薬剤を選択していないため、費用・副作用は表示しません。")

st.divider()
st.markdown("### 詳細表示")

detail_blocks = [
    ("mortality", "💀 全死亡", figure_mortality),
    ("mi", "🫀 心筋梗塞", figure_mi),
    ("stroke", "🧠 脳卒中", figure_stroke),
]

DETAIL_GRAPH_CAPTION = (
    "<span style='font-size: 14px;'>🔴 <strong>現在の推移</strong>　🟢 <strong>目標達成時</strong></span><br>"
    "<span style='font-size: 12px; color: #6b7280;'>※ 薄い帯：95%信頼区間　薄い線：85歳以上の推定域</span>"
)

for outcome_key, heading, fig_fn in detail_blocks:
    st.markdown(f"#### {heading} - 将来予測詳細グラフ")
    fig = fig_fn(cumulative_data, age)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown(DETAIL_GRAPH_CAPTION, unsafe_allow_html=True)
    st.markdown("---")

with st.expander("簡易注記"):
    st.markdown(
        """
- 教育・共有意思決定向けの簡易表示です。医療機器ではありません。
- 本画面は BMI・CKD を含みません（`app_streamlit_outcomes.py` の PC 版で入力できます）。
"""
    )
