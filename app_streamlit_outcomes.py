# app_streamlit_outcomes.py
import re
from datetime import date

import streamlit as st
import plotly.graph_objects as go
import numpy as np

from calc_engine_outcomes import OutcomesEngine
from meds_catalog import load_meds_catalog, apply_meds_to_targets, MedicationAdjustment
import pdf_plan_ui
from treatment_backcast import (
    exposure_adjusted_values,
    reconstruct_untreated_values,
    selected_medications,
)
from lifestyle_interventions import DIET_EFFECTS, EXERCISE_EFFECTS, apply_lifestyle_effects

st.set_page_config(page_title="Lifestyle Care Navigator (English)", layout="wide", page_icon="🌿")

st.markdown("""
<style>
  .stApp { background: #f5f8f6; }
  .stMainBlockContainer { max-width: 1120px; padding-left: 2rem; padding-right: 2rem; }
  [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #dce7df; }
  .care-hero { padding: 1.5rem 1.7rem; border-radius: 22px; color: white;
    background: linear-gradient(125deg,#176b5b 0%,#23856f 58%,#62aa73 100%);
    box-shadow: 0 12px 30px rgba(23,107,91,.18); margin-bottom: 1rem; }
  .care-hero h1 { margin: 0 0 .35rem; font-size: 2rem; }
  .care-hero p { margin: 0; opacity: .92; font-size: 1rem; }
  .step-strip { display:flex; gap:.45rem; flex-wrap:wrap; margin:.6rem 0 1.1rem; }
  .step-pill { background:#e7f2ec; color:#215c4e; padding:.42rem .72rem;
    border-radius:999px; font-size:.82rem; font-weight:700; }
  div[data-testid="stMetric"] { background:white; border:1px solid #dce7df;
    padding: .85rem 1rem; border-radius:16px; box-shadow:0 5px 16px rgba(31,74,61,.06); }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-color:#dce7df !important;
    border-radius:16px !important; background:#fff; }
  .stButton > button[kind="primary"] { border-radius:12px; min-height:3rem;
    background:#176b5b; border-color:#176b5b; font-weight:800; }
  .prediction-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr));
    gap:.65rem; margin:.55rem 0 .35rem; }
  .prediction-item { background:#eef7f2; border:1px solid #cfe3d7; border-radius:12px;
    padding:.65rem .8rem; min-width:0; }
  .prediction-label { color:#547066; font-size:.78rem; font-weight:700; margin-bottom:.12rem; }
  .prediction-value { color:#143f35; font-size:1.28rem; font-weight:850; white-space:nowrap; }
  @media (max-width: 900px) {
    .stMainBlockContainer { max-width: 100%; padding-left: 1rem; padding-right: 1rem; }
    .prediction-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
  }
</style>
<div class="care-hero">
  <h1>🌿 Lifestyle Care Navigator (English)</h1>
  <p>Review progress so far, compare diet, exercise, and medicines together, and choose the next step.</p>
</div>
<div class="step-strip">
  <span class="step-pill">1 Baseline</span><span class="step-pill">2 Progress so far</span>
  <span class="step-pill">3 Choose interventions</span><span class="step-pill">4 Compare the future</span>
  <span class="step-pill">5 Create documents</span>
</div>
""", unsafe_allow_html=True)

st.caption("For clinical education and shared decision-making. This is not a medical device and does not guarantee individual outcomes.")

@st.cache_resource(show_spinner=False)
def _cached_outcomes_engine(config_path: str):
    """CSV基準データを各ウィジェット再実行で読み直さない。"""
    return OutcomesEngine(config_path)


engine = _cached_outcomes_engine("config.yaml")

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

# ====== 薬増減モード（Differenceモデル）用ヘルパー ======
RX_ACTION_NO_CHANGE = "変更なし"
RX_ACTION_STOP = "中止"
RX_ACTION_DOWN = "減量"
RX_ACTION_UP = "増量"
RX_ACTION_SWITCH = "切替"


ACTION_LABELS = {
    RX_ACTION_NO_CHANGE: "No change",
    RX_ACTION_STOP: "Stop",
    RX_ACTION_DOWN: "Reduce dose",
    RX_ACTION_UP: "Increase dose",
    RX_ACTION_SWITCH: "Switch",
}

# Longer phrases first; _display_text also sorts by length to avoid partial hits (e.g. 咳 vs 咳嗽).
DISPLAY_TRANSLATIONS = {
    # Medicines (brand + INN where catalog uses that form)
    "アダラートCR（ニフェジピン）": "Adalat CR (nifedipine controlled-release)",
    "レニベース（エナラプリル）": "Renivace (enalapril)",
    "フルイトラン（トリクロルメチアジド）": "Fluitran (trichlormethiazide)",
    "ミネブロ（エサキセレノン）": "Minnebro (esaxerenone)",
    "レパーサ（エボロクマブ）": "Repatha (evolocumab)",
    "マンジャロ（チルゼパチド）": "Mounjaro (tirzepatide)",
    "オゼンピック（セマグルチド）": "Ozempic (semaglutide)",
    "リベルサス（セマグルチド）": "Rybelsus (semaglutide)",
    "サクビトリル/バルサルタン": "Sacubitril/valsartan",
    "リシノプリル": "Lisinopril",
    "アジルサルタン": "Azilsartan",
    "アムロジピン": "Amlodipine",
    "カルベジロール": "Carvedilol",
    "ビソプロロール": "Bisoprolol",
    "アトルバスタチン": "Atorvastatin",
    "ピタバスタチン": "Pitavastatin",
    "ロスバスタチン": "Rosuvastatin",
    "エゼチミブ": "Ezetimibe",
    "トラゼンタ": "Tradjenta (linagliptin)",
    "ジャディアンス": "Jardiance (empagliflozin)",
    "メトホルミン": "Metformin",
    "ニフェジピン": "nifedipine",
    "エナラプリル": "enalapril",
    # Drug classes
    "GLP-1受容体作動薬（皮下）": "GLP-1 receptor agonist (subcutaneous)",
    "GLP-1受容体作動薬（経口）": "GLP-1 receptor agonist (oral)",
    "GIP/GLP-1受容体作動薬": "GIP/GLP-1 receptor agonist",
    "サイアザイド系利尿薬": "Thiazide diuretic",
    "非ステロイド型MRA": "Nonsteroidal mineralocorticoid receptor antagonist (MRA)",
    "PCSK9阻害薬": "PCSK9 inhibitor",
    "DPP-4阻害薬": "DPP-4 inhibitor",
    "SGLT2阻害薬": "SGLT2 inhibitor",
    "ACE阻害薬": "ACE inhibitor",
    "Ca拮抗薬": "Calcium channel blocker",
    "β遮断薬": "Beta-blocker",
    "吸収阻害薬": "Cholesterol absorption inhibitor",
    "ビグアナイド": "Biguanide",
    "スタチン": "Statin",
    # Adverse effects / clinical phrases
    "投与中止に至る有害事象": "Adverse events leading to discontinuation",
    "低血糖（併用時）": "Hypoglycemia (with concomitant therapy)",
    "副作用発現頻度": "Adverse-event frequency",
    "副作用発現率": "Adverse-event rate",
    "血中カリウム増加": "Increased serum potassium",
    "糸球体濾過率減少": "Decreased glomerular filtration rate (GFR)",
    "注射部位反応": "Injection-site reaction",
    "上気道感染": "Upper respiratory tract infection",
    "肝機能上昇": "Elevated liver enzymes",
    "肝酵素上昇": "Elevated liver enzymes",
    "過度の血圧低下": "Excessive blood pressure reduction",
    "末梢性浮腫": "Peripheral edema",
    "顔面潮紅": "Facial flushing",
    "顔面紅潮": "Flushing",
    "腎機能悪化": "Worsening renal function",
    "消化器症状": "Gastrointestinal symptoms",
    "腹部不快感": "Abdominal discomfort",
    "電解質失調": "Electrolyte imbalance",
    "高尿酸血症": "Hyperuricemia",
    "高血糖症": "Hyperglycemia",
    "勃起障害": "Erectile dysfunction",
    "血管性浮腫": "Angioedema",
    "高K血症": "Hyperkalemia",
    "軽度腎変化": "Mild renal function changes",
    "腎変化": "renal function changes",
    "腎障害": "Renal impairment",
    "尿路感染": "Urinary tract infection",
    "消化不良": "Dyspepsia",
    "筋肉痛": "Myalgia",
    "CK上昇": "Elevated CK",
    "代謝改善": "Improved metabolic profile",
    "疲労感": "Fatigue",
    "空咳": "Dry cough",
    "咳嗽": "Cough",
    "動悸": "Palpitations",
    "めまい": "Dizziness",
    "低血圧": "Hypotension",
    "徐脈": "Bradycardia",
    "抑うつ": "Depression",
    "便秘": "Constipation",
    "下痢": "Diarrhea",
    "悪心": "Nausea",
    "嘔吐": "Vomiting",
    "腹痛": "Abdominal pain",
    "脱水": "Dehydration",
    "浮腫": "Edema",
    "頭痛": "Headache",
    "疲労": "Fatigue",
    "咳": "Cough",
    "は稀": " (rare)",
    # Dosing / punctuation
    "1日2回": "twice daily",
    "隔週注": "every 2 weeks",
    "（開始量）": "(starting dose)",
    "mg/日": "mg/day",
    "mg/週": "mg/week",
    "軽度": "Mild ",
    "未満": " or less",
    "以上": " or more",
    "、": ", ",
    "；": "; ",
    "・": ", ",
    "（": " (",
    "）": ")",
    "〜": "–",
}

