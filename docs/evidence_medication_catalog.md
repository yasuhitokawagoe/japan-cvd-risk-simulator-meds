# 薬剤カタログ拡張の根拠と実装方針

更新日: 2026-09-26

## 方針

- 日本で日常的に選択候補となる主要クラスを優先した。
- 効果は、薬剤・用量別RCTまたはメタ解析を優先し、直接値がない場合は「代表設定値」「補間推定」と明記した。
- 降圧薬はSBP低下量、脂質薬はLDL低下率、糖尿病薬はHbA1c低下量だけをモデルへ渡す。薬剤名だけによる心血管イベント抑制を重ね掛けしない。
- 追加36用量すべての薬価を厚生労働省の2026年8月13日適用リストと照合済み。既存52用量を含め、全88用量の年間薬剤費に欠損なし。既存52用量の価格改定の再照合は今回の対象外。
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

## 薬価補完（2026-09-26）

出典: [厚生労働省・薬価基準収載品目リスト（2026-08-13適用）](https://www.mhlw.go.jp/topics/2026/04/tp20260401-01.html)。
内用薬: https://www.mhlw.go.jp/topics/2026/04/xls/tp20260813-01_01.xlsx
注射薬: https://www.mhlw.go.jp/topics/2026/04/xls/tp20260813-01_02.xlsx

`medication_prices_20260926.json` に36用量およびレパーサ修正分（計37用量）の製品名・薬価基準収載医薬品コード・規格・単価・年間消費数・確認日・出典ファイルのSHA-256を保存。
`scripts/resolve_medication_prices.py` で元リストから再抽出できる。商品名の指定がある薬はその製品、一般名の薬は明記した普通錠の統一名収載価格または代表後発品を採用。

- 日用薬は365日、週1回薬は既存カタログと同じ52回換算。各薬の年間費用を円単位で四捨五入。
- プラバスタチン20mgは10mg錠2錠、メトホルミン1000mgは500mg MT錠2錠、イメグリミン1000mg 1日2回は500mg錠4錠/日として計算。
- ビクトーザは18mg/キット。0.9mg/日は年18.25キット消費量按分（84,571円）、1.8mg/日は年36.5キット（169,141円）。端数キットの購入・導入漸増・針代等は含めない。
- レクビオは394,758円/筒。維持期2回/年の789,516円を合計へ使用し、初年度0・3・9か月の3回分1,184,274円を画面と計算欄に併記。国内製剤300mgナトリウム塩と有効成分インクリシラン284mgは同一1筒に対応する。
- 用法確認: [レクビオ添付文書](https://www.kegg.jp/medicus-bin/japic_med?japic_code=00071042)、[ビクトーザ添付文書](https://www.kegg.jp/medicus-bin/japic_med?japic_code=00058715)、[ツイミーグ添付文書](https://www.kegg.jp/medicus-bin/japic_med?japic_code=00069680)。
- ワークブックの年間価格は単価を参照する数式に変更。既存の文字列表記と数式の数値キャッシュの双方をアプリが読めるようにした。未登録表示のガードは将来の不備検知用として保持。
- 保険試算追加時に既存レパーサの古い薬価を24,302円/140mgペンへ更新。52週・26回換算は631,852円。保険試算は投与暦に応じた回数を使用するため、[保険費用モデルの記録](evidence_insurance_costs.md)を参照。
