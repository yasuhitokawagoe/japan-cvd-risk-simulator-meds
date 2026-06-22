# 設計案A：Delta Wrapper アプローチ

## 概要

`calc_engine_outcomes.py` は一切変更せず、新しい `MedicationAdjustment` class を `meds_catalog.py`（または新規ファイル）に追加するアプローチ。

患者の現在測定値を baseline とし、薬剤変更分の差分（delta）を target に加えることで、薬の増減シミュレーションを実現する。

## 計算モデル

```
baseline = sbp_now（現在の測定値 = 現在の服薬状態を反映済み）
target   = sbp_now + sbp_adjustment_delta

sbp_adjustment_delta = sum(変更後の薬の効果) - sum(現在の薬の効果)
ldl_adjustment_ratio = Π(1 - 変更後の低下率) / Π(1 - 現在の低下率)
a1c_adjustment_delta = sum(変更後の薬の効果) - sum(現在の薬の効果)
```

## クラス設計（案）

```python
class MedicationAdjustment:
    def __init__(self, sbp_now, ldl_now_mg, a1c_now, current_meds, adjusted_meds):
        ...

    def baseline_targets(self) -> dict:
        return {"sbp_target": self.sbp_now, ...}

    def adjusted_targets(self) -> dict:
        return {"sbp_target": self.sbp_now + self._sbp_delta(), ...}

    def costs(self) -> dict:
        return {"baseline": ..., "adjusted": ..., "delta": ...}

    def side_effect_changes(self) -> dict:
        return {"stopped": ..., "added": ...}
```

## ファイル変更

| ファイル | 変更内容 |
|---|---|
| `calc_engine_outcomes.py` | **変更なし** |
| `meds_catalog.py` | `MedicationAdjustment` class 追加 |
| `app_streamlit_outcomes.py` | モード切り替え、二重薬剤選択、class利用 |
| `app_streamlit_mobile.py` | 同上 |

## メリット

1. 既存の計算式に一切手を入れない
2. 後方互換性が完全
3. `MedicationAdjustment` class が独立しているので再利用しやすい
4. テストが容易

## デメリット

1. アプリ側で差分計算のロジックを持つ必要がある
2. PC版・モバイル版で同じ class 使い方を書く必要がある
3. 「baseline = 測定値そのまま」という解釈を前提とする

## 向いている場面

- 既存コードへの変更を最小限に抑えたい
- 計算エンジンは数学的に検証済みで、触りたくない
- 他のプロジェクトでも同じ薬剤差分ロジックを使い回したい
