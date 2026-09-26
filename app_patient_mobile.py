"""Separate patient-facing mobile entrypoint; the PC application is unchanged."""
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from calc_engine_outcomes import OutcomesEngine
from lifestyle_interventions import DIET_EFFECTS, DIET_PATTERN_KEYS, EXERCISE_EFFECTS
from meds_catalog import load_meds_catalog
from patient_mobile_model import (
    BP_CATALOG, LIPID_CATALOG, OUTCOME_LABELS, PatientInputs, calculate_mobile_scenarios,
)
from risk_display import format_hr, hazard_ratio


st.set_page_config(page_title="これからの健康｜患者さん向け", layout="centered")
st.markdown("""<style>
.stMainBlockContainer {max-width:650px;padding:1.7rem 1.1rem 3rem;}
[data-testid="stHeader"] {display:none;}
h1 {font-size:1.8rem!important;line-height:1.4!important;}
h2 {font-size:1.35rem!important;} h3 {font-size:1.1rem!important;}
.stButton button {min-height:48px;border-radius:12px;}
[data-baseweb="select"]>div {min-height:46px;}
[data-testid="stMetricValue"] {font-size:2rem;}
.mobile-eyebrow {color:#18766b;font-size:.85rem;font-weight:600;letter-spacing:.08em;}
.risk-card {border:1px solid #dde5e4;border-radius:14px;padding:16px;margin:10px 0;}
.risk-card strong {display:block;font-size:1.65rem;color:#136a60;margin-top:3px;}
@media(max-width:480px){.stMainBlockContainer{padding-top:1rem;}h1{font-size:1.55rem!important;}}
</style>""", unsafe_allow_html=True)

ROOT = Path(__file__).resolve().parent
DOMAIN_LABELS = {"sbp": "血圧の薬", "ldl": "コレステロールの薬", "hba1c": "血糖の薬"}
EXERCISE_LABELS = {
    None: "今は追加しない", "aerobic_moderate": "速歩などを続ける",
    "combined": "速歩など＋筋力トレーニング", "hiit": "強い運動と休息を交互に行う（要相談）",
}
COMPONENT_LABELS = {"salt": "塩分を控える", "carb": "糖質の量を見直す", "fat": "脂身・バターなどを控える"}


@st.cache_resource
def resources():
    return (OutcomesEngine(str(ROOT / "config.yaml")),
            load_meds_catalog(str(ROOT / BP_CATALOG), str(ROOT / LIPID_CATALOG)))


def data():
    return st.session_state.setdefault("pm_data", {})


def remember(name):
    data()[name] = st.session_state[f"pmw_{name}"]
    if name.startswith("current_") and name != "current_confirmed":
        data()["current_confirmed"] = False
        st.session_state["pmw_current_confirmed"] = False


def field(kind, name, label, default=None, **kwargs):
    """Durable values survive Streamlit's cleanup of widgets on other steps."""
    key = f"pmw_{name}"
    if key not in st.session_state:
        st.session_state[key] = data().get(name, default)
    value = getattr(st, kind)(label, key=key, on_change=remember, args=(name,), **kwargs)
    data()[name] = value
    return value


def navigate(step):
    st.session_state["pm_step"] = step


def reset():
    for key in list(st.session_state):
        if key.startswith("pm_") or key.startswith("pmw_"):
            del st.session_state[key]


def medication_picker(prefix, catalog):
    st.caption("お薬手帳を見ながら選んでください。名前が見つからない場合や量が分からない場合は、推測しなくて大丈夫です。")
    st.caption("量は1日量・投与間隔を確認してください。錠剤1錠の規格と1日量は異なる場合があります。")
    selected, missing = [], []
    for domain, label in DOMAIN_LABELS.items():
        items = catalog[domain]
        names = list(dict.fromkeys(m["drug_name"] for m in items))
        chosen = field("multiselect", f"{prefix}_{domain}", label, default=[], options=names,
                       placeholder="薬の名前で検索・選択")
        for name in chosen:
            options = [m for m in items if m["drug_name"] == name]
            lookup = {m["key"]: m for m in options}
            dose = field("selectbox", f"{prefix}_dose_{domain}_{name}", f"{name} の量",
                         options=list(lookup), index=None, placeholder="量・投与間隔を選ぶ",
                         format_func=lambda key, lookup=lookup: lookup[key]["dose_label"])
            if dose is None:
                missing.append(name)
            else:
                selected.append(lookup[dose])
    return selected, missing


