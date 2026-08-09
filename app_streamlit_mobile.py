import hashlib
import re

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from calc_engine_outcomes import OutcomesEngine
from lifestyle_interventions import DIET_EFFECTS, EXERCISE_EFFECTS, apply_lifestyle_effects
from meds_catalog import load_meds_catalog, apply_meds_to_targets, MedicationAdjustment
import pdf_plan_ui

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

# ====== 薬増減モード（差分モデル）用ヘルパー ======
RX_ACTION_NO_CHANGE = "変更なし"
RX_ACTION_STOP = "中止"
RX_ACTION_DOWN = "減量"
RX_ACTION_UP = "増量"
RX_ACTION_SWITCH = "切替"


def _split_med_key(key: str):
    """'アムロジピン 5 mg' -> ('アムロジピン', 5.0)。用量数値が無ければ (key, None)。"""
    m = re.match(r"^(.*?)\s*([0-9]+(?:\.[0-9]+)?)", key)
    if not m:
        return key.strip(), None
    return m.group(1).strip(), float(m.group(2))


def _dose_ladder_keys(domain_meds, key):
    """同一薬剤名のエントリのキーを用量昇順で返す"""
    name, _ = _split_med_key(key)
    same = [m["key"] for m in domain_meds if _split_med_key(m["key"])[0] == name]
    return sorted(same, key=lambda k: _split_med_key(k)[1] or 0.0)


def _dose_neighbor_key(domain_meds, key, direction: int):
    """direction=+1 なら一段増量、-1 なら一段減量のキー。無ければ None。"""
    ladder = _dose_ladder_keys(domain_meds, key)
    if key not in ladder:
        return None
    idx = ladder.index(key) + direction
    if 0 <= idx < len(ladder):
        return ladder[idx]
    return None


def _switch_candidates(domain_meds, key, current_keys):
    """切替先候補：同ドメインのうち別薬剤名で、服用中でないもの"""
    name, _ = _split_med_key(key)
    return [
        m["key"]
        for m in domain_meds
        if _split_med_key(m["key"])[0] != name and m["key"] not in current_keys
    ]


def _effect_label(domain: str, med) -> str:
    """カタログの効果量をドメインごとの単位付きで表示する"""
    v = float(med["effect"]["mean"])
    if domain == "sbp":
        return f"SBP {v:+.1f} mmHg"
    if domain == "ldl":
        return f"LDL -{v * 100:.0f}%"
    return f"HbA1c {v:+.1f}%"


def render_rx_change_rows(domain_label, domain, domain_meds, current_keys, state_prefix):
    """現在薬1剤ごとにカード（枠付きコンテナ）を描画し、
    (変更後キーのリスト, 変更明細の文字列リスト) を返す。（案B カード型）"""
    by_key = {m["key"]: m for m in domain_meds}
    adjusted_keys = []
    change_lines = []
    for k in current_keys:
        med = by_key.get(k)
        if med is None:
            continue
        options = [RX_ACTION_NO_CHANGE, RX_ACTION_STOP]
        if _dose_neighbor_key(domain_meds, k, -1):
            options.append(RX_ACTION_DOWN)
        if _dose_neighbor_key(domain_meds, k, +1):
            options.append(RX_ACTION_UP)
        switch_opts = _switch_candidates(domain_meds, k, current_keys)
        if switch_opts:
            options.append(RX_ACTION_SWITCH)

        cost = med.get("annual_cost_yen") or 0
        with st.container(border=True):
            st.markdown(f"**{k}**")
            st.caption(
                f"{domain_label}｜{med.get('category', '')}｜"
                f"{_effect_label(domain, med)}・{cost:,} 円/年"
            )

            act_key = f"{state_prefix}_act_{k}"
            if act_key not in st.session_state:
                st.session_state[act_key] = RX_ACTION_NO_CHANGE
            action = st.segmented_control(
                f"{k} の変更",
                options,
                key=act_key,
                label_visibility="collapsed",
            ) or RX_ACTION_NO_CHANGE

            result_key = k
            ladder = _dose_ladder_keys(domain_meds, k)
            cur_idx = ladder.index(k) if k in ladder else 0
            if action == RX_ACTION_STOP:
                result_key = None
            elif action == RX_ACTION_DOWN:
                lower = ladder[:cur_idx]  # 現用量より下の用量（昇順）
                result_key = st.selectbox(
                    "減量後の用量",
                    lower,
                    index=len(lower) - 1,  # 既定は一段下
                    key=f"{state_prefix}_down_{k}",
                ) if lower else k
            elif action == RX_ACTION_UP:
                higher = ladder[cur_idx + 1:]  # 現用量より上の用量（昇順）
                result_key = st.selectbox(
                    "増量後の用量",
                    higher,
                    index=0,  # 既定は一段上
                    key=f"{state_prefix}_up_{k}",
                ) if higher else k
            elif action == RX_ACTION_SWITCH:
                result_key = st.selectbox("切替先", switch_opts, key=f"{state_prefix}_sw_{k}")

            # 変更後プレビュー（効果・費用差分をカード内に表示）
            if result_key is None:
                st.markdown(f"🛑 **中止**（費用 {-cost:+,} 円/年）")
                change_lines.append(f"🛑 中止: {k}")
            elif result_key != k:
                new_med = by_key[result_key]
                new_cost = new_med.get("annual_cost_yen") or 0
                icon = {RX_ACTION_UP: "🔼", RX_ACTION_DOWN: "🔽"}.get(action, "🔁")
                st.markdown(f"{icon} **{action} → {result_key}**")
                st.caption(
                    f"{_effect_label(domain, new_med)}・費用差 {new_cost - cost:+,} 円/年"
                )
                change_lines.append(f"{icon} {action}: {k} → {result_key}")
        if result_key is not None and result_key not in adjusted_keys:
            adjusted_keys.append(result_key)
    return adjusted_keys, change_lines


