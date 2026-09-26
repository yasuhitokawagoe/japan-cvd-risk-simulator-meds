# 食事パターン追加の根拠・実装記録（2026-09-26）

対象：`codex/medication-three-step-selector` の薬剤選択プレビュー。
既存の減塩・糖質制限・飽和脂肪制限の係数、運動係数、画面全体のデザインは変更しない。

## 患者向け表示名の変更

2026-09-26：専門名だけでは食事内容が伝わりにくいという要望に合わせ、表示名・短い説明を変更。

- DASH食 → 「野菜・低脂肪乳製品を増やす減塩食」
- 地中海食 → 「魚・野菜中心で、油の質を見直す食事」
- 減量食（食事置換プログラム）→ 「専用の食品に置き換える減量食」

選択欄・治療内訳・書類に渡す介入名を同じ表示名で統一する。
専門名は「効果量と根拠を確認」内の「研究上の名称」に残す。
これは説明の言い換えであり、日本食で同等の効果を検証したという意味ではない。
内部キー、採用論文、係数、適用条件、計算式は一切変更しない。以下は研究上の名称で記載する。

## 文献確認

最初にPubMed・出版社原文を照合し、その後ユーザーの指定によりConsensusで検索し、
以下の3採用論文と補足のYe 2023をそれぞれfetchして確認した。
Consensusの自動要約だけで係数を決めず、数値・対照群・対象集団を確認した。

| 選択肢 | SBP mmHg | LDL mg/dL | HbA1c ポイント | BMI kg/m² | 採用研究 |
|---|---:|---:|---:|---:|---|
| DASH食 | -3.94 | -3.53 | 追加なし | -0.64 | Lari 2021 |
| 地中海食 | 追加なし | -8.06 | -0.307 | -0.828 | Wu 2025 |
| 減量食（食事置換プログラム） | -4.97 | 追加なし | -0.43 | -0.87 | Noronha 2019 |

「追加なし」は効果がないと証明された意味ではなく、この版で採用する係数を0に置くという意味。
いずれも対照食との差であり、介入群の開始前からの総改善ではない。
各指標の解析集団・試験数は異なる。同時にこの組合せの変化が起きることを検証したモデルではない。

### DASH食

Lari A, et al. *The effects of the Dietary Approaches to Stop Hypertension (DASH) diet on metabolic risk factors in patients with chronic disease: A systematic review and meta-analysis of randomized controlled trials.* Nutrition, Metabolism and Cardiovascular Diseases. 2021;31:2766–2778.

- DOI: https://doi.org/10.1016/j.numecd.2021.05.030
- PubMed: https://pubmed.ncbi.nlm.nih.gov/34353704/
- Consensus: https://consensus.app/papers/the-effects-of-the-dietary-approaches-to-stop-hypertension-lari-sohouli/f326efe690415dc1b8024b7e83b1925a/?utm_source=chatgpt
- 54試験、慢性疾患を有する参加者。採用値は抄録Data synthesis。
- HbA1cの追加係数をこの研究からは設定しない。別の小規模解析の血糖効果を混ぜない。
- 食品内容は腎機能低下・高カリウム血症などに応じて個別調整が必要とUIに記載。

### 地中海食

Wu MJ, Hung CH, Yong SBO, Ching GS, Hsu HJ. *Impact of the Mediterranean Diet on Glycemic Control, Body Mass Index, Lipid Profile, and Blood Pressure in Type 2 Diabetes: A Meta-Analysis of Randomized Controlled Trials.* Nutrients. 2025;17:3908.

- DOI: https://doi.org/10.3390/nu17243908
- 原文: https://www.mdpi.com/2072-6643/17/24/3908
- PubMed: https://pubmed.ncbi.nlm.nih.gov/41470853/
- Consensus: https://consensus.app/papers/impact-of-the-mediterranean-diet-on-glycemic-control-body-wu-hung/12975e39342b5761854a06648467de4b/?utm_source=chatgpt
- 2型糖尿病、11 RCT（10報）。採用値は抄録・本文Primary/Secondary outcomes。
- HbA1c -0.307（95%CI -0.451〜-0.163）、BMI -0.828（-1.400〜-0.256）、LDL -8.060（-14.213〜-1.907）。
- SBPの推定 -5.130（-10.877〜+0.617）は不確実なため、この版の自動反映では0とする。この判断は実装上の保守的な選択。
- 先行Zheng 2024（DOI 10.1186/s40795-024-00836-y）はSBP -4.17、LDLは有意差なし。研究集合によって結果が異なる。2024のSBPと2025のLDLを都合よく合成せず、2025を一つの係数セットとして採用。
- 飲酒開始・増量は推奨しない。

### 減量食（食事置換プログラム）

