# japan-cvd-risk-simulator-meds
薬剤を追加した場合の心血管イベントリスクを表示する

## 健診結果連携版

Streamlit のマルチページ機能で `/checkup` にスマートフォン向け健診フローを追加しています。

```bash
streamlit run app_streamlit_mobile.py
```

- 利用者: `http://localhost:8501/checkup?source=healthcheck&facility_id=001&campaign=A`
- 集計画面: `http://localhost:8501/checkup?admin=1`
- A4 QR 台紙: `http://localhost:8501/checkup?mode=handout`

イベントは既定で `checkup_analytics.jsonl` に保存されます。健診値・リスク値・薬剤選択は保存しません。
保存先は環境変数 `CHECKUP_ANALYTICS_PATH` で変更できます。
