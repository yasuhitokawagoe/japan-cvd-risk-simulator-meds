# japan-cvd-risk-simulator-meds
薬剤を追加した場合の心血管イベントリスクを表示する

## Patient-facing exploration mode

既存の医療者向け画面と計算エンジンを保持したまま、診察前・待ち時間に患者が介入効果を探索する画面を追加しています。

```bash
streamlit run app_streamlit_patient.py
```

既存画面は従来どおり `streamlit run app_streamlit_outcomes.py` で起動でき、Streamlitのページナビゲーションから患者向けモードにも移動できます。

匿名イベントは標準ではメモリ内だけに保持し、外部へ送信しません。院内のJSONLへ保存する場合のみ `PATIENT_EVENT_LOG_PATH` を設定してください。イベントには匿名session ID、時刻、操作種別のみを記録し、入力値や直接識別子は含めません。
