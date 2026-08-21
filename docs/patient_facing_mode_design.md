# Patient-facing exploration mode

## Goal

既存の一次予防CVD計算エンジンを変更せず、診察前・待ち時間に患者が将来リスクと介入のtrade-offを探索し、診察agendaを形成するUIを追加する。

## Existing implementation mapped

- リスク・CI計算: `calc_engine_outcomes.py` の `OutcomesEngine`
- 薬物介入: `meds_catalog.py` のカタログ読込と `apply_meds_to_targets`
- 生活介入: `lifestyle_interventions.py` の定義と `apply_lifestyle_effects`
- 医療者向けUI: `app_streamlit_outcomes.py`
- 既存フロー: 診療目的 → 患者・検査入力 → 現在リスク → 食事・運動・薬剤選択 → 計算 → CI曲線・費用・副作用 → 計画書

## Added structure

```text
app_streamlit_patient.py
  ├─ entry / patient input / current future
  ├─ intervention exploration / burden
  ├─ reaction / doctor questions
  └─ one-screen clinician summary

patient_mode/
  ├─ calculator.py     unchanged engine adapter
  ├─ events.py         replaceable anonymous event sink
  └─ ai_explainer.py   disabled optional AI boundary

pages/1_患者向け_探索モード.py
  └─ entry from the existing Streamlit app
```

## Safety boundaries

- 必須値が不明な場合は計算しない。
- absolute riskを基本表示し、CIはprogressive disclosureとする。
- 薬剤の効果・副作用は既存カタログ以外から生成しない。
- AIはv1では無効。将来も説明・質問整理のみに限定する。
- clinician summaryは閲覧行動・反応・質問を示し、治療推奨を生成しない。
- event loggingに入力値・氏名等を含めない。既定はメモリのみで、外部送信しない。