ENGLISH_LIFESTYLE_LABELS = {
    "salt": "Dietary sodium restriction",
    "carb": "Carbohydrate restriction",
    "fat": "Saturated fat restriction",
    "aerobic_moderate": "Moderate-intensity aerobic exercise",
    "combined": "Combined aerobic and resistance training",
    "hiit": "High-intensity interval training (HIIT)",
}

ENGLISH_LIFESTYLE_DETAILS = {
    "salt": {
        "definition": "Reduce dietary sodium intake (aim for salt <6 g/day)",
        "population": "Adults",
        "evidence_summary": "Meta-analysis of 133 RCTs (12,197 participants). Mean SBP −4.26 mmHg, DBP −2.07 mmHg.",
        "endpoint_evidence": "Hard cardiovascular endpoint RCTs are limited. Effects are applied via blood-pressure reduction in the existing model.",
    },
    "carb": {
        "definition": "Aim for <130 g carbohydrate/day or <26% of total energy intake",
        "population": "Adults with overweight/obesity and type 2 diabetes",
        "evidence_summary": "Meta-analysis of 17 RCTs (1,197 participants). HbA1c −0.36%. No significant LDL effect.",
        "endpoint_evidence": "No direct long-term hard-endpoint RCTs. Applied via HbA1c reduction.",
    },
    "fat": {
        "definition": "Limit saturated fat to <7% of energy and replace with unsaturated fat",
        "population": "Adults",
        "evidence_summary": "Uses the midpoint (9%) of the NHLBI TLC estimated LDL reduction range (8–10%).",
        "endpoint_evidence": "Direct event benefit in low-risk primary prevention is small/uncertain. Only LDL change is applied.",
    },
    "aerobic_moderate": {
        "definition": "3.0–5.9 METs, 150–210 minutes/week (e.g., brisk walking)",
        "population": "Adults with type 2 diabetes",
        "evidence_summary": "100 RCTs (7,195 participants). Sustained aerobic exercise: HbA1c −0.62%. SBP/LDL use conservative lower bounds.",
        "endpoint_evidence": "Mortality evidence is mainly observational; no direct relative risk is applied.",
    },
    "combined": {
        "definition": "Moderate aerobic exercise plus resistance training 2–3 times/week (150–210 min/week total)",
        "population": "Adults with type 2 diabetes",
        "evidence_summary": "100 RCTs (7,195 participants). Combined training: HbA1c −0.74% (largest). SBP/LDL use conservative lower bounds.",
        "endpoint_evidence": "Mortality evidence is mainly observational; no direct relative risk is applied.",
    },
    "hiit": {
        "definition": "Repeated high-intensity intervals ≥6 METs with recovery (clinician clearance required)",
        "population": "Adults with type 2 diabetes",
        "evidence_summary": "100 RCTs (7,195 participants). HIIT: HbA1c −0.71%. SBP/LDL use conservative lower bounds.",
        "endpoint_evidence": "No confirmed additional mortality benefit versus moderate intensity; no direct relative risk is applied.",
    },
}


def _display_text(value: str) -> str:
    text = str(value)
    for source, target in sorted(DISPLAY_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, target)
    return text


def _lifestyle_label(key: str | None) -> str:
    if key is None:
        return "None"
    return ENGLISH_LIFESTYLE_LABELS.get(key, key)



def _split_med_key(key: str):
    """'アムロジピン 5 mg' -> ('アムロジピン', 5.0)。用量数値が無ければ (key, None)。"""
    m = re.match(r"^(.*?)\s*([0-9]+(?:\.[0-9]+)?)", key)
    if not m:
        return key.strip(), None
    return m.group(1).strip(), float(m.group(2))


def _medication_options_by_name(options):
    """用量付きカタログを「薬剤名 → 用量」の2段階選択用にまとめる。"""
    grouped = {}
    for key in options:
        name, dose = _split_med_key(key)
        grouped.setdefault(name, []).append((dose, key))
    return {
        name: [key for _, key in sorted(entries, key=lambda item: item[0] or 0.0)]
        for name, entries in grouped.items()
    }


