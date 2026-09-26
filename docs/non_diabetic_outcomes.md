# PC版：糖尿病なしでも透析・認知症を表示（2026-09-27）

## 範囲

ユーザー要望「DM以外でも透析と認知症は出そうぜよ」に対応。
現PCプレビュー `dm-care-med-selector-preview` のみ更新する。
糖尿病チェックを外しても全死亡・心筋梗塞・脳卒中・透析・認知症の5項目を残す。
適用外・入力不足は「未算出」と理由を示し、ゼロリスクには置き換えない。
大切断・失明は引き続き2型糖尿病モデルのみに表示する。
HbA1cチェックの自動提案・手動優先、既存DMモデル、スマホ版は変更しない。

## 腎不全：4変数KFRE（非北米補正）

### 一次資料

- Tangri et al. *Multinational Assessment of Accuracy of Equations for Predicting Risk of Kidney Failure: A Meta-analysis.* JAMA 2016;315:164–174. DOI:10.1001/jama.2015.18202.
  [本文](https://jamanetwork.com/journals/jama/fullarticle/2481005)、[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4752167/)。糖尿病を含む／含まないCKDで検証された、透析または腎移植の2年・5年予測。非北米補正は日本人専用の較正ではない。
- Ramspek et al. *Which prognostic model predicts kidney failure best?* の[補足資料p.2](https://cdn-links.lww.com/permalink/jsn/c/jsn_32_5_2022_12_07_ramspek_2020071077_sdc1.pdf)に転載されたKFRE eAppendix 2の式と照合。eGFRはCKD-EPI、ACRはmg/g。
- [KDIGO 2024、2.2節](https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf)：CKD G3–G5に妥当性検証済み腎不全予測式を利用。G1–G2への適用はしない。

### 実装

```
LP = -0.2201 × (age/10 - 7.036)
     +0.2467 × (male - 0.5642)
     -0.5567 × (eGFR/5 - 7.222)
     +0.4510 × (ln(UACR_mg_g) - 5.137)
P2 = 1 - 0.9832 ^ exp(LP)
P5 = 1 - 0.9365 ^ exp(LP)
```

UIは20〜95歳、eGFR 5以上60未満、3か月以上持続するCKD確認済み、透析・腎移植未施行に制限。
尿ACRの実測値を追加し、未測定の既定値は空欄。A1〜A3の代表値や尿蛋白/Crを代入しない。
現在eGFRがCKD-EPI式かを明示的に確認し、日本人式・算出式不明では計算しない。数値の自動換算はしない。

予測期間セレクターにかかわらず2年・5年だけを表示。年次曲線、10年以上への外挿、個人95%CIを作らない。
KFREは予後予測式であり、目標eGFR・目標ACRの変更を薬効として扱わない。
介入後リスク、ARR、HR、過去の治療利益は算出しない。HRモードでも「現在の絶対リスク」と明示する。
死亡の競合リスクを直接扱わないため、特に高齢者で過大推定の可能性があると表示する。
eGFRが60以上で「未算出」でも、将来の腎不全が起こらないことを意味しない。

## 認知症：日本一般住民の参考基礎曲線

### 一次資料と転記

Shimada S, Matsuyama Y, Kondo K, Aida J. *The Mediating Effect of Smoking on the Association between Income and Dementia among Japanese Older People.* JMA Journal 2025;8:766–776. DOI:10.31662/jmaj.2025-0018.
[原著PDF Table 2（p.771）](https://www.jstage.jst.go.jp/article/jmaj/8/3/8_766/_pdf)。
Consensusで検索・論文fetch後、原著表に照合した。

JAGESの自立した65歳以上44,083人、2010〜2019年の追跡。
糖尿病を除外した集団ではないため「非糖尿病専用モデル」とは呼ばない。
アウトカムは要介護認定の認知機能レベルII以上（日常生活に支障のある認知症）。全ての臨床診断やMCIではない。

| 開始時年齢 | 男性・人年率 | 女性・人年率 |
| --- | ---: | ---: |
| 65–69 | 0.006 | 0.005 |
| 70–74 | 0.014 | 0.013 |
| 75–79 | 0.031 | 0.032 |
| 80–84 | 0.054 | 0.062 |
| ≥85 | 0.096 | 0.105 |

### 独自近似である部分・限界

- 表の人年率を一定の原因別ハザードλとして近似。これは公表済みの個人予測式ではない。
- 開始時年齢層の率は追跡期間の加齢を既に含むため固定する。到達年齢ごとに上の層へ移して二重に加齢させない。
- 既存の[厚労省2024年簡易生命表](https://www.mhlw.go.jp/toukei/saikin/hw/life/life24/)の性別・到達年齢別死亡確率qからμ = −ln(1−q)を計算。1年間の認知症増分を `S × (1−exp(−λ−μ)) × λ/(λ+μ)`、無イベント生存を `S × exp(−λ−μ)` とする。
- 認知症研究と生命表を組み合わせる仮定は独自であり、元研究の累積発症率を厳密に再現する較正ではない。基礎集団の地域差・時代差・個人差は残る。
- 画面の開始年齢65〜95歳のみ。65歳未満を0%にしない。85歳以上は一括の率で、高齢者内の差を推定できない。
- 2010〜2019年の観察期間を目安に9年超は点線の外挿。開始年齢の層別率と介入倍率の持続を仮定するだけで、長期妥当性は検証されていない。到達年齢110歳までに表示を制限する。
- 元表の率・複合モデルから妥当な95%CIを構成できないため、一般住民曲線には帯や「95%CI」・HR参考幅を表示しない。内部の共通描画形式に限り上下限配列を点推定と同値にし、`has_uncertainty=False`で表示を抑制する。

### 介入の探索的換算

- 血圧：既存のPeters et al. 個人データRCTメタ解析（平均10/4 mmHg低下、認知症OR 0.87）に基づく既存換算を利用。`0.87^(SBP低下/10)`、低下量0〜30 mmHg。ORをハザード倍率として使い、低下量へ対数線形に配分すること自体が追加仮定。
  [原著](https://academic.oup.com/eurheartj/article/43/48/4980/6770632)、[Consensus記録](https://consensus.app/papers/blood-pressure-lowering-and-prevention-of-dementia-an-peters-xu/80e4c462131a5a9da849201e137c347d/)。薬・食事・手入力の同じ低下量には同じ換算を適用するが、各方法の認知症予防を実証するものではない。[2026-09-02訂正](https://academic.oup.com/eurheartj/advance-article/doi/10.1093/eurheartj/ehag701/8779729)も確認：Table 1のプラセボ群人数の誤植修正で、採用したORの修正ではない。
- LDL：既存の観察研究換算 `0.74^(LDL低下/60)`、低下量0〜60 mg/dL。[原論文リンクを含む記録](https://consensus.app/papers/lowdensity-lipoprotein-cholesterol-levels-and-risk-of-lee-lee/4bf9a1f3fed25c058b00c34b5a05de67/)。低LDLとの関連をLDL低下の因果的予防効果と同一視しない。
- スタチン：Westphal Filho et al. 2025、観察研究55件の全体推定HR 0.86（95%CI 0.82–0.91）。既存DM用のサブグループ0.87ではなく全体値を使用。[PubMed原著抄録](https://pubmed.ncbi.nlm.nih.gov/39822593/)、DOI:10.1002/trc2.70039。観察研究であり、認知症予防の処方推奨ではない。
- LDLとスタチンは独立でないため `lipid = min(LDL倍率, スタチン選択時0.86)` とし、**両者を乗算しない**。スタチン内訳はLDL倍率を超える差分のみ。
- 血圧と脂質の倍率は独立と仮定して乗算。この複合推定も未検証と明示。
- GLP-1/SGLT2/メトホルミンの2型糖尿病集団の効果量、HbA1cによる効果は非糖尿病曲線へ流用しない。
- HR表示は従来と同じ累積ハザード比換算でありCox HRではない。HRモードではグラフを出さない。

## 過去利益・書類との分離

非糖尿病の新2項目は現在から将来への参考値のみ。
過去利益は既存3つの心血管系アウトカムに限定し、選択値が残っていても有効な項目に戻す。
患者向けレポートは従来の全死亡・心筋梗塞・脳卒中が対象で、新2項目は出力しない。
新2項目の異なるデータ形式を既存DM曲線として誤って書類へ流し込まない。

## 検証

`test_non_diabetic_outcomes.py`：公表KFRE式・単位・適用外・欠測・腎指標勾配、JAGES全層の率、加齢の二重計上回避、競合死亡、外挿上限、未算出、継続シナリオ、LDL/スタチン重複排除。

`test_pc_diabetes_ui.py`：非糖尿病5項目、65歳未満の理由、一般住民曲線と内訳の一致、95%表示の抑制、HR時のグラフ非表示、KFRE適用条件・固定期間・目標値との分離、既存の手動チェック優先・書類・服薬継続。

結果：`tests/` 全体で **117 passed / 35 subtests passed**。既存の糖尿病モデル・スマホ画面のテストも含む。
ローカルCondaの既知の`readline`クラッシュを避けるため、テスト起動時のみ`sys.modules["readline"] = None`を指定。アプリや計算関数は差し替えていない。