def _se_md_for_changes(stopped, added, continued):
    """副作用表示用Markdown。同一薬剤名の中止+追加は用量変更として1行にまとめる。"""
    stopped_by_name = {}
    for m in stopped:
        stopped_by_name.setdefault(_split_med_key(m["key"])[0], []).append(m)
    dose_changed = []
    pure_added = []
    for m in added:
        name = _split_med_key(m["key"])[0]
        if stopped_by_name.get(name):
            old = stopped_by_name[name].pop(0)
            dose_changed.append((old, m))
        else:
            pure_added.append(m)
    pure_stopped = [m for lst in stopped_by_name.values() for m in lst]

    def _items(meds_list):
        return [
            f"- {m['key']}: {(m.get('side_effects') or '').strip()}"
            for m in meds_list
            if (m.get("side_effects") or "").strip()
        ]

    sections = []
    if pure_stopped:
        items = _items(pure_stopped)
        if items:
            sections.append("**中止で消える副作用**\n" + "\n".join(items))
    if dose_changed:
        items = [
            f"- {old['key']} → {new['key']}: {(new.get('side_effects') or '').strip()}"
            for old, new in dose_changed
            if (new.get("side_effects") or "").strip()
        ]
        if items:
            sections.append("**用量変更後も続く副作用**\n" + "\n".join(items))
    if pure_added:
        items = _items(pure_added)
        if items:
            sections.append("**新規で追加される副作用**\n" + "\n".join(items))
    if continued:
        items = _items(continued)
        if items:
            sections.append("**継続中の副作用**\n" + "\n".join(items))
    return "\n\n".join(sections)


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

    # 療養計画書PDF用: 目標スライダーの値を保持（この後 use_meds で上書きされるため）
    sbp_tgt_manual = int(sbp_tgt)
    a1c_tgt_manual = float(a1c_tgt)

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

# ====== 食事・運動・薬剤（PC版と同じ統一介入モデル） ======
st.subheader("治療を選ぶ")
diet_intervention_keys = st.multiselect(
    "🥗 食事",
    list(DIET_EFFECTS),
    format_func=lambda key: DIET_EFFECTS[key].label,
    key="mobile_diet_interventions",
    placeholder="食事介入を選択",
)
exercise_intervention_key = st.selectbox(
    "🏃 運動",
    [None, *EXERCISE_EFFECTS],
    format_func=lambda key: "選択しない" if key is None else EXERCISE_EFFECTS[key].label,
    key="mobile_exercise_intervention",
)
with st.expander("効果量と文献を確認"):
    selected_lifestyle_keys = [
        *(DIET_EFFECTS[key] for key in diet_intervention_keys),
        *([EXERCISE_EFFECTS[exercise_intervention_key]] if exercise_intervention_key else []),
    ]
    if not selected_lifestyle_keys:
        st.caption("介入を選ぶと、ここに定義・効果量・根拠が表示されます。")
    for effect in selected_lifestyle_keys:
        st.markdown(f"**{effect.label}** — {effect.definition}")
        st.caption(f"{effect.evidence_summary} {effect.endpoint_evidence}")
        st.link_button("根拠文献", effect.source_url, key=f"mobile_lifestyle_source_{effect.key}")

