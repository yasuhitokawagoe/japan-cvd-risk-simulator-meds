# 設計案B：Calc Engine 拡張アプローチ

## 概要

`calc_engine_outcomes.py` の `cumulative_incidence()` および `cumulative_incidence_with_ci()` に、baseline側の目標値パラメータを追加するアプローチ。

baseline側にも薬効を反映させ、target側と対称的に扱う。

## 計算モデル

```
baseline = sbp_now に「現在の薬の効果」を適用
target   = sbp_now に「変更後の薬の効果」を適用

sbp_target_baseline = sbp_now + sum(現在の薬のSBP効果)
sbp_target          = sbp_now + sum(変更後の薬のSBP効果)
```

## calc_engine の変更点

```python
def cumulative_incidence_with_ci(
    self,
    ...,
    sbp_target_baseline: float = None,
    ldl_target_baseline: float = None,
    a1c_target_baseline: float = None,
    ...
):
```

- `None` の場合は現在値を使用（後方互換）
- baseline側のRR計算も target側と同じく `_alpha_by_age()` で年齢減衰

## ファイル変更

| ファイル | 変更内容 |
|---|---|
| `calc_engine_outcomes.py` | baseline側目標値パラメータ追加 |
| `meds_catalog.py` | 変更なし（既存関数を流用） |
| `app_streamlit_outcomes.py` | モード切り替え、二重薬剤選択、費用表示 |
| `app_streamlit_mobile.py` | 同上 |

## メリット

1. baseline と target が対称的で概念がわかりやすい
2. 計算ロジックがエンジン側に集約される
3. アプリ側は単純にパラメータを渡すだけ
4. 将来、より複雑なシナリオ比較にも拡張しやすい

## デメリット

1. `calc_engine_outcomes.py` に手を入れる必要がある
2. baseline/target 両方の年齢減衰処理を追加実装する必要がある
3. 既存メソッドのシグネチャ変更による影響範囲を確認する必要がある

## 注意点

このアプローチでは `sbp_now` を「未治療時の値」と解釈する必要がある。患者が実際に測定した値（薬効込み）をそのまま使うと、baseline に薬効を二重に反映してしまう。

## 向いている場面

- 計算ロジックをエンジン側で一元管理したい
- 将来的に多くのシナリオ比較を追加する予定がある
- `calc_engine` の内部を理解したうえで拡張しても問題ない
