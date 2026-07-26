# app_streamlit_outcomes.py
import re
from datetime import date

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

from calc_engine_outcomes import OutcomesEngine
from meds_catalog import load_meds_catalog, apply_meds_to_targets, MedicationAdjustment
import pdf_fill

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
    current_sbp_keys = []
    current_ldl_keys = []
    current_a1c_keys = []
    adjusted_sbp_keys = []
    adjusted_ldl_keys = []
    adjusted_a1c_keys = []
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
            # 薬増減UI：現在の治療をベースラインに、各薬をワンタップで 中止/減量/増量/切替
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

            st.markdown("**各薬の変更（タップで選択）**")
            if not (current_sbp_keys or current_ldl_keys or current_a1c_keys):
                st.caption("現在服用中の薬を選ぶと、ここに変更ボタンが表示されます。")
            adjusted_sbp_keys, sbp_changes = render_rx_change_rows(
                "降圧薬", "sbp", meds_catalog["sbp"], current_sbp_keys, "pc_sbp"
            )
            adjusted_ldl_keys, ldl_changes = render_rx_change_rows(
                "脂質薬", "ldl", meds_catalog["ldl"], current_ldl_keys, "pc_ldl"
            )
            adjusted_a1c_keys, a1c_changes = render_rx_change_rows(
                "糖尿病薬", "hba1c", meds_catalog["hba1c"], current_a1c_keys, "pc_a1c"
            )

            with st.expander("➕ 薬を追加する（任意）"):
                add_sbp_keys = st.multiselect(
                    "降圧薬（追加）",
                    options=[o for o in sbp_options
                             if o not in current_sbp_keys and o not in adjusted_sbp_keys],
                    key="pc_add_sbp",
                )
                add_ldl_keys = st.multiselect(
                    "脂質薬（追加）",
                    options=[o for o in ldl_options
                             if o not in current_ldl_keys and o not in adjusted_ldl_keys],
                    key="pc_add_ldl",
                )
                add_a1c_keys = st.multiselect(
                    "糖尿病薬（追加）",
                    options=[o for o in a1c_options
                             if o not in current_a1c_keys and o not in adjusted_a1c_keys],
                    key="pc_add_a1c",
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
            st.caption("薬増減モード：現在服用中の薬を選択してください。")

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
    st.plotly_chart(fig, width="stretch")
    if outcome_config["key"] == "mortality":
        st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)
    st.markdown("---")


# ============================================================
# 📄 療養計画書PDF（AcroForm記入 / ロードマップ Step 4-A: 自動17項目）
#   氏名・生年月日・主病名等はサーバーに載せない方針（決定1）で空欄・手書き。
#   確認画面は pdf_fill に渡す値をそのまま表示する（決定5・再計算しない）。
# ============================================================
st.divider()
st.markdown("## 📄 療養計画書を作成")
st.caption(
    "アプリが持つ値を療養計画書（別紙様式9）に記入します。"
    "氏名・生年月日・主病名などは空欄のまま。印刷後に手書きで補ってください。"
)

# --- 計画書に固有の入力（アプリ本体にはない項目） ---
col_v, col_d = st.columns(2)
with col_v:
    visit_label = st.radio("区分", ["初回", "継続"], horizontal=True, key="plan_visit")
with col_d:
    dbp_tgt_input = st.number_input(
        "目標拡張期血圧 (mmHg)", min_value=50, max_value=120, value=80, step=1,
        key="plan_dbp",
        help="収縮期は自動で入ります。拡張期はここで指定（帳票は 130/80 の形式）",
    )

# --- 任意項目を載せるか（決定5: 既定値の誤記入を避けるため人が選ぶ） ---
st.markdown("**計画書に載せる項目**（チェックした値だけ記入されます）")
c1, c2, c3 = st.columns(3)
with c1:
    inc_bp = st.checkbox("目標血圧", value=True, key="plan_inc_bp")
    inc_bmi = st.checkbox("目標BMI", value=True, key="plan_inc_bmi")
with c2:
    inc_a1c_tgt = st.checkbox("目標HbA1c", value=True, key="plan_inc_a1ctgt")
    inc_ldl = st.checkbox("実測LDL", value=True, key="plan_inc_ldl")
with c3:
    inc_a1c_now = st.checkbox("実測HbA1c", value=True, key="plan_inc_a1cnow")

# --- 手入力項目（Step 4-B。アプリが値を持たない欄。空欄なら記入されない） ---
with st.expander("✍ 手入力項目（主病名・体重・栄養状態・行動目標）"):
    st.caption("アプリが値を持たない欄です。入力したものだけ記入されます（空欄は手書き）。")

    st.markdown("**主病名**（該当にチェック。自動推定はしません）")
    dcol1, dcol2, dcol3 = st.columns(3)
    with dcol1:
        dx_dm = st.checkbox("糖尿病", key="plan_dx_dm")
    with dcol2:
        dx_htn = st.checkbox("高血圧症", key="plan_dx_htn")
    with dcol3:
        dx_dl = st.checkbox("脂質異常症", key="plan_dx_dl")

    mcol1, mcol2 = st.columns(2)
    with mcol1:
        weight_input = st.number_input(
            "目標体重 (kg)（0＝記入しない）",
            min_value=0.0, max_value=200.0, value=0.0, step=0.1, key="plan_weight",
        )
    with mcol2:
        nutrition_input = st.selectbox(
            "栄養状態",
            ["（記入しない）", *pdf_fill.NUTRITION_OPTIONS],
            key="plan_nutrition",
        )

    plan_freetext = st.text_area(
        "達成目標・行動目標（自由記述）",
        key="plan_freetext",
        placeholder="例）1日8000歩を目標にする／間食を1日1回までにする",
    )
    achievement_status = st.text_area(
        "目標の達成状況（継続の場合のみ）",
        key="plan_achievement",
        placeholder="継続受診時、前回目標の達成状況を記入",
    )