def patient_from_data():
    values = data()
    required = ("age", "sex", "sbp", "ldl", "a1c", "smoking")
    if any(values.get(k) is None for k in required):
        raise ValueError("年齢・性別・血圧・LDL・HbA1c・喫煙状況を入力してください。")
    height, weight = values.get("height"), values.get("weight")
    if (height is None) != (weight is None):
        raise ValueError("身長と体重は両方入力するか、両方を空欄にしてください。")
    smoking = values["smoking"]
    smoke_values = {}
    if smoking != "never":
        for key in ("cigs_per_day", "years_smoked") + (("years_since_quit",) if smoking == "former" else ()):
            if values.get(key) is None:
                raise ValueError("喫煙の本数・年数を入力してください。")
            smoke_values[key] = values[key]
    return PatientInputs(
        age=values["age"], sex=values["sex"], sbp=values["sbp"], ldl=values["ldl"], a1c=values["a1c"],
        bmi=weight / (height / 100) ** 2 if height and weight else None,
        egfr=values.get("egfr"), acr=values.get("acr"), smoking_status=smoking, **smoke_values,
    )


def welcome():
    st.markdown('<p class="mobile-eyebrow">これからの健康 · スマホ試作版</p>', unsafe_allow_html=True)
    st.title("いま、生活習慣病の薬を使っていますか？")
    st.write("血圧・コレステロール・糖尿病の薬。注射も含みます。")
    st.caption("この試算は、2型糖尿病のある20〜95歳の方向けです。")
    eligible = st.checkbox("2型糖尿病と診断されています", key="pm_eligible")
    for mode, label in (("without", "使っていない"), ("with", "使っている")):
        if st.button(label, key=f"entry_{mode}", type="primary" if mode == "without" else "secondary",
                     use_container_width=True, disabled=not eligible):
            st.session_state["pm_mode"] = mode
            navigate("medications" if mode == "with" else "measurements")
            st.rerun()
    st.info("食事・運動や、今の治療を続ける意味を考えるための参考試算です。薬の開始・変更・中止は、主治医と相談してください。")
    st.caption("氏名・連絡先は不要です。入力内容をアプリのデータベースやURLには保存しません。")


def medications():
    st.header("今使っている薬")
    st.write("量まで分かると、今の治療を続ける場合の参考比較ができます。")
    _, catalog = resources()
    meds, missing = medication_picker("current", catalog)
    unknown = field("checkbox", "current_unknown", "名前・量が分からない薬や、一覧にない薬がある", default=False)
    complete = field("checkbox", "current_confirmed", "血圧・コレステロール・血糖の薬を、量まで全部確認した", default=False)
    if unknown or missing:
        st.info("薬の比較は保留にして、今の治療を続けながら食事・運動を変えた場合の試算に進めます。")
    data()["current_meds"] = meds
    data()["medications_complete"] = bool(complete and meds and not unknown and not missing)
    if st.button("検査値の入力へ", key="meds_next", type="primary", use_container_width=True):
        if not meds and not missing and not unknown:
            st.error("薬を選ぶか、「名前・量が分からない薬や、一覧にない薬がある」にチェックしてください。")
        elif not data()["medications_complete"] and not unknown and not missing:
            st.error("薬を全部確認したか、分からない薬があるかを確認してください。")
        else:
            navigate("measurements")
            st.rerun()