def render_two_stage_med_picker(label, options, key_prefix):
    """Two-stage picker: drug name, then dose; returns catalog keys."""
    grouped = _medication_options_by_name(options)
    selected_names = st.multiselect(
        f"{label}: 1) Select medication",
        options=list(grouped),
        format_func=_display_text,
        key=f"{key_prefix}_names",
    )
    selected_keys = []
    for name in selected_names:
        dose_options = grouped[name]
        selected_keys.append(st.selectbox(
            f"{_display_text(name)}: 2) Select dose",
            options=dose_options,
            format_func=lambda key, n=name: _display_text(key[len(n):].strip() or key),
            key=f"{key_prefix}_dose_{name}",
        ))
    return selected_keys


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
    (After changeキーのリスト, 変更明細の文字列リスト) を返す。（案B カード型）"""
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
                    lower,
                    format_func=_display_text,
                    index=len(lower) - 1,  # default one step down
                    key=f"{state_prefix}_down_{k}",
                ) if lower else k
            elif action == RX_ACTION_UP:
                higher = ladder[cur_idx + 1:]  # doses above current (ascending)
                result_key = st.selectbox(
                    "Dose after increase",
                    higher,
                    format_func=_display_text,
                    index=0,  # default one step up
                    key=f"{state_prefix}_up_{k}",
                ) if higher else k
            elif action == RX_ACTION_SWITCH:
                result_key = st.selectbox(
                    "Switch to", switch_opts, format_func=_display_text, key=f"{state_prefix}_sw_{k}"
                )

            # Preview after change (effect and cost delta inside the card)
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
                change_lines.append(
                    f"{icon} {ACTION_LABELS[action]}: {_display_text(k)} → {_display_text(result_key)}"
                )
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
            sections.append("**Adverse effects that stop**\n" + "\n".join(items))
    if dose_changed:
        items = [
            f"- {old['key']} → {new['key']}: {(new.get('side_effects') or '').strip()}"
            for old, new in dose_changed
            if (new.get("side_effects") or "").strip()
        ]
        if items:
            sections.append("**Adverse effects continuing after dose change**\n" + "\n".join(items))
    if pure_added:
        items = _items(pure_added)
        if items:
            sections.append("**New adverse effects**\n" + "\n".join(items))
    if continued:
        items = _items(continued)
        if items:
            sections.append("**Ongoing adverse effects**\n" + "\n".join(items))
    return "\n\n".join(sections)


with st.container(border=True):
    st.markdown("## Inputs")
    st.subheader("Today's visit")
    care_path = st.segmented_control(
        "Visit purpose",
        ["initial", "adjust", "continue"],
        default="initial",
        format_func=lambda value: {
            "initial": "Start treatment",
            "adjust": "Review treatment",
            "continue": "Continue current treatment",
        }[value],
        key="care_path",
    ) or "initial"
    if st.session_state.get("last_care_path") != care_path:
        st.session_state["initial_risk_reviewed"] = False
        st.session_state["initial_baseline_result"] = None
        st.session_state["last_care_path"] = care_path
    backcast_enabled = care_path == "continue"
    initial_risk_reviewed = bool(st.session_state.get("initial_risk_reviewed", False))
    if backcast_enabled:
        st.caption("Enter current medicines to estimate benefit versus never having taken them.")
    elif care_path == "adjust":
        st.caption("Compare current medicines with proposed changes.")
    else:
        st.caption("Compare diet, exercise, and medicine options.")

    st.divider()
    st.markdown("**Patient profile**")
    profile_col1, profile_col2, profile_col3 = st.columns([1, 1, 2.4])
    with profile_col1:
        sex = st.selectbox("Sex", ["male", "female"], format_func=lambda x: "Male" if x == "male" else "Female")
    with profile_col2:
        age = st.number_input("Age", 20, 95, 60, step=1)
    with profile_col3:
        diagnosis_flags = st.multiselect(
            "Diagnosed",
            ["diabetes", "hypertension", "dyslipidemia", "ckd"],
            format_func=lambda value: {
                "diabetes": "Diabetes", "hypertension": "Hypertension",
                "dyslipidemia": "Dyslipidemia", "ckd": "CKD",
            }[value],
            key="diagnosis_flags",
            placeholder="Relevant conditions",
        )
    diabetes_diagnosed = "diabetes" in diagnosis_flags
    ckd_diagnosed = "ckd" in diagnosis_flags

    st.subheader("Current labs" if backcast_enabled else "Risk factors (current → target)")
    st.caption("Enter values directly, or adjust with − / +.")
    now_col1, now_col2, now_col3 = st.columns(3)
    with now_col1:
        sbp_now = st.number_input("Systolic BP", 90, 250, 150, step=10, key="sbp_now_input")
    with now_col2:
        ldl_now = st.number_input("LDL", 20, 300, 160, step=10, key="ldl_now_input")
    with now_col3:
        a1c_now = st.number_input("HbA1c", 4.0, 15.0, 8.0, step=0.5, format="%.1f", key="a1c_now_input")
    if backcast_enabled:
        sbp_tgt_manual, ldl_tgt_manual, a1c_tgt_manual = sbp_now, ldl_now, a1c_now
        smoking_status, cigs_per_day = "never", 0
        years_smoked, years_since_quit, quit_today = 0, 0, False
    elif care_path == "initial" and not initial_risk_reviewed:
        sbp_tgt_manual, ldl_tgt_manual, a1c_tgt_manual = sbp_now, ldl_now, a1c_now
        smoking_status = st.selectbox(
            "Smoking", ["never", "current", "former"],
            format_func=lambda x: {"never": "Never", "current": "Current", "former": "Former"}[x],
            key="smoking_status_compact",
        )
        smoke_col1, smoke_col2 = st.columns(2)
        with smoke_col1:
            cigs_per_day = st.number_input("Cigarettes per day", 0, 80, 20, step=5, key="cigs_compact") if smoking_status == "current" else 0
        with smoke_col2:
            years_smoked = st.number_input("Years smoked", 0, 80, 20, step=5, key="years_smoked_compact") if smoking_status != "never" else 0
        years_since_quit = st.number_input("Years since quitting", 0, 80, 5, step=1, key="quit_years_compact") if smoking_status == "former" else 0
        quit_today = False
    else:
        st.markdown("**Targets**")
        target_col1, target_col2, target_col3 = st.columns(3)
        with target_col1:
            sbp_tgt_manual = st.number_input("BP target", 90, 200, 130, step=10, key="sbp_target_input")
        with target_col2:
            ldl_tgt_manual = st.number_input("LDL target", 20, 250, 100, step=10, key="ldl_target_input")
        with target_col3:
            a1c_tgt_manual = st.number_input("HbA1c target", 4.0, 12.0, 7.0, step=0.5, format="%.1f", key="a1c_target_input")

        st.markdown("**Smoking**")
        smoking_status = st.selectbox(
            "Status", ["never", "current", "former"],
            format_func=lambda x: {"never": "Never", "current": "Current", "former": "Former"}[x],
            key="smoking_status_compact",
        )
        smoke_col1, smoke_col2 = st.columns(2)
        with smoke_col1:
            cigs_per_day = st.number_input("Cigarettes per day", 0, 80, 20, step=5, key="cigs_compact") if smoking_status == "current" else 0
        with smoke_col2:
            years_smoked = st.number_input("Years smoked", 0, 80, 20, step=5, key="years_smoked_compact") if smoking_status != "never" else 0
        years_since_quit = st.number_input("Years since quitting", 0, 80, 5, step=1, key="quit_years_compact") if smoking_status == "former" else 0
        quit_today = st.checkbox("Also compare quitting today", key="quit_today_compact") if smoking_status == "current" else False

    st.markdown("**Body size (sex-specific defaults if blank)**")
    default_height, default_weight = ((170.0, 65.0) if sex == "male" else (160.0, 55.0))
    body_col1, body_col2, body_col3 = st.columns(3)
    with body_col1:
        height_input = st.number_input("Height (cm)", min_value=120.0, max_value=220.0, value=None, step=1.0, placeholder=f"Default {default_height:.0f}")
    with body_col2:
        weight_input = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, value=None, step=1.0, placeholder=f"Default {default_weight:.0f}")
    with body_col3:
        dbp_now = st.number_input("Diastolic BP", min_value=40, max_value=130, value=90, step=5)
    height_cm = float(height_input if height_input is not None else default_height)
    weight_kg = float(weight_input if weight_input is not None else default_weight)
    bmi_now = weight_kg / (height_cm / 100.0) ** 2
    bmi_target = 22.0
    if backcast_enabled:
        st.caption(f"Current BMI: {bmi_now:.1f}")
    else:
        st.caption(f"Current BMI: {bmi_now:.1f} / Target BMI: 22.0 (target weight {22 * (height_cm / 100.0) ** 2:.1f} kg)")

    st.caption(f"Used in calculation: {height_cm:.0f} cm, {weight_kg:.0f} kg, BMI {bmi_now:.1f}")

    if backcast_enabled:
        egfr_now = egfr_target = 80.0
        acr_now = acr_target = "A1"
        which = "10-year"
    else:
        if ckd_diagnosed:
            st.markdown("**🫀 CKD**")
            kidney_col1, kidney_col2 = st.columns(2)
            with kidney_col1:
                egfr_now = st.number_input("eGFR", min_value=5.0, max_value=120.0, value=45.0, step=5.0)
            with kidney_col2:
                acr_now = st.selectbox("Urine albumin/protein", ["A1", "A2", "A3"], index=1)
            egfr_target, acr_target = egfr_now, acr_now
        else:
            egfr_now = egfr_target = 80.0
            acr_now = acr_target = "A1"

        st.subheader("Prediction horizon")
        which = st.radio(
            "Select horizon", ["5-year", "10-year", "20-year", "30-year", "50-year", "Both"], index=2,
            format_func=lambda x: {"5-year": "5 years", "10-year": "10 years", "20-year": "20 years", "30-year": "30 years", "50-year": "50 years", "Both": "Both"}[x]
        )

    # 初診は「Currentリスクの確認」を終えるまで介入選択を表示しない。
    if care_path == "initial" and not initial_risk_reviewed:
        st.divider()
        st.markdown("### 1. Review current risk first")
        baseline_horizon = {"5-year": 5, "10-year": 10, "20-year": 20, "30-year": 30, "50-year": 50, "Both": 10}[which]
        baseline_signature = (
            sex, age, sbp_now, ldl_now, a1c_now, smoking_status, cigs_per_day,
            years_smoked, years_since_quit, bmi_now, egfr_now, acr_now, baseline_horizon,
        )
        if st.session_state.get("initial_baseline_signature") != baseline_signature:
            st.session_state["initial_baseline_result"] = None
            st.session_state["initial_baseline_signature"] = baseline_signature
        reference_values = {"sbp": 120.0, "ldl": 100.0, "a1c": 5.7, "bmi": 22.0}
        deviation_cols = st.columns(4)
        deviation_cols[0].metric("Systolic BP", f"{sbp_now:.0f}", delta=f"vs reference {sbp_now-reference_values['sbp']:+.0f} mmHg", delta_color="inverse")
        deviation_cols[1].metric("LDL", f"{ldl_now:.0f}", delta=f"vs reference {ldl_now-reference_values['ldl']:+.0f} mg/dL", delta_color="inverse")
        deviation_cols[2].metric("HbA1c", f"{a1c_now:.1f}%", delta=f"vs reference {a1c_now-reference_values['a1c']:+.1f}%", delta_color="inverse")
        deviation_cols[3].metric("BMI", f"{bmi_now:.1f}", delta=f"vs reference {bmi_now-reference_values['bmi']:+.1f}", delta_color="inverse")
        st.caption("Reference: SBP 120 mmHg, LDL 100 mg/dL, HbA1c 5.7%, BMI 22, never smoked. This differs from individualized treatment targets.")
        if st.button("Compare future risk: current vs reference", type="primary", use_container_width=True, key="calculate_initial_baseline"):
            baseline_result = {}
            with st.spinner("Calculating cumulative risk and prediction intervals..."):
                for outcome in OUTCOME_DISPLAY_ORDER:
                    curve = {key: [0.0] for key in ("time", "current", "reference", "current_low", "current_high", "reference_low", "reference_high")}
                    for year in range(1, baseline_horizon + 1):
                        result = engine.cumulative_incidence_with_ci(
                            outcome, sex, int(age), year,
                            sbp_now, reference_values["sbp"], ldl_now, reference_values["ldl"], a1c_now, reference_values["a1c"],
                            smoking_status, cigs_per_day, years_smoked, years_since_quit,
                            smoking_status == "current",
                            bmi_now=bmi_now, bmi_target=reference_values["bmi"],
                            egfr_now=egfr_now, egfr_target=egfr_now,
                            acr_now=acr_now, acr_target="A1" if ckd_diagnosed else acr_now,
                        )
                        curve["time"].append(float(year))
                        curve["current"].append(result["point"]["baseline"] * 100.0)
                        curve["reference"].append(result["point"]["target"] * 100.0)
                        curve["current_low"].append(result["lower"]["baseline"] * 100.0)
                        curve["current_high"].append(result["upper"]["baseline"] * 100.0)
                        curve["reference_low"].append(result["lower"]["target"] * 100.0)
                        curve["reference_high"].append(result["upper"]["target"] * 100.0)
                    baseline_result[outcome] = curve
            st.session_state["initial_baseline_result"] = baseline_result
        baseline_result = st.session_state.get("initial_baseline_result")
        if baseline_result:
            st.success(f"Difference over {baseline_horizon} years between staying at current values and reaching the reference.")
            baseline_cols = st.columns(3)
            for col, outcome, label in zip(baseline_cols, OUTCOME_DISPLAY_ORDER, ["All-cause mortality", "Myocardial infarction", "Stroke"]):
                curve = baseline_result[outcome]
                col.metric(label, f"{curve['current'][-1]:.1f}%", delta=f"If reference {curve['reference'][-1]:.1f}%", delta_color="inverse")
            for outcome, label in zip(OUTCOME_DISPLAY_ORDER, ["All-cause mortality", "Myocardial infarction", "Stroke"]):
                curve = baseline_result[outcome]
                with st.container(border=True):
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=curve["time"], y=curve["current_high"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
                    fig.add_trace(go.Scatter(x=curve["time"], y=curve["current_low"], line=dict(width=0), fill="tonexty", fillcolor="rgba(220,79,68,.14)", name="Current 95% prediction interval", hoverinfo="skip"))
                    fig.add_trace(go.Scatter(x=curve["time"], y=curve["current"], mode="lines", name="Stay at current values", line=dict(color="#d94f45", width=3)))
                    fig.add_trace(go.Scatter(x=curve["time"], y=curve["reference"], mode="lines", name="Reach reference targets", line=dict(color="#16846b", width=3)))
                    fig.update_layout(title=f"{label} cumulative risk", xaxis_title="Years from now", yaxis_title="Cumulative risk (%)", height=360, hovermode="x unified", margin=dict(l=20, r=20, t=55, b=20))
                    st.plotly_chart(fig, width="stretch")
                    st.caption("The light red band is the 95% prediction interval based on current values. It does not determine individual events.")
            if st.button("Next: choose diet, exercise, and medicines", type="primary", use_container_width=True, key="open_initial_interventions"):
                st.session_state["initial_risk_reviewed"] = True
                st.rerun()
        st.stop()

    st.divider()
    st.subheader("Choose treatment")
    lifestyle_col1, lifestyle_col2 = st.columns(2)
    with lifestyle_col1:
        diet_intervention_keys = st.multiselect(
            "Diet",
            list(DIET_EFFECTS),
            format_func=lambda key: _lifestyle_label(key),
            key="unified_diet_interventions",
            placeholder="Select diet interventions",
        )
    with lifestyle_col2:
        exercise_intervention_key = st.selectbox(
            "Exercise",
            [None, *EXERCISE_EFFECTS],
            format_func=lambda key: _lifestyle_label(key),
            key="unified_exercise_intervention",
        )
    with st.expander("Effect sizes and references"):
        selected_lifestyle_keys = [
            *(DIET_EFFECTS[key] for key in diet_intervention_keys),
            *([EXERCISE_EFFECTS[exercise_intervention_key]] if exercise_intervention_key else []),
        ]
        if not selected_lifestyle_keys:
            st.caption("Select interventions to see definitions, effect sizes, and evidence here.")
        for effect in selected_lifestyle_keys:
            detail = ENGLISH_LIFESTYLE_DETAILS.get(effect.key, {})
            st.markdown(
                f"**{_lifestyle_label(effect.key)}** — "
                f"{detail.get('definition', effect.definition)}"
            )
            st.caption(
                f"{detail.get('evidence_summary', effect.evidence_summary)} "
                f"{detail.get('endpoint_evidence', effect.endpoint_evidence)}"
            )
            st.link_button("Source paper", effect.source_url, key=f"lifestyle_source_{effect.key}")

    st.markdown("**Medicines**")

    # 1. 薬剤オプションを先に定義
    sbp_options = [m["key"] for m in meds_catalog["sbp"]]
    ldl_options = [m["key"] for m in meds_catalog["ldl"]]
    a1c_options = [m["key"] for m in meds_catalog["hba1c"]]

    # 2. 薬剤を使うかどうかのチェック
    use_meds = True if backcast_enabled else st.checkbox(
        "Select medicines to auto-calculate targets", value=True
    )

    # 薬剤カタログ読み込み失敗時の警告
    if catalog_error:
        st.warning("Failed to load the medicine catalog. Check Excel path / sheet / column names.")
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
        if backcast_enabled:
            mode = "backcast"
            med_cols = st.columns(3)
            with med_cols[0]:
                current_sbp_keys = render_two_stage_med_picker("BP medicines", sbp_options, "backcast_current_sbp")
            with med_cols[1]:
                current_ldl_keys = render_two_stage_med_picker("Lipid medicines", ldl_options, "backcast_current_ldl")
            with med_cols[2]:
                current_a1c_keys = render_two_stage_med_picker("Diabetes medicines", a1c_options, "backcast_current_a1c")
            adjusted_sbp_keys = list(current_sbp_keys)
            adjusted_ldl_keys = list(current_ldl_keys)
            adjusted_a1c_keys = list(current_a1c_keys)
            current_meds = {
                "sbp": [m for m in meds_catalog["sbp"] if m["key"] in current_sbp_keys],
                "ldl": [m for m in meds_catalog["ldl"] if m["key"] in current_ldl_keys],
                "hba1c": [m for m in meds_catalog["hba1c"] if m["key"] in current_a1c_keys],
            }
            adj = MedicationAdjustment(
                sbp_now=float(sbp_now), ldl_now_mg=float(ldl_now), a1c_now=float(a1c_now),
                current_meds=current_meds, adjusted_meds=current_meds,
            )
            all_current_meds = [m for domain in current_meds.values() for m in domain]
            costs = adj.costs()
            meds_summary = {
                "sbp_target": float(sbp_now), "ldl_target": float(ldl_now), "a1c_target": float(a1c_now),
                "annual_cost_yen": costs["baseline"],
                "side_effects_md": _se_md_for_changes([], [], all_current_meds),
                "mode": "backcast", "costs": costs,
            }
        else:
            mode = "adjust" if care_path == "adjust" else "add"

        if mode == "add":
            med_cols = st.columns(3)
            with med_cols[0]:
                sbp_sel_keys = render_two_stage_med_picker("BP medicines", sbp_options, "add_sbp")
            selected_sbp_meds = [m for m in meds_catalog["sbp"] if m["key"] in sbp_sel_keys]
            with med_cols[1]:
                ldl_sel_keys = render_two_stage_med_picker("Lipid medicines", ldl_options, "add_ldl")
            selected_ldl_meds = [m for m in meds_catalog["ldl"] if m["key"] in ldl_sel_keys]
            with med_cols[2]:
                a1c_sel_keys = render_two_stage_med_picker("Diabetes medicines", a1c_options, "add_a1c")
            selected_a1c_meds = [m for m in meds_catalog["hba1c"] if m["key"] in a1c_sel_keys]

            meds_summary = apply_meds_to_targets(
                sbp_now=float(sbp_now),
                ldl_now_mg=float(ldl_now),
                a1c_now=float(a1c_now),
                selected_sbp=selected_sbp_meds,
                selected_ldl=selected_ldl_meds,
                selected_a1c=selected_a1c_meds,
            )

        elif mode == "adjust":
            # 薬増減UI：Currentの治療をベースラインに、各薬をワンタップで 中止/減量/増量/切替
            st.markdown("**Current medicines**")
            med_cols = st.columns(3)
            with med_cols[0]:
                current_sbp_keys = render_two_stage_med_picker("BP medicines", sbp_options, "adjust_current_sbp")
            with med_cols[1]:
                current_ldl_keys = render_two_stage_med_picker("Lipid medicines", ldl_options, "adjust_current_ldl")
            with med_cols[2]:
                current_a1c_keys = render_two_stage_med_picker("Diabetes medicines", a1c_options, "adjust_current_a1c")

            st.markdown("**Change each medicine**")
            if not (current_sbp_keys or current_ldl_keys or current_a1c_keys):
                st.caption("Select current medicines to show change options.")
            adjusted_sbp_keys, sbp_changes = render_rx_change_rows(
                "BP medicines", "sbp", meds_catalog["sbp"], current_sbp_keys, "pc_sbp"
            )
            adjusted_ldl_keys, ldl_changes = render_rx_change_rows(
                "Lipid medicines", "ldl", meds_catalog["ldl"], current_ldl_keys, "pc_ldl"
            )
            adjusted_a1c_keys, a1c_changes = render_rx_change_rows(
                "Diabetes medicines", "hba1c", meds_catalog["hba1c"], current_a1c_keys, "pc_a1c"
            )

            with st.expander("Add medicines (optional)"):
                add_sbp_keys = render_two_stage_med_picker(
                    "BP medicines (add)",
                    [o for o in sbp_options
                     if o not in current_sbp_keys and o not in adjusted_sbp_keys],
                    "pc_add_sbp",
                )
                add_ldl_keys = render_two_stage_med_picker(
                    "Lipid medicines (add)",
                    [o for o in ldl_options
                     if o not in current_ldl_keys and o not in adjusted_ldl_keys],
                    "pc_add_ldl",
                )
                add_a1c_keys = render_two_stage_med_picker(
                    "Diabetes medicines (add)",
                    [o for o in a1c_options
                     if o not in current_a1c_keys and o not in adjusted_a1c_keys],
                    "pc_add_a1c",
                )
            adjusted_sbp_keys = adjusted_sbp_keys + [k for k in add_sbp_keys if k not in adjusted_sbp_keys]
            adjusted_ldl_keys = adjusted_ldl_keys + [k for k in add_ldl_keys if k not in adjusted_ldl_keys]
            adjusted_a1c_keys = adjusted_a1c_keys + [k for k in add_a1c_keys if k not in adjusted_a1c_keys]

            rx_change_lines = (
                sbp_changes + ldl_changes + a1c_changes
                + [f"➕ Add: {_display_text(k)}" for k in list(add_sbp_keys) + list(add_ldl_keys) + list(add_a1c_keys)]
            )
            if rx_change_lines:
                st.markdown("**Changes**")
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
        st.caption("Combination rule: SBP additive / LDL multiplicative % / HbA1c additive")
        if meds_summary is not None:
            if meds_summary.get("mode") == "backcast":
                st.metric("Estimated annual drug cost", f"{meds_summary['annual_cost_yen']:,} JPY/year")
                st.caption("Counterfactual lab results are shown in the main pane.")
            elif meds_summary.get("mode") == "adjust":
                st.metric("Annual drug cost (after change)", f"{meds_summary['annual_cost_yen']:,} JPY/year")
                st.markdown("**Auto-calculated targets (used for risk calculation)**")
                st.write(f"- SBP Target: **{meds_summary['sbp_target']:.0f} mmHg**")
                st.write(f"- LDL Target: **{meds_summary['ldl_target']:.0f} mg/dL**")
                st.write(f"- HbA1c Target: **{meds_summary['a1c_target']:.1f} %**")

                st.markdown("**Medicine-change comparison**")
                costs = meds_summary["costs"]
                delta = costs["delta"]
                delta_sign = "+" if delta > 0 else ""
                st.write(
                    f"- Annual drug cost: {costs['baseline']:,} JPY/year → {costs['adjusted']:,} JPY/year "
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
                st.markdown("**Prediction after medicine intervention**")
                st.markdown(
                    f'<div class="prediction-strip">'
                    f'<div class="prediction-item"><div class="prediction-label">Systolic BP</div><div class="prediction-value">{meds_summary["sbp_target"]:.0f} <small>mmHg</small></div></div>'
                    f'<div class="prediction-item"><div class="prediction-label">LDL</div><div class="prediction-value">{meds_summary["ldl_target"]:.0f} <small>mg/dL</small></div></div>'
                    f'<div class="prediction-item"><div class="prediction-label">HbA1c</div><div class="prediction-value">{meds_summary["a1c_target"]:.1f}<small>%</small></div></div>'
                    f'<div class="prediction-item"><div class="prediction-label">Estimated annual drug cost</div><div class="prediction-value">{meds_summary["annual_cost_yen"]:,}<small>JPY/year</small></div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if meds_summary["side_effects_md"].strip():
                with st.expander("Main adverse effects (by medicine)"):
                    st.markdown(_display_text(meds_summary["side_effects_md"]))
        elif mode == "adjust":
            st.caption("Adjust mode: select currently used medicines.")

    backcast_treatment_years = 1
    backcast_medication_years = {}
    backcast_keys = [*current_sbp_keys, *current_ldl_keys, *current_a1c_keys]
    if backcast_enabled:
        st.markdown("**Treatment duration**")
        if not backcast_keys:
            st.info("Enter current medicines above to calculate.")
        else:
            backcast_treatment_years = st.number_input(
                "Years since starting treatment",
                min_value=1,
                max_value=max(1, int(age) - 20),
                value=min(10, max(1, int(age) - 20)),
                step=1,
                key="backcast_treatment_years",
            )
            for med_key in backcast_keys:
                backcast_medication_years[med_key] = float(backcast_treatment_years)

with st.sidebar:
    st.markdown("### Today's navigator")
    st.caption("Enter data in the main pane. This sidebar shows the run button and a summary only.")
    calculation_button_slot = st.empty()

# ====== 実際に使うTarget値 ======
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

# 食事・運動も薬剤と同列の介入として、最終的なPredicted valuesに重ねる。
diabetes_context = bool(
    diabetes_diagnosed or a1c_now >= 6.5 or current_a1c_keys or a1c_sel_keys or adjusted_a1c_keys
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

with st.sidebar:
    if lifestyle_result["applied"]:
        with st.container(border=True):
            st.markdown("**Predicted values after selected interventions**")
            st.markdown(
                f"BP **{sbp_tgt:.0f} mmHg**  \n"
                f"🧪 LDL　**{ldl_tgt:.0f} mg/dL**  \n"
                f"🍬 HbA1c　**{a1c_tgt:.1f}%**"
            )
    for effect in lifestyle_result["skipped"]:
        st.warning(
            f"{_lifestyle_label(effect.key)} is based on evidence in {ENGLISH_LIFESTYLE_DETAILS.get(effect.key, {}).get('population', effect.population)}; effect size was not applied to the current inputs."
        )

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

# ---- パラメータ変更検知と手動計算 ----
# Currentのパラメータを文字列化してハッシュ化（変更検知用）
import hashlib
current_params = {
    "sex": sex, "age": age,
    "height_cm": height_cm, "weight_kg": weight_kg, "dbp_now": dbp_now,
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
    "diagnoses": tuple(diagnosis_flags),
    "backcast_treatment_years": int(backcast_treatment_years),
    "diet_interventions": tuple(diet_intervention_keys),
    "exercise_intervention": exercise_intervention_key,
}
params_hash = hashlib.md5(str(sorted(current_params.items())).encode()).hexdigest()

# セッション状態の初期化
if "params_hash" not in st.session_state:
    st.session_state.params_hash = None
    st.session_state.calculated = False
    st.session_state.cumulative_data = None
    st.session_state.years = None
if "backcast_params_hash" not in st.session_state:
    st.session_state.backcast_params_hash = None

horizons = [5, 10] if which == "Both" else [_years_from_choice(which)]
years_for_curve = max(horizons)

selected_intervention_labels = [_lifestyle_label(effect.key) for effect in lifestyle_result["applied"]]
selected_medication_labels = [
    _display_text(k)
    for k in list(current_sbp_keys or sbp_sel_keys) + list(current_ldl_keys or ldl_sel_keys) + list(current_a1c_keys or a1c_sel_keys)
]
with st.container(border=True):
    st.markdown(
        f"**Predicted values**  BP {sbp_now:.0f}→**{sbp_tgt:.0f}**  "
        f"LDL {ldl_now:.0f}→**{ldl_tgt:.0f}**  HbA1c {a1c_now:.1f}→**{a1c_tgt:.1f}%**  \n"
        f"🥗 {(', '.join(selected_intervention_labels) if selected_intervention_labels else 'None selected')}  /  "
        f"💊 {(', '.join(selected_medication_labels) if selected_medication_labels else 'None selected')}"
    )

if diabetes_diagnosed or ckd_diagnosed:
    st.markdown("### 🩺 Condition-specific view")
    disease_cols = st.columns(int(diabetes_diagnosed) + int(ckd_diagnosed))
    disease_index = 0
    if diabetes_diagnosed:
        with disease_cols[disease_index].container(border=True):
            st.markdown("**Diabetes module**")
            st.metric("Current HbA1c", f"{a1c_now:.1f}%", delta=f"After intervention {a1c_tgt:.1f}%")
            st.caption("HbA1c-based MI, stroke, and mortality adjustments are integrated into the shared model.")
        disease_index += 1
    if ckd_diagnosed:
        g_stage = "G1" if egfr_now >= 90 else "G2" if egfr_now >= 60 else "G3a" if egfr_now >= 45 else "G3b" if egfr_now >= 30 else "G4" if egfr_now >= 15 else "G5"
        with disease_cols[disease_index].container(border=True):
            st.markdown("**CKD module**")
            st.metric("eGFR stage", g_stage, delta=f"Urine protein {acr_now}")
            st.caption("eGFR and urine albumin/protein adjustments for MI, stroke, and mortality are integrated into the shared model.")

# 入力が変わったら古い結果を無効化するが、自動再計算はしない。
params_changed = st.session_state.params_hash != params_hash
if not backcast_enabled and params_changed and st.session_state.calculated:
    st.session_state.calculated = False
    st.session_state.cumulative_data = None
    st.session_state.years = None

# 通常モデルはボタンを押したときだけ重い計算を実行する。
manual_button_clicked = False
if not backcast_enabled:
    sidebar_calculate_clicked = calculation_button_slot.button(
        "🔄 Run risk calculation",
        type="primary",
        use_container_width=True,
        key="risk_calculate_sidebar",
    )
    main_calculate_clicked = st.button(
        "🔄 Run risk calculation",
        type="primary",
        use_container_width=True,
        key="risk_calculate_main",
    )
    manual_button_clicked = sidebar_calculate_clicked or main_calculate_clicked
if not backcast_enabled and manual_button_clicked:
    with st.spinner("Calculating risk..."):
        st.session_state.cumulative_data = calculate_cumulative_risk_curves(years_for_curve)
        st.session_state.calculated = True
        st.session_state.years = years_for_curve
        st.session_state.params_hash = params_hash

# 反実仮想も薬剤名・用量の選択中は計算せず、専用ボタンで確定する。
backcast_ready = False
if backcast_enabled and backcast_keys:
    sidebar_backcast_clicked = calculation_button_slot.button(
        "Calculate counterfactual",
        type="primary",
        use_container_width=True,
        key="backcast_calculate_sidebar",
    )
    main_backcast_clicked = st.button(
        "Calculate counterfactual",
        type="primary",
        use_container_width=True,
        key="backcast_calculate_main",
    )
    backcast_button_clicked = sidebar_backcast_clicked or main_backcast_clicked
    if backcast_button_clicked:
        st.session_state.backcast_params_hash = params_hash
    backcast_ready = st.session_state.backcast_params_hash == params_hash
    if not backcast_ready:
        st.info("Confirm medicines and doses, then press Calculate counterfactual.")

if not backcast_enabled and not st.session_state.calculated:
    st.info('Set the parameters above, then press "Run risk calculation".')
    st.stop()

cumulative_data = st.session_state.cumulative_data or {}
labels = {"mi": "Myocardial infarction", "stroke": "Stroke", "mortality": "All-cause mortality"}

# ---- 反実仮想モード：通常の将来リスク表示を、この結果へ丸ごと差し替える ----
backcast_summary = None
if backcast_enabled and backcast_keys and backcast_ready:
    past_sbp_meds = selected_medications(meds_catalog, "sbp", current_sbp_keys)
    past_ldl_meds = selected_medications(meds_catalog, "ldl", current_ldl_keys)
    past_a1c_meds = selected_medications(meds_catalog, "hba1c", current_a1c_keys)
    untreated_values = reconstruct_untreated_values(
        sbp_now=sbp_now, ldl_now=ldl_now, a1c_now=a1c_now,
        sbp_meds=past_sbp_meds, ldl_meds=past_ldl_meds, a1c_meds=past_a1c_meds,
    )
    treated_average = exposure_adjusted_values(
        untreated=untreated_values,
        current={"sbp": sbp_now, "ldl": ldl_now, "a1c": a1c_now},
        treatment_years=int(backcast_treatment_years),
        medication_years=backcast_medication_years,
        sbp_meds=past_sbp_meds, ldl_meds=past_ldl_meds, a1c_meds=past_a1c_meds,
    )
    start_age = int(age) - int(backcast_treatment_years)
    event_effects = {}
    event_curves = {}
    future_years = min(10, max(1, 110 - int(age)))
    for outcome in OUTCOME_DISPLAY_ORDER:
        timeline = []
        untreated_curve = []
        treated_curve = []
        for elapsed in range(0, int(backcast_treatment_years) + 1):
            if elapsed == 0:
                untreated_risk = treated_risk = 0.0
            else:
                past_result = engine.cumulative_incidence(
                    outcome, sex, start_age, elapsed,
                    untreated_values["sbp"], treated_average["sbp"],
                    untreated_values["ldl"], treated_average["ldl"],
                    untreated_values["a1c"], treated_average["a1c"],
                    smoking_status, cigs_per_day, years_smoked, years_since_quit,
                    assume_quit_today_in_target=False,
                )
                untreated_risk = past_result["baseline"] * 100.0
                treated_risk = past_result["target"] * 100.0
            timeline.append(elapsed - int(backcast_treatment_years))
            untreated_curve.append(untreated_risk)
            treated_curve.append(treated_risk)

        past_untreated = untreated_curve[-1] / 100.0
        past_treated = treated_curve[-1] / 100.0
        for future in range(1, future_years + 1):
            future_result = engine.cumulative_incidence(
                outcome, sex, int(age), future,
                untreated_values["sbp"], float(sbp_now),
                untreated_values["ldl"], float(ldl_now),
                untreated_values["a1c"], float(a1c_now),
                smoking_status, cigs_per_day, years_smoked, years_since_quit,
                assume_quit_today_in_target=False,
            )
            timeline.append(future)
            untreated_curve.append((1.0 - (1.0 - past_untreated) * (1.0 - future_result["baseline"])) * 100.0)
            treated_curve.append((1.0 - (1.0 - past_treated) * (1.0 - future_result["target"])) * 100.0)

        untreated_risk = untreated_curve[int(backcast_treatment_years)]
        treated_risk = treated_curve[int(backcast_treatment_years)]
        event_effects[outcome] = {
            "untreated": untreated_risk,
            "treated": treated_risk,
            "avoided": max(0.0, untreated_risk - treated_risk),
        }
        event_curves[outcome] = {
            "time": timeline, "untreated": untreated_curve, "treated": treated_curve,
        }
    backcast_summary = {
        "treatment_years": int(backcast_treatment_years),
        "medications": [*current_sbp_keys, *current_ldl_keys, *current_a1c_keys],
        "current_sbp": float(sbp_now), "current_ldl": float(ldl_now), "current_a1c": float(a1c_now),
        "untreated_sbp": float(untreated_values["sbp"]),
        "untreated_ldl": float(untreated_values["ldl"]),
        "untreated_a1c": float(untreated_values["a1c"]),
        "event_effects": event_effects,
        "event_curves": event_curves,
        "future_years": future_years,
    }
    st.markdown("## 5. Estimated comparison if medicines had not been taken")
    st.caption(f"Estimate for the past {int(backcast_treatment_years)} years, back-calculated from catalog average effects.")
    result_cols = st.columns(3)
    for col, label, untreated, current, unit in (
        (result_cols[0], "Systolic BP", untreated_values["sbp"], sbp_now, "mmHg"),
        (result_cols[1], "LDL", untreated_values["ldl"], ldl_now, "mg/dL"),
        (result_cols[2], "HbA1c", untreated_values["a1c"], a1c_now, "%"),
    ):
        with col:
            st.metric(label, f"Current {current:.1f} {unit}", delta=f"No-drug estimate {untreated:.1f} {unit}")
    st.markdown(f"### Events that may have been avoided over these {int(backcast_treatment_years)} years")
    event_cols = st.columns(3)
    for col, outcome in zip(event_cols, OUTCOME_DISPLAY_ORDER):
        effect = event_effects[outcome]
        with col:
            st.metric(
                labels[outcome],
                f"{effect['avoided']:.1f} percentage points avoided",
                delta=f"No drug {effect['untreated']:.1f}% → On treatment {effect['treated']:.1f}%",
            )
            if effect["avoided"] > 0.05:
                st.caption(f"About {effect['avoided']:.1f} events per 100 people / NNT ≈ {100/effect['avoided']:.0f}")
            else:
                st.caption("Estimated difference is very small")
    st.markdown(f"### Benefit so far and outlook for the next {future_years} years")
    st.caption("Year 0 is now. Left is the past; right is the future estimate.")
    colors = {"mortality": "#6B7280", "mi": "#E45756", "stroke": "#4C78A8"}
    for outcome in OUTCOME_DISPLAY_ORDER:
        curve = event_curves[outcome]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=curve["time"], y=curve["untreated"], mode="lines",
            name="If medicines had not been taken", line=dict(color=colors[outcome], dash="dash", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=curve["time"], y=curve["treated"], mode="lines",
            name="If medicines are continued", line=dict(color=colors[outcome], width=3),
        ))
        fig.add_vline(x=0, line_dash="dot", line_color="#111827", annotation_text="Current")
        fig.update_layout(
            title=labels[outcome], xaxis_title="Years relative to now (0 = today)", yaxis_title="Cumulative event risk (%)",
            height=420, hovermode="x unified", legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig, width="stretch")
    st.success("Current values reflect benefit from continued treatment. Do not stop medicines on your own; discuss the plan with the clinician.")
elif backcast_enabled and not backcast_keys:
    st.info("Select current medicines to show estimates if they had not been taken.")

# ---- サマリー ----
if not backcast_enabled:
    st.markdown("## 📊 Risk comparison summary")
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
                st.metric(f"{horizon}-year risk reduction (ARR)", f"{arr:.1f}%", delta=f"Current {r['baseline']*100:.1f}% → Target {r['target']*100:.1f}%")
            if outcome == "mortality":
                st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)

st.divider()

st.markdown("## 💴 Cost and adverse effects (when medicines selected)")
if use_meds and meds_summary is not None:
    if meds_summary.get("mode") == "backcast":
        annual_cost = int(meds_summary["annual_cost_yen"])
        st.metric("Annual drug cost (current)", f"{annual_cost:,} JPY/year")
        st.metric(
            f"Approx. drug cost over {int(backcast_treatment_years)} treatment years",
            f"{annual_cost * int(backcast_treatment_years):,} JPY",
        )
        st.caption("Rough estimate = current list price × treatment years. Past prices, regimen changes, and co-pay are not included.")
    elif meds_summary.get("mode") == "adjust":
        costs = meds_summary["costs"]
        delta = costs["delta"]
        delta_sign = "+" if delta > 0 else ""
        st.metric("Annual drug cost (current)", f"{costs['baseline']:,} JPY/year")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Annual drug cost (after change)", f"{costs['adjusted']:,} JPY/year")
        with col2:
            st.metric("Difference", f"{delta_sign}{delta:,} JPY/year")
        st.markdown("**Target value changes**")
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
        st.metric("Annual drug cost (total)", f"{annual_cost_yen:,} JPY/year")
    if side_effects_md.strip():
        st.markdown("**Main adverse effects (by medicine)**")
        st.markdown(_display_text(side_effects_md))
else:
    st.info("No medicines selected, so cost and adverse effects are not shown.")

st.divider()

# ---- 曲線（MI / Stroke / Mortality すべて表示） ----
if not backcast_enabled:
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
        hovertemplate="%{x:.1f} y: %{y:.2f}%<extra></extra>",
        line=dict(color="red", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=t[cut_idx:], y=b[cut_idx:], mode="lines", name="Current (≥85y extrapolated)",
        opacity=0.4, hovertemplate="%{x:.1f} y: %{y:.2f}%<extra></extra>", showlegend=False,
        line=dict(color="red", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=t[:cut_idx], y=tg[:cut_idx], mode="lines", name="Medicine/target",
        hovertemplate="%{x:.1f} y: %{y:.2f}%<extra></extra>",
        line=dict(color="blue", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=t[cut_idx:], y=tg[cut_idx:], mode="lines", name="Medicine/target (≥85y extrapolated)",
        opacity=0.4, hovertemplate="%{x:.1f} y: %{y:.2f}%<extra></extra>", showlegend=False,
        line=dict(color="blue", width=2)
    ))

    # CI band: baseline
    fig.add_trace(go.Scatter(x=t, y=b_u, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=b_l, mode="lines", fill="tonexty", line=dict(width=0),
                             name="Current 95%CI", hoverinfo="skip", fillcolor="rgba(255, 0, 0, 0.08)"))

    # CI band: target
    fig.add_trace(go.Scatter(x=t, y=tg_u, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=tg_l, mode="lines", fill="tonexty", line=dict(width=0),
                             name="Medicine/target 95% CI", hoverinfo="skip", fillcolor="rgba(0, 0, 255, 0.08)"))

    fig.update_layout(
        title=title,
        xaxis_title="Years",
        yaxis_title="Cumulative risk (%)",
        hovermode="x unified",
        height=520,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )

    return fig

if not backcast_enabled:
    for outcome_config in outcomes_config:
        st.markdown(f"### {outcome_config['title']}")
        fig = plot_risk_curve(outcome_config["key"], outcome_config["title"])
        st.plotly_chart(fig, width="stretch")
        if outcome_config["key"] == "mortality":
            st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)
        st.markdown("---")


# ============================================================
# ⏪ これまでの治療で得られた利益（反実仮想）
# ============================================================
if False:  # 旧イベント推定表示は、上の検査値比較へ置き換え済み
    past_sbp_meds = selected_medications(meds_catalog, "sbp", current_sbp_keys)
    past_ldl_meds = selected_medications(meds_catalog, "ldl", current_ldl_keys)
    past_a1c_meds = selected_medications(meds_catalog, "hba1c", current_a1c_keys)
    untreated_values = reconstruct_untreated_values(
        sbp_now=sbp_now, ldl_now=ldl_now, a1c_now=a1c_now,
        sbp_meds=past_sbp_meds, ldl_meds=past_ldl_meds, a1c_meds=past_a1c_meds,
    )
    treated_average = exposure_adjusted_values(
        untreated=untreated_values,
        current={"sbp": sbp_now, "ldl": ldl_now, "a1c": a1c_now},
        treatment_years=int(backcast_treatment_years),
        medication_years=backcast_medication_years,
        sbp_meds=past_sbp_meds, ldl_meds=past_ldl_meds, a1c_meds=past_a1c_meds,
    )
    start_age = int(age) - int(backcast_treatment_years)
    backcast_curves = {}
    for outcome in OUTCOME_DISPLAY_ORDER:
        no_treatment, treated = [0.0], [0.0]
        time_points = [0]
        for elapsed in range(1, int(backcast_treatment_years) + 1):
            result = engine.cumulative_incidence(
                outcome, sex, start_age, elapsed,
                untreated_values["sbp"], treated_average["sbp"],
                untreated_values["ldl"], treated_average["ldl"],
                untreated_values["a1c"], treated_average["a1c"],
                smoking_status, cigs_per_day, years_smoked, years_since_quit,
                assume_quit_today_in_target=False,
            )
            time_points.append(elapsed)
            no_treatment.append(result["baseline"] * 100)
            treated.append(result["target"] * 100)
        backcast_curves[outcome] = {
            "time": time_points, "untreated": no_treatment, "treated": treated,
        }

    st.divider()
    st.markdown("## 5. Results: accumulated treatment benefit")
    st.caption(
        f"{start_age}y to now over {int(backcast_treatment_years)} years, compared with a no-medicine counterfactual."
        ""
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Estimated values if medicines had not been taken**")
        st.write(
            f"SBP {untreated_values['sbp']:.0f} mmHg／LDL {untreated_values['ldl']:.0f} mg/dL／"
            f"HbA1c {untreated_values['a1c']:.1f}%"
        )
    with c2:
        st.markdown("**Duration-weighted period average**")
        st.write(
            f"SBP {treated_average['sbp']:.0f} mmHg／LDL {treated_average['ldl']:.0f} mg/dL／"
            f"HbA1c {treated_average['a1c']:.1f}%"
        )

    metric_cols = st.columns(3)
    for col, outcome in zip(metric_cols, OUTCOME_DISPLAY_ORDER):
        no_tx = backcast_curves[outcome]["untreated"][-1]
        tx = backcast_curves[outcome]["treated"][-1]
        arr = max(0.0, no_tx - tx)
        nnt_text = f"NNT ≈ {100/arr:.0f}" if arr > 0.05 else "Difference is very small"
        with col:
            st.metric(
                labels[outcome], f"{arr:.1f}points avoided",
                delta=f"No treatment {no_tx:.1f}% → Treated {tx:.1f}%",
            )
            st.caption(f"About {arr:.1f} events per 100 people / {nnt_text}")

    fig_backcast = go.Figure()
    colors = {"mortality": "#6B7280", "mi": "#E45756", "stroke": "#4C78A8"}
    for outcome in OUTCOME_DISPLAY_ORDER:
        curve = backcast_curves[outcome]
        fig_backcast.add_trace(go.Scatter(
            x=curve["time"], y=curve["untreated"], mode="lines",
            name=f"{labels[outcome]}：No drug", line=dict(color=colors[outcome], dash="dash"),
        ))
        fig_backcast.add_trace(go.Scatter(
            x=curve["time"], y=curve["treated"], mode="lines",
            name=f"{labels[outcome]}: continued treatment", line=dict(color=colors[outcome]),
        ))
    fig_backcast.update_layout(
        title="No-medicine path vs continued treatment",
        xaxis_title="Years since treatment start", yaxis_title="Cumulative risk (%)",
        height=500, hovermode="x unified",
    )
    st.plotly_chart(fig_backcast, width="stretch")
    avoided = sum(
        max(0.0, backcast_curves[o]["untreated"][-1] - backcast_curves[o]["treated"][-1])
        for o in ("mi", "stroke")
    )
    backcast_summary = {
        "treatment_years": int(backcast_treatment_years),
        "start_age": start_age,
        "medications": [*current_sbp_keys, *current_ldl_keys, *current_a1c_keys],
        "mortality_avoided": max(0.0, backcast_curves["mortality"]["untreated"][-1] - backcast_curves["mortality"]["treated"][-1]),
        "mi_avoided": max(0.0, backcast_curves["mi"]["untreated"][-1] - backcast_curves["mi"]["treated"][-1]),
        "stroke_avoided": max(0.0, backcast_curves["stroke"]["untreated"][-1] - backcast_curves["stroke"]["treated"][-1]),
        "mi_stroke_avoided": avoided,
    }
    st.success(
        f"Continuing treatment may have avoided about {avoided:.1f} myocardial infarction "
        f"and stroke events combined per 100 people—benefit built through medicines and follow-up."
    )
    st.caption(
        "This is a counterfactual estimate back-calculated from catalog average effects."
        "Pre-treatment measured values, adherence, dose changes, and lifestyle shifts cannot be fully reconstructed."
    )


# ============================================================
# 📄 療養計画書PDF（共通UIヘルパー pdf_plan_ui に委譲）
#   Target欄はTargetスライダーを直接使用（設計判断A）。BMIはPCにあるので渡す。
# ============================================================
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
    bp_medications=tuple(current_sbp_keys or sbp_sel_keys),
    lipid_medications=tuple(current_ldl_keys or ldl_sel_keys),
    diabetes_medications=tuple(current_a1c_keys or a1c_sel_keys),
    lifestyle_interventions=tuple(
        _lifestyle_label(effect.key) for effect in lifestyle_result["applied"]
    ),
    risk_curves=None if backcast_enabled else cumulative_data,
    risk_horizon_years=int(st.session_state.years) if st.session_state.years else None,
    sbp_after=sbp_tgt,
    ldl_after=ldl_tgt,
    a1c_after=a1c_tgt,
    treatment_benefit=backcast_summary,
    key_prefix="pc",
    lang="en",
)
