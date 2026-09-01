"""Public, mobile-first health-check flow mounted by Streamlit at /checkup."""
from __future__ import annotations

import hashlib
import html
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calc_engine_outcomes import OutcomesEngine
from checkup_analytics import aggregate_events, record_event
from checkup_pdf import create_checkup_handout
from lifestyle_interventions import DIET_EFFECTS, EXERCISE_EFFECTS, apply_lifestyle_effects
from meds_catalog import apply_meds_to_targets, load_meds_catalog

st.set_page_config(page_title="健診から未来をみる", page_icon="✦", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
:root{--ink:#17324d;--muted:#66788a;--teal:#147d75;--mint:#e8f4f1;--line:#dbe5e8;--warm:#fbfaf7}
[data-testid="stHeader"]{background:transparent}.stApp{background:linear-gradient(180deg,#f4f8f7 0,#fff 340px)}
.block-container{max-width:480px;padding:1rem .9rem 4.5rem}h1,h2,h3{color:var(--ink);letter-spacing:-.025em}
h1{font-size:clamp(1.75rem,7vw,2.35rem)!important;line-height:1.25!important}.eyebrow{color:var(--teal);font-size:.78rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.lead{font-size:1rem;line-height:1.85;color:#425466}.soft{color:var(--muted);font-size:.88rem}.hero{padding:1.6rem 0 1.1rem}
.hero-mark{width:42px;height:42px;border-radius:14px;background:var(--ink);color:white;display:grid;place-items:center;font-size:19px;box-shadow:0 10px 26px #17324d2a;margin-bottom:1.4rem}
.trust{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}.pill{background:white;border:1px solid var(--line);border-radius:999px;padding:.4rem .7rem;color:#526777;font-size:.8rem}
.panel{background:#fff;border:1px solid var(--line);border-radius:18px;padding:1rem .95rem;box-shadow:0 10px 32px rgba(23,50,77,.06);margin:.65rem 0}
.risk-stack{display:grid;gap:.65rem;margin:.5rem 0}.risk-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:.95rem 1rem}
.risk-number{font-size:2.1rem;font-weight:750;color:var(--ink);line-height:1}.risk-label{font-size:.8rem;color:var(--muted);margin-bottom:.45rem}
.section-label{font-size:.82rem;font-weight:700;color:var(--ink);margin:.2rem 0 .55rem}
.choice-on{background:var(--mint)!important;border-color:#9fd4cf!important;color:#0d6b64!important}
.delta{display:inline-block;background:var(--mint);color:#0d6b64;border-radius:8px;padding:.28rem .5rem;font-weight:650;font-size:.82rem}
.progress-copy{display:flex;justify-content:space-between;color:var(--muted);font-size:.76rem;margin-bottom:.4rem}.progress-track{height:4px;background:#e7edef;border-radius:5px;margin-bottom:1.6rem}.progress-fill{height:4px;background:var(--teal);border-radius:5px}
.summary-row{display:flex;justify-content:space-between;gap:1rem;padding:.75rem 0;border-bottom:1px solid #edf1f2}.summary-row:last-child{border:0}.summary-row span:first-child{color:var(--muted)}
.notice{border-left:3px solid var(--teal);padding:.2rem 0 .2rem 1rem;color:#526777;line-height:1.7;font-size:.9rem}
.stButton>button,.stDownloadButton>button{border-radius:12px!important;min-height:3.25rem;font-weight:700;border-color:#cbd9dc;width:100%}
.stButton>button[kind="primary"]{background:var(--ink);border-color:var(--ink);box-shadow:0 8px 22px #17324d26}
[data-testid="stNumberInput"] input{font-size:1.2rem;font-weight:650;min-height:3rem}.stRadio label,.stCheckbox label{line-height:1.5}
div[data-testid="column"]{width:100%!important;flex:1 1 100%!important;min-width:100%!important}
@media(max-width:480px){.block-container{padding-top:.65rem}.panel{border-radius:16px}.hero{padding-top:1rem}.risk-number{font-size:1.95rem}}
@media print{[data-testid="stHeader"],.stButton,button{display:none!important}.block-container{max-width:100%;padding:0}.panel{box-shadow:none}}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def engine() -> OutcomesEngine:
    return OutcomesEngine(str(ROOT / "config.yaml"))


@st.cache_data(show_spinner=False)
def catalog():
    return load_meds_catalog(str(ROOT / "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx"),
                             str(ROOT / "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx"))


def qp(name: str) -> str:
    value = st.query_params.get(name, "")
    return value[0] if isinstance(value, list) else str(value)


if "checkup_session_id" not in st.session_state:
    st.session_state.checkup_session_id = uuid.uuid4().hex
if "checkup_stage" not in st.session_state:
    st.session_state.checkup_stage = "landing"
if "checkup_referral_id" not in st.session_state:
    st.session_state.checkup_referral_id = uuid.uuid4().hex[:12]
if "checkup_events" not in st.session_state:
    st.session_state.checkup_events = set()

CTX = {
    "session_id": st.session_state.checkup_session_id,
    "source": qp("source"), "campaign": qp("campaign"), "facility_id": qp("facility_id"),
    "referral_id": st.session_state.checkup_referral_id, "parent_referral_id": qp("ref"),
}


def track(event: str, once_key: str | None = None) -> None:
    key = once_key or event
    if key not in st.session_state.checkup_events:
        record_event(event, CTX)
        st.session_state.checkup_events.add(key)


def navigate(stage: str, event: str | None = None) -> None:
    if event:
        track(event)
    st.session_state.checkup_stage = stage
    st.rerun()


def progress(step: int, total: int = 7) -> None:
    st.markdown(f'<div class="progress-copy"><span>健診結果から入力</span><span>{step} / {total}</span></div><div class="progress-track"><div class="progress-fill" style="width:{100*step/total:.0f}%"></div></div>', unsafe_allow_html=True)


def val(key: str, default=None):
    value = st.session_state.get(key, default)
    return default if value is None else value


def baseline_targets() -> dict:
    return {
        "sbp": float(val("c_sbp", 130)),
        "ldl": float(val("c_ldl", 140)),
        "a1c": float(val("c_a1c", 5.8)),
        "bmi": float(val("c_bmi", 23.9)),
        "quit": False,
    }


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(float(a) - float(b)) <= tol


def scenario_unchanged(targets: dict) -> bool:
    """No user-selected change: same labs/BMI and no explicit quit scenario."""
    if targets.get("quit"):
        return False
    base = baseline_targets()
    for key in ("sbp", "ldl", "a1c", "bmi"):
        if not _close(targets.get(key, base[key]), base[key]):
            return False
    return True


def _normalize_unchanged(point: dict) -> dict:
    """Engine may apply target-only corrections (e.g. low HbA1c U-shape); zero diff when unchanged."""
    return {
        outcome: {"baseline": values["baseline"], "target": values["baseline"]}
        for outcome, values in point.items()
    }


def risk_params(targets: dict | None = None) -> dict:
    smoking = val("c_smoking", "never")
    target = targets or {"sbp": val("c_sbp", 130), "ldl": val("c_ldl", 140), "a1c": val("c_a1c", 5.8),
                         "bmi": val("c_bmi", 23.9), "quit": False}
    return dict(sex=val("c_sex", "male"), start_age=int(val("c_age", 52)),
                sbp_now=float(val("c_sbp", 130)), sbp_target=float(target["sbp"]),
                ldl_now_mg=float(val("c_ldl", 140)), ldl_target_mg=float(target["ldl"]),
                hba1c_now=float(val("c_a1c", 5.8)), hba1c_target=float(target["a1c"]),
                smoking_status=smoking, cigs_per_day=int(val("c_cigs", 0)),
                years_smoked=float(val("c_smoke_years", 0)), years_since_quit=float(val("c_quit_years", 0)),
                assume_quit_today_in_target=bool(target.get("quit", False)), bmi_now=val("c_bmi", 23.9),
                bmi_target=target.get("bmi", val("c_bmi", 23.9)), egfr_now=val("c_egfr"),
                egfr_target=val("c_egfr"), acr_now=None, acr_target=None)


def risks(targets: dict | None = None) -> dict:
    out = {}
    age = int(val("c_age", 52))
    horizons = {"10年": min(10, 110-age), "20年": min(20, 110-age), "生涯相当": 110-age}
    for label, years in horizons.items():
        if years <= 0:
            continue
        out[label] = {}
        for outcome in ("mi", "stroke", "mortality"):
            point = engine().cumulative_incidence_with_ci(outcome=outcome, years=years, **risk_params(targets))["point"]
            if targets is not None and scenario_unchanged(targets):
                point = _normalize_unchanged(point)
            out[label][outcome] = point
    return out


stage = st.session_state.checkup_stage
if qp("mode") == "handout":
    stage = "handout"

if qp("admin") == "1":
    st.markdown('<p class="eyebrow">Operations</p>', unsafe_allow_html=True)
    st.title("健診フロー 利用状況")
    st.caption("健診値などの個人データは記録していません。施設・キャンペーン別のイベント集計のみです。")
    rows = aggregate_events()
    if rows:
        import pandas as pd
        frame = pd.DataFrame(rows)
        st.dataframe(frame.pivot_table(index=["facility_id", "campaign"], columns="event", values="count", fill_value=0), width="stretch")
    else:
        st.info("まだイベントはありません。")
    st.stop()

if stage == "landing":
    track("landing_view")
    campaign = qp("campaign").upper()
    alt = {"A": "この健診結果で、あなたの20年後はどう変わる？", "B": "あなたに一番効果の大きい健康対策は？"}.get(campaign)
    st.markdown('<div class="hero"><div class="hero-mark">✦</div><p class="eyebrow">Your health, in perspective</p>', unsafe_allow_html=True)
    st.title("健診、おつかれさまでした。")
    st.markdown(f'<p class="lead">{html.escape(alt or "その数字を「未来」にしてみませんか？")}<br><span class="soft">今の状態と、生活や治療を変えた未来を比べられます。</span></p>', unsafe_allow_html=True)
    st.markdown('<div class="trust"><span class="pill">約3分</span><span class="pill">登録不要</span><span class="pill">入力値は解析に保存しません</span></div></div>', unsafe_allow_html=True)
    if st.button("健診結果を見ながら始める　→", type="primary"):
        navigate("consent", "start_clicked")
    with st.expander("どんなサービス？"):
        st.write("健診の数字が将来にどう影響し、何を変えると推定リスクがどの程度変わるかを、グラフで比較するシミュレーターです。診断や治療の推奨を行うものではありません。")
    st.stop()

if stage == "consent":
    progress(1)
    st.markdown('<p class="eyebrow">Before you begin</p>', unsafe_allow_html=True)
    st.title("はじめに、ご確認ください")
    st.markdown('<div class="notice">本サービスは医療診断を行わず、将来の発症を確実に予測するものではありません。<br><br>表示値は疫学研究・臨床研究等をもとにした推定値です。医薬品の開始・中止・変更を自己判断せず、治療は医師などの医療専門職にご相談ください。</div>', unsafe_allow_html=True)
    ok = st.checkbox("内容を確認しました")
    if st.button("次へ", type="primary", disabled=not ok):
        navigate("basic", "consent_completed")
    st.stop()

if stage == "basic":
    progress(2); st.title("まず、基本情報から")
    st.caption("健診結果に記載された内容を入力してください。")
    with st.form("basic_form"):
        st.number_input("年齢", 20, 95, val("c_age", 52), step=1, key="c_age", help="歳")
        st.radio("性別", ["male", "female"], index=0, format_func=lambda x: "男性" if x == "male" else "女性", horizontal=True, key="c_sex")
        st.number_input("身長（cm）", 120.0, 210.0, val("c_height", 165.0), .1, key="c_height")
        st.number_input("体重（kg）", 30.0, 180.0, val("c_weight", 65.0), .1, key="c_weight")
        submitted = st.form_submit_button("次へ", type="primary")
    if submitted:
        st.session_state.c_bmi = st.session_state.c_weight / (st.session_state.c_height / 100) ** 2
        track("basic_input_completed"); navigate("bp")
    st.stop()

if stage == "bp":
    progress(3); st.title("血圧")
    st.caption("上の血圧・下の血圧を、そのまま転記してください。")
    with st.form("bp_form"):
        st.number_input("収縮期（上）", 70, 250, val("c_sbp", 130), key="c_sbp", help="mmHg")
        st.number_input("拡張期（下）", 40, 150, val("c_dbp", 80), key="c_dbp", help="mmHg")
        st.radio("降圧薬", ["no", "yes", "unknown"], index=0, format_func=lambda x:{"no":"使用していない","yes":"使用している","unknown":"分からない"}[x], key="c_bp_med")
        submitted = st.form_submit_button("次へ", type="primary")
    if submitted: navigate("lipid")
    st.stop()

if stage == "lipid":
    progress(4); st.title("コレステロール")
    st.caption("LDL-Cは現在の計算モデルで必要です。HDL-Cなどは確認用に表示します。")
    with st.form("lipid_form"):
        st.number_input("LDLコレステロール（mg/dL）", 20, 400, val("c_ldl", 140), key="c_ldl")
        st.number_input("HDL-C（任意）", 0, 200, val("c_hdl", 0), key="c_hdl", help="不明なら0")
        st.number_input("中性脂肪（任意）", 0, 1000, val("c_tg", 0), key="c_tg", help="不明なら0")
        st.radio("脂質低下薬", ["no","yes","unknown"], index=0, format_func=lambda x:{"no":"使用していない","yes":"使用している","unknown":"分からない"}[x], key="c_lipid_med")
        submitted=st.form_submit_button("次へ",type="primary")
    if submitted: navigate("other")
    st.stop()

if stage == "other":
    progress(5); st.title("その他の項目")
    with st.form("other_form"):
        st.number_input("HbA1c（%）", 3.0, 20.0, val("c_a1c", 5.8), .1, key="c_a1c")
        st.radio("糖尿病", ["no","yes","unknown"], index=0, format_func=lambda x:{"no":"なし","yes":"あり","unknown":"分からない"}[x], horizontal=True, key="c_diabetes")
        st.radio("喫煙", ["never","current","former"], index=0, format_func=lambda x:{"never":"吸わない","current":"現在吸っている","former":"以前吸っていた"}[x], key="c_smoking")
        if val("c_smoking", "never") in {"current","former"}:
            st.number_input("1日の本数",0,80,val("c_cigs",10),key="c_cigs")
            st.number_input("喫煙年数",0,70,val("c_smoke_years",20),key="c_smoke_years")
        if val("c_smoking", "never") == "former":
            st.number_input("禁煙してから（年）",0,70,val("c_quit_years",5),key="c_quit_years")
        known = st.checkbox("eGFRが分かる", value=val("c_egfr_known", False), key="c_egfr_known")
        if known: st.number_input("eGFR（mL/min/1.73㎡）",1.0,150.0,val("c_egfr",75.0),.1,key="c_egfr")
        submitted=st.form_submit_button("入力内容を確認",type="primary")
    if submitted:
        if not known: st.session_state.c_egfr=None
        track("full_input_completed"); navigate("confirm")
    st.stop()

if stage == "confirm":
    progress(6); st.title("入力内容の確認")
    smoke_label={"never":"なし","current":"あり","former":"過去にあり"}[val("c_smoking", "never")]
    rows=[("年齢・性別",f'{val("c_age",52)}歳・{"男性" if val("c_sex","male")=="male" else "女性"}'),("BMI",f'{val("c_bmi",23.9):.1f}'),("血圧",f'{val("c_sbp",130)} / {val("c_dbp",80)} mmHg'),("LDL-C",f'{val("c_ldl",140)} mg/dL'),("HbA1c",f'{val("c_a1c",5.8):.1f}%'),("喫煙",smoke_label),("eGFR",f'{val("c_egfr"):.1f}' if val("c_egfr") else "未入力")]
    st.markdown('<div class="panel">'+''.join(f'<div class="summary-row"><span>{a}</span><strong>{b}</strong></div>' for a,b in rows)+'</div>',unsafe_allow_html=True)
    if st.button("この内容で未来を見る",type="primary"):
        track("result_viewed"); navigate("result")
    if st.button("入力を修正する"):
        navigate("basic")
    st.stop()

if stage in {"result", "simulate", "handoff"}:
    current = risks()
    if stage == "result":
        st.markdown('<p class="eyebrow">Your perspective</p>',unsafe_allow_html=True); st.title("あなたの現在の結果から推定すると")
        st.caption("現在の状態が続いた場合に推定されるリスク")
        cards = "".join(
            f'<div class="risk-card"><div class="risk-label">{label}・心筋梗塞</div>'
            f'<div class="risk-number">{100*data["mi"]["baseline"]:.1f}<small style="font-size:.95rem">%</small></div></div>'
            for label, data in current.items()
        )
        st.markdown(f'<div class="risk-stack">{cards}</div>', unsafe_allow_html=True)
        with st.expander("脳卒中・全死亡も見る"):
            for label,data in current.items():
                st.write(f'{label}：脳卒中 **{100*data["stroke"]["baseline"]:.1f}%** ／ 全死亡 **{100*data["mortality"]["baseline"]:.1f}%**')
        # Existing engine sampled across its supported age range.
        age=int(val("c_age")); max_year=110-age; xs=sorted(set([0,*range(5,max_year+1,5),max_year])); ys=[]
        for y in xs:
            ys.append(0 if y==0 else 100*engine().cumulative_incidence_with_ci(outcome="mi",years=y,**risk_params())["point"]["baseline"])
        fig=go.Figure(go.Scatter(x=xs,y=ys,mode="lines",line=dict(color="#17324d",width=4,shape="spline"),fill="tozeroy",fillcolor="rgba(20,125,117,.09)",hovertemplate="%{x}年後　%{y:.1f}%<extra></extra>"))
        fig.update_layout(height=280,margin=dict(l=8,r=8,t=35,b=8),title="今の状態が続いた場合｜心筋梗塞",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",xaxis_title="現在からの年数",yaxis_title="推定リスク（%）",font=dict(family="sans-serif",color="#526777",size=12),showlegend=False)
        st.plotly_chart(fig,width="stretch",config={"displayModeBar":False}); track("trajectory_viewed")
        st.markdown('<div class="notice">「生涯相当」は既存モデルが対応する110歳までの推定です。将来を断定する値ではなく、比較のための目安です。</div>',unsafe_allow_html=True)
        st.write("");
        if st.button("未来を変えてみる　→",type="primary"): navigate("simulate")
        st.stop()

    if stage == "simulate":
        st.markdown('<p class="eyebrow">Shape a scenario</p>',unsafe_allow_html=True); st.title("未来を変えてみる")
        st.caption("比較したいものを選んでください。選択は治療の推奨ではありません。")
        if "c_quit" not in st.session_state:
            st.session_state.c_quit = False
        bp_drugs = list(val("c_bp_drugs", []) or [])
        ldl_drugs = list(val("c_ldl_drugs", []) or [])
        meds = None
        with st.container(border=True):
            st.subheader("暮らしから変える")
            if val("c_smoking") == "current":
                st.markdown('<p class="section-label">喫煙</p>', unsafe_allow_html=True)
                quit_smoke = bool(st.session_state.c_quit)
                quit_label = "禁煙した未来を比較から外す" if quit_smoke else "禁煙した未来を比較する"
                quit_type = "secondary" if quit_smoke else "primary"
                if st.button(quit_label, type=quit_type, use_container_width=True, key="c_quit_toggle"):
                    st.session_state.c_quit = not quit_smoke
                    st.rerun()
                if quit_smoke:
                    st.caption("禁煙した場合のリスクを比較に含めています。")
            else:
                st.session_state.c_quit = False
                quit_smoke = False
            diet_keys=st.multiselect("食生活",list(DIET_EFFECTS),format_func=lambda k:DIET_EFFECTS[k].label,key="c_diets")
            exercise=st.selectbox("運動",[None,*EXERCISE_EFFECTS],format_func=lambda k:"選択しない" if k is None else EXERCISE_EFFECTS[k].label,key="c_exercise")
        if diet_keys or exercise or quit_smoke: track("lifestyle_intervention_clicked",f'lifestyle_{hash(str((diet_keys,exercise,quit_smoke)))}')
        with st.container(border=True):
            st.subheader("検査値を改善した場合")
            improve_bp=st.checkbox("血圧を改善した場合",key="c_improve_bp")
            bp_target=st.slider("収縮期血圧",90,min(180,int(val("c_sbp"))),min(130,int(val("c_sbp"))),key="c_bp_target",disabled=not improve_bp)
            improve_ldl=st.checkbox("LDLコレステロールを改善した場合",key="c_improve_ldl")
            ldl_target=st.slider("LDL-C",40,min(250,int(val("c_ldl"))),min(100,int(val("c_ldl"))),key="c_ldl_target",disabled=not improve_ldl)
            if improve_bp or improve_ldl: track("medical_intervention_clicked",f'medical_{improve_bp}_{improve_ldl}')
            with st.expander("具体的な治療方法も比較できます"):
                try:
                    meds=catalog(); bp_opts=[m["key"] for m in meds["sbp"]]; ldl_opts=[m["key"] for m in meds["ldl"]]
                    bp_drugs=st.multiselect("降圧薬",bp_opts,default=bp_drugs,key="c_bp_drugs")
                    ldl_drugs=st.multiselect("脂質低下薬",ldl_opts,default=ldl_drugs,key="c_ldl_drugs")
                except Exception:
                    bp_drugs=[];ldl_drugs=[];st.info("薬剤カタログを読み込めませんでした。")
                if bp_drugs or ldl_drugs: track("specific_drug_clicked",f'drugs_{hash(str((bp_drugs,ldl_drugs)))}')
        base_targets=baseline_targets()
        if improve_bp: base_targets["sbp"]=float(bp_target)
        if improve_ldl: base_targets["ldl"]=float(ldl_target)
        if quit_smoke: base_targets["quit"]=True
        if (bp_drugs or ldl_drugs) and meds:
            selected_bp=[m for m in meds["sbp"] if m["key"] in bp_drugs]; selected_ldl=[m for m in meds["ldl"] if m["key"] in ldl_drugs]
            med_result=apply_meds_to_targets(float(base_targets["sbp"]),float(base_targets["ldl"]),float(base_targets["a1c"]),selected_bp,selected_ldl,[])
            base_targets.update(sbp=med_result["sbp_target"],ldl=med_result["ldl_target"],a1c=med_result["a1c_target"])
        lifestyle=apply_lifestyle_effects(sbp=base_targets["sbp"],ldl=base_targets["ldl"],a1c=base_targets["a1c"],diet_keys=diet_keys,exercise_key=exercise,diabetes_context=val("c_diabetes")=="yes" or val("c_a1c")>=6.5)
        base_targets.update(sbp=lifestyle["sbp"],ldl=lifestyle["ldl"],a1c=lifestyle["a1c"])
        selected=not scenario_unchanged(base_targets)
        planned=risks(base_targets)
        st.subheader("選択した未来との比較")
        labels=list(current); before=[100*current[k]["mi"]["baseline"] for k in labels]; after=[100*planned[k]["mi"]["target"] for k in labels]
        fig=go.Figure([go.Bar(name="現在の状態",x=labels,y=before,marker_color="#b8c5cb"),go.Bar(name="選択したプラン",x=labels,y=after,marker_color="#147d75")])
        fig.update_layout(barmode="group",height=300,margin=dict(l=8,r=8,t=15,b=8),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",yaxis_title="心筋梗塞 推定リスク（%）",legend_orientation="h",font=dict(size=12))
        st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})
        if "10年" in current:
            b,a=before[0],after[0]
            delta_text = "変化なし" if abs(a - b) < 1e-6 else f"絶対差 {a-b:+.1f} ポイント"
            st.markdown(f'<div class="panel"><div class="risk-label">10年リスク｜心筋梗塞</div><div class="risk-number">{b:.1f}% <span style="color:#91a0a8">→</span> {a:.1f}%</div><br><span class="delta">{delta_text}</span></div>',unsafe_allow_html=True)
        chosen=[DIET_EFFECTS[k].label for k in diet_keys]+([EXERCISE_EFFECTS[exercise].label] if exercise else [])+(["禁煙"] if quit_smoke else [])+([f"血圧 {base_targets['sbp']:.0f} mmHg"] if improve_bp or bp_drugs else [])+([f"LDL-C {base_targets['ldl']:.0f} mg/dL"] if improve_ldl or ldl_drugs else [])
        st.session_state.c_plan={"targets":base_targets,"labels":chosen,"risks":planned}
        if selected: track("plan_created",f'plan_{hash(str(chosen))}')
        st.subheader("あなたが選んだ未来")
        st.markdown('<div class="panel">'+(''.join(f'<div class="summary-row"><span>✓</span><strong>{html.escape(x)}</strong></div>' for x in chosen) if chosen else '<span class="soft">介入を選ぶとここに表示されます。</span>')+'</div>',unsafe_allow_html=True)
        st.caption("薬剤の効果は研究データ等から推定した平均的な値で、実際の効果には個人差があります。")
        if st.button("このプランについて医師と相談する",type="primary",disabled=not selected):
            track("doctor_handoff_clicked"); navigate("handoff")
        st.divider(); st.subheader("ご家族の健診結果も確認してみませんか？")
        base_url=qp("base_url") or "https://japan-cvd-risk-simulator.streamlit.app/checkup"; share_url=base_url+"?"+urlencode({"source":"family_share","ref":CTX["referral_id"]})
        if st.button("家族に送る"):
            track("family_share_clicked")
            components.html(f'''<button onclick="share()" style="width:100%;height:48px;border:0;border-radius:12px;background:#17324d;color:#fff;font-weight:700">共有メニューを開く</button><script>async function share(){{const d={{title:'健診から未来をみる',text:'健診結果から将来の健康を考えてみませんか？',url:{share_url!r}}};if(navigator.share){{await navigator.share(d)}}else{{await navigator.clipboard.writeText(d.url);document.body.innerHTML='<p style="font-family:sans-serif;color:#147d75">URLをコピーしました</p>'}}}}</script>''',height=58)
            st.code(share_url,language=None)
        st.stop()

    if stage == "handoff":
        plan=val("c_plan",{}); planned=plan.get("risks",current)
        st.markdown('<p class="eyebrow">For consultation</p>',unsafe_allow_html=True);st.title("医師に見せるサマリー")
        st.caption("利用者が比較のために選択したシミュレーションです。処方指示ではありません。")
        st.markdown(f'<div class="panel"><h3>主要健診値</h3><div class="summary-row"><span>年齢・性別</span><strong>{val("c_age")}歳・{"男性" if val("c_sex")=="male" else "女性"}</strong></div><div class="summary-row"><span>血圧</span><strong>{val("c_sbp")} / {val("c_dbp")} mmHg</strong></div><div class="summary-row"><span>LDL-C / HbA1c</span><strong>{val("c_ldl")} mg/dL / {val("c_a1c"):.1f}%</strong></div><div class="summary-row"><span>BMI / eGFR</span><strong>{val("c_bmi"):.1f} / {val("c_egfr") or "未入力"}</strong></div></div>',unsafe_allow_html=True)
        st.subheader("リスク比較（心筋梗塞）")
        for label in current:
            b=100*current[label]["mi"]["baseline"]; a=100*planned[label]["mi"]["target"]
            st.markdown(f'<div class="summary-row"><span>{label}</span><strong>{b:.1f}% → {a:.1f}%（{a-b:+.1f}pt）</strong></div>',unsafe_allow_html=True)
        st.subheader("利用者が選択したプラン")
        for item in plan.get("labels",[]): st.write(f"✓ {item}")
        st.markdown('<div class="notice">推定値には不確実性があり、個人差があります。治療方針は診察・検査結果とあわせてご判断ください。</div>',unsafe_allow_html=True)
        st.button("印刷する",on_click=lambda:None)
        if st.button("シミュレーションに戻る"): navigate("simulate")
        st.stop()

if stage == "handout":
    st.title("健診結果添付用 A4 PDF")
    facility=st.text_input("施設名（任意）")
    url=st.text_input("QRコードのリンク先",value="https://japan-cvd-risk-simulator.streamlit.app/checkup?source=healthcheck")
    pdf=create_checkup_handout(url,facility)
    st.download_button("A4 PDFをダウンロード",pdf,"checkup_qr_handout.pdf","application/pdf",type="primary")