def measurements(mode):
    st.header("いまの体の状態")
    st.write("薬を使っている今の検査値を入力してください。" if mode == "with" else "最近の健診・検査結果を入力してください。")
    st.caption("範囲外の値は近い数字に置き換えず、主治医にご相談ください。空欄のままでは計算しません。")
    field("number_input", "age", "年齢", min_value=20, max_value=95, value=None, step=1, placeholder="歳")
    field("selectbox", "sex", "性別（計算に用いる項目）", options=["male", "female"], index=None,
          format_func=lambda x: {"male": "男性", "female": "女性"}[x], placeholder="選んでください")
    field("number_input", "sbp", "上の血圧（mmHg）", min_value=90.0, max_value=200.0, value=None, step=1.0, format="%.0f")
    field("number_input", "ldl", "LDLコレステロール（mg/dL）", min_value=50.0, max_value=250.0, value=None, step=1.0, format="%.0f")
    field("number_input", "a1c", "HbA1c（%）", min_value=5.0, max_value=12.0, value=None, step=0.1, format="%.1f")
    smoking = field("selectbox", "smoking", "たばこ", options=["never", "current", "former"], index=None,
                    format_func=lambda x: {"never": "吸ったことがない", "current": "今も吸っている", "former": "以前吸っていた"}[x],
                    placeholder="選んでください")
    if smoking in ("current", "former"):
        field("number_input", "cigs_per_day", "吸っていた時の1日本数" if smoking == "former" else "1日の本数", min_value=0, max_value=40, value=None, step=1)
        field("number_input", "years_smoked", "吸っていた年数", min_value=0, max_value=80, value=None, step=1)
        if smoking == "former":
            field("number_input", "years_since_quit", "やめてからの年数", min_value=0, max_value=80, value=None, step=1)
    with st.expander("身長・体重、腎臓の検査（分かる場合）"):
        field("number_input", "height", "身長（cm）", min_value=100.0, max_value=220.0, value=None, step=0.1)
        field("number_input", "weight", "体重（kg）", min_value=20.0, max_value=200.0, value=None, step=0.1)
        field("number_input", "egfr", "eGFR", min_value=5.0, max_value=120.0, value=None, step=1.0)
        field("selectbox", "acr", "尿アルブミン／クレアチニン比（mg/gCr）", options=["A1", "A2", "A3"], index=None,
              format_func=lambda x: {"A1": "30未満（A1）", "A2": "30〜299（A2）", "A3": "300以上（A3）"}[x],
              placeholder="不明の場合は空欄")
        st.caption("尿蛋白とは別の検査です。分からない場合は空欄にしてください。")
    if st.button("食事・運動を選ぶ", key="measurements_next", type="primary", use_container_width=True):
        try:
            patient_from_data()
        except ValueError as exc:
            st.error(str(exc))
        else:
            navigate("lifestyle")
            st.rerun()
    if mode == "with":
        st.button("薬の入力に戻る", key="measurements_back", on_click=navigate, args=("medications",), use_container_width=True)


def lifestyle(mode):
    st.header("できそうなことを選ぶ")
    if mode == "with":
        st.caption("今の薬を続ける前提です。生活改善は何も選ばずに進むこともできます。")
    st.caption("新たに取り組む内容を選んでください。すでに続けている内容を重ねると、効果を大きく見積もる可能性があります。")
    labels = {None: "今は追加しない", "components": "塩分・糖質・脂身を個別に見直す",
              **{k: DIET_EFFECTS[k].label for k in DIET_PATTERN_KEYS}}
    pattern = field("selectbox", "diet_pattern", "食事", options=list(labels), format_func=labels.get,
                    placeholder="今は追加しない")
    diet_keys = []
    if pattern == "components":
        diet_keys = field("multiselect", "diet_components", "見直す内容", default=[], options=list(COMPONENT_LABELS),
                          format_func=COMPONENT_LABELS.get, placeholder="複数選べます")
    elif pattern:
        diet_keys = [pattern]
    for key in diet_keys:
        st.caption(DIET_EFFECTS[key].definition)
    data()["diet_keys"] = diet_keys
    exercise = field("selectbox", "exercise", "運動", options=list(EXERCISE_LABELS), format_func=EXERCISE_LABELS.get,
                     placeholder="今は追加しない")
    if exercise:
        st.caption(EXERCISE_EFFECTS[exercise].definition)
    st.caption("食事・運動の変更は体調や治療内容に合わせて相談してください。低血糖などのリスクはこの試算には含みません。")
    proposed, missing = [], []
    if mode == "without":
        with st.expander("医師から提案された薬も比較する（任意）"):
            enable = field("checkbox", "proposed_enabled", "提案された薬を試算に含める", default=False)
            if enable:
                st.info("薬をおすすめする機能ではありません。開始前に、主治医と内容・量を確認してください。")
                _, catalog = resources()
                proposed, missing = medication_picker("proposed", catalog)
    data()["proposed_meds"] = proposed
    if st.button("結果を見る", key="lifestyle_next", type="primary", use_container_width=True):
        if missing or (mode == "without" and data().get("proposed_enabled") and not proposed):
            st.error("提案された薬の名前・量を確認するか、薬を試算に含めるチェックを外してください。")
        else:
            navigate("results")
            st.rerun()
    st.button("検査値に戻る", key="lifestyle_back", on_click=navigate, args=("measurements",), use_container_width=True)


