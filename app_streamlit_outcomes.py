# app_streamlit_outcomes.py
import re

import streamlit as st
import plotly.graph_objects as go
import numpy as np

from calc_engine_outcomes import OutcomesEngine
from meds_catalog import load_meds_catalog, apply_meds_to_targets, MedicationAdjustment

st.set_page_config(page_title="JP Outcomes Prevention Simulator (MVP)", layout="wide", page_icon="🫀")

st.title("🫀📈 Outcome-Based Primary Prevention Simulator (MVP)")
st.caption("For education and shared decision-making. This is not a medical device.")

engine = OutcomesEngine("config.yaml")

MORTALITY_ALL_CAUSE_DEATH_CAPTION = (
    "All-cause mortality includes deaths from cancer and other diseases, not only cardiovascular disease."
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

ACTION_LABELS = {
    RX_ACTION_NO_CHANGE: "No change", RX_ACTION_STOP: "Stop",
    RX_ACTION_DOWN: "Reduce dose", RX_ACTION_UP: "Increase dose", RX_ACTION_SWITCH: "Switch",
}

DISPLAY_TRANSLATIONS = {
    "リシノプリル": "Lisinopril", "アジルサルタン": "Azilsartan", "サクビトリル/バルサルタン": "Sacubitril/valsartan",
    "アムロジピン": "Amlodipine", "カルベジロール": "Carvedilol", "ビソプロロール": "Bisoprolol",
    "フルイトラン（トリクロルメチアジド）": "Fluitran (trichlormethiazide)", "ミネブロ（エサキセレノン）": "Minnebro (esaxerenone)",
    "レパーサ（エボロクマブ）": "Repatha (evolocumab)", "アトルバスタチン": "Atorvastatin", "ピタバスタチン": "Pitavastatin",
    "ロスバスタチン": "Rosuvastatin", "エゼチミブ": "Ezetimibe", "トラゼンタ": "Tradjenta", "マンジャロ（チルゼパチド）": "Mounjaro (tirzepatide)",
    "オゼンピック（セマグルチド）": "Ozempic (semaglutide)", "リベルサス（セマグルチド）": "Rybelsus (semaglutide)", "ジャディアンス": "Jardiance", "メトホルミン": "Metformin",
    "ACE阻害薬": "ACE inhibitor", "Ca拮抗薬": "Calcium channel blocker", "β遮断薬": "Beta-blocker", "サイアザイド系利尿薬": "Thiazide diuretic",
    "非ステロイド型MRA": "Nonsteroidal MRA", "PCSK9阻害薬": "PCSK9 inhibitor", "スタチン": "Statin", "吸収阻害薬": "Absorption inhibitor",
    "DPP-4阻害薬": "DPP-4 inhibitor", "GIP/GLP-1受容体作動薬": "GIP/GLP-1 receptor agonist", "GLP-1受容体作動薬（皮下）": "GLP-1 receptor agonist (subcutaneous)",
    "GLP-1受容体作動薬（経口）": "GLP-1 receptor agonist (oral)", "SGLT2阻害薬": "SGLT2 inhibitor", "ビグアナイド": "Biguanide",
    "空咳": "Dry cough", "咳": "Cough", "めまい": "Dizziness", "高K血症": "Hyperkalemia", "血管性浮腫": "Angioedema", "頭痛": "Headache", "腎変化": "renal changes",
    "低血圧": "Hypotension", "浮腫": "Edema", "腎障害": "Renal impairment", "顔面紅潮": "Flushing", "疲労感": "Fatigue", "疲労": "Fatigue", "代謝改善": "Improved metabolism",
    "徐脈": "Bradycardia", "勃起障害": "Erectile dysfunction", "抑うつ": "Depression", "高尿酸血症": "Hyperuricemia", "高血糖症": "Hyperglycemia", "電解質失調": "Electrolyte imbalance",
    "副作用発現率": "Adverse-event rate", "副作用発現頻度": "Adverse-event rate", "血中カリウム増加": "Increased blood potassium", "糸球体濾過率減少": "Decreased glomerular filtration rate",
    "注射部位反応": "Injection-site reaction", "上気道感染": "Upper respiratory tract infection", "便秘": "Constipation", "肝機能上昇": "Elevated liver function tests", "肝酵素上昇": "Elevated liver enzymes",
    "筋肉痛": "Myalgia", "CK上昇": "Elevated CK", "下痢": "Diarrhea", "低血糖（併用時）": "Hypoglycemia (with combination therapy)", "悪心": "Nausea", "投与中止に至る有害事象": "Adverse events leading to discontinuation",
    "嘔吐": "Vomiting", "腹部不快感": "Abdominal discomfort", "腹痛": "Abdominal pain", "消化不良": "Dyspepsia", "尿路感染": "Urinary tract infection", "脱水": "Dehydration", "消化器症状": "Gastrointestinal symptoms",
    "mg/日": "mg/day", "mg/週": "mg/week", "隔週注": "every 2 weeks", "（開始量）": "(starting dose)", "軽度": "Mild ", "未満": "", "以上": " or more", "、": ", ", "・": ", ", "（": " (", "）": ")", "〜": "–",
}

def _display_text(value: str) -> str:
    text = str(value)
    for source, target in DISPLAY_TRANSLATIONS.items():
        text = text.replace(source, target)
    return text


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
    """Switch to候補：同ドメインのうち別薬剤名で、服用中でないもの"""
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
    """Current薬1剤ごとにカード（枠付きコンテナ）を描画し、
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
            st.markdown(f"**{_display_text(k)}**")
            st.caption(
                f"{domain_label} | {_display_text(med.get('category', ''))} | "
                f"{_effect_label(domain, med)} | Estimated cost in Japan: {cost:,} JPY/year"
            )

            act_key = f"{state_prefix}_act_{k}"
            if act_key not in st.session_state:
                st.session_state[act_key] = RX_ACTION_NO_CHANGE
            action = st.segmented_control(
                f"{_display_text(k)} adjustment",
                options,
                key=act_key,
                format_func=lambda x: ACTION_LABELS[x],
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
                    "Dose after reduction",
                    lower, format_func=_display_text,
                    index=len(lower) - 1,  # 既定は一段下
                    key=f"{state_prefix}_down_{k}",
                ) if lower else k
            elif action == RX_ACTION_UP:
                higher = ladder[cur_idx + 1:]  # 現用量より上の用量（昇順）
                result_key = st.selectbox(
                    "Dose after increase",
                    higher, format_func=_display_text,
                    index=0,  # 既定は一段上
                    key=f"{state_prefix}_up_{k}",
                ) if higher else k
            elif action == RX_ACTION_SWITCH:
                result_key = st.selectbox("Switch to", switch_opts, format_func=_display_text, key=f"{state_prefix}_sw_{k}")

            # 変更後プレビュー（効果・費用差分をカード内に表示）
            if result_key is None:
                st.markdown(f"🛑 **Stop** (cost {-cost:+,} JPY/year)")
                change_lines.append(f"🛑 Stop: {_display_text(k)}")
            elif result_key != k:
                new_med = by_key[result_key]
                new_cost = new_med.get("annual_cost_yen") or 0
                icon = {RX_ACTION_UP: "🔼", RX_ACTION_DOWN: "🔽"}.get(action, "🔁")
                st.markdown(f"{icon} **{ACTION_LABELS[action]} → {_display_text(result_key)}**")
                st.caption(
                    f"{_effect_label(domain, new_med)} · Cost difference {new_cost - cost:+,} JPY/year"
                )
                change_lines.append(f"{icon} {ACTION_LABELS[action]}: {_display_text(k)} → {_display_text(result_key)}")
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
            f"- {_display_text(m['key'])}: {_display_text((m.get('side_effects') or '').strip())}"
            for m in meds_list
            if (m.get("side_effects") or "").strip()
        ]

    sections = []
    if pure_stopped:
        items = _items(pure_stopped)
        if items:
            sections.append("**Adverse effects removed by stopping**\n" + "\n".join(items))
    if dose_changed:
        items = [
            f"- {_display_text(old['key'])} → {_display_text(new['key'])}: {_display_text((new.get('side_effects') or '').strip())}"
            for old, new in dose_changed
            if (new.get("side_effects") or "").strip()
        ]
        if items:
            sections.append("**Adverse effects continuing after dose change**\n" + "\n".join(items))
    if pure_added:
        items = _items(pure_added)
        if items:
            sections.append("**Adverse effects from newly added medications**\n" + "\n".join(items))
    if continued:
        items = _items(continued)
        if items:
            sections.append("**Adverse effects from continued medications**\n" + "\n".join(items))
    return "\n\n".join(sections)


with st.sidebar:
    st.subheader("Patient profile")
    sex = st.selectbox("Sex", ["male", "female"], format_func=lambda x: "Male" if x == "male" else "Female")
    age = st.number_input("Age (years)", 20, 95, 60, step=1)

    st.subheader("Risk factors (current → target)")
    sbp_now = st.slider("Current systolic blood pressure (mmHg)", 90, 200, 150)
    sbp_tgt_manual = st.slider("Target systolic blood pressure (mmHg)", 90, 160, 130)

    ldl_now = st.slider("Current LDL (mg/dL)", 50, 250, 160)
    ldl_tgt_manual = st.slider("Target LDL (mg/dL)", 50, 160, 100)

    a1c_now = st.slider("Current HbA1c (%)", 5.0, 12.0, 8.0, step=0.1)
    a1c_tgt_manual = st.slider("Target HbA1c (%)", 5.0, 9.0, 7.0, step=0.1)

    st.subheader("Smoking status")
    smoking_status = st.selectbox(
        "Status", ["never", "current", "former"],
        format_func=lambda x: {"never": "Never smoked", "current": "Current smoker", "former": "Former smoker"}[x]
    )
    cigs_per_day = st.slider("Cigarettes per day", 0, 40, 20)
    years_smoked = st.slider("Years smoked", 0, 60, 20)
    years_since_quit = st.slider("Years since quitting (former smokers)", 0, 40, 5)
    quit_today = st.checkbox("Assume smoking cessation today (target scenario)")

    st.subheader("BMI (optional)")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        bmi_now = st.number_input("Current BMI", min_value=10.0, max_value=50.0, value=24.0, step=0.1)
    with col_b2:
        bmi_target = st.number_input("Target BMI (optional)", min_value=10.0, max_value=50.0, value=24.0, step=0.1)

    st.subheader("CKD (optional)")
    egfr_now = st.number_input("Current eGFR", min_value=5.0, max_value=120.0, value=80.0, step=1.0)
    egfr_target = st.number_input("Target eGFR (optional)", min_value=5.0, max_value=120.0, value=80.0, step=1.0)
    acr_now = st.selectbox("Current urine albumin/protein category", ["A1", "A2", "A3"], index=0)
    acr_target = st.selectbox("Target urine albumin/protein category (optional)", ["A1", "A2", "A3"], index=0)

    st.subheader("Prediction horizon")
    which = st.radio(
        "Select horizon", ["5-year", "10-year", "20-year", "30-year", "50-year", "Both"], index=2,
        format_func=lambda x: {"5-year": "5 years", "10-year": "10 years", "20-year": "20 years", "30-year": "30 years", "50-year": "50 years", "Both": "5 and 10 years"}[x]
    )

    st.divider()
    st.subheader("💊 Generate targets from medications and doses")

    # 1. 薬剤オプションを先に定義
    sbp_options = [m["key"] for m in meds_catalog["sbp"]]
    ldl_options = [m["key"] for m in meds_catalog["ldl"]]
    a1c_options = [m["key"] for m in meds_catalog["hba1c"]]

    # 2. 薬剤を使うかどうかのチェック
    use_meds = st.checkbox("Automatically calculate targets from selected medications", value=True)

    # 薬剤カタログ読み込み失敗時の警告
    if catalog_error:
        st.warning("Could not load the medication catalog. Check the Excel path, sheet names, and column names.")
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
            "Simulation mode",
            ["add", "adjust"],
            format_func=lambda x: (
                "💊 Add medications" if x == "add"
                else "💊 Adjust current medications"
            ),
        )

        if mode == "add":
            # 既存の薬追加UI
            sbp_sel_keys = st.multiselect("Antihypertensive medications (affect SBP)", options=sbp_options, format_func=_display_text)
            selected_sbp_meds = [m for m in meds_catalog["sbp"] if m["key"] in sbp_sel_keys]

            ldl_sel_keys = st.multiselect("Lipid-lowering medications (affect LDL)", options=ldl_options, format_func=_display_text)
            selected_ldl_meds = [m for m in meds_catalog["ldl"] if m["key"] in ldl_sel_keys]

            a1c_sel_keys = st.multiselect("Glucose-lowering medications (affect HbA1c)", options=a1c_options, format_func=_display_text)
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
            # 薬増減UI：Currentの治療をベースラインに、各薬をワンタップで 中止/減量/増量/切替
            st.markdown("**Current medications**")
            current_sbp_keys = st.multiselect(
                "Current antihypertensive medications", options=sbp_options, format_func=_display_text, key="current_sbp"
            )
            current_ldl_keys = st.multiselect(
                "Current lipid-lowering medications", options=ldl_options, format_func=_display_text, key="current_ldl"
            )
            current_a1c_keys = st.multiselect(
                "Current glucose-lowering medications", options=a1c_options, format_func=_display_text, key="current_a1c"
            )

            st.markdown("**Changes to each medication**")
            if not (current_sbp_keys or current_ldl_keys or current_a1c_keys):
                st.caption("Select current medications to display adjustment controls here.")
            adjusted_sbp_keys, sbp_changes = render_rx_change_rows(
                "Antihypertensive", "sbp", meds_catalog["sbp"], current_sbp_keys, "pc_sbp"
            )
            adjusted_ldl_keys, ldl_changes = render_rx_change_rows(
                "Lipid-lowering", "ldl", meds_catalog["ldl"], current_ldl_keys, "pc_ldl"
            )
            adjusted_a1c_keys, a1c_changes = render_rx_change_rows(
                "Glucose-lowering", "hba1c", meds_catalog["hba1c"], current_a1c_keys, "pc_a1c"
            )

            with st.expander("➕ Add medications (optional)"):
                add_sbp_keys = st.multiselect(
                    "Add antihypertensive medications",
                    options=[o for o in sbp_options
                             if o not in current_sbp_keys and o not in adjusted_sbp_keys],
                    format_func=_display_text,
                    key="pc_add_sbp",
                )
                add_ldl_keys = st.multiselect(
                    "Add lipid-lowering medications",
                    options=[o for o in ldl_options
                             if o not in current_ldl_keys and o not in adjusted_ldl_keys],
                    format_func=_display_text,
                    key="pc_add_ldl",
                )
                add_a1c_keys = st.multiselect(
                    "Add glucose-lowering medications",
                    options=[o for o in a1c_options
                             if o not in current_a1c_keys and o not in adjusted_a1c_keys],
                    format_func=_display_text,
                    key="pc_add_a1c",
                )
            adjusted_sbp_keys = adjusted_sbp_keys + [k for k in add_sbp_keys if k not in adjusted_sbp_keys]
            adjusted_ldl_keys = adjusted_ldl_keys + [k for k in add_ldl_keys if k not in adjusted_ldl_keys]
            adjusted_a1c_keys = adjusted_a1c_keys + [k for k in add_a1c_keys if k not in adjusted_a1c_keys]

            rx_change_lines = (
                sbp_changes + ldl_changes + a1c_changes
                + [f"➕ Add: {_display_text(k)}" for k in list(add_sbp_keys) + list(add_ldl_keys) + list(add_a1c_keys)]
            )
            if rx_change_lines:
                st.markdown("**Medication changes**")
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
        st.caption("Combination rules: SBP effects are additive / LDL percentage reductions are multiplicative / HbA1c effects are additive")
        if meds_summary is not None:
            if meds_summary.get("mode") == "adjust":
                st.metric("Estimated annual cost in Japan after changes", f"{meds_summary['annual_cost_yen']:,} JPY/year")
                st.markdown("**Automatically calculated targets used for risk estimation**")
                st.write(f"- Target SBP: **{meds_summary['sbp_target']:.0f} mmHg**")
                st.write(f"- Target LDL: **{meds_summary['ldl_target']:.0f} mg/dL**")
                st.write(f"- Target HbA1c: **{meds_summary['a1c_target']:.1f} %**")

                st.markdown("**Medication change comparison**")
                costs = meds_summary["costs"]
                delta = costs["delta"]
                delta_sign = "+" if delta > 0 else ""
                st.write(
                    f"- Estimated annual cost in Japan: {costs['baseline']:,} JPY/year → {costs['adjusted']:,} JPY/year "
                    f"(difference {delta_sign}{delta:,} JPY/year)"
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
                st.metric("Total estimated annual cost in Japan", f"{meds_summary['annual_cost_yen']:,} JPY/year")
                st.markdown("**Automatically calculated targets used for risk estimation**")
                st.write(f"- Target SBP: **{meds_summary['sbp_target']:.0f} mmHg**")
                st.write(f"- Target LDL: **{meds_summary['ldl_target']:.0f} mg/dL**")
                st.write(f"- Target HbA1c: **{meds_summary['a1c_target']:.1f} %**")

            if meds_summary["side_effects_md"].strip():
                with st.expander("Key adverse effects by medication"):
                    st.markdown(_display_text(meds_summary["side_effects_md"]))
        elif mode == "adjust":
            st.caption("Adjustment mode: select current medications.")

# ====== 実際に使うTarget値 ======
if use_meds and meds_summary is not None:
    sbp_tgt = float(meds_summary["sbp_target"])
    ldl_tgt = float(meds_summary["ldl_target"])
    a1c_tgt = float(meds_summary["a1c_target"])
    annual_cost_yen = int(meds_summary["annual_cost_yen"])
    side_effects_md = _display_text(meds_summary["side_effects_md"])
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
# Currentのパラメータを文字列化してハッシュ化（変更検知用）
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
manual_button_clicked = st.button("🔄 Calculate risk", type="primary")
if manual_button_clicked or should_auto_calculate:
    with st.spinner("Calculating risk..."):
        st.session_state.cumulative_data = calculate_cumulative_risk_curves(years_for_curve)
        st.session_state.calculated = True
        st.session_state.years = years_for_curve
        st.session_state.params_hash = params_hash

if not st.session_state.calculated:
    st.info("👆 Set the parameters above, then select Calculate risk.")
    st.stop()

cumulative_data = st.session_state.cumulative_data

# ---- サマリー ----
st.markdown("## 📊 Risk comparison summary")
labels = {"mi": "Myocardial infarction", "stroke": "Stroke", "mortality": "All-cause mortality"}
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
                f"{horizon}-year absolute risk reduction (ARR)",
                f"{arr:.1f}%",
                delta=f"Current {r['baseline']*100:.1f}% → target {r['target']*100:.1f}%"
            )
        if outcome == "mortality":
            st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)

st.divider()

st.markdown("## 💴 Estimated cost in Japan and adverse effects")
if use_meds and meds_summary is not None:
    if meds_summary.get("mode") == "adjust":
        costs = meds_summary["costs"]
        delta = costs["delta"]
        delta_sign = "+" if delta > 0 else ""
        st.metric("Current estimated annual cost in Japan", f"¥{costs['baseline']:,}/year")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Estimated annual cost in Japan after changes", f"¥{costs['adjusted']:,}/year")
        with col2:
            st.metric("Difference", f"{delta_sign}¥{delta:,}/year")
        st.markdown("**Change in target values**")
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
        st.metric("Total estimated annual cost in Japan", f"¥{annual_cost_yen:,}/year")
    if side_effects_md.strip():
        st.markdown("**Key adverse effects by medication**")
        st.markdown(side_effects_md)
else:
    st.info("No medications are selected, so cost and adverse effects are not shown.")

st.divider()

# ---- 曲線（MI / Stroke / Mortality すべて表示） ----
st.markdown("## 📈 Cumulative risk curves (95% CI)")

_OUTCOME_DETAIL_META = {
    "mortality": {"title": "💀 All-cause mortality", "icon": "💀"},
    "mi": {"title": "🫀 Myocardial infarction", "icon": "🫀"},
    "stroke": {"title": "🧠 Stroke", "icon": "🧠"},
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
        x=t[:cut_idx], y=b[:cut_idx], mode="lines", name="Current",
        hovertemplate="%{x:.1f} years: %{y:.2f}%<extra></extra>",
        line=dict(color="red", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=t[cut_idx:], y=b[cut_idx:], mode="lines", name="Current (estimated range at age ≥85)",
        opacity=0.4, hovertemplate="%{x:.1f} years: %{y:.2f}%<extra></extra>", showlegend=False,
        line=dict(color="red", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=t[:cut_idx], y=tg[:cut_idx], mode="lines", name="Medication/target",
        hovertemplate="%{x:.1f} years: %{y:.2f}%<extra></extra>",
        line=dict(color="blue", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=t[cut_idx:], y=tg[cut_idx:], mode="lines", name="Medication/target (estimated range at age ≥85)",
        opacity=0.4, hovertemplate="%{x:.1f} years: %{y:.2f}%<extra></extra>", showlegend=False,
        line=dict(color="blue", width=2)
    ))

    # CI band: baseline
    fig.add_trace(go.Scatter(x=t, y=b_u, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=b_l, mode="lines", fill="tonexty", line=dict(width=0),
                             name="Current 95% CI", hoverinfo="skip", fillcolor="rgba(255, 0, 0, 0.08)"))

    # CI band: target
    fig.add_trace(go.Scatter(x=t, y=tg_u, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=tg_l, mode="lines", fill="tonexty", line=dict(width=0),
                             name="Medication/target 95% CI", hoverinfo="skip", fillcolor="rgba(0, 0, 255, 0.08)"))

    fig.update_layout(
        title=title,
        xaxis_title="Years",
        yaxis_title="Cumulative risk (%)",
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
