#!/usr/bin/env python3
"""One-shot translator for app_streamlit_outcomes.py UI strings (English PC branch)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app_streamlit_outcomes.py"

HELPERS = '''
ACTION_LABELS = {
    RX_ACTION_NO_CHANGE: "No change",
    RX_ACTION_STOP: "Stop",
    RX_ACTION_DOWN: "Reduce dose",
    RX_ACTION_UP: "Increase dose",
    RX_ACTION_SWITCH: "Switch",
}

DISPLAY_TRANSLATIONS = {
    "リシノプリル": "Lisinopril", "アジルサルタン": "Azilsartan", "サクビトリル/バルサルタン": "Sacubitril/valsartan",
    "アムロジピン": "Amlodipine", "カルベジロール": "Carvedilol", "ビソプロロール": "Bisoprolol",
    "フルイトラン（トリクロルメチアジド）": "Fluitran (trichlormethiazide)", "ミネブロ（エサキセレノン）": "Minnebro (esaxerenone)",
    "レパーサ（エボロクマブ）": "Repatha (evolocumab)", "アトルバスタチン": "Atorvastatin", "ピタバスタチン": "Pitavastatin",
    "ロスバスタチン": "Rosuvastatin", "エゼチミブ": "Ezetimibe", "トラゼンタ": "Tradjenta", "マンジャロ（チルゼパチド）": "Mounjaro (tirzepatide)",
    "オゼンピック（セマグルチド）": "Ozempic (semaglutide)", "リベルサス（セマグルチド）": "Rybelsus (semaglutide)", "ジャディアンス": "Jardiance", "メトホルミン": "Metformin",
    "ACE阻害薬": "ACE inhibitor", "Ca拮抗薬": "Calcium channel blocker", "β遮断薬": "Beta-blocker", "サイアザイド系利尿薬": "Thiazide diuretic",
    "非ステロイド型MRA": "Nonsteroidal MRA", "PCSK9阻害薬": "PCSK9 inhibitor", "スタチン": "Statin", "吸収阻害薬": "Absorption inhibitor",
    "DPP-4阻害薬": "DPP-4 inhibitor", "GIP/GLP-1受容体作動薬": "GIP/GLP-1 receptor agonist", "GLP-1受容体作動薬（皮下）": "GLP-1 receptor agonist (subcutaneous)",
    "GLP-1受容体作動薬（経口）": "GLP-1 receptor agonist (oral)", "SGLT2阻害薬": "SGLT2 inhibitor", "ビグアナイド": "Biguanide",
    "空咳": "Dry cough", "咳": "Cough", "めまい": "Dizziness", "高K血症": "Hyperkalemia", "血管性浮腫": "Angioedema", "頭痛": "Headache", "腎変化": "renal changes",
    "低血圧": "Hypotension", "浮腫": "Edema", "腎障害": "Renal impairment", "顔面紅潮": "Flushing", "疲労感": "Fatigue", "疲労": "Fatigue", "代謝改善": "Improved metabolism",
    "徐脈": "Bradycardia", "勃起障害": "Erectile dysfunction", "抑うつ": "Depression", "高尿酸血症": "Hyperuricemia", "高血糖症": "Hyperglycemia", "電解質失調": "Electrolyte imbalance",
    "副作用発現率": "Adverse-event rate", "副作用発現頻度": "Adverse-event rate", "血中カリウム増加": "Increased blood potassium", "糸球体濾過率減少": "Decreased glomerular filtration rate",
    "注射部位反応": "Injection-site reaction", "上気道感染": "Upper respiratory tract infection", "便秘": "Constipation", "肝機能上昇": "Elevated liver function tests", "肝酵素上昇": "Elevated liver enzymes",
    "筋肉痛": "Myalgia", "CK上昇": "Elevated CK", "下痢": "Diarrhea", "低血糖（併用時）": "Hypoglycemia (with combination therapy)", "悪心": "Nausea", "投与中止に至る有害事象": "Adverse events leading to discontinuation",
    "嘔吐": "Vomiting", "腹部不快感": "Abdominal discomfort", "腹痛": "Abdominal pain", "消化不良": "Dyspepsia", "尿路感染": "Urinary tract infection", "脱水": "Dehydration", "消化器症状": "Gastrointestinal symptoms",
    "mg/日": "mg/day", "mg/週": "mg/week", "隔週注": "every 2 weeks", "（開始量）": "(starting dose)", "軽度": "Mild ", "未満": "", "以上": " or more", "、": ", ", "・": ", ", "（": " (", "）": ")", "〜": "–",
}

ENGLISH_LIFESTYLE_LABELS = {
    "salt": "Sodium reduction",
    "carb": "Carbohydrate restriction",
    "fat": "Saturated fat reduction",
    "aerobic_moderate": "Moderate aerobic exercise",
    "combined": "Aerobic + strength training",
    "hiit": "High-intensity interval training",
}


def _display_text(value: str) -> str:
    text = str(value)
    for source, target in DISPLAY_TRANSLATIONS.items():
        text = text.replace(source, target)
    return text


def _lifestyle_label(key: str | None) -> str:
    if key is None:
        return "None"
    return ENGLISH_LIFESTYLE_LABELS.get(key, key)

'''

# Longest-first replacements for user-visible UI (keep internal JP action keys).
REPLACEMENTS: list[tuple[str, str]] = [
    ('page_title="生活習慣病ケアナビ"', 'page_title="Lifestyle Care Navigator (English)"'),
    (
        """<div class="care-hero">
  <h1>🌿 生活習慣病ケアナビ</h1>
  <p>これまでの努力を確かめ、食事・運動・お薬を一緒に比べて、次の一歩を決めます。</p>