def draw_curve(curve, comparison, outcome):
    fig = go.Figure()
    for side, label, color, shade in (
        ("baseline", comparison["before_label"], "#7a8793", "rgba(122,135,147,.13)"),
        ("target", comparison["after_label"], "#147d70", "rgba(20,125,112,.16)"),
    ):
        if outcome != "dementia":
            fig.add_trace(go.Scatter(x=curve["time"], y=curve[f"{side}_ci_upper"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=curve["time"], y=curve[f"{side}_ci_lower"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor=shade, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=curve["time"], y=curve[f"{side}_cumulative"], name=label, mode="lines",
                                line=dict(color=color, width=3, dash="dot" if outcome == "dementia" else "solid"),
                                hovertemplate="%{x:.0f}年後：%{y:.1f}%<extra>%{fullData.name}</extra>"))
    fig.update_layout(height=340, margin=dict(l=8, r=8, t=15, b=8),
                      legend=dict(orientation="h", y=-0.25, x=0, font=dict(size=11)),
                      xaxis=dict(title="今からの年数", fixedrange=True, dtick=5),
                      yaxis=dict(title="推定される割合（%）", rangemode="tozero", fixedrange=True),
                      font=dict(size=12), paper_bgcolor="white", plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})


def results(mode):
    st.header("これからの見通し")
    patient = patient_from_data()
    years = field("selectbox", "years", "何年後まで見る？", default=10, options=[5, 10, 20], format_func=lambda x: f"{x}年後")
    values = data()
    kwargs = dict(mode=mode, current_medications=values.get("current_meds", []) if mode == "with" else [],
                  medications_complete=values.get("medications_complete", False),
                  proposed_medications=values.get("proposed_meds", []) if mode == "without" else [],
                  diet_keys=values.get("diet_keys", []), exercise_key=values.get("exercise"), years=years)
    signature = (patient, repr(kwargs))
    if st.session_state.get("pm_signature") != signature:
        engine, _ = resources()
        st.session_state["pm_result"] = calculate_mobile_scenarios(patient, engine=engine, **kwargs)
        st.session_state["pm_signature"] = signature
    result = st.session_state["pm_result"]
    if result["medication"] is not None:
        choice = field("radio", "comparison", "比べる内容", default="lifestyle" if result["has_changes"] else "medication",
                       options=["medication", "lifestyle"],
                       format_func=lambda x: {"medication": "今の薬を続ける意味", "lifestyle": "生活改善を加えた場合"}[x])
    else:
        choice = "lifestyle"
    comparison = result[choice]
    if choice == "medication":
        st.info("「薬がなかった場合」は、今の検査値と薬の平均効果から逆算した参考値です。実際に薬をやめた後の予測ではありません。自己判断で中止しないでください。")
    elif not result["has_changes"]:
        st.info("生活改善をまだ選んでいないため、比較する2つの値は同じです。")
    for warning in result["warnings"]:
        st.caption(warning)
    outcomes = list(comparison["curves"])
    if data().get("outcome", "mi") not in outcomes:
        data()["outcome"] = "mi"
        st.session_state.pop("pmw_outcome", None)
    outcome = field("selectbox", "outcome", "確認したい病気", default="mi", options=outcomes, format_func=OUTCOME_LABELS.get)
    curve = comparison["curves"][outcome]
    baseline, target = curve["baseline_cumulative"][-1], curve["target_cumulative"][-1]
    st.caption(f"今から{result['years']}年間の参考推定。入力時点から選んだ状態を続けると仮定しています。")
    if result["years"] != years:
        st.caption("計算の上限年齢（110歳）までの期間に調整しています。")
    hr_mode = field("checkbox", "hr", "比率で見る（HR相当・詳しい方向け）", default=False)
    if hr_mode:
        st.metric("比較前を1としたHR相当", format_hr(hazard_ratio(target, baseline)))
        st.caption("累積リスクから求めた累積ハザードの比です。論文の瞬間的なHRや、個人の確定的な予測ではありません。")
    else:
        for label, value in ((comparison["before_label"], baseline), (comparison["after_label"], target)):
            st.markdown(f'<div class="risk-card">{label}<strong>{value:.1f}%</strong></div>', unsafe_allow_html=True)
        difference = baseline - target
        st.write(f"差は {abs(difference):.1f} ポイント{'減少' if difference > 0 else '増加' if difference < 0 else '（変化なし）'}です。")
        draw_curve(curve, comparison, outcome)
        st.caption("点線は探索的な推定です。認知症の95%区間は確立していないため表示していません。" if outcome == "dementia" else
                   "帯は既存モデルの95%推定幅です。食事・運動の効果のばらつきなど、すべての不確実性を含むものではありません。")
    with st.expander("計算に使った数値・選んだ内容"):
        st.write("現在：" + f"血圧 {patient.sbp:g} / LDL {patient.ldl:g} / HbA1c {patient.a1c:g}")
        markers = result["untreated"] if choice == "medication" else result["targets"]
        st.write(("薬がなかった場合（逆算）：" if choice == "medication" else "選んだ改善後（推定）：") +
                 f"血圧 {markers['sbp']:.1f} / LDL {markers['ldl']:.1f} / HbA1c {markers['a1c']:.2f}")
        st.caption("単位：血圧 mmHg / LDL mg/dL / HbA1c %。これらは治療目標や実測値ではありません。")
        for med in kwargs["current_medications"] + kwargs["proposed_medications"]:
            st.write(med["key"])
        for key in result["applied"]:
            effect = DIET_EFFECTS.get(key) or EXERCISE_EFFECTS[key]
            st.write(effect.label)
    with st.expander("根拠と、この試算で分からないこと"):
        st.write("PC版と同じ計算モデル・薬剤カタログ・食事／運動の効果量を使っています。患者さん個人の将来を保証する、検証済みの診断ツールではありません。")
        st.write("短期間の研究で得られた平均の変化が長期間続くと仮定しています。年ごとに効果を足し続ける計算ではありません。薬と生活改善の効果が重なり、利益を大きく見積もる可能性があります。副作用や低血糖との釣り合いは評価していません。")
        st.write("認知症には観察研究に基づく探索的な効果を含みます。因果関係や薬の予防効果が確定したことを意味しません。病気ごとの値は足し合わせられません。")
        st.write("不明なBMI・腎臓の検査値を正常値で補いませんが、未補正の推定には限界があります。")
        for key in result["applied"]:
            effect = DIET_EFFECTS.get(key) or EXERCISE_EFFECTS[key]
            st.markdown(f"**{effect.label}**：{effect.evidence_summary} [根拠]({effect.source_url})")
    st.warning("薬の開始・変更・中止や、食事・運動の変更は主治医と相談してください。")
    st.button("食事・運動を変えてみる", key="results_lifestyle", type="primary", on_click=navigate, args=("lifestyle",), use_container_width=True)
    st.button("検査値を修正する", key="results_measurements", on_click=navigate, args=("measurements",), use_container_width=True)
    if mode == "with":
        st.button("今の薬を確認する", key="results_medications", on_click=navigate, args=("medications",), use_container_width=True)


def main():
    step = st.session_state.get("pm_step", "welcome")
    if step == "welcome":
        welcome()
        return
    mode = st.session_state["pm_mode"]
    steps = ["medications", "measurements", "lifestyle", "results"] if mode == "with" else ["measurements", "lifestyle", "results"]
    st.caption(f"{'薬を使っている方' if mode == 'with' else '薬を使っていない方'} · {steps.index(step) + 1} / {len(steps)}")
    if step == "medications":
        medications()
    elif step == "measurements":
        measurements(mode)
    elif step == "lifestyle":
        lifestyle(mode)
    else:
        results(mode)
    st.divider()
    st.button("入力を消して最初に戻る", key="reset_mobile", on_click=reset, use_container_width=True)


main()
