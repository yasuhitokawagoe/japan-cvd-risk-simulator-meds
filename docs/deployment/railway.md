# Railwayデプロイ設定

## ゴール
技術に詳しくなくてもが、GitHubリポジトリを繋ぐだけでRailwayにデプロイできる状態を作る。
→ 設定をすべてリポジトリ側に入れ、Railway上での手作業（ビルダー選択・起動コマンド入力）をゼロにする。

## 対象リポジトリ
- `/japan-cvd-risk-simulator-meds`
- Streamlit製アプリ（日本のCVD（心血管疾患）リスクシミュレータ、薬剤選択機能あり）
- scipy / numpy を使用（＝Pythonバージョンとwheelの相性がシビア）
- リポジトリ内に複数アプリが存在し、起動対象を固定する必要がある

---

## 決定事項

### 方式：Dockerfile方式で確定
比較検討の結果、Railpack方式ではなく **Dockerfile方式** を採用。

採用理由：
- Pythonバージョンを完全固定でき、scipy/numpyのビルド失敗を構造的に回避できる
- Dockerfileは業界標準で、将来プラットフォーム独自方式が変わっても陳腐化しにくい
- 「一度書けば動く」再現性が高く、非技術者への引き渡しと相性が良い
- コストはビルドが数分ぶん遅い程度で、エンドユーザーの操作は一切変わらない

補足（誤解しやすい点）：
- ローカルにDockerをインストールする必要は**一切ない**。DockerイメージのビルドはRailway側サーバーが実行する。Dockerfileはただの設計図テキスト。
- スクショで出ていた「Deprecated」表示は **Nixpacks** に対するもの。現行デフォルトは **Railpack**（非推奨ではない）。今回はそれでもDockerfileを選択。

---

## リポジトリのルート直下に置くファイル（確定版）

### `Dockerfile`
```dockerfile
# Pythonバージョンを完全固定（scipy/numpy等のwheel相性問題を回避）
FROM python:3.11-slim

WORKDIR /app

# 依存だけ先にコピーしてインストール（レイヤーキャッシュを効かせる）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体をコピー
COPY . .

# 起動するアプリはここで固定（$PORT はRailwayが注入）
# ※ shell形式で書くこと。exec形式 CMD ["..."] だと $PORT が展開されない
CMD streamlit run app_streamlit_mobile.py --server.address 0.0.0.0 --server.port $PORT
```

### `railway.json`
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

---

## 技術的な確定事項（再検討不要な前提）
- `railway.json` はリポジトリの**ルート直下**必須（サブフォルダ運用時は絶対パス指定が別途必要）。
- Streamlit起動には `--server.address 0.0.0.0` と `--server.port $PORT` が必須。
- `Dockerfile` の `CMD` は **shell形式**で書く（exec形式だと `$PORT` が展開されない）。
- `restartPolicyMaxRetries` を入れているのは、ON_FAILUREでリトライ回数未指定だと無限リトライになるため。
- 起動対象アプリの指定は Dockerfile の CMD で管理（railway.json 側には startCommand を置かない＝単一の管理場所にする）。

---

## 残タスク

### 1.【要確認・最優先】起動対象アプリ名の確定
- 現状は既存スクショに合わせて `app_streamlit_mobile.py` を起動対象にしている。
- 別ファイルなら Dockerfile の CMD の該当箇所を差し替える。
- リポジトリ内の Streamlit エントリーポイント候補を洗い出して、正しいものを特定するのが望ましい。

### 2. requirements.txt の確認
- ルートに `requirements.txt` が存在する前提。無ければ作成が必要。
- scipy / numpy 等のバージョンが Python 3.11 と整合しているか確認。
- （Dockerfile方式なので pip が requirements.txt からインストールする）

### 3. 手順書づくり
- 手持ちのスクショを流用し、以下の5ステップだけに絞った手順書を作る：
  1. Railwayにサインイン（Continue with GitHub）
  2. New → GitHub Repo → 対象リポジトリを選択
  3. 数分待つ（自動ビルド・デプロイ）
  4. Settings → Networking → **Generate Domain** を1回押す
  5. 表示されたURLにアクセス
- ビルダー選択・start command入力は不要になっている点を明記する。

---

## 補足メモ（任意対応）
- トライアル枠（$5 / 30日）の消費を抑えたい場合、Settings → Deploy の Serverless（無アクセス時スリープ）を検討可。ただし初回アクセスがやや遅くなる。
- 起動確認を厳密にするなら、Streamlitのヘルスチェック用エンドポイント `/_stcore/health` を `railway.json` の `deploy.healthcheckPath` に指定する手もある（必須ではない）。
- Railwayの設定スキーマ・Railpack/Nixpacksの扱いは仕様変更が起きやすい領域なので、確定作業の直前に最新の公式ドキュメントを一度確認するのが安全。
```
参照：Railway Config as Code / Railpack Python docs
```