"""PC-only pharmacist counseling UI. Never writes simulation input keys."""
from __future__ import annotations

import streamlit as st

from pharmacist_guidance import (
    BY_ID, GUIDES, GENERAL, EMERGENCY, DIABETES_GROUPS, LOW_GLUCOSE,
    LOW_GLUCOSE_URL, SICK_DAY_URL, SGLT2_URL, REVIEWED_ON, VERSION,
    candidate_ids, selection_alerts, export_ready, handout_html,
)


def clear_counseling():
    """Explicit new-patient action; discard only this module's session fields."""
    for key in list(st.session_state):
        if key.startswith("pharm_"):
            del st.session_state[key]
    st.session_state["pharm_selection"] = []


def _import_candidates(ids):
    clear_counseling()
    st.session_state["pharm_selection"] = list(ids)


def invalidate_review(signature):
    """Changes to any handout content require fresh confirmation (even on revert)."""
    if st.session_state.get("pharm_signature") != signature:
        st.session_state["pharm_actual_confirmed"] = False
        st.session_state["pharm_reviewed"] = False
        st.session_state["pharm_signature"] = signature


def render_pharmacist_mode(selected_meds, bone_key="none"):
    with st.container(border=True):
        st.markdown("### 薬剤師の服薬指導")
        st.caption(
            f"全{len(GUIDES)}薬剤の指導用データ／資料確認日 {REVIEWED_ON}。"
            "この欄で薬を選んでも、予防効果の試算や処方は変更されません。"
        )
        st.warning("試算の薬は実際の処方とは限りません。お薬手帳・薬袋と照合してから患者さんへ説明してください。成人向けの補助情報で、全禁忌・副作用・相互作用のチェックではありません。")
        st.error(EMERGENCY)
        candidates, missing = candidate_ids(selected_meds, bone_key)
        if candidates:
            st.caption("試算の候補（未確認）：" + " / ".join(BY_ID[key].name for key in candidates))
        if missing:
            st.warning("指導データ未登録の候補があります。処方を原資料で確認してください：" + " / ".join(missing))
        st.button(
            "試算の薬を指導候補に取り込む", key="pharm_import", disabled=not candidates,
            on_click=_import_candidates, args=(tuple(candidates),),
            help="指導欄の薬・メモ・確認状態を置き換えます。実薬の用法は自動入力しません。",
        )
        st.button("新しい患者さん・指導欄をクリア", key="pharm_clear", on_click=clear_counseling)
        ids = st.multiselect(
            "指導する薬（検索して追加・複数選択可）", list(BY_ID),
            format_func=lambda key: BY_ID[key].name, key="pharm_selection",
            help="糖尿病のチェックに関係なく全薬剤を選べます。登録外の薬・配合剤は個別に原資料を確認してください。",
        )
        if not ids:
            invalidate_review((VERSION, ()))
            st.info("指導する薬を選ぶと、薬別の注意点とシックデイ対応が縦に表示されます。")
            return
        alerts = selection_alerts(ids)
        for level, message in alerts:
            (st.error if level == "block" else st.warning)(message)
        if any(level == "block" for level, _ in alerts):
            st.caption("禁忌の組合せが解消されるまで患者用資料は作成できません。アプリの表示だけで薬を中止せず、処方医へ確認してください。")
        st.markdown("**全てのお薬に共通すること**")
        for message in GENERAL:
            st.write(message)
        if any(BY_ID[key].group in DIABETES_GROUPS for key in ids):
            with st.expander("低血糖・シックデイの共通説明", expanded=True):
                st.write(LOW_GLUCOSE)
                st.caption("水分の量は心不全・腎臓病などの指示に合わせます。インスリンは一律に中断せず、事前の個別指示を確認してください。")
                st.markdown(f"[低血糖の対応]({LOW_GLUCOSE_URL}) ／ [シックデイの対応]({SICK_DAY_URL})")
        regimens, notes = {}, {}
        for key in ids:
            guide, content = BY_ID[key], BY_ID[key].content
            with st.container(border=True):
                st.markdown(f"#### {guide.name}")
                st.markdown(f"**{content.focus}**")
                regimens[key] = st.text_input(
                    "実薬の製品・剤形・用量・回数", key=f"pharm_regimen_{key}",
                    placeholder="薬袋・お薬手帳で確認して入力",
                    help="試算用の用量は転記しません。骨粗鬆症薬は剤形・投与間隔も確認してください。",
                )
                for title, messages in (
                    ("普段の注意", content.routine),
                    ("体調が悪いとき", content.sick),
                    ("すぐ相談・受診する症状", content.urgent),
                    ("飲み忘れ・注射忘れ", (content.missed,)),
                ):
                    st.markdown(f"**{title}**")
                    for message in messages:
                        st.write(message)
                notes[key] = st.text_area(
                    "処方医に確認した個別指示（任意）", key=f"pharm_note_{key}", height=90,
                    placeholder="休薬・再開の条件、相談する血圧や血糖の目安、指示を確認した日など",
                    help="未確認の指示は記入しないでください。患者氏名などの個人識別情報は不要です。",
                )
                st.markdown(f"[根拠：PMDA 添付文書・患者向け情報]({guide.source_url})")
                if guide.group == "sglt2":
                    st.markdown(f"[日本糖尿病学会：SGLT2阻害薬の適正使用]({SGLT2_URL})")
        contact = st.text_input("相談先の医療機関・薬局と電話番号（任意）", key="pharm_contact")
        signature = (VERSION, tuple(sorted((key, regimens[key], notes[key]) for key in ids)), contact)
        invalidate_review(signature)
        actual = st.checkbox(
            "薬剤師として、実際の服用薬・製品・用法を薬袋等と照合した", key="pharm_actual_confirmed",
        )
        reviewed = st.checkbox(
            "注意点・個別指示を確認し、患者さんと対応方法を確認した（未解決の疑義なし）",
            key="pharm_reviewed",
        )
        ready = export_ready(ids, regimens, actual_confirmed=actual, reviewed=reviewed)
        if not ready:
            st.caption("全薬剤の実薬の用法を入力し、2つの確認にチェックすると保存できます。内容を変更すると確認チェックは解除されます。")
        data = handout_html(ids, regimens, notes, contact, actual_confirmed=actual, reviewed=reviewed) if ready else ""
        st.download_button(
            "患者用の説明メモを保存（印刷用）", data=data, file_name="medication-counseling.html",
            mime="text/html", disabled=not ready, key="pharm_download",
        )
        st.caption("保存したHTMLをブラウザで開くと印刷できます。入力は指導欄の一時データで、カルテへの記録ではありません。患者さんが変わる際は指導欄をクリアしてください。")