# --- PlanInput を組み立て ---
# 療養計画書の「目標」は医師が設定する目標そのもの。サイドバーの目標スライダー
# （sbp_tgt_manual / a1c_tgt_manual）を直接使う。有効目標値 sbp_tgt/a1c_tgt は
# use_meds ON時に薬剤計算の予測到達値になるため、目標欄には使わない。
plan = pdf_fill.PlanInput(
    sex=sex,
    age=int(age),
    visit_type="initial" if visit_label == "初回" else "continued",
    created=date.today(),
    sbp_tgt=int(round(sbp_tgt_manual)) if inc_bp else None,
    dbp_tgt=int(dbp_tgt_input) if inc_bp else None,
    bmi_target=float(bmi_target) if inc_bmi else None,
    a1c_tgt=float(a1c_tgt_manual) if inc_a1c_tgt else None,
    ldl_now=int(round(ldl_now)) if inc_ldl else None,
    a1c_now=float(a1c_now) if inc_a1c_now else None,
)

if st.button("📄 記入内容を確認する", key="plan_make"):
    st.session_state.plan_ready = True

if st.session_state.get("plan_ready"):
    fv = pdf_fill.build_field_values(plan)

    # 確認画面（決定5）: PDFに書き込む値を表示し、ここで最終調整できる。
    # 空欄にした行はその項目も連動チェックも記入されない。
    st.markdown("#### 記入内容（この値が印字されます・編集可）")
    st.caption("数値や内容はここで最終調整できます。空欄にするとその項目は印字されません。")
    label_map = {
        pdf_fill.F_SEX: "性別",
        pdf_fill.F_AGE: "年齢",
        pdf_fill.F_DATE_Y: "作成日(年)",
        pdf_fill.F_DATE_M: "作成日(月)",
        pdf_fill.F_DATE_D: "作成日(日)",
        pdf_fill.F_BP: "目標血圧(収縮期/拡張期)",
        pdf_fill.F_BMI: "目標BMI",
        pdf_fill.F_A1C_TGT: "目標HbA1c",
        pdf_fill.F_LDL_NOW: "実測LDL",
        pdf_fill.F_A1C_NOW: "実測HbA1c",
    }
    # 編集対象はテキスト/ドロップダウン欄。区分（初回/継続）は上のラジオで指定済み。
    field_order = list(fv.text.keys())
    editor_df = pd.DataFrame(
        {
            "欄": [label_map.get(f, f) for f in field_order],
            "値": [fv.text[f] for f in field_order],
        }
    )
    edited = st.data_editor(
        editor_df,
        column_config={
            "欄": st.column_config.TextColumn("欄", disabled=True),
            "値": st.column_config.TextColumn("値"),
        },
        hide_index=True,
        key="plan_editor",
    )
    st.caption(
        "空欄（手書き）: 氏名・生年月日・主病名・行動目標・食事/運動/喫煙指導・栄養状態"
    )

    # 編集後の値で FieldValues を再構築（値があれば連動チェックもON）
    fv_final = pdf_fill.FieldValues()
    for fname, val in zip(field_order, edited["値"].tolist()):
        val = "" if val is None else str(val).strip()
        if not val:
            continue
        fv_final.text[fname] = val
        chk = pdf_fill.FIELD_CONNECTED_CHECK.get(fname)
        if chk:
            fv_final.checks[chk] = True

    # --- 手入力項目（Step 4-B）を反映 ---
    # 主病名（該当のみON）
    for on, cb in (
        (dx_dm, pdf_fill.C_DX_DIABETES),
        (dx_htn, pdf_fill.C_DX_HYPERTENSION),
        (dx_dl, pdf_fill.C_DX_DYSLIPIDEMIA),
    ):
        if on:
            fv_final.checks[cb] = True
    # 目標体重（0は未記入）
    if weight_input and weight_input > 0:
        fv_final.text[pdf_fill.F_WEIGHT] = f"{weight_input:.1f}"
        fv_final.checks[pdf_fill.C_WEIGHT] = True
    # 栄養状態
    if nutrition_input in pdf_fill.NUTRITION_OPTIONS:
        fv_final.text[pdf_fill.F_NUTRITION] = nutrition_input
        fv_final.checks[pdf_fill.C_NUTRITION] = True
    # 達成目標・行動目標（自由記述）
    if plan_freetext and plan_freetext.strip():
        fv_final.text[pdf_fill.F_PLAN_FREETEXT] = plan_freetext.strip()
    # 目標の達成状況（継続の場合のみ）
    if achievement_status and achievement_status.strip():
        fv_final.text[pdf_fill.F_ACHIEVEMENT_STATUS] = achievement_status.strip()

    # 区分（初回/継続）
    if plan.visit_type == "initial":
        fv_final.checks[pdf_fill.F_VISIT_FIRST] = True
    else:
        fv_final.checks[pdf_fill.F_VISIT_CONT] = True

    pdf_bytes = pdf_fill.fill_pdf(fv_final)
    st.download_button(
        "⬇ PDFをダウンロード",
        data=pdf_bytes,
        file_name=f"療養計画書_{date.today():%Y%m%d}.pdf",
        mime="application/pdf",
        key="plan_dl",
        type="primary",
    )

