# 設計案C：ハイブリッドアプローチ（推奨）

## 概要

設計案Aの「調整差分（delta）」という計算モデルを採用しつつ、`calc_engine_outcomes.py` 内に新しいメソッド `cumulative_incidence_with_adjustment()` を追加するアプローチ。

患者の現在測定値を baseline とし、薬剤変更分の差分を target に反映する。計算の本質は Delta Wrapper と同じだが、エンジン側に集約することでアプリ側をシンプルに保つ。

## 計算モデル

```
baseline = sbp_now（現在の測定値 = 現在の服薬状態を反映済み）
target   = sbp_now + sbp_adjustment_delta

sbp_adjustment_delta = sum(変更後の薬の効果) - sum(現在の薬の効果)
ldl_adjustment_ratio = Π(1 - 変更後の低下率) / Π(1 - 現在の低下率)
a1c_adjustment_delta = sum(変更後の薬の効果) - sum(現在の薬の効果)
```

## 新しいメソッド

```python
def cumulative_incidence_with_adjustment(
    self,
    outcome, sex, start_age, years,
    sbp_now, ldl_now_mg, a1c_now,
    current_meds, adjusted_meds,
    smoking_status, cigs_per_day, years_smoked, years_since_quit,
    assume_quit_today_in_target=False,
    confidence_level=0.95,
    bmi_now=None, bmi_target=None,
    egfr_now=None, egfr_target=None,
    acr_now=None, acr_target=None,
) -> dict:
    """
    現在の服薬状態から変更後の服薬状態へのシミュレーション。
    内部で調整差分を計算し、既存の cumulative_incidence_with_ci() を呼び出す。
    """
```

## 内部構成

```
cumulative_incidence_with_adjustment()
├── MedicationAdjustment class で差分・費用・副作用を計算
├── adjusted_targets = baseline_targets + delta
└── cumulative_incidence_with_ci() を呼び出し
```

## ファイル変更

| ファイル | 変更内容 |
|---|---|
| `calc_engine_outcomes.py` | 新メソッド `cumulative_incidence_with_adjustment()` を追加（既存メソッドは変更なし） |
| `meds_catalog.py` | `MedicationAdjustment` class 追加 |
| `app_streamlit_outcomes.py` | モード切り替え、二重薬剤選択、新メソッド利用 |
| `app_streamlit_mobile.py` | 同上 |

## メリット

1. **既存の計算式に手を入れない**
   - `cumulative_incidence_with_ci()` の中身は完全にそのまま
2. **計算ロジックがエンジン側に集約**
   - アプリ2つ（PC/モバイル）で同じロジックを書かなくて済む
3. **臨床的に自然**
   - 患者の実測値をそのまま baseline として使える
4. **後方互換性が完全**
   - 既存の薬追加モードは一切変更なし
5. **テストしやすい**
   - `MedicationAdjustment` class と新メソッドを個別にテスト可能

## デメリット

1. `calc_engine_outcomes.py` に新しいメソッドを追加する必要がある
2. 新しい class と新しいメソッドの2つを理解する必要がある

## 向いている場面

- 既存の計算式は守りつつ、エンジン側でロジックを集約したい
- 将来的な拡張性も考慮したい
- チーム内で責務分離（計算はエンジン、表示はアプリ）を明確にしたい

## 実装順序（案）

1. `meds_catalog.py` に `MedicationAdjustment` class を追加
2. `calc_engine_outcomes.py` に `cumulative_incidence_with_adjustment()` を追加
3. PC版アプリにモード切り替えと二重薬剤選択を追加
4. モバイル版アプリに同様のUIを追加
5. テスト・動作確認