selected_sbp_meds = []
selected_ldl_meds = []
selected_a1c_meds = []
sbp_sel_keys = []
ldl_sel_keys = []
a1c_sel_keys = []
current_sbp_keys = []
current_ldl_keys = []
current_a1c_keys = []
adjusted_sbp_keys = []
adjusted_ldl_keys = []
adjusted_a1c_keys = []
meds_summary = None
use_meds = False
mode = "add"

with st.expander("💊 お薬", expanded=True):
    use_meds = st.checkbox("薬剤を選んで目標値を自動計算する", value=True)

    if catalog_error:
        st.warning("薬剤カタログ読み込みに失敗。Excelのパス/シート名/列名を確認してください。")
        st.caption(catalog_error)
        use_meds = False

    if use_meds and meds_catalog:
        sbp_options = [m["key"] for m in meds_catalog["sbp"]]
        ldl_options = [m["key"] for m in meds_catalog["ldl"]]
        a1c_options = [m["key"] for m in meds_catalog["hba1c"]]

        mode = st.radio(
            "シミュレーションモード",
            ["add", "adjust"],
            format_func=lambda x: (
                "💊 薬を追加する" if x == "add"
                else "💊 薬を増減させる"
            ),
        )

        if mode == "add":
            sbp_sel_keys = st.multiselect("降圧薬（SBPに反映）", options=sbp_options)
            selected_sbp_meds = [m for m in meds_catalog["sbp"] if m["key"] in sbp_sel_keys]

            ldl_sel_keys = st.multiselect("脂質薬（LDLに反映）", options=ldl_options)
            selected_ldl_meds = [m for m in meds_catalog["ldl"] if m["key"] in ldl_sel_keys]

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
        else:
            # 薬増減UI：現在の治療をベースラインに、各薬をワンタップで 中止/減量/増量/切替
            st.markdown("**現在服用中の薬**")
            current_sbp_keys = st.multiselect(
                "降圧薬（現在）", options=sbp_options, key="mobile_current_sbp"
            )
            current_ldl_keys = st.multiselect(
                "脂質薬（現在）", options=ldl_options, key="mobile_current_ldl"
            )
            current_a1c_keys = st.multiselect(
                "糖尿病薬（現在）", options=a1c_options, key="mobile_current_a1c"
            )

            st.markdown("**各薬の変更（タップで選択）**")
            if not (current_sbp_keys or current_ldl_keys or current_a1c_keys):
                st.caption("現在服用中の薬を選ぶと、ここに変更ボタンが表示されます。")
            adjusted_sbp_keys, sbp_changes = render_rx_change_rows(
                "降圧薬", "sbp", meds_catalog["sbp"], current_sbp_keys, "m_sbp"
            )
            adjusted_ldl_keys, ldl_changes = render_rx_change_rows(
                "脂質薬", "ldl", meds_catalog["ldl"], current_ldl_keys, "m_ldl"
            )
            adjusted_a1c_keys, a1c_changes = render_rx_change_rows(
                "糖尿病薬", "hba1c", meds_catalog["hba1c"], current_a1c_keys, "m_a1c"
            )

            st.markdown("**➕ 薬を追加する（任意）**")
            add_sbp_keys = st.multiselect(
                "降圧薬（追加）",
                options=[o for o in sbp_options
                         if o not in current_sbp_keys and o not in adjusted_sbp_keys],
                key="m_add_sbp",
            )
            add_ldl_keys = st.multiselect(
                "脂質薬（追加）",
                options=[o for o in ldl_options
                         if o not in current_ldl_keys and o not in adjusted_ldl_keys],
                key="m_add_ldl",
            )
            add_a1c_keys = st.multiselect(
                "糖尿病薬（追加）",
                options=[o for o in a1c_options
                         if o not in current_a1c_keys and o not in adjusted_a1c_keys],
                key="m_add_a1c",
            )
            adjusted_sbp_keys = adjusted_sbp_keys + [k for k in add_sbp_keys if k not in adjusted_sbp_keys]
            adjusted_ldl_keys = adjusted_ldl_keys + [k for k in add_ldl_keys if k not in adjusted_ldl_keys]
            adjusted_a1c_keys = adjusted_a1c_keys + [k for k in add_a1c_keys if k not in adjusted_a1c_keys]

            rx_change_lines = (
                sbp_changes + ldl_changes + a1c_changes
                + [f"➕ 追加: {k}" for k in list(add_sbp_keys) + list(add_ldl_keys) + list(add_a1c_keys)]
            )
            if rx_change_lines:
                st.markdown("**変更内容**")
                for line in rx_change_lines:
                    st.write(line)

            current_meds = {
                "sbp": [m for m in meds_catalog["sbp"] if m["key"] in current_sbp_keys],
                "ldl": [m for m in meds_catalog["ldl"] if m["key"] in current_ldl_keys],
                "hba1c": [m for m in meds_catalog["hba1c"] if m["key"] in current_a1c_keys],
            }
            adjusted_meds = {
                "sbp": [m for m in meds_catalog["sbp"] if m["key"] in adjusted_sbp_keys],
                "ldl": [m for m in meds_catalog["ldl"] if m["key"] in adjusted_ldl_keys],
                "hba1c": [m for m in meds_catalog["hba1c"] if m["key"] in adjusted_a1c_keys],
            }

            adj = MedicationAdjustment(
                sbp_now=float(sbp_now),
                ldl_now_mg=float(ldl_now),
                a1c_now=float(a1c_now),
                current_meds=current_meds,
                adjusted_meds=adjusted_meds,
            )
            baseline_targets = adj.baseline_targets()
            adjusted_targets = adj.adjusted_targets()
            costs = adj.costs()
            se_changes = adj.side_effect_changes()

            current_key_set = {m["key"] for domain in current_meds.values() for m in domain}
            continued_meds = [
                m
                for domain in adjusted_meds.values()
                for m in domain
                if m["key"] in current_key_set
            ]

            side_effects_md = _se_md_for_changes(
                se_changes["stopped"], se_changes["added"], continued_meds
            )

            meds_summary = {
                "sbp_target": adjusted_targets["sbp_target"],
                "ldl_target": adjusted_targets["ldl_target"],
                "a1c_target": adjusted_targets["a1c_target"],
                "annual_cost_yen": costs["adjusted"],
                "side_effects_md": side_effects_md,
                "mode": "adjust",
                "baseline_targets": baseline_targets,
                "costs": costs,
            }

        st.caption("合成ルール：SBPは足し算 / LDLは%低下を掛け算 / HbA1cは足し算")
        if meds_summary is not None:
            if meds_summary.get("mode") == "adjust":
                st.metric("年間薬剤費（変更後）", f"{meds_summary['annual_cost_yen']:,} 円/年")
                st.markdown("**自動計算された目標値**")
                st.write(f"- SBP: **{meds_summary['sbp_target']:.0f} mmHg**")
                st.write(f"- LDL: **{meds_summary['ldl_target']:.0f} mg/dL**")
                st.write(f"- HbA1c: **{meds_summary['a1c_target']:.1f} %**")

                st.markdown("**薬剤変更の比較**")
                costs = meds_summary["costs"]
                delta = costs["delta"]
                delta_sign = "＋" if delta > 0 else ""
                st.write(
                    f"- 年間費用: {costs['baseline']:,} → {costs['adjusted']:,} "
                    f"（{delta_sign}{delta:,}）"
                )
                st.write(
                    f"- SBP: {meds_summary['baseline_targets']['sbp_target']:.0f} → "
                    f"{meds_summary['sbp_target']:.0f} mmHg"
                )
                st.write(
                    f"- LDL: {meds_summary['baseline_targets']['ldl_target']:.0f} → "
                    f"{meds_summary['ldl_target']:.0f} mg/dL"
                )
                st.write(
                    f"- HbA1c: {meds_summary['baseline_targets']['a1c_target']:.1f} → "
                    f"{meds_summary['a1c_target']:.1f} %"
                )
            else:
                st.metric("年間薬剤費（合計）", f"{meds_summary['annual_cost_yen']:,} 円/年")
                st.markdown("**自動計算された目標値**")
                st.write(f"- SBP: **{meds_summary['sbp_target']:.0f} mmHg**")
                st.write(f"- LDL: **{meds_summary['ldl_target']:.0f} mg/dL**")
                st.write(f"- HbA1c: **{meds_summary['a1c_target']:.1f} %**")

            if meds_summary["side_effects_md"].strip():
                # 外側が expander のためネストできない。見出し＋本文で表示する。
                st.markdown("**主な副作用（薬剤ごと）**")
                st.markdown(meds_summary["side_effects_md"])
        elif mode == "adjust":
            st.caption("薬増減モード：現在服用中の薬を選択してください。")
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

