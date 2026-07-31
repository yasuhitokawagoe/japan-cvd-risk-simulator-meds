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
from typing import Optional

import streamlit as st

import pdf_fill

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


def render_plan_section(
    *,
    sex: str,
    age: float,
    ldl_now: float,
    a1c_now: float,
    sbp_tgt_manual: float,
    a1c_tgt_manual: float,
    bmi_target: Optional[float] = None,
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
        "氏名・生年月日・主病名などは空欄のまま。印刷後に手書きで補ってください。"
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

    # --- 手入力項目（Step 4-B。アプリが値を持たない欄。空欄なら記入されない） ---
    with st.expander("✍ 手入力項目（主病名・体重・栄養状態・行動目標）"):
        st.caption("アプリが値を持たない欄です。入力したものだけ記入されます（空欄は手書き）。")

        st.markdown("**主病名**（該当にチェック。自動推定はしません）")
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            dx_dm = st.checkbox("糖尿病", key=f"{p}_dx_dm")
        with dcol2:
            dx_htn = st.checkbox("高血圧症", key=f"{p}_dx_htn")
        with dcol3:
            dx_dl = st.checkbox("脂質異常症", key=f"{p}_dx_dl")

        mcol1, mcol2 = st.columns(2)
        with mcol1:
            weight_input = st.number_input(
                "目標体重 (kg)（0＝記入しない）",
                min_value=0.0, max_value=200.0, value=0.0, step=0.1, key=f"{p}_weight",
            )
        with mcol2:
            nutrition_input = st.selectbox(
                "栄養状態",
                ["（記入しない）", *pdf_fill.NUTRITION_OPTIONS],
                key=f"{p}_nutrition",
            )

        plan_freetext = st.text_area(
            "達成目標・行動目標（自由記述）",
            key=f"{p}_freetext",
            placeholder="例）1日8000歩を目標にする／間食を1日1回までにする",
        )
        achievement_status = st.text_area(
            "目標の達成状況（継続の場合のみ）",
            key=f"{p}_achievement",
            placeholder="継続受診時、前回目標の達成状況を記入",
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
        "空欄（手書き）: 氏名・生年月日・主病名・行動目標・食事/運動/喫煙指導・栄養状態"
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
    if weight_input and weight_input > 0:
        fv_final.text[pdf_fill.F_WEIGHT] = f"{weight_input:.1f}"
        fv_final.checks[pdf_fill.C_WEIGHT] = True
    if nutrition_input in pdf_fill.NUTRITION_OPTIONS:
        fv_final.text[pdf_fill.F_NUTRITION] = nutrition_input
        fv_final.checks[pdf_fill.C_NUTRITION] = True
    if plan_freetext and plan_freetext.strip():
        fv_final.text[pdf_fill.F_PLAN_FREETEXT] = plan_freetext.strip()
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
        key=f"{p}_plan_dl",
        type="primary",
    )
