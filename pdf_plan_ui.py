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
    PLAN_GOAL_FIELD_CAPACITY,
    PLAN_GOAL_MAX_ITEMS,
    build_plan_goal_text,
    goal_text_width,
    ideal_weight_kg,
    infer_diagnoses,
    suggested_goals,
    suggested_instructions,
)

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

# (指導項目, 達成目標)。達成目標は【①達成目標】欄に印字されるため全角10字以内に保つ
# （plan_logic.PLAN_GOAL_FIELD_CAPACITY 参照）。指導項目はチェックボックスなので字数制限なし。
_INTERVENTION_PLAN_ITEMS = {
    "減塩": (["食塩・調味料を控える"], ["食塩1日6g未満"]),
    "糖質制限": (["食事摂取量を適正にする", "間食を減らす"], ["糖質と甘い飲料を制限"]),
    "飽和脂肪制限": (["油を使った料理の摂取を減らす"], ["飽和脂肪を減らす"]),
    "中強度有酸素運動": (["運動処方", "日常生活の活動量を増やす"], ["中強度運動を週150分"]),
    "有酸素＋筋力トレーニング": (["運動処方", "日常生活の活動量を増やす"], ["有酸素＋筋トレ週2回"]),
    "高強度インターバル運動": (["運動処方", "運動時の注意事項を確認する"], ["安全確認し高強度運動"]),
}

