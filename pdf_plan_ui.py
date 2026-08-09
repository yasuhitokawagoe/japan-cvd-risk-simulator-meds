# pdf_plan_ui.py
# -*- coding: utf-8 -*-
"""
療養計画書PDFの作成UI（PC版・モバイル版で共有）。

PC版 app_streamlit_outcomes.py とモバイル版 app_streamlit_mobile.py は、この
render_plan_section() を呼ぶだけ。UIの重複とドリフトを防ぐため共通化している。
PDF生成ロジックは pdf_fill.py（さらにその下層）。

BMIの扱いだけアプリで異なる:
  - bmi_target を渡す（PC: サイドバーにBMI入力あり）→ 「載せる項目」チェックで制御
  - bmi_target=None（モバイル: BMI入力なし）→ 計画書内で手入力
"""
from __future__ import annotations

from datetime import date
from typing import Mapping, Optional

import streamlit as st

import pdf_fill
from patient_report_pdf import generate_patient_report_pdf
from plan_logic import (
    LIFESTYLE_GOALS,
    ideal_weight_kg,
    infer_diagnoses,
    suggested_goals,
    suggested_instructions,
)


_UI = {
    "ja": {
        "title": "## 📄 療養計画書を作成",
        "caption": "アプリが持つ値を療養計画書（別紙様式9）に記入します。一次予防モデルの患者情報・検査値・服薬内容を引き継ぎます。主病名は検査値と服薬内容から候補を示すため、必ず確認してください。",
        "visit": "区分", "visit_first": "初回", "visit_cont": "継続",
        "dbp": "目標拡張期血圧 (mmHg)",
        "include": "**計画書に載せる項目**（チェックした値だけ記入されます）",
        "inc_bp": "目標血圧", "inc_a1c": "目標HbA1c", "inc_ldl": "実測LDL", "inc_a1c_now": "実測HbA1c", "inc_bmi": "目標BMI",
        "bmi_manual": "目標BMI（0＝記入しない）",
        "handed": "**一次予防モデルから引き継いだ内容**",
        "male": "男性", "female": "女性", "meds": "服薬内容: ", "meds_none": "なし／未入力",
        "manual": "✍ 手入力項目（主病名・体重・栄養状態・行動目標）",
        "manual_cap": "自動入力された候補を確認し、患者さんとの相談内容に合わせて修正してください。",
        "dx": "**主病名の候補**（検査値または該当薬から自動チェック・確定診断ではありません）",
        "dm": "糖尿病", "htn": "高血圧症", "dl": "脂質異常症",
        "wt_bmi": "目標体重 (kg)（BMI 22から自動計算）",
        "wt_manual": "目標体重 (kg)（0＝記入しない）",
        "nutrition": "栄養状態", "nutrition_skip": "（記入しない）",
        "life": "**生活習慣から指導項目・行動目標を選ぶ**",
        "life_items": "生活習慣・相談事項",
        "default_life": "運動不足",
        "instr": "療養計画書にチェックする指導項目",
        "goals": "療養計画書と患者さん向け資料に反映する目標",
        "extra_goal": "追加の達成目標・行動目標",
        "extra_ph": "患者さんと相談して決めた内容を追加",
        "achieve": "目標の達成状況（継続の場合のみ）",
        "achieve_ph": "継続受診時、前回目標の達成状況を記入",
        "backcast_eval": "反実仮想の結果を踏まえた評価・方針",
        "backcast_ok": "現在の治療で目標は達成できている。治療を継続する",
        "backcast_improve": "一定の成果は得られている。さらに改善を目指す",
        "ready": "📄 記入内容を確認する",
        "review": "#### 記入内容（この値が印字されます・編集可）",
        "review_cap": "数値や内容はここで最終調整できます。空欄にするとその項目は印字されません。",
        "privacy": "氏名・生年月日は個人情報保護のため空欄です。未入力の項目は印刷後に手書きできます。",
        "maintain": "治療効果の維持",
        "download_plan": "⬇ PDFをダウンロード",
        "patient_title": "#### 患者さん向け資料",
        "patient_ok": "現在の状態、介入前後の検査値、全死亡・心筋梗塞・脳卒中のリスク差と推移グラフ、相談して決めた目標を2ページにまとめました。",
        "download_patient": "⬇ グラフ付き患者さん向け資料（PDF）",
        "patient_need_calc": "リスク計算を実行すると、グラフ付き患者さん向け資料を作成できます。",
        "plan_filename": "療養計画書",
        "patient_filename": "健康づくりプラン",
    },
    "en": {
        "title": "## 📄 Create care plan form",
        "caption": "Fill the Japanese official care-plan form (Annex Form 9) with values from the app. Confirm diagnosis candidates suggested from labs and medicines.",
        "visit": "Visit type", "visit_first": "Initial", "visit_cont": "Follow-up",
        "dbp": "Target diastolic BP (mmHg)",
        "include": "**Items to include** (only checked values are filled)",
        "inc_bp": "BP target", "inc_a1c": "HbA1c target", "inc_ldl": "Measured LDL", "inc_a1c_now": "Measured HbA1c", "inc_bmi": "BMI target",
        "bmi_manual": "BMI target (0 = leave blank)",
        "handed": "**Carried over from the prevention model**",
        "male": "Male", "female": "Female", "meds": "Medicines: ", "meds_none": "None / not entered",
        "manual": "✍ Manual items (diagnoses, weight, nutrition, goals)",
        "manual_cap": "Review auto-suggestions and adjust based on discussion with the patient.",
        "dx": "**Diagnosis candidates** (auto-checked from labs/meds; not a confirmed diagnosis)",
        "dm": "Diabetes", "htn": "Hypertension", "dl": "Dyslipidemia",
        "wt_bmi": "Target weight (kg) (from BMI 22)", "wt_manual": "Target weight (kg) (0 = leave blank)",
        "nutrition": "Nutrition status", "nutrition_skip": "(leave blank)",
        "life": "**Choose counseling items and goals from lifestyle topics**",
        "life_items": "Lifestyle / counseling topics",
        "default_life": "運動不足",
        "instr": "Counseling items to check on the form",
        "goals": "Goals for the form and patient handout",
        "extra_goal": "Additional achievement / action goals",
        "extra_ph": "Add what you agreed with the patient",
        "achieve": "Goal achievement status (follow-up only)",
        "achieve_ph": "At follow-up, record progress on prior goals",
        "backcast_eval": "Assessment based on the counterfactual estimate",
        "backcast_ok": "Targets are met with current treatment; continue therapy",
        "backcast_improve": "Some benefit achieved; aim for further improvement",
        "ready": "📄 Review form values",
        "review": "#### Form values (editable; these will be printed)",
        "review_cap": "Adjust values here. Blank fields are not printed.",
        "privacy": "Name and date of birth are left blank for privacy. Other blanks can be handwritten after printing.",
        "maintain": "Maintain treatment benefit",
        "download_plan": "⬇ Download PDF",
        "patient_title": "#### Patient handout",
        "patient_ok": "A 2-page handout with current status, lab changes, risk differences for all-cause death / MI / stroke, charts, and agreed goals.",
        "download_patient": "⬇ Patient handout with charts (PDF)",
        "patient_need_calc": "Run the risk calculation to create a patient handout with charts.",
        "plan_filename": "care_plan",
        "patient_filename": "health_plan",
    },
}