Noronha JC, et al. *The Effect of Liquid Meal Replacements on Cardiometabolic Risk Factors in Overweight/Obese Individuals With Type 2 Diabetes: A Systematic Review and Meta-analysis of Randomized Controlled Trials.* Diabetes Care. 2019;42:767–776.

- DOI: https://doi.org/10.2337/dc18-2270
- PubMed: https://pubmed.ncbi.nlm.nih.gov/30923163/
- Consensus: https://consensus.app/papers/the-effect-of-liquid-meal-replacements-on-cardiometabolic-noronha-nishi/8df5b77d72f6530c8501c2d5a9341ffd/?utm_source=chatgpt
- 9試験比較・961人、追跡中央値24週。過体重・肥満を伴う2型糖尿病。
- SBP -4.97（95%CI -7.32〜-2.62）、HbA1c -0.43（-0.66〜-0.19）、BMI -0.87（-1.31〜-0.42）。脂質の追加係数は採用しない。
- 対照は従来の減量食。効果の確実性は低〜中等度。単なる「カロリーを控える食事」すべてに適用できる値ではない。
- 原著の体重差 -2.37 kgをBMI係数と同時に足さない。BMIのみ採用し、身長・体重欄の実測値は書き換えない。
- 2023年の17 RCT・2,112人の解析でもHbA1c -0.46、BMI -0.65という方向性を確認。ただし対象・置換方法が広いため、今回の係数を部分的に入れ替えない。
  Ye W, et al., JCEM, DOI https://doi.org/10.1210/clinem/dgad273 、Consensus https://consensus.app/papers/the-efficacy-and-safety-of-meal-replacement-in-patients-ye-xu/4b236594cb5657a692357ca16080b888/?utm_source=chatgpt

## 適用範囲と二重加算防止

1. 「個別の食事介入」では従来3項目を併用可能。食事全体のパターンは3種類から1種類のみ選択する。
2. パターンと既存の個別介入は同時に計算しない。計算関数にも競合拒否・同一キー重複除去を設け、UI以外からの重複も防ぐ。
3. 地中海食・食事置換は2型糖尿病の文脈に限定。このアプリは糖尿病モデルだが、共通関数を糖尿病以外に呼んだ際は適用しない。
4. **BMI 25の境界はモデルの適用ガードであり、RCTで検証された効果の有無の境界ではない。** DASH・地中海食はBMI 25未満でも検査値の係数は使用するが、BMIは自動で下げない。食事置換はBMI 25未満・BMI不明なら全係数を適用せず警告。高齢者の栄養状態・フレイルは別途判断が必要。
5. 新パターンのBMIは現在BMIから算出。手入力BMI目標をさらに引き下げない。解除時には手入力モードへ戻る。SBP・LDL・HbA1cも従来どおり現在値＋選択した介入の効果を使う。
6. 改善後の状態を開始時から維持すると仮定。年数にBMI減少量や検査値変化を掛けない。未適用の食事置換を治療内訳・書類の実施介入に載せない。

## アウトカムへの反映と限界

- SBP・LDL・HbA1c・BMIを既存エンジンへ渡す。各アウトカムに既存の入力項目だけが作用する。BMIは心筋梗塞・脳卒中・全死亡の既存BMIモデルに反映し、糖尿病合併症・認知症・骨折に新たな独立効果は作らない。
- BMIの関連は減量RCT由来の独立した治療効果ではない。血圧・血糖などとの重複や交絡が残り、既存の年齢依存U字モデルでは低BMI側のリスクが増える場合もある。BMI低下を常に利益として固定しない。
- PREDIMEDなどの複合心血管イベントHRは追加乗算しない。既存の危険因子経由の効果との重複や、複合イベントから全死亡・各合併症への不適切な転用を避ける。
- 薬剤・運動との併用は個別効果を組み合わせたモデル仮定。相互作用・介入内容の重複を除去した独立した追加効果とはいえず、その限界をUIに表示。
- 食事の係数の不確実性・個人差・長期維持はグラフの既存の幅には伝播していない。食事込みの検証済み95%CIと誤解されないようUIに表示。
- 海外試験の平均差を日本人個人に外挿した試算で、個人の目標値や治療指示ではない。特に薬剤併用時の低血糖と食事置換の栄養管理に注意を表示。

## 検証

- 既存食事・運動6テストの維持。
- `tests/test_diet_patterns.py`：係数、競合・重複、糖尿病/BMI適用ガード、運動との計算、BMI入力検証。
- `tests/test_diet_patterns_ui.py`：切替後の値、旧選択の非加算、手入力目標の置換と復元、再実行時の非累積、BMIの治療内訳への帰属、HR表示、書類への値の受け渡し、継続/中止モードへの非適用。
- 既存の薬剤順序・HR表示・心肺体力・薬剤費・累計アクセスの回帰テストも実行。