</div>
<div class="step-strip">
  <span class="step-pill">1 現在地</span><span class="step-pill">2 これまでの成果</span>
  <span class="step-pill">3 介入を選ぶ</span><span class="step-pill">4 将来を比べる</span>
  <span class="step-pill">5 書類を作る</span>
</div>""",
        """<div class="care-hero">
  <h1>🌿 Lifestyle Care Navigator</h1>
  <p>Review progress so far, compare diet, exercise, and medicines together, and choose the next step.</p>
</div>
<div class="step-strip">
  <span class="step-pill">1 Baseline</span><span class="step-pill">2 Progress so far</span>
  <span class="step-pill">3 Choose interventions</span><span class="step-pill">4 Compare the future</span>
  <span class="step-pill">5 Create documents</span>
</div>""",
    ),
    (
        "診療と共有意思決定の支援用です。個人の結果を保証する医療機器ではありません。",
        "For clinical education and shared decision-making. This is not a medical device and does not guarantee individual outcomes.",
    ),
    (
        "※全死亡は、心血管疾患に限らず、がんや他の病気を含むすべての死亡を対象としています。",
        "All-cause mortality includes deaths from cancer and other diseases, not only cardiovascular disease.",
    ),
    ("## 入力", "## Inputs"),
    ("🩺 今日の診療", "Today's visit"),
    ("診療の目的", "Visit purpose"),
    ("治療を始める", "Start treatment"),
    ("治療を見直す", "Review treatment"),
    ("現在の治療を続ける", "Continue current treatment"),
    ("現在のお薬を入力すると、飲まなかった場合と比べてこれまでの成果を表示します。", "Enter current medicines to estimate benefit versus never having taken them."),
    ("現在のお薬と変更後を比べます。", "Compare current medicines with proposed changes."),
    ("食事・運動・お薬の介入案を比べます。", "Compare diet, exercise, and medicine options."),
    ("**患者プロフィール**", "**Patient profile**"),
    ("性別", "Sex"),
    ('"男性"', '"Male"'),
    ('"女性"', '"Female"'),
    ("年齢", "Age"),
    ("診断済み", "Diagnosed"),
    ("糖尿病", "Diabetes"),
    ("高血圧症", "Hypertension"),
    ("脂質異常症", "Dyslipidemia"),
    ("該当する病気", "Relevant conditions"),
    ("現在の検査値", "Current labs"),
    ("リスク因子（現在 → 目標）", "Risk factors (current → target)"),
    ("数値を直接入力、または −／＋ で調整できます。", "Enter values directly, or adjust with − / +."),
    ("収縮期血圧", "Systolic BP"),
    ("喫煙", "Smoking"),
    ("吸わない", "Never"),
    ("現在吸っている", "Current"),
    ("過去に吸っていた", "Former"),
    ("1日の本数", "Cigarettes per day"),
    ("喫煙年数", "Years smoked"),
    ("禁煙してからの年数", "Years since quitting"),
    ("**目標値**", "**Targets**"),
    ("目標血圧", "BP target"),
    ("目標LDL", "LDL target"),
    ("目標HbA1c", "HbA1c target"),
    ("**喫煙**", "**Smoking**"),
    ("状況", "Status"),
    ("今日から禁煙する場合も比較", "Also compare quitting today"),
    ("**体格（未入力なら性別の標準値を使用）**", "**Body size (sex-specific defaults if blank)**"),
    ("身長 (cm)", "Height (cm)"),
    ("体重 (kg)", "Weight (kg)"),
    ("BMI（自動計算）", "BMI (auto)"),
    ("**腎機能（任意）**", "**Kidney function (optional)**"),
    ("eGFR", "eGFR"),
    ("尿蛋白区分", "Urine protein category"),
    ("基準値と比べる", "Compare with reference values"),
    ("現在値のまま", "Stay at current values"),
    ("基準値を達成", "Reach reference targets"),
    ("次へ：食事・運動・お薬を選ぶ", "Next: choose diet, exercise, and medicines"),
    ("治療を選ぶ", "Choose treatment"),
    ("🥗 食事", "Diet"),
    ("食事介入を選択", "Select diet interventions"),
    ("🏃 運動", "Exercise"),
    ("選択しない", "None"),
    ("効果量と文献を確認", "Effect sizes and references"),
    ("介入を選ぶと、ここに定義・効果量・根拠が表示されます。", "Select interventions to see definitions, effect sizes, and evidence here."),
    ("根拠文献", "Source paper"),
    ("💊 お薬", "Medicines"),
    ("薬剤を選んで目標値を自動計算する", "Select medicines to auto-calculate targets"),
    ("薬剤カタログ読み込みに失敗。Excelのパス/シート名/列名を確認してください。", "Failed to load the medicine catalog. Check Excel path / sheet / column names."),
    ("降圧薬", "BP medicines"),
    ("脂質薬", "Lipid medicines"),
    ("糖尿病薬", "Diabetes medicines"),
    ("💊 薬を追加する", "Add medicines"),
    ("💊 薬を増減させる", "Adjust current medicines"),
    ("シミュレーションモード", "Simulation mode"),
    ("降圧薬（SBPに反映）", "BP medicines (affects SBP)"),
    ("脂質薬（LDLに反映）", "Lipid medicines (affects LDL)"),
    ("糖尿病薬（HbA1cに反映）", "Diabetes medicines (affects HbA1c)"),
    ("現在服用中の薬", "Current medicines"),
    ("各薬の変更（タップで選択）", "Change each medicine"),
    ("現在服用中の薬を選ぶと、ここに変更ボタンが表示されます。", "Select current medicines to show change options."),
    ("➕ 薬を追加する（任意）", "Add medicines (optional)"),
    ("変更内容", "Changes"),
    ("年間薬剤費（変更後）", "Annual drug cost (after change)"),
    ("年間薬剤費（合計）", "Annual drug cost (total)"),
    ("自動計算された目標値", "Auto-calculated targets"),
    ("薬剤変更の比較", "Medicine-change comparison"),
    ("主な副作用（薬剤ごと）", "Main adverse effects (by medicine)"),
    ("薬増減モード：現在服用中の薬を選択してください。", "Adjust mode: select currently used medicines."),
    ("薬剤を使わない場合は、上の手動目標値で計算します。", "If medicines are off, manual targets above are used."),
    ("合成ルール：SBPは足し算 / LDLは%低下を掛け算 / HbA1cは足し算", "Combination rule: SBP additive / LDL multiplicative % / HbA1c additive"),
    ("🌿 今日のナビ", "Today's navigator"),
    ("入力はメイン画面で行います。ここには実行ボタンと要約だけを表示します。", "Enter data in the main pane. This sidebar shows the run button and a summary only."),
    ("🎯 選択した介入による予測値", "Predicted values after selected interventions"),
    ("のリスクのため、現在の入力には効果量を適用していません。", " evidence population; effect size was not applied to the current inputs."),
    ("予測値", "Predicted values"),
    ("未選択", "None selected"),
    ("疾患別の評価", "Condition-specific view"),
    ("糖尿病モジュール", "Diabetes module"),
    ("CKDモジュール", "CKD module"),
    ("現在のHbA1c", "Current HbA1c"),
    ("介入後予測", "After intervention"),
    ("eGFR区分", "eGFR stage"),
    ("尿蛋白", "Urine protein"),
    ("HbA1cによる心筋梗塞・脳卒中・死亡リスク補正を共通モデルへ統合しています。", "HbA1c-based MI, stroke, and mortality adjustments are integrated into the shared model."),
    ("eGFRと尿アルブミン／蛋白による心筋梗塞・脳卒中・死亡リスク補正を共通モデルへ統合しています。", "eGFR and urine albumin/protein adjustments for MI, stroke, and mortality are integrated into the shared model."),
    ("リスク計算を実行", "Run risk calculation"),
    ("リスク計算中...", "Calculating risk..."),
    ("上記のパラメータを設定して「リスク計算を実行」を押してください", 'Set the parameters above, then press "Run risk calculation".'),
    ("結果サマリー", "Results summary"),
    ("全死亡", "All-cause death"),
    ("心筋梗塞", "Myocardial infarction"),
    ("脳卒中", "Stroke"),
    ("現在", "Current"),
    ("目標", "Target"),
    ("費用と副作用", "Cost and adverse effects"),
    ("詳細表示", "Details"),
    ("将来予測詳細グラフ", "Projected risk over time"),
    ("簡易注記", "Brief notes"),
    ("円/年", "JPY/year"),
    ("費用差", "Cost change"),
    ("変更後", "After change"),
    ("差分", "Difference"),
]


def main() -> None:
    text = TARGET.read_text()
    if "DISPLAY_TRANSLATIONS" not in text:
        anchor = 'RX_ACTION_SWITCH = "切替"\n'
        if anchor not in text:
            raise SystemExit("anchor for helpers not found")
        text = text.replace(anchor, anchor + "\n" + HELPERS, 1)

    # Apply replacements longest-first within list order already roughly long-first
    for old, new in sorted(REPLACEMENTS, key=lambda p: len(p[0]), reverse=True):
        if old in text:
            text = text.replace(old, new)

    # Lifestyle format_func hooks if still Japanese label usage
    text = text.replace(
        "format_func=lambda key: DIET_EFFECTS[key].label",
        "format_func=lambda key: _lifestyle_label(key)",
    )
    text = text.replace(
        'format_func=lambda key: "選択しない" if key is None else EXERCISE_EFFECTS[key].label',
        'format_func=lambda key: _lifestyle_label(key)',
    )
    text = text.replace(
        'format_func=lambda key: "None" if key is None else EXERCISE_EFFECTS[key].label',
        'format_func=lambda key: _lifestyle_label(key)',
    )

    # Display med names where common patterns remain
    # two-stage picker labels
    text = text.replace('f"{label}：① 薬剤を選択"', 'f"{label}: 1) Choose medicine"')
    text = text.replace('f"{name}：② 用量を選択"', 'f"{_display_text(name)}: 2) Choose dose"')
    text = text.replace('st.markdown(f"**{k}**")', 'st.markdown(f"**{_display_text(k)}**")')
    text = text.replace(
        'f"{domain_label}｜{med.get(\'category\', \'\')}｜"',
        'f"{domain_label} | {_display_text(med.get(\'category\', \'\'))} | "',
    )

    TARGET.write_text(text)
    print("updated", TARGET)


if __name__ == "__main__":
    main()
