# 食事・運動介入の効果量と実装方針

## 原則

- 効果量はRCTの系統的レビュー・メタ解析を優先する。
- 血圧、LDL、HbA1cの変化を既存アウトカムモデルへ入力する。
- 同じ経路を表すハードエンドポイントRRは二重計上しない。
- 観察研究の死亡率・イベント率は説明には使っても、計算へ直接掛けない。
- 対象集団が2型糖尿病に限られる効果は、HbA1c 6.5%以上または糖尿病薬入力時だけ適用する。

| 介入 | モデルへ入れる効果 | 根拠・注意 |
|---|---:|---|
| 減塩 | SBP -4.26 mmHg | 133 RCT、12,197人。DBP -2.07 mmHgだが現行アウトカム式はSBPのみ使用。 |
| 糖質制限 | HbA1c -0.36% | 過体重・肥満を伴う2型糖尿病、17 RCT・1,197人。LDLは有意差なし。 |
| 飽和脂肪制限 | LDL -9% | NHLBI TLCの8-10%低下範囲の中点。飽和脂肪を不飽和脂肪へ置換する前提。 |
| 中強度有酸素 | SBP -1.24 mmHg、LDL -6.96 mg/dL、HbA1c -0.62% | 運動メタ解析のHbA1c値と、SBP・LDL範囲の保守的下限。 |
| 有酸素＋筋トレ | SBP -1.24 mmHg、LDL -6.96 mg/dL、HbA1c -0.74% | 複合運動がHbA1cで最大。 |
| HIIT | SBP -1.24 mmHg、LDL -6.96 mg/dL、HbA1c -0.71% | 高強度は6 METs以上。中強度より死亡率をさらに下げる確証はない。 |

## 主要文献

- Huang et al. BMJ 2020. Sodium reduction dose-response meta-analysis: https://consensus.app/papers/effect-of-dose-and-duration-of-reduction-in-dietary-sodium-huang-trieu/372f847fb1c05c3fb3345df923ce3856/
- Tian et al. Frontiers in Nutrition 2025. Low carbohydrate diet in T2DM: https://consensus.app/papers/the-effects-of-lowcarbohydrate-diet-on-glucose-and-lipid-tian-cao/1e38e99b73365874ae76fa1c988623ba/
- NHLBI TLC guide. Saturated fat reduction and LDL: https://www.nhlbi.nih.gov/sites/default/files/publications/Your_Guide_to_Lowering_Your_Cholesterol_with_TLC.pdf
- Michielsen et al. Cardiovascular Diabetology 2025. Exercise characteristics in T2DM: https://consensus.app/papers/the-effect-of-exercise-characteristics-on-hba1c-and-other-michielsen-yagiz/64edf5b242b4590abba16d5d9d958843/
- Rey Lopez et al. BMJ Open Sport & Exercise Medicine 2020. Moderate vs vigorous activity and mortality: https://consensus.app/papers/do-vigorousintensity-and-moderateintensity-physical-lopez-sabag/23c6bd3a32d054b7bdebecfc8282dbb4/
- Steen et al. Ann Intern Med 2025. Saturated fat and hard endpoints: https://consensus.app/papers/effect-of-interventions-aimed-at-reducing-or-modifying-steen-klatt/1b72013e107c5413993dbb7eae993060/
