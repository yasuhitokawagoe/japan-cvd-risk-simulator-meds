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

st.set_page_config(page_title="生活習慣病ケアナビ", layout="wide", page_icon="🌿")

st.markdown("""
<style>
  .stApp { background: #f5f8f6; }
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
</style>
<div class="care-hero">
  <h1>🌿 生活習慣病ケアナビ</h1>
  <p>これまでの努力を確かめ、食事・運動・お薬を一緒に比べて、次の一歩を決めます。</p>
</div>
<div class="step-strip">
  <span class="step-pill">1 現在地</span><span class="step-pill">2 これまでの成果</span>
  <span class="step-pill">3 介入を選ぶ</span><span class="step-pill">4 将来を比べる</span>
  <span class="step-pill">5 書類を作る</span>
</div>
""", unsafe_allow_html=True)

st.caption("診療と共有意思決定の支援用です。個人の結果を保証する医療機器ではありません。")

@st.cache_resource(show_spinner=False)
def _cached_outcomes_engine(config_path: str):
    """CSV基準データを各ウィジェット再実行で読み直さない。"""
    return OutcomesEngine(config_path)


engine = _cached_outcomes_engine("config.yaml")

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
    """第1段階で薬剤名、第2段階で各薬剤の用量を選び、カタログキーを返す。"""
    grouped = _medication_options_by_name(options)
    selected_names = st.multiselect(
        f"{label}：① 薬剤を選択",
        options=list(grouped),
        key=f"{key_prefix}_names",
    )
    selected_keys = []
    for name in selected_names:
        dose_options = grouped[name]
        selected_keys.append(st.selectbox(
            f"{name}：② 用量を選択",
            options=dose_options,
            format_func=lambda key: key[len(name):].strip() or key,
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
    st.subheader("🩺 今日の診療")
    care_path = st.segmented_control(
        "診療の目的",
        ["initial", "adjust", "continue"],
        default="initial",
        format_func=lambda value: {
            "initial": "治療を始める",
            "adjust": "治療を見直す",
            "continue": "現在の治療を続ける",
        }[value],
        key="care_path",
    ) or "initial"
    backcast_enabled = care_path == "continue"
    if backcast_enabled:
        st.caption("現在のお薬を入力すると、飲まなかった場合と比べてこれまでの成果を表示します。")
    elif care_path == "adjust":
        st.caption("現在のお薬と変更後を比べます。")
    else:
        st.caption("食事・運動・お薬の介入案を比べます。")

    st.divider()
    st.subheader("② 現在の状態" if backcast_enabled else "患者プロフィール")
    sex = st.selectbox("性別", ["male", "female"], format_func=lambda x: "男性" if x == "male" else "女性")
    age = st.number_input("年齢（歳）", 20, 95, 60, step=1)

    st.subheader("現在の検査値" if backcast_enabled else "リスク因子（現在 → 目標）")
    sbp_now = st.slider("収縮期血圧 現在 (mmHg)", 90, 200, 150)
    ldl_now = st.slider("LDL 現在 (mg/dL)", 50, 250, 160)
    a1c_now = st.slider("HbA1c 現在 (%)", 5.0, 12.0, 8.0, step=0.1)
    if backcast_enabled:
        sbp_tgt_manual, ldl_tgt_manual, a1c_tgt_manual = sbp_now, ldl_now, a1c_now
        smoking_status, cigs_per_day = "never", 0
        years_smoked, years_since_quit, quit_today = 0, 0, False
    else:
        sbp_tgt_manual = st.slider("収縮期血圧 目標 (mmHg)", 90, 160, 130)
        ldl_tgt_manual = st.slider("LDL 目標 (mg/dL)", 50, 160, 100)
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

    st.subheader("体格")
    height_cm = st.number_input("身長 (cm)", min_value=120.0, max_value=220.0, value=165.0, step=0.1)
    weight_kg = st.number_input("体重 (kg)", min_value=30.0, max_value=200.0, value=65.0, step=0.1)
    bmi_now = weight_kg / (height_cm / 100.0) ** 2
    bmi_target = 22.0
    if backcast_enabled:
        st.caption(f"現在BMI: {bmi_now:.1f}")
    else:
        st.caption(f"現在BMI: {bmi_now:.1f}／目標BMI: 22.0（目標体重 {22 * (height_cm / 100.0) ** 2:.1f} kg）")

    dbp_now = st.number_input("拡張期血圧 現在 (mmHg)", min_value=40, max_value=130, value=90, step=1)
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.metric("現在BMI", f"{bmi_now:.1f}")
    with col_b2:
        if not backcast_enabled:
            st.metric("目標BMI", "22.0")

    if backcast_enabled:
        egfr_now = egfr_target = 80.0
        acr_now = acr_target = "A1"
        which = "10-year"
    else:
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
    st.subheader("🥗 介入1：食事と運動")
    st.caption("お薬と同じように、実行する介入として選びます。")
    diet_intervention_keys = st.multiselect(
        "食事介入",
        list(DIET_EFFECTS),
        format_func=lambda key: f"{DIET_EFFECTS[key].label}｜{DIET_EFFECTS[key].definition}",
        key="unified_diet_interventions",
    )
    exercise_intervention_key = st.selectbox(
        "運動介入",
        [None, *EXERCISE_EFFECTS],
        format_func=lambda key: "選択しない" if key is None else (
            f"{EXERCISE_EFFECTS[key].label}｜{EXERCISE_EFFECTS[key].definition}"
        ),
        key="unified_exercise_intervention",
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
            st.link_button("根拠文献", effect.source_url, key=f"lifestyle_source_{effect.key}")

    st.divider()
    st.subheader("💊 介入2：お薬" if not backcast_enabled else "③ 現在飲んでいるお薬")
    st.caption("食事・運動に加えて、継続・追加・変更するお薬を選びます。")

    # 1. 薬剤オプションを先に定義
    sbp_options = [m["key"] for m in meds_catalog["sbp"]]
    ldl_options = [m["key"] for m in meds_catalog["ldl"]]
    a1c_options = [m["key"] for m in meds_catalog["hba1c"]]

    # 2. 薬剤を使うかどうかのチェック
    use_meds = True if backcast_enabled else st.checkbox(
        "薬剤を選んで目標値を自動計算する", value=True
    )

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
        if backcast_enabled:
            mode = "backcast"
            st.info("反実仮想では、現在服用中の薬を入力します。")
            current_sbp_keys = render_two_stage_med_picker(
                "降圧薬（現在）", sbp_options, "backcast_current_sbp"
            )
            current_ldl_keys = render_two_stage_med_picker(
                "脂質薬（現在）", ldl_options, "backcast_current_ldl"
            )
            current_a1c_keys = render_two_stage_med_picker(
                "糖尿病薬（現在）", a1c_options, "backcast_current_a1c"
            )
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
            sbp_sel_keys = render_two_stage_med_picker(
                "降圧薬（SBPに反映）", sbp_options, "add_sbp"
            )
            selected_sbp_meds = [m for m in meds_catalog["sbp"] if m["key"] in sbp_sel_keys]

            ldl_sel_keys = render_two_stage_med_picker(
                "脂質薬（LDLに反映）", ldl_options, "add_ldl"
            )
            selected_ldl_meds = [m for m in meds_catalog["ldl"] if m["key"] in ldl_sel_keys]

            a1c_sel_keys = render_two_stage_med_picker(
                "糖尿病薬（HbA1cに反映）", a1c_options, "add_a1c"
            )
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
            # 薬増減UI：現在の治療をベースラインに、各薬をワンタップで 中止/減量/増量/切替
            st.markdown("**現在服用中の薬**")
            current_sbp_keys = render_two_stage_med_picker(
                "降圧薬（現在）", sbp_options, "adjust_current_sbp"
            )
            current_ldl_keys = render_two_stage_med_picker(
                "脂質薬（現在）", ldl_options, "adjust_current_ldl"
            )
            current_a1c_keys = render_two_stage_med_picker(
                "糖尿病薬（現在）", a1c_options, "adjust_current_a1c"
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
                add_sbp_keys = render_two_stage_med_picker(
                    "降圧薬（追加）",
                    [o for o in sbp_options
                     if o not in current_sbp_keys and o not in adjusted_sbp_keys],
                    "pc_add_sbp",
                )
                add_ldl_keys = render_two_stage_med_picker(
                    "脂質薬（追加）",
                    [o for o in ldl_options
                     if o not in current_ldl_keys and o not in adjusted_ldl_keys],
                    "pc_add_ldl",
                )
                add_a1c_keys = render_two_stage_med_picker(
                    "糖尿病薬（追加）",
                    [o for o in a1c_options
                     if o not in current_a1c_keys and o not in adjusted_a1c_keys],
                    "pc_add_a1c",
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
            if meds_summary.get("mode") == "backcast":
                st.metric("年間薬剤費（概算）", f"{meds_summary['annual_cost_yen']:,} 円/年")
                st.caption("検査値の反実仮想結果はメイン画面に表示します。")
            elif meds_summary.get("mode") == "adjust":
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

    st.divider()
    st.subheader("④ 治療期間を入力" if backcast_enabled else "⏪ これまでの治療で得られた利益")
    backcast_treatment_years = 1
    backcast_medication_years = {}
    backcast_keys = [*current_sbp_keys, *current_ldl_keys, *current_a1c_keys]
    if backcast_enabled:
        if not backcast_keys:
            st.info("上で現在服用中の薬を入力すると計算できます。")
        else:
            backcast_treatment_years = st.number_input(
                "治療を始めてからの年数",
                min_value=1,
                max_value=max(1, int(age) - 20),
                value=min(10, max(1, int(age) - 20)),
                step=1,
                key="backcast_treatment_years",
            )
            for med_key in backcast_keys:
                backcast_medication_years[med_key] = float(backcast_treatment_years)

    st.divider()
    calculation_button_slot = st.empty()

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

with st.sidebar:
    if lifestyle_result["applied"]:
        with st.container(border=True):
            st.markdown("**🎯 選択した介入による予測値**")
            preview_cols = st.columns(3)
            preview_cols[0].metric("血圧", f"{sbp_tgt:.0f}")
            preview_cols[1].metric("LDL", f"{ldl_tgt:.0f}")
            preview_cols[2].metric("HbA1c", f"{a1c_tgt:.1f}")
    for effect in lifestyle_result["skipped"]:
        st.warning(f"{effect.label}は{effect.population}の根拠のため、現在の入力には効果量を適用していません。")

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
# 現在のパラメータを文字列化してハッシュ化（変更検知用）
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

st.markdown("## 📍 今日の現在地と介入プラン")
status_cols = st.columns(4)
status_cols[0].metric("血圧", f"{sbp_now:.0f} mmHg", delta=f"予測 {sbp_tgt:.0f}")
status_cols[1].metric("LDL", f"{ldl_now:.0f} mg/dL", delta=f"予測 {ldl_tgt:.0f}")
status_cols[2].metric("HbA1c", f"{a1c_now:.1f}%", delta=f"予測 {a1c_tgt:.1f}")
status_cols[3].metric("BMI", f"{bmi_now:.1f}", delta=f"目標 {bmi_target:.1f}")
selected_intervention_labels = [effect.label for effect in lifestyle_result["applied"]]
selected_medication_labels = list(current_sbp_keys or sbp_sel_keys) + list(current_ldl_keys or ldl_sel_keys) + list(current_a1c_keys or a1c_sel_keys)
with st.container(border=True):
    st.markdown("**選択中の介入**")
    st.write("🥗 食事・運動：" + ("、".join(selected_intervention_labels) if selected_intervention_labels else "まだ選択されていません"))
    st.write("💊 お薬：" + ("、".join(selected_medication_labels) if selected_medication_labels else "なし／まだ選択されていません"))

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
        "🔄 リスク計算を実行",
        type="primary",
        use_container_width=True,
        key="risk_calculate_sidebar",
    )
    main_calculate_clicked = st.button(
        "🔄 リスク計算を実行",
        type="primary",
        use_container_width=True,
        key="risk_calculate_main",
    )
    manual_button_clicked = sidebar_calculate_clicked or main_calculate_clicked
if not backcast_enabled and manual_button_clicked:
    with st.spinner("リスク計算中..."):
        st.session_state.cumulative_data = calculate_cumulative_risk_curves(years_for_curve)
        st.session_state.calculated = True
        st.session_state.years = years_for_curve
        st.session_state.params_hash = params_hash

# 反実仮想も薬剤名・用量の選択中は計算せず、専用ボタンで確定する。
backcast_ready = False
if backcast_enabled and backcast_keys:
    sidebar_backcast_clicked = calculation_button_slot.button(
        "🔄 反実仮想を計算",
        type="primary",
        use_container_width=True,
        key="backcast_calculate_sidebar",
    )
    main_backcast_clicked = st.button(
        "🔄 反実仮想を計算",
        type="primary",
        use_container_width=True,
        key="backcast_calculate_main",
    )
    backcast_button_clicked = sidebar_backcast_clicked or main_backcast_clicked
    if backcast_button_clicked:
        st.session_state.backcast_params_hash = params_hash
    backcast_ready = st.session_state.backcast_params_hash == params_hash
    if not backcast_ready:
        st.info("👆 薬剤と用量を確認し「反実仮想を計算」を押してください")

if not backcast_enabled and not st.session_state.calculated:
    st.info("👆 上記のパラメータを設定して「リスク計算を実行」を押してください")
    st.stop()

cumulative_data = st.session_state.cumulative_data or {}
labels = {"mi": "心筋梗塞", "stroke": "脳卒中", "mortality": "全死亡"}

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
    st.markdown("## ⑤ 服薬しなかった場合との推定比較")
    st.caption(f"現在までの{int(backcast_treatment_years)}年間について、薬剤カタログの平均効果から逆算した推定です。")
    result_cols = st.columns(3)
    for col, label, untreated, current, unit in (
        (result_cols[0], "収縮期血圧", untreated_values["sbp"], sbp_now, "mmHg"),
        (result_cols[1], "LDL", untreated_values["ldl"], ldl_now, "mg/dL"),
        (result_cols[2], "HbA1c", untreated_values["a1c"], a1c_now, "%"),
    ):
        with col:
            st.metric(label, f"現在 {current:.1f} {unit}", delta=f"薬なし推定 {untreated:.1f} {unit}")
    st.markdown(f"### この{int(backcast_treatment_years)}年間に回避できた可能性があるイベント")
    event_cols = st.columns(3)
    for col, outcome in zip(event_cols, OUTCOME_DISPLAY_ORDER):
        effect = event_effects[outcome]
        with col:
            st.metric(
                labels[outcome],
                f"{effect['avoided']:.1f}ポイント回避",
                delta=f"薬なし {effect['untreated']:.1f}% → 服薬あり {effect['treated']:.1f}%",
            )
            if effect["avoided"] > 0.05:
                st.caption(f"100人あたり約{effect['avoided']:.1f}件／NNT相当 約{100/effect['avoided']:.0f}人")
            else:
                st.caption("推定差はごく小さい")
    st.markdown(f"### これまでの利益と今後{future_years}年間の見通し")
    st.caption("横軸の0年が現在です。左側がこれまで、右側が今後の推定です。")
    colors = {"mortality": "#6B7280", "mi": "#E45756", "stroke": "#4C78A8"}
    for outcome in OUTCOME_DISPLAY_ORDER:
        curve = event_curves[outcome]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=curve["time"], y=curve["untreated"], mode="lines",
            name="薬を飲まなかった場合", line=dict(color=colors[outcome], dash="dash", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=curve["time"], y=curve["treated"], mode="lines",
            name="服薬を続ける場合", line=dict(color=colors[outcome], width=3),
        ))
        fig.add_vline(x=0, line_dash="dot", line_color="#111827", annotation_text="現在")
        fig.update_layout(
            title=labels[outcome], xaxis_title="現在を0とした年数", yaxis_title="累積イベントリスク（%）",
            height=420, hovermode="x unified", legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig, width="stretch")
    st.success("現在の数値は、服薬を続けて得られている成果です。自己判断で中止せず、今後の方針を主治医と相談しましょう。")
elif backcast_enabled and not backcast_keys:
    st.info("現在服用中の薬を選ぶと、服薬しなかった場合の推定値を表示します。")

# ---- サマリー ----
if not backcast_enabled:
    st.markdown("## 📊 リスク比較サマリー")
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
                st.metric(f"{horizon}年 リスク減少（ARR）", f"{arr:.1f}%", delta=f"現在 {r['baseline']*100:.1f}% → 目標 {r['target']*100:.1f}%")
            if outcome == "mortality":
                st.caption(MORTALITY_ALL_CAUSE_DEATH_CAPTION)

st.divider()

st.markdown("## 💴 費用と副作用（薬剤選択時）")
if use_meds and meds_summary is not None:
    if meds_summary.get("mode") == "backcast":
        annual_cost = int(meds_summary["annual_cost_yen"])
        st.metric("年間薬剤費（現在）", f"{annual_cost:,} 円/年")
        st.metric(
            f"治療{int(backcast_treatment_years)}年間に支払った薬剤費の概算",
            f"{annual_cost * int(backcast_treatment_years):,} 円",
        )
        st.caption("現在の薬価を治療期間に単純乗算した概算です。過去の薬価・処方変更・自己負担割合は反映していません。")
    elif meds_summary.get("mode") == "adjust":
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
if not backcast_enabled:
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
    st.markdown("## ⑤ 計算結果：これまでの治療で積み上げた成果")
    st.caption(
        f"{start_age}歳から現在までの{int(backcast_treatment_years)}年間を、"
        "薬を飲まなかった反実仮想と比較します。"
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**薬を飲まなかった場合の推定値**")
        st.write(
            f"SBP {untreated_values['sbp']:.0f} mmHg／LDL {untreated_values['ldl']:.0f} mg/dL／"
            f"HbA1c {untreated_values['a1c']:.1f}%"
        )
    with c2:
        st.markdown("**服薬年数を考慮した期間平均**")
        st.write(
            f"SBP {treated_average['sbp']:.0f} mmHg／LDL {treated_average['ldl']:.0f} mg/dL／"
            f"HbA1c {treated_average['a1c']:.1f}%"
        )

    metric_cols = st.columns(3)
    for col, outcome in zip(metric_cols, OUTCOME_DISPLAY_ORDER):
        no_tx = backcast_curves[outcome]["untreated"][-1]
        tx = backcast_curves[outcome]["treated"][-1]
        arr = max(0.0, no_tx - tx)
        nnt_text = f"NNT相当 約{100/arr:.0f}人" if arr > 0.05 else "差はごく小さい"
        with col:
            st.metric(
                labels[outcome], f"{arr:.1f}ポイント回避",
                delta=f"無治療 {no_tx:.1f}% → 治療あり {tx:.1f}%",
            )
            st.caption(f"100人あたり約{arr:.1f}件／{nnt_text}")

    fig_backcast = go.Figure()
    colors = {"mortality": "#6B7280", "mi": "#E45756", "stroke": "#4C78A8"}
    for outcome in OUTCOME_DISPLAY_ORDER:
        curve = backcast_curves[outcome]
        fig_backcast.add_trace(go.Scatter(
            x=curve["time"], y=curve["untreated"], mode="lines",
            name=f"{labels[outcome]}：薬なし", line=dict(color=colors[outcome], dash="dash"),
        ))
        fig_backcast.add_trace(go.Scatter(
            x=curve["time"], y=curve["treated"], mode="lines",
            name=f"{labels[outcome]}：治療継続", line=dict(color=colors[outcome]),
        ))
    fig_backcast.update_layout(
        title="薬を飲まなかった経路 vs 治療を続けた経路",
        xaxis_title="治療開始からの年数", yaxis_title="累積リスク（%）",
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
        f"治療を続けたことで、心筋梗塞・脳卒中を合わせて100人あたり約{avoided:.1f}件を"
        f"回避してきた可能性があります。これまでの服薬と通院で積み上げた成果です。"
    )
    st.caption(
        "これは薬剤カタログの平均効果から逆算した反実仮想推定です。"
        "治療開始前の実測値、服薬遵守、用量変更、生活習慣の変化は完全には再現できません。"
    )


# ============================================================
# 📄 療養計画書PDF（共通UIヘルパー pdf_plan_ui に委譲）
#   目標欄は目標スライダーを直接使用（設計判断A）。BMIはPCにあるので渡す。
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
    lifestyle_interventions=tuple(effect.label for effect in lifestyle_result["applied"]),
    risk_curves=None if backcast_enabled else cumulative_data,
    risk_horizon_years=int(st.session_state.years) if st.session_state.years else None,
    sbp_after=sbp_tgt,
    ldl_after=ldl_tgt,
    a1c_after=a1c_tgt,
    treatment_benefit=backcast_summary,
    key_prefix="pc",
)