# 食事・運動も薬剤と同列の介入として、最終的な予測値に重ねる。
diabetes_context = bool(
    a1c_now >= 6.5 or current_a1c_keys or a1c_sel_keys or adjusted_a1c_keys
)
lifestyle_result = apply_lifestyle_effects(
    sbp=sbp_tgt,
    ldl=ldl_tgt,
    a1c=a1c_tgt,
    diet_keys=diet_intervention_keys,
    exercise_key=exercise_intervention_key,
    diabetes_context=diabetes_context,
)
sbp_tgt = lifestyle_result["sbp"]
ldl_tgt = lifestyle_result["ldl"]
a1c_tgt = lifestyle_result["a1c"]

selected_intervention_labels = [effect.label for effect in lifestyle_result["applied"]]
selected_medication_labels = (
    list(current_sbp_keys or sbp_sel_keys)
    + list(current_ldl_keys or ldl_sel_keys)
    + list(current_a1c_keys or a1c_sel_keys)
)
with st.container(border=True):
    st.markdown(
        f"**予測値**　血圧 {sbp_now:.0f}→**{sbp_tgt:.0f}**　"
        f"LDL {ldl_now:.0f}→**{ldl_tgt:.0f}**　HbA1c {a1c_now:.1f}→**{a1c_tgt:.1f}%**  \n"
        f"🥗 {('、'.join(selected_intervention_labels) if selected_intervention_labels else '未選択')}　／　"
        f"💊 {('、'.join(selected_medication_labels) if selected_medication_labels else '未選択')}"
    )
