"""Insurance controls and after-reimbursement estimates for selected medicines."""
import streamlit as st

from medical_costs import (
    INCOME_LABELS, SOURCE_URL, estimate_outpatient_costs, income_options,
    medication_schedule, yen,
)


def render_medication_costs(medications: list[dict], *, age: int, continuing: bool):
    st.markdown("##### 保険・自己負担額")
    band = "under70" if age < 70 else "70to74" if age < 75 else "75plus"
    rates = [3, 10] if age < 70 else [2, 3, 10] if age < 75 else [1, 2, 3, 10]
    rate = st.segmented_control(
        "保険の自己負担割合", rates, default=rates[0], required=True,
        format_func=lambda x: "保険なし（10割）" if x == 10 else f"{x}割負担",
        key=f"cost_copay_{band}",
    )
    first_year = False
    if any("インクリシラン" in m["key"] for m in medications):
        first_year = st.radio(
            "レクビオの投与期間", ["初年度（3回）", "維持期（年2回）"],
            index=1 if continuing else 0, horizontal=True, key="cost_inclisiran_phase",
        ).startswith("初年度")
    income = None
    history = []
    if rate != 10:
        options = income_options(age, rate)
        labels = dict(INCOME_LABELS)
        if age >= 70:
            labels.update({"a": "現役並み所得Ⅲ", "b": "現役並み所得Ⅱ", "c": "現役並み所得Ⅰ"})
        income = st.selectbox(
            "高額療養費の所得区分", options, index=None,
            format_func=lambda k: labels[k], placeholder="保険者の認定区分を選択",
            key=f"cost_income_{band}_{rate}",
        )
        st.caption("年収は目安です。国保・被用者保険などで判定基準が異なるため、保険者の認定区分を選んでください。")
        with st.expander("多数回該当の履歴（該当する場合）", expanded=False):
            history = st.multiselect(
                "同じ保険で高額療養費に該当した月", list(range(-11, 0)),
                format_func=lambda i: f"{2026 + (7+i)//12}年{(7+i)%12+1}月",
                key="cost_previous_hits",
            )
            st.caption("未選択は過去の該当なしとして試算。70歳以上の外来個人上限だけに達した月は含めません。")
    st.caption("2026年8月～2027年7月の制度・12か月で試算。年齢・所得区分・保険は期間中同じと仮定します。")
    try:
        schedule = medication_schedule(medications, inclisiran_first_year=first_year)
    except ValueError as exc:
        st.error(str(exc))
        return
    gross = sum(schedule["monthly_gross"])
    if rate != 10 and income is None:
        columns = st.columns(2)
        columns[0].metric("年間薬剤費（10割）", f"{yen(gross):,} 円")
        columns[1].metric("年間自己負担（高額療養費適用前）", f"{yen(gross*rate/10):,} 円")
        st.info("所得区分を選ぶと、高額療養費を自動適用した自己負担額を表示します。")
    else:
        result = estimate_outpatient_costs(
            schedule["monthly_gross"], age=age, copay=rate, income=income,
            previous_hit_months=history,
        )
        columns = st.columns(2)
        columns[0].metric("年間自己負担（適用後・概算）", f"{yen(result['after']):,} 円")
        columns[1].metric("月平均の自己負担", f"{yen(result['after']/12):,} 円")
        st.caption(
            f"薬剤費10割：{yen(result['gross']):,}円/年 ／ "
            f"高額療養費適用前：{yen(result['before']):,}円/年 ／ "
            f"軽減見込：{yen(result['total_relief']):,}円/年"
        )
        if rate != 10:
            st.caption("高額療養費は自動計算済みです。表示は払い戻し後の概算で、窓口支払額や自動申請を示すものではありません。")
        with st.expander("月別の費用・高額療養費", expanded=False):
            st.dataframe([
                {"診療月": r["month"], "薬剤費10割（円）": yen(r["gross"]),
                 "適用前自己負担（円）": yen(r["before"]),
                 "月額上限適用後（円）": yen(r["after_monthly"]),
                 "月単位の軽減額（円）": yen(r["monthly_relief"]),
                 "多数回該当": "適用" if r["multiple"] else "―"}
                for r in result["months"]
            ], hide_index=True, width="stretch")
            st.write(f"年間上限による追加の払い戻し見込：{yen(result['annual_relief']):,} 円")
            st.caption("年間上限は8月～翌7月の集計後に適用。月平均は家計の目安で、毎月の請求額ではありません。")
    with st.expander("薬剤費の内訳・計算条件", expanded=False):
        st.dataframe(schedule["details"], hide_index=True, width="stretch")
        st.caption(
            "同じ医療機関からの外来処方と調剤薬局分を合算する想定です。"
            "内服は毎月処方、週1回・隔週注射は8月1日から投与月に計上（53回・27回）。"
            "処方日・まとめ処方・他院受診によって実際の負担は変わります。"
        )
        st.caption(
            "この薬剤欄で選んだ薬の費用のみ。診察・検査・調剤・注射手技・針代、"
            "骨の健康欄の薬剤、他の医療費・世帯合算・自治体助成・付加給付は含みません。"
        )
        st.caption("ビクトーザ等の複数回使用ペンは消費量按分。レクビオは初年度8・11・5月、維持期8・2月に計上します。")
        st.markdown(f"[制度と自己負担限度額の出典（協会けんぽ）]({SOURCE_URL})")