# 反実仮想の結果は詳細版を患者さん向け資料へ載せ、達成目標欄には短縮版を入れる
# （詳細版は49字あり、21.4字の欄には入らないため）。
_TREATMENT_BENEFIT_PLAN_GOAL = "服薬を続け効果を維持"


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
) -> None:
    """
    療養計画書の作成セクションを描画する。

    「目標」は医師が設定する目標そのもの。目標スライダー（sbp_tgt_manual /
    a1c_tgt_manual）を直接使う。use_meds ON時の有効目標値（薬剤計算の予測到達値）は
    目標欄には使わない（設計判断A）。氏名・生年月日等は決定1で空欄・手書き。
    """
    p = key_prefix

    st.divider()
    st.markdown("## 📄 療養計画書を作成")
    st.caption(
        "アプリが持つ値を療養計画書（別紙様式9）に記入します。"
        "シミュレーターの患者情報・検査値・服薬内容を引き継ぎます。"
        "主病名は検査値と服薬内容から候補を示すため、必ず確認してください。"
    )

    # --- 計画書に固有の入力 ---
    col_v, col_d = st.columns(2)
    with col_v:
        visit_label = st.radio("区分", ["初回", "継続"], horizontal=True, key=f"{p}_plan_visit")
    with col_d:
        dbp_tgt_input = st.number_input(
            "目標拡張期血圧 (mmHg)", min_value=50, max_value=120, value=80, step=1,
            key=f"{p}_plan_dbp",
            help="収縮期は自動で入ります。拡張期はここで指定（帳票は 130/80 の形式）",
        )

    # --- 載せる項目（決定5: 既定値の誤記入を避けるため人が選ぶ） ---
    st.markdown("**計画書に載せる項目**（チェックした値だけ記入されます）")
    c1, c2 = st.columns(2)
    with c1:
        inc_bp = st.checkbox("目標血圧", value=True, key=f"{p}_inc_bp")
        inc_a1c_tgt = st.checkbox("目標HbA1c", value=True, key=f"{p}_inc_a1ctgt")
    with c2:
        inc_ldl = st.checkbox("実測LDL", value=True, key=f"{p}_inc_ldl")
        inc_a1c_now = st.checkbox("実測HbA1c", value=True, key=f"{p}_inc_a1cnow")

    # BMI: アプリがBMIを持つ（PC）ならチェックで制御、持たない（モバイル）なら手入力
    if bmi_target is not None:
        inc_bmi = st.checkbox("目標BMI", value=True, key=f"{p}_inc_bmi")
        bmi_value = float(bmi_target) if inc_bmi else None
    else:
        bmi_in = st.number_input(
            "目標BMI（0＝記入しない）", min_value=0.0, max_value=50.0, value=0.0, step=0.1,
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
            st.markdown("**一次予防モデルから引き継いだ内容**")
            st.write(
                f"{int(age)}歳・{'男性' if sex == 'male' else '女性'}／"
                f"身長 {height_cm:.1f} cm・体重 {weight_kg:.1f} kg／"
                f"血圧 {int(round(sbp_now))}/{int(round(dbp_now))} mmHg／"
                f"LDL {ldl_now:.0f} mg/dL・HbA1c {a1c_now:.1f}%"
            )
            st.write("服薬内容: " + ("、".join(medication_names) if medication_names else "なし／未入力"))
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
    with st.expander("✍ 手入力項目（主病名・体重・栄養状態・行動目標）"):
        st.caption("自動入力された候補を確認し、患者さんとの相談内容に合わせて修正してください。")

        st.markdown("**主病名の候補**（検査値または該当薬から自動チェック・確定診断ではありません）")
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            dx_dm = st.checkbox("糖尿病", key=f"{p}_dx_dm")
        with dcol2:
            dx_htn = st.checkbox("高血圧症", key=f"{p}_dx_htn")
        with dcol3:
            dx_dl = st.checkbox("脂質異常症", key=f"{p}_dx_dl")

        mcol1, mcol2 = st.columns(2)
        with mcol1:
            if height_cm is not None:
                weight_input = st.number_input(
                    "目標体重 (kg)（BMI 22から自動計算）",
                    min_value=20.0, max_value=200.0, value=ideal_weight_kg(height_cm),
                    step=0.1, key=f"{p}_weight",
                )
            else:
                weight_input = st.number_input(
                    "目標体重 (kg)（0＝記入しない）",
                    min_value=0.0, max_value=200.0, value=0.0,
                    step=0.1, key=f"{p}_weight",
                )
        with mcol2:
            nutrition_input = st.selectbox(
                "栄養状態",
                ["（記入しない）", *pdf_fill.NUTRITION_OPTIONS],
                key=f"{p}_nutrition",
            )

        st.markdown("**生活習慣から指導項目・行動目標を選ぶ**")
        lifestyle_items = st.multiselect(
            "生活習慣・相談事項",
            list(LIFESTYLE_GOALS),
            default=["運動不足"] if not medication_names else [],
            key=f"{p}_lifestyle",
        )
        intervention_instructions, intervention_goals = _plan_items_for_interventions(lifestyle_interventions)
        goal_candidates = list(dict.fromkeys([*suggested_goals(lifestyle_items), *intervention_goals]))
        instruction_candidates = list(dict.fromkeys([*suggested_instructions(lifestyle_items), *intervention_instructions]))
        lifestyle_signature = (tuple(lifestyle_items), tuple(lifestyle_interventions))
        lifestyle_signature_key = f"{p}_lifestyle_signature"
        if st.session_state.get(lifestyle_signature_key) != lifestyle_signature:
            st.session_state[f"{p}_selected_instructions"] = instruction_candidates
            # 初期値は計画書に入る分だけ。全件入れると既定で溢れ警告が出続け、
            # 警告そのものが見過ごされるようになるため。追加は医師が行う。
            st.session_state[f"{p}_selected_goals"] = goal_candidates[:PLAN_GOAL_MAX_ITEMS]
            st.session_state[lifestyle_signature_key] = lifestyle_signature
        selected_instructions = st.multiselect(
            "療養計画書にチェックする指導項目",
            list(pdf_fill.PLAN_INSTRUCTION_FIELDS),
            key=f"{p}_selected_instructions",
        )
        selected_goals = st.multiselect(
            f"目標（計画書には上から{PLAN_GOAL_MAX_ITEMS}件・患者さん向け資料には全件）",
            goal_candidates,
            key=f"{p}_selected_goals",
            help=(
                "達成目標欄は1行しかないため、計画書に入るのは先に選んだ"
                f"{PLAN_GOAL_MAX_ITEMS}件だけです。それ以降は資料にのみ載ります。"
            ),
        )
        additional_goal = st.text_area(
            "追加の達成目標・行動目標",
            key=f"{p}_freetext",
            placeholder="患者さんと相談して決めた内容を追加",
        )

        # 患者さん向け資料には全件・詳細版を載せ、計画書の達成目標欄には収まる分だけ入れる。
        final_goals = list(selected_goals)
        if additional_goal and additional_goal.strip():
            final_goals.append(additional_goal.strip())
        plan_goals = list(final_goals)
        if treatment_benefit:
            years = int(treatment_benefit.get("treatment_years", 0))
            events = treatment_benefit.get("event_effects", {})
            mi_stroke = float(events.get("mi", {}).get("avoided", 0.0)) + float(
                events.get("stroke", {}).get("avoided", 0.0)
            )
            final_goals.append(
                f"服薬継続{years}年で得られた検査値改善と、心筋梗塞・脳卒中の推定回避効果"
                f"（100人あたり約{mi_stroke:.1f}件）を維持する"
            )
            plan_goals.append(_TREATMENT_BENEFIT_PLAN_GOAL)
        plan_goal_text, dropped_goals = build_plan_goal_text(plan_goals)
        # 何が印字され何が落ちるかを入力欄の直下で見せる。上限で選択を止めると
        # 他の候補が見えなくなるため、選択は自由にして印字側だけ絞る。
        st.caption(
            f"計画書に印字: {plan_goal_text or '（なし）'}"
            f"　{goal_text_width(plan_goal_text):.1f}／{PLAN_GOAL_FIELD_CAPACITY:.1f}字"
        )
        if dropped_goals:
            st.caption("患者さん向け資料のみ: " + "／".join(dropped_goals))
            # 印字されるのは選択順の先頭から。multiselectに並び替えが無いため、
            # 入れ替え方（外して選び直す）を溢れているときだけ明示する。
            st.caption(
                "計画書に載る順番は選んだ順です。入れ替えるには、載せたい目標を"
                "タグの × で一度外して選び直してください。"
            )

        achievement_status = st.text_area(
            "目標の達成状況（継続の場合のみ）",
            key=f"{p}_achievement",
            placeholder="継続受診時、前回目標の達成状況を記入",
        )
        treatment_plan_status = None
        if treatment_benefit:
            treatment_plan_status = st.radio(
                "反実仮想の結果を踏まえた評価・方針",
                [
                    "現在の治療で目標は達成できている。治療を継続する",
                    "一定の成果は得られている。さらに改善を目指す",
                ],
                key=f"{p}_backcast_plan_status",
            )

    # --- PlanInput 組み立て ---
    plan = pdf_fill.PlanInput(
        sex=sex,
        age=int(age),
        visit_type="initial" if visit_label == "初回" else "continued",
        created=date.today(),
        sbp_tgt=int(round(sbp_tgt_manual)) if inc_bp else None,
        dbp_tgt=int(dbp_tgt_input) if inc_bp else None,
        bmi_target=bmi_value,
        a1c_tgt=float(a1c_tgt_manual) if inc_a1c_tgt else None,
        ldl_now=int(round(ldl_now)) if inc_ldl else None,
        a1c_now=float(a1c_now) if inc_a1c_now else None,
    )

    ready_key = f"{p}_plan_ready"
    if st.button("📄 記入内容を確認する", key=f"{p}_plan_make"):
        st.session_state[ready_key] = True

    if not st.session_state.get(ready_key):
        return

    fv = pdf_fill.build_field_values(plan)

    # 確認画面（決定5）: 書き込む値を表示し、ここで最終調整できる。空欄行は記入しない。
    st.markdown("#### 記入内容（この値が印字されます・編集可）")
    st.caption("数値や内容はここで最終調整できます。空欄にするとその項目は印字されません。")
    field_order = list(fv.text.keys())
    # st.data_editor は内部で DataFrame を PyArrow に変換する。Railway の
    # pandas/PyArrow 組み合わせでは、この変換がネイティブ層で segfault して
    # アプリ全体を再起動させるため、通常のテキスト入力で確認・編集する。
    edited_values = []
    for index, fname in enumerate(field_order):
        edited_values.append(
            st.text_input(
                _LABEL_MAP.get(fname, fname),
                value=fv.text[fname],
                key=f"{p}_plan_value_{index}",
            )
        )
    st.caption(
        "氏名・生年月日は個人情報保護のため空欄です。未入力の項目は印刷後に手書きできます。"
    )

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
    if plan_goal_text:
        fv_final.text[pdf_fill.F_PLAN_FREETEXT] = plan_goal_text
    if dropped_goals:
        # 溢れた分はPDF上で黙って消えるため、印刷前の確認画面で必ず知らせる。
        st.warning(
            "達成目標欄（1行・全角"
            f"{PLAN_GOAL_FIELD_CAPACITY:.1f}字）に入らないため、次の目標は計画書に"
            "**印字されません**（患者さん向け資料には載ります）: "
            + "／".join(dropped_goals)
        )
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
        "⬇ PDFをダウンロード",
        data=pdf_bytes,
        file_name=f"療養計画書_{date.today():%Y%m%d}.pdf",
        mime="application/pdf",
        key=f"{p}_plan_dl",
        type="primary",
    )

    if height_cm is not None and weight_kg is not None and sbp_now is not None and dbp_now is not None:
        st.markdown("#### 患者さん向け資料")
        if (risk_curves and risk_horizon_years) or treatment_benefit:
            selected_diagnoses = [
                label for enabled, label in (
                    (dx_dm, "糖尿病"), (dx_htn, "高血圧症"), (dx_dl, "脂質異常症")
                ) if enabled
            ]
            report_treatment_benefit = dict(treatment_benefit or {})
            if treatment_plan_status:
                report_treatment_benefit["plan_status"] = treatment_plan_status
            report_pdf = generate_patient_report_pdf(
                age=int(age),
                sex_label="男性" if sex == "male" else "女性",
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
            )
            st.success(
                "現在の状態、介入前後の検査値、全死亡・心筋梗塞・脳卒中の"
                "リスク差と推移グラフ、相談して決めた目標を2ページにまとめました。"
            )
            st.download_button(
                "⬇ グラフ付き患者さん向け資料（PDF）",
                data=report_pdf,
                file_name=f"健康づくりプラン_{date.today():%Y%m%d}.pdf",
                mime="application/pdf",
                key=f"{p}_patient_report_dl",
                type="primary",
            )
        else:
            st.info("リスク計算を実行すると、グラフ付き患者さん向け資料を作成できます。")
