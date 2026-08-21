from __future__ import annotations

import uuid

import plotly.graph_objects as go
import streamlit as st

from calc_engine_outcomes import OutcomesEngine
from lifestyle_interventions import DIET_EFFECTS, EXERCISE_EFFECTS
from meds_catalog import load_meds_catalog
from patient_mode.ai_explainer import is_available as ai_is_available
from patient_mode.calculator import PatientInputs, InterventionPlan, calculate_snapshot
from patient_mode.events import default_sink, make_event


OUTCOME_LABELS = {"mortality": "すべての原因による死亡", "mi": "心筋梗塞", "stroke": "脳卒中"}
REACTIONS = [
    "少し変えてみたい", "薬について先生に聞いてみたい", "生活習慣について相談したい",
    "もう少し詳しく知りたい", "今は特に変えたくない", "よく分からない",
    "先生のおすすめを聞きたい",
]
DOCTOR_QUESTIONS = [
    "私のリスクは高いですか？", "薬を使うメリットはありますか？", "薬の副作用が気になります",
    "血圧について相談したい", "コレステロールについて相談したい", "禁煙について相談したい",
    "生活習慣だけで改善できますか？", "先生ならどうするか聞きたい", "特にありません",
]


@st.cache_resource(show_spinner=False)
def engine() -> OutcomesEngine:
    return OutcomesEngine("config.yaml")


@st.cache_data(show_spinner=False)
def medication_catalog():
    return load_meds_catalog(
        "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx",
        "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx",
    )


def emit(name: str, **properties) -> None:
    st.session_state.event_sink.emit(make_event(st.session_state.patient_session_id, name, **properties))


