# app_streamlit_outcomes.py
import streamlit as st
import plotly.graph_objects as go
import numpy as np

from calc_engine_outcomes import OutcomesEngine
from meds_catalog import load_meds_catalog, apply_meds_to_targets, MedicationAdjustment

st.set_page_config(page_title="JP Outcomes Prevention Simulator (MVP)", layout="wide", page_icon="🫀")

st.title("🫀📈 アウトカムベース一次予防シミュレーター（MVP）")
st.caption("教育・共有意思決定のため。医療機器ではありません。")

engine = OutcomesEngine("config.yaml")

MORTALITY_ALL_CAUSE_DEATH_CAPTION = (
    "※全死亡は、心血管疾患に限らず、がんや他の病気を含むすべての死亡を対象としています。"
)

# 画面上の表示順（サマリー横並び・詳細グラフの並びを統一）
OUTCOME_DISPLAY_ORDER = ("mortality", "mi", "stroke")

# ====== 薬剤Excelのパス（必要なら修正） ======
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

with st.sidebar:
    st.subheader("患者プロフィール")
    sex = st.selectbox("性別", ["male", "female"], format_func=lambda x: "男性" if x == "male" else "女性")
    age = st.number_input("年齢（歳）", 20, 95, 60, step=1)

    st.subheader("リスク因子（現在 → 目標）")
    sbp_now = st.slider("収縮期血圧 現在 (mmHg)", 90, 200, 150)
    sbp_tgt_manual = st.slider("収縮期血圧 目標 (mmHg)", 90, 160, 130)

    ldl_now = st.slider("LDL 現在 (mg/dL)", 50, 250, 160)
    ldl_tgt_manual = st.slider("LDL 目標 (mg/dL)", 50, 160, 100)

    a1c_now = st.slider("HbA1c 現在 (%)", 5.0, 12.0, 8.0, step=0.1)
    a1c_tgt_manual = st.slider("HbA1c 目標 (%)", 5.0, 9.0, 7.0, step=0.1)

    st.subheader("喫煙状況")
    smoking_status = st.selectbox(
        "状況", ["never", "current", "former"],
        format_func=lambda x: {"never": "非喫煙者", "current": "現在喫煙者", "former": "元喫煙者"}[x]
    )
    cigs_per_day = st.slider("1日あたりの喫煙本数", 0, 40, 20)
    years_smoked = st.slider("喫煙年数", 0, 60, 20)
    years_since_quit = st.slider("禁煙からの年数（元喫煙者の場合）", 0, 40, 5)
    quit_today = st.checkbox("今日禁煙したと仮定（目標シナリオ）")

    st.subheader("BMI（任意）")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        bmi_now = st.number_input("現在のBMI", min_value=10.0, max_value=50.0, value=24.0, step=0.1)
    with col_b2:
        bmi_target = st.number_input("目標BMI（任意）", min_value=10.0, max_value=50.0, value=24.0, step=0.1)

    st.subheader("CKD（任意）")
    egfr_now = st.number_input("eGFR 現在", min_value=5.0, max_value=120.0, value=80.0, step=1.0)
    egfr_target = st.number_input("eGFR 目標（任意）", min_value=5.0, max_value=120.0, value=80.0, step=1.0)
    acr_now = st.selectbox("尿アルブミン/蛋白（現在）", ["A1", "A2", "A3"], index=0)
    acr_target = st.selectbox("尿アルブミン/蛋白（目標・任意）", ["A1", "A2", "A3"], index=0)

    st.subheader("予測期間")
    which = st.radio(
        "期間を選択", ["5-year", "10-year", "20-year", "30-year", "50-year", "Both"], index=2,
        format_func=lambda x: {"5-year": "5年", "10-year": "10年", "20-year": "20年", "30-year": "30年", "50-year": "50年", "Both": "両方"}[x]
    )

    st.divider()
    st.subheader("💊 薬剤（薬品名＝用量）で目標値を自動生成")

    # 1. 薬剤オプションを先に定義
    sbp_options = [m["key"] for m in meds_catalog["sbp"]]
    ldl_options = [m["key"] for m in meds_catalog["ldl"]]
    a1c_options = [m["key"] for m in meds_catalog["hba1c"]]

    # 2. 薬剤を使うかどうかのチェック
    use_meds = st.checkbox("薬剤を選んで目標値を自動計算する", value=True)

    # 薬剤カタログ読み込み失敗時の警告
    if catalog_error:
        st.warning("薬剤カタログ読み込みに失敗。Excelのパス/シート名/列名を確認してください。")
        st.caption(catalog_error)
        use_meds = False

    # 3. 薬剤を使う場合のみモード切り替えと選択UIを表示
    selected_sbp_meds = []
    selected_ldl_meds = []
    selected_a1c_meds = []
    sbp_sel_keys = []
    ldl_sel_keys = []
    a1c_sel_keys = []
    meds_summary = None
    mode = "add"  # デフォルト（catalog_error時やuse_meds=False時も安全に参照できるように）

    if use_meds and meds_catalog:
        # モード切り替え
        mode = st.radio(
            "シミュレーションモード",
            ["add", "adjust"],
            format_func=lambda x: (
                "💊 薬を追加する" if x == "add"
                else "💊 薬を増減させる"
            ),
        )

        if mode == "add":
            # 既存の薬追加UI
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
            # 新規：薬増減UI
            st.markdown("**現在服用中の薬**")
            current_sbp_keys = st.multiselect(
                "降圧薬（現在）", options=sbp_options, key="current_sbp"
            )
            current_ldl_keys = st.multiselect(
                "脂質薬（現在）", options=ldl_options, key="current_ldl"
            )
            current_a1c_keys = st.multiselect(
                "糖尿病薬（現在）", options=a1c_options, key="current_a1c"
            )

            # MVP：明示的に「現在の薬を変更後にコピー」するボタン
            if st.button("現在の薬を変更後に反映", use_container_width=True):
                st.session_state.adjusted_sbp = list(current_sbp_keys)
                st.session_state.adjusted_ldl = list(current_ldl_keys)
                st.session_state.adjusted_a1c = list(current_a1c_keys)

            st.markdown("**変更後に残す薬**")
            adjusted_sbp_keys = st.multiselect(
                "降圧薬（変更後）", options=sbp_options, key="adjusted_sbp"
            )
            adjusted_ldl_keys = st.multiselect(
                "脂質薬（変更後）", options=ldl_options, key="adjusted_ldl"
            )
            adjusted_a1c_keys = st.multiselect(
                "糖尿病薬（変更後）", options=a1c_options, key="adjusted_a1c"
            )

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

            def _se_md_for_changes(stopped, added, continued):
                lines = []
                if stopped:
                    lines.append("**中止で消える副作用**")
                    for m in stopped:
                        se = (m.get("side_effects") or "").strip()
                        if se:
                            lines.append(f"- {m['key']}: {se}")
                if added:
                    lines.append("**新規で追加される副作用**")
                    for m in added:
                        se = (m.get("side_effects") or "").strip()
                        if se:
                            lines.append(f"- {m['key']}: {se}")
                if continued:
                    lines.append("**継続中の副作用**")
                    for m in continued:
                        se = (m.get("side_effects") or "").strip()
                        if se:
                            lines.append(f"- {m['key']}: {se}")
                return "\n".join(lines)

            # 継続薬 = current と adjusted の両方にある薬
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
                "side_effect_changes": se_changes,
            }

        # 結果表示
        st.caption("合成ルール：SBPは足し算 / LDLは%低下を掛け算 / HbA1cは足し算")
        if meds_summary is not None:
            if meds_summary.get("mode") == "adjust":
                st.metric("年間薬剤費（変更後）", f"{meds_summary['annual_cost_yen']:,} 円/年")
                st.markdown("**自動計算された目標値（この値でリスク計算）**")
                st.write(f"- SBP 目標: **{meds_summary['sbp_target']:.0f} mmHg**")
                st.write(f"- LDL 目標: **{meds_summary['ldl_target']:.0f} mg/dL**")
                st.write(f"- HbA1c 目標: **{meds_summary['a1c_target']:.1f} %**")

                st.markdown("**薬剤変更の比較**")
                costs = meds_summary["costs"]
                delta = costs["delta"]
                delta_sign = "＋" if delta > 0 else ""
                st.write(
                    f"- 年間薬剤費: {costs['baseline']:,} 円/年 → {costs['adjusted']:,} 円/年 "
                    f"（差分 {delta_sign}{delta:,} 円/年）"
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
                st.markdown("**自動計算された目標値（この値でリスク計算）**")
                st.write(f"- SBP 目標: **{meds_summary['sbp_target']:.0f} mmHg**")
                st.write(f"- LDL 目標: **{meds_summary['ldl_target']:.0f} mg/dL**")
                st.write(f"- HbA1c 目標: **{meds_summary['a1c_target']:.1f} %**")

            if meds_summary["side_effects_md"].strip():
                with st.expander("主な副作用（薬剤ごと）"):
                    st.markdown(meds_summary["side_effects_md"])
        elif mode == "adjust":
            st.caption("薬増減モード：現在の薬と変更後の薬を選択してください。")

# ====== 実際に使う目標値 ======
if use_meds and meds_summary is not None:
    sbp_tgt = float(meds_summary["sbp_target"])
    ldl_tgt = float(meds_summary["ldl_target"])
    a1c_tgt = float(meds_summary["a1c_target"])
    annual_cost_yen = int(meds_summary["annual_cost_yen"])
    side_effects_md = meds_summary["side_effects_md"]
else:
    sbp_tgt = float(sbp_tgt_manual)
    ldl_tgt = float(ldl_tgt_manual)
    a1c_tgt = float(a1c_tgt_manual)
    annual_cost_yen = 0
    side_effects_md = ""

def _years_from_choice(choice: str) -> int:
    return {"5-year": 5, "10-year": 10, "20-year": 20, "30-year": 30, "50-year": 50}.get(choice, 10)

def calculate_cumulative_risk_curves(years: int):
    calc_years = np.arange(1, years + 1, 1)
    cumulative_data = {}

    for outcome in ["mi", "stroke", "mortality"]:
        cumulative_data[outcome] = {
            "baseline_cumulative": [0.0],
            "target_cumulative": [0.0],
            "baseline_ci_lower": [0.0],
            "baseline_ci_upper": [0.0],
            "target_ci_lower": [0.0],
            "target_ci_upper": [0.0],
            "time": [0.0],
        }

        AGE_CAP = 110
        for y in calc_years:
            if age + y > AGE_CAP:
                break

            res = engine.cumulative_incidence_with_ci(
                outcome, sex, age, int(y),
                sbp_now, sbp_tgt, ldl_now, ldl_tgt, a1c_now, a1c_tgt,
                smoking_status, cigs_per_day, years_smoked, years_since_quit,
                quit_today,
                bmi_now=bmi_now,
                bmi_target=bmi_target if bmi_target != bmi_now else None,
                egfr_now=egfr_now,
                egfr_target=egfr_target if egfr_target != egfr_now else None,
                acr_now=acr_now,
                acr_target=acr_target if acr_target != acr_now else None,
            )

            cumulative_data[outcome]["time"].append(float(y))
            cumulative_data[outcome]["baseline_cumulative"].append(res["point"]["baseline"] * 100.0)
            cumulative_data[outcome]["target_cumulative"].append(res["point"]["target"] * 100.0)
            cumulative_data[outcome]["baseline_ci_lower"].append(res["lower"]["baseline"] * 100.0)
            cumulative_data[outcome]["baseline_ci_upper"].append(res["upper"]["baseline"] * 100.0)
            cumulative_data[outcome]["target_ci_lower"].append(res["lower"]["target"] * 100.0)
            cumulative_data[outcome]["target_ci_upper"].append(res["upper"]["target"] * 100.0)

    return cumulative_data

# ---- パラメータ変更検知と自動計算 ----
# 現在のパラメータを文字列化してハッシュ化（変更検知用）
import hashlib
current_params = {
    "sex": sex, "age": age,
    "sbp_now": sbp_now, "sbp_tgt": sbp_tgt,
    "ldl_now": ldl_now, "ldl_tgt": ldl_tgt,
    "a1c_now": a1c_now, "a1c_tgt": a1c_tgt,
    "smoking_status": smoking_status, "cigs_per_day": cigs_per_day,
    "years_smoked": years_smoked, "years_since_quit": years_since_quit,
    "quit_today": quit_today,
    "bmi_now": bmi_now, "bmi_target": bmi_target,
    "egfr_now": egfr_now, "egfr_target": egfr_target,
    "acr_now": acr_now, "acr_target": acr_target,
    "which": which,
    "sbp_meds": tuple(sbp_sel_keys) if use_meds and meds_catalog else (),
    "ldl_meds": tuple(ldl_sel_keys) if use_meds and meds_catalog else (),
    "a1c_meds": tuple(a1c_sel_keys) if use_meds and meds_catalog else (),
    "use_meds": use_meds,
}
params_hash = hashlib.md5(str(sorted(current_params.items())).encode()).hexdigest()

# セッション状態の初期化
if "params_hash" not in st.session_state:
    st.session_state.params_hash = None
    st.session_state.calculated = False
    st.session_state.cumulative_data = None
    st.session_state.years = None

horizons = [5, 10] if which == "Both" else [_years_from_choice(which)]
years_for_curve = max(horizons)

# パラメータが変更されたか、または初回実行か
params_changed = st.session_state.params_hash != params_hash
should_auto_calculate = params_changed and st.session_state.calculated

# 手動ボタンまたは自動計算
manual_button_clicked = st.button("🔄 リスク計算を実行", type="primary")
if manual_button_clicked or should_auto_calculate:
    with st.spinner("リスク計算中..."):
        st.session_state.cumulative_data = calculate_cumulative_risk_curves(years_for_curve)
        st.session_state.calculated = True
        st.session_state.years = years_for_curve
        st.session_state.params_hash = params_hash

if not st.session_state.calculated:
    st.info("👆 上記のパラメータを設定して「リスク計算を実行」を押してください")
    st.stop()

cumulative_data = st.session_state.cumulative_data

# ---- サマリー ----
st.markdown("## 📊 リスク比較サマリー")
labels = {"mi": "心筋梗塞", "stroke": "脳卒中", "mortality": "全死亡"}
cols = st.columns(3)

for i, outcome in enumerate(OUTCOME_DISPLAY_ORDER):
    with cols[i]:
        st.subheader(labels[outcome])
        for horizon in horizons:
            r = engine.cumulative_incidence(
                outcome, sex, age, horizon,
                sbp_now, sbp_tgt, ldl_now, ldl_tgt, a1c_now, a1c_tgt,
                smoking_status, cigs_per_day, years_smoked, years_since_quit,
                assume_quit_today_in_target=quit_today
            )
            arr = (r["baseline"] - r["target"]) * 100.0
            st.metric(
                f"{horizon}年 リスク減少（ARR）",
                f"{arr:.1f}%",
                delta=f"現在 {r['baseline']*100:.1f}% → 目標 {r['target']*100:.1f}%"
            )
        if outcome == "mortality":
            st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)

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
            st.metric("年間薬剤費（変更後）", f"{costs['adjusted']:,} 円/年")
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

