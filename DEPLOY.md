# このアプリを公開する手順（Railway デプロイ手順書）

プログラミングの知識がなくても、**上から順にボタンを押していくだけ**で
このアプリをインターネットに公開できます。

## 全体像（最初に読んでください）

- 使うのは **Railway**（ https://railway.com ）という、GitHub のコードをそのまま
  Web アプリとして公開してくれるサービスです。
- 対象リポジトリは **`yasuhitokawagoe/japan-cvd-risk-simulator-meds`**、
  デプロイに使う枝（ブランチ）は **`feature/morita-dev`** です。
- このアプリには **モバイル版** と **PC版** の2つがあり、**1つのリポジトリから
  2つのアプリを別々のURLで公開**します。
- Railway は「1つのアプリ＝1つのサービス」なので、**サービスを2つ**作ります。
- 難しい設定はすべてコード側（リポジトリ内）に入っているので、あなたは
  **画面のボタンを押すだけ**です。

> ⏱ ビルド（公開の準備）は毎回**数分**かかります。画面が止まって見えても
> 故障ではありません。落ち着いて待ってください。

---

## STEP 1. Railway にサインイン

1. `https://railway.com` を開く。
2. **「Login」→「Continue with GitHub」** を押す
   （リポジトリを持っている GitHub アカウントでログイン）。
3. 初回は Railway が GitHub へのアクセス許可を求めます。
   **「Configure GitHub App」** が出たら、
   `japan-cvd-risk-simulator-meds` にチェックを入れて許可する。

---

## STEP 2. 1つ目のサービス（モバイル版）を作る

### 2-1. リポジトリを選ぶ
1. **「New Project」→「Deploy from GitHub repo」** を押す。
2. 一覧から **`japan-cvd-risk-simulator-meds`** を選ぶ。

### 2-2.【⚠️最重要】ブランチを `feature/morita-dev` に変える
公開に必要な設定（アプリ一式＋Dockerfile など）は **`feature/morita-dev`** という枝
（ブランチ）に入っています。Railway が初期状態で見る **`main` のままだと
ビルドに失敗します。**（← つまずく人が一番多いポイント）

1. 作られたサービス（四角いカード）をクリックする。
2. **「Settings」** タブを開く。
3. **「Source」** の中の **Branch** を、**`main` → `feature/morita-dev`** に変更する。
4. 変更すると自動でビルドが始まります。

### 2-3. 設定が合っているか確認（見るだけ）
- **「Settings」→「Build」** の **Builder** 欄に
  **「The value is set in /railway.json」** と表示されていれば正解です
  （`railway.json` が自動で **モバイル版**＝`Dockerfile.mobile` を選んでいます）。
- ※ Builder のドロップダウンが「Railpack（Default）」と表示されていても問題ありません。
  コード側（`railway.json`）の指定が優先されます（表示は書き換わりません）。

### 2-4. 完成を待って、URLを発行
1. **「Deployments」** タブでビルドの進行を確認（数分）。最後に **Success / Online** になればOK。
2. **「Settings」→「Networking」→「Generate Domain」** を1回押す。
3. 表示された `xxxx.up.railway.app` が **モバイル版の公開URL**です 🎉
   （ポートは自動で **8080** になります）

---

## STEP 3. 2つ目のサービス（PC版）を作る

同じプロジェクトの中に、もう1つサービスを追加します。**モバイル版のサービスは消さずに残します。**

### 3-1. 同じリポジトリでサービスを追加
1. プロジェクトの画面（サービスが並ぶ背景）で **「＋ New」→「GitHub Repo」** を押す。
2. **さっきと同じ `japan-cvd-risk-simulator-meds`** を選ぶ（2つ目のサービスができます）。

### 3-2. ブランチを `feature/morita-dev` に変える
1. できたサービスの **「Settings」→「Source」** を開く。
2. **Branch** を **`feature/morita-dev`** に変更する（STEP 2-2 と同じ）。

### 3-3.【PC版のキモ】設定ファイルを `railway.outcomes.json` に指定
このサービスだけは **PC版**（`Dockerfile.outcomes`）を使わせる必要があります。
そのために、**使う設定ファイルを切り替え**ます。

1. **「Settings」** の中の **「Config-as-code」**（または **Railway Config File / Config Path**
   という名前の入力欄）を探す。
2. そこに **`railway.outcomes.json`** と入力して保存する。
3. これで、このサービスは自動的に **PC版**をビルドします（`railway.outcomes.json` が
   `Dockerfile.outcomes` を選ぶ仕組みです）。保存すると再ビルドが始まります。

### 3-4. 完成を待って、URLを発行
1. **「Deployments」** でビルド完了を待つ（数分）。
2. **「Settings」→「Networking」→「Generate Domain」** を1回押す。
3. 表示されたURLが **PC版の公開URL**です 🎉

---

## これで完了

- **モバイル版URL** と **PC版URL** の2つが手に入りました。それぞれ別のアプリとして動きます。

---

## 困ったとき・覚えておくこと

### うまくいかないとき
- **ビルドが失敗（赤い×／Failed）した場合**：**「Deployments」** タブでその回を開き、
  ログの**赤い行**をコピーして共有してください。原因を特定できます。
- **一番多い失敗**：STEP 2-2 / 3-2 の **ブランチを `feature/morita-dev` にし忘れ**。
  `main` のままだと設定ファイルが見つからず失敗します。まずここを確認。

### 料金
- 無料トライアルは **$5 / 30日** ぶん。2つのアプリを常時起動すると消費が早くなります。
- 節約したいサービスは **「Settings」→「Deploy」** で **Serverless**
  （アクセスが無い間はスリープ）をONにできます。
  代わりに、久しぶりの初回アクセスが少し遅くなります。

### アプリを更新したとき
- コードを直したら、`feature/morita-dev` ブランチに push するだけです：
  ```
  git push origin feature/morita-dev
  ```
  Railway が変更を検知して**自動で再デプロイ**します（ボタン操作は不要）。

### 補足
- Railway の画面デザインやボタン名は時々変わります。**「Generate Domain」** や
  **「Config-as-code」** 周りの表示が説明と違うときは、公式ドキュメント
  （ https://docs.railway.com ）を一度確認してください。

---

## 技術メモ（触らなくてOK・参考）

このリポジトリに入っている、デプロイ用のファイル：

| ファイル | 役割 |
|---|---|
| `Dockerfile.mobile` | モバイル版の設計図。`app_streamlit_mobile.py` を起動 |
| `Dockerfile.outcomes` | PC版の設計図。`app_streamlit_outcomes.py` を起動 |
| `railway.json` | モバイル版サービス用。`Dockerfile.mobile` を選ぶ（既定で読まれる） |
| `railway.outcomes.json` | PC版サービス用。`Dockerfile.outcomes` を選ぶ（STEP 3-3 で指定） |
| `requirements.txt` | 必要なライブラリを固定バージョンで記載（再現性のため） |

- Python は両方とも `python:3.12-slim` に固定（開発環境と同じ版でビルドの再現性を担保）。
- Streamlit は `--server.address 0.0.0.0 --server.port $PORT` で起動（Railway が渡すポート
  =8080 で待機）。`$PORT` を展開させるため Dockerfile の `CMD` は shell 形式で書いています。