for effect in lifestyle_result["skipped"]:
    st.warning(
        f"{effect.label}は{effect.population}の根拠のため、現在の入力には効果量を適用していません。"
    )

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
    "mode": mode,
    "sbp_meds": (
        tuple(sbp_sel_keys)
        if mode == "add"
        else tuple(current_sbp_keys) + tuple(adjusted_sbp_keys)
    ),
    "ldl_meds": (
        tuple(ldl_sel_keys)
        if mode == "add"
        else tuple(current_ldl_keys) + tuple(adjusted_ldl_keys)
    ),
    "a1c_meds": (
        tuple(a1c_sel_keys)
        if mode == "add"
        else tuple(current_a1c_keys) + tuple(adjusted_a1c_keys)
    ),
    "use_meds": use_meds,
    "diet_interventions": tuple(diet_intervention_keys),
    "exercise_intervention": exercise_intervention_key,
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
    if meds_summary.get("mode") == "adjust":
        costs = meds_summary["costs"]
        delta = costs["delta"]
        delta_sign = "＋" if delta > 0 else ""
        st.metric("年間薬剤費（現在）", f"{costs['baseline']:,} 円/年")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("変更後", f"{costs['adjusted']:,} 円/年")
        with col2:
            st.metric("差分", f"{delta_sign}{delta:,} 円/年")
        st.markdown("**目標値の変化**")
        st.write(
            f"- SBP: {meds_summary['baseline_targets']['sbp_target']:.0f} → "
            f"{meds_summary['sbp_target']:.0f} mmHg"
        )
        st.write(
            f"- LDL: {meds_summary['baseline_targets']['ldl_target']:.0f} → "
            f"{meds_summary['ldl_target']:.0f} mg/dL"
        )
        st.write(
            f"- HbA1c: {meds_summary['baseline_targets']['a1c_target']:.1f} → "
            f"{meds_summary['a1c_target']:.1f} %"
        )
    else:
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
    st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
    st.markdown(DETAIL_GRAPH_CAPTION, unsafe_allow_html=True)
    st.markdown("---")

with st.expander("簡易注記"):
    st.markdown(
        """
- 教育・共有意思決定向けの簡易表示です。医療機器ではありません。
- 本画面は BMI・CKD を含みません（`app_streamlit_outcomes.py` の PC 版で入力できます）。
"""
    )

# ============================================================
# 📄 療養計画書PDF（共通UIヘルパー pdf_plan_ui に委譲）
#   モバイルはBMI入力を持たないため bmi_target を渡さず、計画書内で手入力させる。
# ============================================================
pdf_plan_ui.render_plan_section(
    sex=sex,
    age=age,
    ldl_now=ldl_now,
    a1c_now=a1c_now,
    sbp_tgt_manual=sbp_tgt_manual,
    a1c_tgt_manual=a1c_tgt_manual,
    bmi_target=None,
    sbp_now=sbp_now,
    bp_medications=tuple(current_sbp_keys or sbp_sel_keys),
    lipid_medications=tuple(current_ldl_keys or ldl_sel_keys),
    diabetes_medications=tuple(current_a1c_keys or a1c_sel_keys),
    lifestyle_interventions=tuple(effect.label for effect in lifestyle_result["applied"]),
    risk_curves=cumulative_data,
    risk_horizon_years=h,
    sbp_after=sbp_tgt,
    ldl_after=ldl_tgt,
    a1c_after=a1c_tgt,
    key_prefix="mobile",
)
