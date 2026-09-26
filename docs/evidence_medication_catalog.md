# 薬剤カタログ拡張の根拠と実装方針

更新日: 2026-09-26

## 方針

- 日本で日常的に選択候補となる主要クラスを優先した。
- 効果は、薬剤・用量別RCTまたはメタ解析を優先し、直接値がない場合は「代表設定値」「補間推定」と明記した。
- 降圧薬はSBP低下量、脂質薬はLDL低下率、糖尿病薬はHbA1c低下量だけをモデルへ渡す。薬剤名だけによる心血管イベント抑制を重ね掛けしない。
- 現行薬価を確認できていない追加薬は空欄とし、アプリでは「登録済み分」の合計と未登録薬を表示する。0円とは扱わない。
- インスリンは用量調節依存、フィブラート・EPAはTG未実装のため今回の固定効果カタログから除外した。

## 追加範囲

- 降圧: テルミサルタン、カンデサルタン、ニフェジピンCR、シルニジピン、ヒドロクロロチアジド、スピロノラクトン（13用量）
- LDL: 低用量スタチン、プラバスタチン、インクリシラン（7用量）
- HbA1c: メトホルミン追加用量、ダパグリフロジン、カナグリフロジン、イプラグリフロジン、シタグリプチン、テネリグリプチン、デュラグルチド、リラグルチド、グリメピリド、ピオグリタゾン、イメグリミン（16用量）

## 主な根拠

1. Law MR, Wald NJ, Morris JK, Jordan RE. Value of low dose combination treatment with blood pressure lowering drugs: analysis of 354 randomised trials. BMJ. 2003;326:1427.
2. Reif M, et al. Effects of candesartan cilexetil in patients with systemic hypertension. Clin Ther. 1998;20:100–115.
3. Williams B, et al. Spironolactone versus placebo, bisoprolol, and doxazosin for resistant hypertension (PATHWAY-2). Lancet. 2015;386:2059–2068.
4. Law MR, Wald NJ, Rudnicka AR. Quantifying effect of statins on LDL cholesterol. BMJ. 2003;326:1423.
5. Ray KK, et al. Two phase 3 trials of inclisiran in patients with elevated LDL cholesterol. N Engl J Med. 2020;382:1507–1519.
6. Musso G, et al. A novel approach to control hyperglycemia in type 2 diabetes: systematic review and meta-analysis of SGLT2 inhibitors. BMJ Open. 2012;2:e001007.
7. NICE. Type 2 diabetes in adults: evidence review for medicines. 2025.
8. Bouchi R, et al. Practical guidance for diabetes treatment in Japan. Diabetol Int. 2024;15:410–434.
9. Dubourg J, et al. Efficacy and safety of imeglimin in Japanese patients with type 2 diabetes (TIMES 1). Diabetes Obes Metab. 2021;23:800–810.

各行の採用値、直接値か推定値か、副作用、引用は2つの薬剤マスターワークブックに保存する。