# ---- 曲線（MI / Stroke / Mortality すべて表示） ----
st.markdown("## 📈 累積リスク曲線（95%CI）")

_OUTCOME_DETAIL_META = {
    "mortality": {"title": "💀 全死亡", "icon": "💀"},
    "mi": {"title": "🫀 心筋梗塞", "icon": "🫀"},
    "stroke": {"title": "🧠 脳卒中", "icon": "🧠"},
}
outcomes_config = [{"key": k, **_OUTCOME_DETAIL_META[k]} for k in OUTCOME_DISPLAY_ORDER]

def plot_risk_curve(outcome_key: str, title: str):
    """リスク曲線を描画する関数"""
    t = np.array(cumulative_data[outcome_key]["time"], dtype=float)
    b = np.array(cumulative_data[outcome_key]["baseline_cumulative"], dtype=float)
    tg = np.array(cumulative_data[outcome_key]["target_cumulative"], dtype=float)
    b_l = np.array(cumulative_data[outcome_key]["baseline_ci_lower"], dtype=float)
    b_u = np.array(cumulative_data[outcome_key]["baseline_ci_upper"], dtype=float)
    tg_l = np.array(cumulative_data[outcome_key]["target_ci_lower"], dtype=float)
    tg_u = np.array(cumulative_data[outcome_key]["target_ci_upper"], dtype=float)

    cutoff_year = max(0.0, 85.0 - float(age))
    cut_idx = int(np.searchsorted(t, cutoff_year, side="right"))

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=t[:cut_idx], y=b[:cut_idx], mode="lines", name="現在",
        hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        line=dict(color="red", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=t[cut_idx:], y=b[cut_idx:], mode="lines", name="現在（≥85歳推定域）",
        opacity=0.4, hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>", showlegend=False,
        line=dict(color="red", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=t[:cut_idx], y=tg[:cut_idx], mode="lines", name="薬剤/目標",
        hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>",
        line=dict(color="blue", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=t[cut_idx:], y=tg[cut_idx:], mode="lines", name="薬剤/目標（≥85歳推定域）",
        opacity=0.4, hovertemplate="%{x:.1f}年: %{y:.2f}%<extra></extra>", showlegend=False,
        line=dict(color="blue", width=2)
    ))

    # CI band: baseline
    fig.add_trace(go.Scatter(x=t, y=b_u, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=b_l, mode="lines", fill="tonexty", line=dict(width=0),
                             name="現在 95%CI", hoverinfo="skip", fillcolor="rgba(255, 0, 0, 0.08)"))

    # CI band: target
    fig.add_trace(go.Scatter(x=t, y=tg_u, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=tg_l, mode="lines", fill="tonexty", line=dict(width=0),
                             name="薬剤/目標 95%CI", hoverinfo="skip", fillcolor="rgba(0, 0, 255, 0.08)"))

    fig.update_layout(
        title=title,
        xaxis_title="年数",
        yaxis_title="累積リスク（%）",
        hovermode="x unified",
        height=520,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )

    return fig

for outcome_config in outcomes_config:
    st.markdown(f"### {outcome_config['title']}")
    fig = plot_risk_curve(outcome_config["key"], outcome_config["title"])
    st.plotly_chart(fig, use_container_width=True)
    if outcome_config["key"] == "mortality":
        st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)
    st.markdown("---")