_LIFESTYLE_TOPIC_EN = {
    "塩分が多い": "High dietary sodium intake",
    "野菜が少ない": "Low vegetable intake",
    "間食・甘い飲料が多い": "Frequent snacks / sweetened beverages",
    "運動不足": "Insufficient physical activity",
    "体重を減らしたい": "Weight-loss goal",
    "喫煙している": "Current smoking",
    "飲酒量が多い": "Heavy alcohol use",
    "服薬を忘れる": "Medication nonadherence",
}

_INTERVENTION_LABEL_EN = {
    "減塩": "Dietary sodium restriction",
    "糖質制限": "Carbohydrate restriction",
    "飽和脂肪制限": "Saturated fat restriction",
    "中強度有酸素運動": "Moderate-intensity aerobic exercise",
    "有酸素＋筋力トレーニング": "Combined aerobic and resistance training",
    "高強度インターバル運動": "High-intensity interval training (HIIT)",
}

_LABEL_MAP = {
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

# 達成目標は短い見出し語。詳細な行動は指導項目チェック側で表現する。
_INTERVENTION_PLAN_ITEMS = {
    "減塩": (["食塩・調味料を控える"], ["減塩"]),
    "糖質制限": (["食事摂取量を適正にする", "間食を減らす"], ["食事の改善"]),
    "飽和脂肪制限": (["油を使った料理の摂取を減らす"], ["食事の改善"]),
    "中強度有酸素運動": (["運動処方", "日常生活の活動量を増やす"], ["運動"]),
    "有酸素＋筋力トレーニング": (["運動処方", "日常生活の活動量を増やす"], ["運動"]),
    "高強度インターバル運動": (["運動処方", "運動時の注意事項を確認する"], ["運動"]),
}
# English display labels from the PC English app also map to the same Japanese PDF items.
for _jp, _en in _INTERVENTION_LABEL_EN.items():
    _INTERVENTION_PLAN_ITEMS[_en] = _INTERVENTION_PLAN_ITEMS[_jp]


def _plan_items_for_interventions(labels: tuple[str, ...]) -> tuple[list[str], list[str]]:
    instructions, goals = [], []
    for label in labels:
        mapped_instructions, mapped_goals = _INTERVENTION_PLAN_ITEMS.get(label, ([], []))
        instructions.extend(item for item in mapped_instructions if item not in instructions)
        goals.extend(item for item in mapped_goals if item not in goals)
    return instructions, goals


def render_plan_section(
    *,
    sex: str,
    age: float,
    ldl_now: float,
    a1c_now: float,
    sbp_tgt_manual: float,
    a1c_tgt_manual: float,
    bmi_target: Optional[float] = None,
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    sbp_now: Optional[float] = None,
    dbp_now: Optional[float] = None,
    bp_medications: tuple[str, ...] = (),
    lipid_medications: tuple[str, ...] = (),
    diabetes_medications: tuple[str, ...] = (),
    lifestyle_interventions: tuple[str, ...] = (),
    risk_curves: Optional[Mapping] = None,
    risk_horizon_years: Optional[int] = None,
    sbp_after: Optional[float] = None,
    ldl_after: Optional[float] = None,
    a1c_after: Optional[float] = None,
    treatment_benefit: Optional[Mapping] = None,
    key_prefix: str = "pc",
    lang: str = "ja",
) -> None:
    """
    療養計画書の作成セクションを描画する。

    「目標」は医師が設定する目標そのもの。目標スライダー（sbp_tgt_manual /
    a1c_tgt_manual）を直接使う。use_meds ON時の有効目標値（薬剤計算の予測到達値）は
    目標欄には使わない（設計判断A）。氏名・生年月日等は決定1で空欄・手書き。
    """
    p = key_prefix
    ui = _UI.get(lang, _UI["ja"])
    label_map = (
        {
            pdf_fill.F_SEX: "Sex",
            pdf_fill.F_AGE: "Age",
            pdf_fill.F_DATE_Y: "Created (year)",
            pdf_fill.F_DATE_M: "Created (month)",
            pdf_fill.F_DATE_D: "Created (day)",
            pdf_fill.F_BP: "BP target (SBP/DBP)",
            pdf_fill.F_BMI: "BMI target",
            pdf_fill.F_A1C_TGT: "HbA1c target",
            pdf_fill.F_LDL_NOW: "Measured LDL",
            pdf_fill.F_A1C_NOW: "Measured HbA1c",
        }
        if lang == "en"
        else _LABEL_MAP
    )

    st.divider()
    st.markdown(ui["title"])
    st.caption(ui["caption"])

    # --- 計画書に固有の入力 ---
    col_v, col_d = st.columns(2)
    with col_v:
        visit_label = st.radio(
            ui["visit"],
            [ui["visit_first"], ui["visit_cont"]],
            horizontal=True,
            key=f"{p}_plan_visit",
        )
    with col_d:
        dbp_tgt_input = st.number_input(
            ui["dbp"], min_value=50, max_value=120, value=80, step=1,
            key=f"{p}_plan_dbp",
        )

    # --- 載せる項目（決定5: 既定値の誤記入を避けるため人が選ぶ） ---
    st.markdown(ui["include"])
    c1, c2 = st.columns(2)
    with c1:
        inc_bp = st.checkbox(ui["inc_bp"], value=True, key=f"{p}_inc_bp")
        inc_a1c_tgt = st.checkbox(ui["inc_a1c"], value=True, key=f"{p}_inc_a1ctgt")
    with c2:
        inc_ldl = st.checkbox(ui["inc_ldl"], value=True, key=f"{p}_inc_ldl")
        inc_a1c_now = st.checkbox(ui["inc_a1c_now"], value=True, key=f"{p}_inc_a1cnow")

    # BMI: アプリがBMIを持つ（PC）ならチェックで制御、持たない（モバイル）なら手入力
    if bmi_target is not None:
        inc_bmi = st.checkbox(ui["inc_bmi"], value=True, key=f"{p}_inc_bmi")
        bmi_value = float(bmi_target) if inc_bmi else None
    else:
        bmi_in = st.number_input(
            ui["bmi_manual"], min_value=0.0, max_value=50.0, value=0.0, step=0.1,
            key=f"{p}_bmi",
        )
        bmi_value = float(bmi_in) if bmi_in > 0 else None

    diagnoses = infer_diagnoses(
        sbp=sbp_now or 0, dbp=dbp_now or 0, ldl=ldl_now, a1c=a1c_now,
        has_bp_meds=bool(bp_medications),
        has_lipid_meds=bool(lipid_medications),
        has_diabetes_meds=bool(diabetes_medications),
    )
    medication_names = [*bp_medications, *lipid_medications, *diabetes_medications]

    if height_cm is not None and weight_kg is not None and sbp_now is not None and dbp_now is not None:
        with st.container(border=True):
            st.markdown(ui["handed"])
            sex_label = ui["male"] if sex == "male" else ui["female"]
            st.write(
                f"{int(age)} / {sex_label} / "
                f"Ht {height_cm:.1f} cm / Wt {weight_kg:.1f} kg / "
                f"BP {int(round(sbp_now))}/{int(round(dbp_now))} mmHg / "
                f"LDL {ldl_now:.0f} mg/dL / HbA1c {a1c_now:.1f}%"
                if lang == "en"
                else (
                    f"{int(age)}歳・{sex_label}／"
                    f"身長 {height_cm:.1f} cm・体重 {weight_kg:.1f} kg／"
                    f"血圧 {int(round(sbp_now))}/{int(round(dbp_now))} mmHg／"
                    f"LDL {ldl_now:.0f} mg/dL・HbA1c {a1c_now:.1f}%"
                )
            )
            meds_text = ("、".join(medication_names) if medication_names else ui["meds_none"]) if lang != "en" else (", ".join(medication_names) if medication_names else ui["meds_none"])
            st.write(ui["meds"] + meds_text)
    diagnosis_signature = (
        round(float(sbp_now or 0), 1), round(float(dbp_now or 0), 1),
        round(float(ldl_now), 1), round(float(a1c_now), 1), tuple(medication_names),
    )
    diagnosis_signature_key = f"{p}_diagnosis_signature"
    if st.session_state.get(diagnosis_signature_key) != diagnosis_signature:
        st.session_state[f"{p}_dx_dm"] = diagnoses["diabetes"]
        st.session_state[f"{p}_dx_htn"] = diagnoses["hypertension"]
        st.session_state[f"{p}_dx_dl"] = diagnoses["dyslipidemia"]
        st.session_state[diagnosis_signature_key] = diagnosis_signature

    # --- 計画書の追加項目 ---
    with st.expander(ui["manual"]):
        st.caption(ui["manual_cap"])

        st.markdown(ui["dx"])
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            dx_dm = st.checkbox(ui["dm"], key=f"{p}_dx_dm")
        with dcol2:
            dx_htn = st.checkbox(ui["htn"], key=f"{p}_dx_htn")
        with dcol3:
            dx_dl = st.checkbox(ui["dl"], key=f"{p}_dx_dl")

        mcol1, mcol2 = st.columns(2)
        with mcol1:
            if height_cm is not None:
                weight_input = st.number_input(
                    ui["wt_bmi"],
                    min_value=20.0, max_value=200.0, value=ideal_weight_kg(height_cm),
                    step=0.1, key=f"{p}_weight",
                )
            else:
                weight_input = st.number_input(
                    ui["wt_manual"],
                    min_value=0.0, max_value=200.0, value=0.0,
                    step=0.1, key=f"{p}_weight",
                )
        with mcol2:
            nutrition_input = st.selectbox(
                ui["nutrition"],
                [ui["nutrition_skip"], *pdf_fill.NUTRITION_OPTIONS],
                key=f"{p}_nutrition",
            )

        st.markdown(ui["life"])
        life_options = list(LIFESTYLE_GOALS)
        lifestyle_items = st.multiselect(
            ui["life_items"],
            life_options,
            format_func=(lambda k: _LIFESTYLE_TOPIC_EN.get(k, k) if lang == "en" else k),
            default=[ui["default_life"]] if not medication_names else [],
            key=f"{p}_lifestyle",
        )
        intervention_instructions, intervention_goals = _plan_items_for_interventions(lifestyle_interventions)
        goal_candidates = list(dict.fromkeys([*suggested_goals(lifestyle_items), *intervention_goals]))
        instruction_candidates = list(dict.fromkeys([*suggested_instructions(lifestyle_items), *intervention_instructions]))
        lifestyle_signature = (tuple(lifestyle_items), tuple(lifestyle_interventions))
        lifestyle_signature_key = f"{p}_lifestyle_signature"
        if st.session_state.get(lifestyle_signature_key) != lifestyle_signature:
            st.session_state[f"{p}_selected_instructions"] = instruction_candidates
            st.session_state[f"{p}_selected_goals"] = goal_candidates
            st.session_state[lifestyle_signature_key] = lifestyle_signature
        selected_instructions = st.multiselect(
            ui["instr"],
            list(pdf_fill.PLAN_INSTRUCTION_FIELDS),
            key=f"{p}_selected_instructions",
        )
        selected_goals = st.multiselect(
            ui["goals"],
            goal_candidates,
            key=f"{p}_selected_goals",
        )
        additional_goal = st.text_area(
            ui["extra_goal"],
            key=f"{p}_freetext",
            placeholder=ui["extra_ph"],
        )
        achievement_status = st.text_area(
            ui["achieve"],
            key=f"{p}_achievement",
            placeholder=ui["achieve_ph"],
        )
        treatment_plan_status = None
        if treatment_benefit:
            treatment_plan_status = st.radio(
                ui["backcast_eval"],
                [ui["backcast_ok"], ui["backcast_improve"]],
                key=f"{p}_backcast_plan_status",
            )

    # --- PlanInput 組み立て ---
    plan = pdf_fill.PlanInput(
        sex=sex,
        age=int(age),
        visit_type="initial" if visit_label in (ui["visit_first"], "初回") else "continued",
        created=date.today(),
        sbp_tgt=int(round(sbp_tgt_manual)) if inc_bp else None,
        dbp_tgt=int(dbp_tgt_input) if inc_bp else None,
        bmi_target=bmi_value,
        a1c_tgt=float(a1c_tgt_manual) if inc_a1c_tgt else None,
        ldl_now=int(round(ldl_now)) if inc_ldl else None,
        a1c_now=float(a1c_now) if inc_a1c_now else None,
    )

    ready_key = f"{p}_plan_ready"
    if st.button(ui["ready"], key=f"{p}_plan_make"):
        st.session_state[ready_key] = True

    if not st.session_state.get(ready_key):
        return

    fv = pdf_fill.build_field_values(plan)

    # 確認画面（決定5）: 書き込む値を表示し、ここで最終調整できる。空欄行は記入しない。
    st.markdown(ui["review"])
    st.caption(ui["review_cap"])
    field_order = list(fv.text.keys())
    # st.data_editor は内部で DataFrame を PyArrow に変換する。Railway の
    # pandas/PyArrow 組み合わせでは、この変換がネイティブ層で segfault して
    # アプリ全体を再起動させるため、通常のテキスト入力で確認・編集する。
    edited_values = []
    for index, fname in enumerate(field_order):
        edited_values.append(
            st.text_input(
                label_map.get(fname, fname),
                value=fv.text[fname],
                key=f"{p}_plan_value_{index}",
            )
        )
    st.caption(ui["privacy"])

    # 編集後の値で FieldValues を再構築（値があれば連動チェックもON）
    fv_final = pdf_fill.FieldValues()
    for fname, val in zip(field_order, edited_values):
        val = "" if val is None else str(val).strip()
        if not val:
            continue
        fv_final.text[fname] = val
        chk = pdf_fill.FIELD_CONNECTED_CHECK.get(fname)
        if chk:
            fv_final.checks[chk] = True

    # 手入力項目（Step 4-B）を反映
    for on, cb in (
        (dx_dm, pdf_fill.C_DX_DIABETES),
        (dx_htn, pdf_fill.C_DX_HYPERTENSION),
        (dx_dl, pdf_fill.C_DX_DYSLIPIDEMIA),
    ):
        if on:
            fv_final.checks[cb] = True
    for instruction in selected_instructions:
        fv_final.checks[pdf_fill.PLAN_INSTRUCTION_FIELDS[instruction]] = True
    if weight_input and weight_input > 0:
        fv_final.text[pdf_fill.F_WEIGHT] = f"{weight_input:.1f}"
        fv_final.checks[pdf_fill.C_WEIGHT] = True
    if nutrition_input in pdf_fill.NUTRITION_OPTIONS:
        fv_final.text[pdf_fill.F_NUTRITION] = nutrition_input
        fv_final.checks[pdf_fill.C_NUTRITION] = True
    final_goals = list(selected_goals)
    if additional_goal and additional_goal.strip():
        final_goals.append(additional_goal.strip())
    if treatment_benefit:
        final_goals.append(ui["maintain"])
    if final_goals:
        fv_final.text[pdf_fill.F_PLAN_FREETEXT] = "／".join(final_goals)
    final_achievement = achievement_status.strip() if achievement_status else ""
    if not final_achievement and treatment_plan_status:
        final_achievement = treatment_plan_status
    if final_achievement:
        fv_final.text[pdf_fill.F_ACHIEVEMENT_STATUS] = final_achievement

    # 区分（初回/継続）
    if plan.visit_type == "initial":
        fv_final.checks[pdf_fill.F_VISIT_FIRST] = True
    else:
        fv_final.checks[pdf_fill.F_VISIT_CONT] = True

    pdf_bytes = pdf_fill.fill_pdf(fv_final)
    st.download_button(
        ui["download_plan"],
        data=pdf_bytes,
        file_name=(
            f"care_plan_{date.today():%Y%m%d}.pdf"
            if lang == "en"
            else f"療養計画書_{date.today():%Y%m%d}.pdf"
        ),
        mime="application/pdf",
        key=f"{p}_plan_dl",
        type="primary",
    )

    if height_cm is not None and weight_kg is not None and sbp_now is not None and dbp_now is not None:
        st.markdown("#### Patient handout" if lang == "en" else "#### 患者さん向け資料")
        if (risk_curves and risk_horizon_years) or treatment_benefit:
            selected_diagnoses = [
                label for enabled, label in (
                    (dx_dm, ui["dm"]), (dx_htn, ui["htn"]), (dx_dl, ui["dl"])
                ) if enabled
            ]
            report_treatment_benefit = dict(treatment_benefit or {})
            if treatment_plan_status:
                report_treatment_benefit["plan_status"] = treatment_plan_status
            report_pdf = generate_patient_report_pdf(
                age=int(age),
                sex_label=ui["male"] if sex == "male" else ui["female"],
                height_cm=height_cm,
                weight_kg=weight_kg,
                current_values={"sbp": sbp_now, "ldl": ldl_now, "a1c": a1c_now},
                target_values={
                    "sbp": sbp_after if sbp_after is not None else sbp_tgt_manual,
                    "ldl": ldl_after if ldl_after is not None else ldl_now,
                    "a1c": a1c_after if a1c_after is not None else a1c_tgt_manual,
                },
                diagnoses=selected_diagnoses,
                medications=medication_names,
                lifestyle_interventions=lifestyle_interventions,
                instructions=selected_instructions,
                goals=final_goals,
                risks=risk_curves,
                horizon_years=risk_horizon_years,
                treatment_benefit=report_treatment_benefit or None,
                lang=lang,
            )
            st.success(
                "Compiled current status, lab changes, mortality/MI/stroke risk differences, "
                "trend charts, and agreed goals into a 2-page handout."
                if lang == "en"
                else (
                    "現在の状態、介入前後の検査値、全死亡・心筋梗塞・脳卒中の"
                    "リスク差と推移グラフ、相談して決めた目標を2ページにまとめました。"
                )
            )
            st.download_button(
                ui["download_patient"],
                data=report_pdf,
                file_name=(
                    f"patient_handout_{date.today():%Y%m%d}.pdf"
                    if lang == "en"
                    else f"健康づくりプラン_{date.today():%Y%m%d}.pdf"
                ),
                mime="application/pdf",
                key=f"{p}_patient_report_dl",
                type="primary",
            )
        else:
            st.info(
                "Run the risk calculation to create a graphed patient handout."
                if lang == "en"
                else "リスク計算を実行すると、グラフ付き患者さん向け資料を作成できます。"
            )