def init_state() -> None:
    defaults = {
        "patient_step": 1,
        "patient_input_page": 0,
        "patient_session_id": str(uuid.uuid4()),
        "event_sink": default_sink(),
        "patient_interventions": [],
        "patient_reactions": [],
        "patient_questions": [],
        "patient_free_question": "",
        "patient_form": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.get("patient_session_started"):
        emit("session_start")
        st.session_state.patient_session_started = True


def go(step: int) -> None:
    st.session_state.patient_step = step
    st.rerun()


def restore_form_values(keys: list[str]) -> None:
    for key in keys:
        if key not in st.session_state and key in st.session_state.patient_form:
            st.session_state[key] = st.session_state.patient_form[key]


def save_form_values(keys: list[str]) -> None:
    for key in keys:
        if key in st.session_state:
            st.session_state.patient_form[key] = st.session_state[key]


def header() -> None:
    st.markdown(
        """
        <style>
        .stApp {background:#f6f8f7;color:#16332b}
        .block-container{max-width:760px;padding:1rem 1rem 5rem}
        h1,h2,h3{color:#163f34}
        .patient-hero{background:linear-gradient(135deg,#0f6d58,#48a176);color:white;
          padding:1.5rem;border-radius:24px;margin:.25rem 0 1rem;box-shadow:0 12px 28px #155c4930}
        .patient-hero h1{color:white;font-size:2rem;margin:0 0 .5rem}.patient-hero p{font-size:1.08rem;margin:0}
        .step-line{height:7px;background:#dce9e3;border-radius:99px;margin:.4rem 0 1.3rem;overflow:hidden}
        .step-fill{height:100%;background:#18765f}
        div[data-testid="stVerticalBlockBorderWrapper"]{background:white;border-radius:18px!important;border-color:#dce7e1!important}
        .stButton button{min-height:3.25rem;border-radius:14px;font-size:1rem;font-weight:750}
        .stButton button[kind="primary"]{background:#176f5a;border-color:#176f5a;color:white}
        div[data-baseweb="select"]>div{min-height:3.1rem}
        div[data-testid="stMetric"]{background:white;border:1px solid #dce7e1;padding:1rem;border-radius:16px}
        .plain-card{background:white;border:1px solid #dce7e1;border-radius:18px;padding:1rem 1.1rem;margin:.55rem 0}
        .risk-number{font-size:2.25rem;font-weight:850;color:#165d4c}
        @media(max-width:600px){.patient-hero h1{font-size:1.65rem}.block-container{padding:.7rem .75rem 4rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.patient_step > 1:
        pct = min(100, (st.session_state.patient_step - 1) / 7 * 100)
        st.markdown(f'<div class="step-line"><div class="step-fill" style="width:{pct}%"></div></div>', unsafe_allow_html=True)


def render_entry() -> None:
    st.markdown(
        """<div class="patient-hero"><h1>これからの心臓・脳卒中のリスクを見てみますか？</h1>
        <p>健診結果などを入力すると、生活習慣や治療で将来がどの程度変わる可能性があるか、自分で試して比べられます。</p></div>""",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown("#### このツールでできること")
        st.write("今の状態を確認し、いくつかの選択肢を自由に試して、先生に聞きたいことを整理できます。")
        st.caption("診断や治療の指示をするものではありません。結果をもとに、医師と相談するためのツールです。")
    if st.button("はじめる", type="primary", use_container_width=True):
        go(2)


def render_input() -> None:
    page = st.session_state.patient_input_page
    st.markdown("## 健診結果などを入力します")
    st.caption("分からない項目は健診結果を確認してください。必要な値がない場合、不正確な推定は表示しません。")
    if page == 0:
        page_keys = ["p_sex", "p_age", "p_height", "p_weight"]
        restore_form_values(page_keys)
        st.markdown("### 1/3 あなたについて")
        st.selectbox("性別", ["male", "female"], index=None, placeholder="選んでください", format_func=lambda x: "男性" if x == "male" else "女性", key="p_sex")
        st.number_input("年齢", min_value=20, max_value=95, value=None, step=1, placeholder="例：60", key="p_age")
        st.number_input("身長（cm）", min_value=120.0, max_value=220.0, value=None, step=1.0, placeholder="例：165", key="p_height")
        st.number_input("体重（kg）", min_value=30.0, max_value=200.0, value=None, step=1.0, placeholder="例：60", key="p_weight")
        with st.expander("わからない場合"):
            st.write("年齢・性別・身長・体重は計算に必要です。受付で確認するか、分かる範囲で健診結果をご覧ください。")
    elif page == 1:
        page_keys = ["p_sbp", "p_ldl", "p_a1c", "p_diabetes", "p_ckd", "p_egfr", "p_acr"]
        restore_form_values(page_keys)
        st.markdown("### 2/3 健診結果")
        st.number_input("上の血圧", min_value=90, max_value=250, value=None, step=1, placeholder="例：140", key="p_sbp")
        st.caption("健診結果では「収縮期血圧」と書かれていることがあります。")
        st.number_input("悪玉コレステロール（LDL）", min_value=20, max_value=300, value=None, step=1, placeholder="例：140", key="p_ldl")
        st.caption("健診結果の「LDL-C」または「LDLコレステロール」の欄です。")
        st.number_input("HbA1c（%）", min_value=4.0, max_value=15.0, value=None, step=.1, placeholder="例：5.8", key="p_a1c")
        st.checkbox("糖尿病と診断されている", key="p_diabetes")
        st.checkbox("慢性腎臓病（CKD）と診断されている", key="p_ckd")
        if st.session_state.get("p_ckd"):
            st.number_input("eGFR", min_value=5.0, max_value=120.0, value=None, step=1.0, key="p_egfr")
            st.selectbox("尿アルブミン／尿蛋白", ["A1", "A2", "A3"], index=None, placeholder="選んでください", key="p_acr")
        with st.expander("健診結果のどこを見る？"):
            st.write("血圧欄の高い方が上の血圧です。LDL-CとHbA1cは血液検査欄にあります。見つからない場合は受付でお尋ねください。")
    else:
        page_keys = ["p_smoking", "p_cigs", "p_smoke_years", "p_quit_years"]
        restore_form_values(page_keys)
        st.markdown("### 3/3 タバコについて")
        st.selectbox("現在の状況", ["never", "current", "former"], index=None, placeholder="選んでください", format_func=lambda x: {"never":"吸ったことがない", "current":"現在吸っている", "former":"以前吸っていた"}[x], key="p_smoking")
        status = st.session_state.get("p_smoking")
        if status == "current":
            st.number_input("1日に吸う本数", min_value=0, max_value=80, value=None, step=1, key="p_cigs")
            st.number_input("これまで吸った年数", min_value=0, max_value=80, value=None, step=1, key="p_smoke_years")
        elif status == "former":
            st.number_input("以前、1日に吸っていた本数", min_value=0, max_value=80, value=None, step=1, key="p_cigs")
            st.number_input("これまで吸った年数", min_value=0, max_value=80, value=None, step=1, key="p_smoke_years")
            st.number_input("禁煙してからの年数", min_value=0, max_value=80, value=None, step=1, key="p_quit_years")
    c1, c2 = st.columns(2)
    if page > 0 and c1.button("戻る", use_container_width=True):
        save_form_values(page_keys)
        st.session_state.patient_input_page -= 1
        st.rerun()
    if page < 2:
        if c2.button("次へ", type="primary", use_container_width=True):
            required = (["p_sex", "p_age", "p_height", "p_weight"] if page == 0 else ["p_sbp", "p_ldl", "p_a1c"])
            if all(st.session_state.get(k) is not None for k in required):
                save_form_values(page_keys)
                st.session_state.patient_input_page += 1
                st.rerun()
            else:
                st.error("計算に必要な項目を入力してください。")
    else:
        if c2.button("今の状態を見る", type="primary", use_container_width=True):
            status = st.session_state.get("p_smoking")
            smoking_required = status is not None and (status == "never" or all(st.session_state.get(k) is not None for k in ["p_cigs", "p_smoke_years"]))
            former_ok = status != "former" or st.session_state.get("p_quit_years") is not None
            kidney_ok = not st.session_state.get("p_ckd") or (st.session_state.get("p_egfr") is not None and st.session_state.get("p_acr") is not None)
            if smoking_required and former_ok and kidney_ok:
                save_form_values(page_keys)
                st.session_state.patient_inputs = build_inputs()
                go(3)
            else:
                st.error("計算に必要な項目を入力してください。分からない場合は受付でご確認ください。")


def build_inputs() -> PatientInputs:
    form = st.session_state.patient_form
    height = float(form["p_height"]) / 100
    return PatientInputs(
        sex=form["p_sex"], age=int(form["p_age"]),
        sbp=float(form["p_sbp"]), ldl=float(form["p_ldl"]), hba1c=float(form["p_a1c"]),
        smoking_status=form["p_smoking"], cigs_per_day=int(form.get("p_cigs") or 0),
        years_smoked=int(form.get("p_smoke_years") or 0), years_since_quit=int(form.get("p_quit_years") or 0),
        bmi=float(form["p_weight"]) / height**2,
        egfr=float(form.get("p_egfr") or 80), acr=form.get("p_acr") or "A1",
        diabetes_context=bool(form.get("p_diabetes")),
    )


def horizons(inputs: PatientInputs) -> tuple[int, ...]:
    long_horizon = max(10, min(30, 110 - inputs.age))
    return tuple(dict.fromkeys((10, long_horizon)))


def render_current() -> None:
    inputs = st.session_state.patient_inputs
    hs = horizons(inputs)
    data = calculate_snapshot(engine(), inputs, InterventionPlan(), hs)
    st.session_state.patient_current_snapshot = data
    if not st.session_state.get("risk_view_logged"):
        emit("risk_result_viewed")
        st.session_state.risk_view_logged = True
    st.markdown("## 今の状態では")
    st.write("今の検査値や生活状況が続いた場合の推定です。まず全体像を見てみましょう。")
    selected_h = st.segmented_control("表示する期間", list(hs), default=hs[0], format_func=lambda x: f"{x}年", key="p_current_horizon") or hs[0]
    for outcome in ("mi", "stroke", "mortality"):
        r = data["outcomes"][outcome][selected_h]
        st.markdown(f'<div class="plain-card"><b>{OUTCOME_LABELS[outcome]}</b><div class="risk-number">{r["point"]["baseline"]*100:.1f}%</div><span>{selected_h}年間の推定</span></div>', unsafe_allow_html=True)
    st.caption("これは集団データに基づく推定で、あなたに起こる・起こらないことを断定するものではありません。絶対リスクを表示しています。")
    if st.toggle("数字で詳しく見る", key="p_show_numbers"):
        if not st.session_state.get("details_logged"):
            emit("detailed_numbers_opened")
            st.session_state.details_logged = True
        for outcome in ("mi", "stroke", "mortality"):
            r = data["outcomes"][outcome][selected_h]
            st.write(f"**{OUTCOME_LABELS[outcome]}**：{r['point']['baseline']*100:.2f}%（95%予測幅 {r['lower']['baseline']*100:.2f}〜{r['upper']['baseline']*100:.2f}%）")
        st.caption("予測幅は推定の不確かさを表します。")
    if st.button("もし変えたら？を試す", type="primary", use_container_width=True):
        go(4)


def selected_plan() -> InterventionPlan:
    catalog = medication_catalog()
    chosen = set(st.session_state.patient_interventions)
    med_keys = st.session_state.get("p_med_keys", [])
    selected = [m for domain in catalog.values() for m in domain if m["key"] in med_keys]
    return InterventionPlan(
        target_sbp=float(st.session_state.p_target_sbp) if "bp" in chosen and st.session_state.get("p_target_sbp") else None,
        target_ldl=float(st.session_state.p_target_ldl) if "ldl" in chosen and st.session_state.get("p_target_ldl") else None,
        quit_smoking="smoking" in chosen,
        diet_keys=st.session_state.get("p_diet_keys", []) if "diet" in chosen else [],
        exercise_key=st.session_state.get("p_exercise") if "exercise" in chosen else None,
        selected_sbp_meds=[m for m in selected if m["domain"] == "sbp"],
        selected_ldl_meds=[m for m in selected if m["domain"] == "ldl"],
        selected_a1c_meds=[m for m in selected if m["domain"] == "hba1c"],
    )


def render_explore() -> None:
    inputs = st.session_state.patient_inputs
    st.markdown("## もし○○したら？")
    st.write("気になるものから自由に選び、組み合わせて比べられます。選ばないこともできます。")
    options = [("bp", "上の血圧を改善したら？"), ("ldl", "悪玉コレステロールを改善したら？"),
               ("exercise", "運動したら？"), ("diet", "食生活を変えたら？"), ("meds", "薬を使ったら？")]
    if inputs.smoking_status == "current":
        options.insert(2, ("smoking", "タバコをやめたら？"))
    previous = set(st.session_state.patient_interventions)
    if "patient_interventions_widget" not in st.session_state:
        st.session_state.patient_interventions_widget = list(previous)
    chosen = st.pills(
        "試したいこと", [key for key, _ in options],
        format_func=dict(options).get, selection_mode="multi",
        key="patient_interventions_widget",
    ) or []
    current = set(chosen)
    st.session_state.patient_interventions = list(chosen)
    for key in current - previous:
        emit("intervention_selected", category=key)
    for key in previous - current:
        emit("intervention_removed", category=key)
    if "bp" in current:
        st.slider("上の血圧をどこまで変えた場合を見る？", 90, int(inputs.sbp), min(130, int(inputs.sbp)), key="p_target_sbp")
    if "ldl" in current:
        st.slider("LDLをどこまで変えた場合を見る？", 20, int(inputs.ldl), min(100, int(inputs.ldl)), key="p_target_ldl")
    if "smoking" in current:
        with st.container(border=True):
            st.write("**タバコをやめた場合**")
            st.caption("禁煙を続けた場合として既存モデルで比較します。実際の変化には個人差があります。")
    if "exercise" in current:
        st.selectbox("試す運動", list(EXERCISE_EFFECTS), format_func=lambda k: EXERCISE_EFFECTS[k].label, key="p_exercise")
        if st.toggle("必要な行動と根拠を見る", key="p_show_exercise_detail"):
            emit_once("lifestyle_details_opened", "exercise_detail_logged", kind="exercise")
            effect = EXERCISE_EFFECTS[st.session_state.p_exercise]
            st.write(effect.definition); st.caption(effect.evidence_summary)
    if "diet" in current:
        st.multiselect("試す食生活", list(DIET_EFFECTS), format_func=lambda k: DIET_EFFECTS[k].label, key="p_diet_keys")
        if st.toggle("必要な行動と根拠を見る", key="p_show_diet_detail"):
            emit_once("lifestyle_details_opened", "diet_detail_logged", kind="diet")
            for key in st.session_state.get("p_diet_keys", []):
                effect = DIET_EFFECTS[key]
                st.write(f"**{effect.label}**：{effect.definition}"); st.caption(effect.evidence_summary)
    if "meds" in current:
        catalog = medication_catalog()
        options_meds = [m["key"] for domain in ("sbp", "ldl", "hba1c") for m in catalog[domain]]
        st.multiselect("効果を見たい薬（薬名・用量が分かる場合）", options_meds, key="p_med_keys", placeholder="選ばなくても構いません")
        if st.toggle("服用の負担・副作用を見る", key="p_show_med_detail"):
            emit_once("medication_details_opened", "med_detail_logged")
            emit_once("burden_information_opened", "burden_logged", kind="medication")
            st.write("・毎日服用します\n\n・定期的な診察や採血が必要になることがあります\n\n・副作用が起こる可能性があります\n\n・詳しくは医師と相談してください")
            by_key = {m["key"]: m for domain in catalog.values() for m in domain}
            for key in st.session_state.get("p_med_keys", []):
                med = by_key[key]
                if med.get("side_effects"):
                    st.caption(f"{key}：{med['side_effects']}")
    if current:
        plan = selected_plan()
        hs = horizons(inputs)
        data = calculate_snapshot(engine(), inputs, plan, hs)
        st.session_state.patient_plan = plan
        st.session_state.patient_comparison = data
        render_comparison(st.session_state.patient_current_snapshot, data, hs[0])
    else:
        st.info("カードを選ぶと、ここに現在との比較が表示されます。")
    if ai_is_available() and st.button("AIに聞いてみる"):
        emit("ai_help_opened")
    if st.button("見た感想へ進む", type="primary", use_container_width=True):
        go(6)


def emit_once(event: str, state_key: str, **properties) -> None:
    if not st.session_state.get(state_key):
        emit(event, **properties)
        st.session_state[state_key] = True


def render_comparison(current: dict, changed: dict, horizon: int) -> None:
    emit_once("comparison_viewed", "comparison_logged")
    st.markdown(f"### 現在 → 変えた場合（{horizon}年）")
    labels, before, after = [], [], []
    for outcome in ("mi", "stroke", "mortality"):
        labels.append(OUTCOME_LABELS[outcome])
        before.append(current["outcomes"][outcome][horizon]["point"]["baseline"] * 100)
        after.append(changed["outcomes"][outcome][horizon]["point"]["target"] * 100)
    fig = go.Figure()
    for label, b, a in zip(labels, before, after):
        fig.add_trace(go.Scatter(x=[b, a], y=[label, label], mode="lines+markers+text", text=[f"今 {b:.1f}%", f"変更後 {a:.1f}%"], textposition="top center", showlegend=False, line=dict(color="#84a99d", width=4), marker=dict(size=13, color=["#d26b5f", "#16745e"])))
    fig.update_layout(height=290, margin=dict(l=10, r=10, t=25, b=30), xaxis_title="推定リスク（%）", yaxis_title="", hovermode=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("効果を保証するものではありません。複数の変更は既存モデルの組み合わせ計算です。")
    targets = changed["targets"]
    if targets["lifestyle_skipped"]:
        st.warning("対象となる条件が確認できない生活介入は計算に反映していません。")


def render_reaction() -> None:
    st.markdown("## 見てみて、今どう思いますか？")
    st.write("いくつ選んでも構いません。まだ決めなくても大丈夫です。")
    if "patient_reactions_widget" not in st.session_state:
        st.session_state.patient_reactions_widget = list(st.session_state.patient_reactions)
    selected = st.pills("今の気持ち", REACTIONS, selection_mode="multi", key="patient_reactions_widget") or []
    if st.button("次へ", type="primary", use_container_width=True):
        st.session_state.patient_reactions = list(selected)
        for reaction in selected:
            emit("final_reaction_selected", option=REACTIONS.index(reaction))
        go(7)


def render_questions() -> None:
    st.markdown("## 今日、先生に聞いてみたいことはありますか？")
    if "patient_questions_widget" not in st.session_state:
        st.session_state.patient_questions_widget = list(st.session_state.patient_questions)
    selected = st.pills("1〜2個選んでください", DOCTOR_QUESTIONS, selection_mode="multi", key="patient_questions_widget") or []
    if len(selected) > 2:
        st.warning("先生に見せる質問は2個まで選んでください。")
    free_question = st.text_input("ほかに聞きたいこと（短く）", max_chars=120, value=st.session_state.patient_free_question, key="patient_free_question_widget")
    if st.button("先生に見せる画面へ", type="primary", use_container_width=True):
        if len(selected) > 2:
            st.stop()
        st.session_state.patient_questions = list(selected)
        st.session_state.patient_free_question = free_question
        for question in selected:
            emit("doctor_question_selected", option=DOCTOR_QUESTIONS.index(question))
        go(8)


def render_summary() -> None:
    emit_once("doctor_summary_viewed", "summary_logged")
    inputs = st.session_state.patient_inputs
    horizon = horizons(inputs)[0]
    current = st.session_state.patient_current_snapshot
    st.markdown("## 診察前サマリー")
    st.caption("患者が診察前に自分で見た内容です。治療推奨ではありません。")
    with st.container(border=True):
        st.markdown("#### 現在の推定リスク")
        cols = st.columns(3)
        for col, outcome in zip(cols, ("mi", "stroke", "mortality")):
            value = current["outcomes"][outcome][horizon]["point"]["baseline"] * 100
            col.metric(f"{horizon}年 {OUTCOME_LABELS[outcome]}", f"{value:.1f}%")
        st.markdown("#### 患者が確認した介入")
        labels = dict([("bp", "血圧改善"), ("ldl", "LDL低下"), ("smoking", "禁煙"), ("exercise", "運動"), ("diet", "食生活"), ("meds", "薬物療法")])
        selected = [labels[k] for k in st.session_state.patient_interventions]
        st.write("・" + "\n\n・".join(selected) if selected else "なし")
        st.markdown("#### 患者の現在の反応")
        st.write("・" + "\n\n・".join(st.session_state.patient_reactions) if st.session_state.patient_reactions else "選択なし")
        st.markdown("#### 今日聞きたいこと")
        questions = list(st.session_state.patient_questions)
        if st.session_state.patient_free_question.strip():
            questions.append(st.session_state.patient_free_question.strip())
        st.write("・" + "\n\n・".join(questions) if questions else "特になし")
    st.info("この画面を先生に見せてください。AIによる治療推奨は含まれていません。")
    if st.button("完了", type="primary", use_container_width=True):
        emit("session_complete")
        st.success("入力ありがとうございました。この画面を開いたままお待ちください。")


def main() -> None:
    st.set_page_config(page_title="これからの心臓・脳卒中リスク", page_icon="🌿", layout="centered")
    init_state()
    header()
    step = st.session_state.patient_step
    {1: render_entry, 2: render_input, 3: render_current, 4: render_explore,
     6: render_reaction, 7: render_questions, 8: render_summary}[step]()


if __name__ == "__main__":
    main()
