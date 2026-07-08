# 引き継ぎ：デプロイ手順書（README）の作成（Claude Code向け）

## タスク
ブラウザ操作だけでこのアプリをRailwayに公開できるようにする
**手順書（README）** を作成する。プログラミング知識ゼロでも上から順にボタンを押すだけで
進められる内容にすること。

## 前提となる作業リポジトリ
- リポジトリ：`/japan-cvd-risk-simulator-meds`
- 対象ブランチ：`deploy/railway`（アプリ一式＋デプロイ設定はこのブランチにある。main にはない）
- Streamlit製アプリ。1リポジトリから **2つのアプリ** を別URLで公開する構成：
  - **モバイル版** … `Dockerfile.mobile`
  - **PC版** … `Dockerfile.outcomes`
- Railwayは「1アプリ＝1サービス」なので、サービスを2つ作る運用。

---

## リポジトリを調べて確定してほしいこと（重要）
Claude Codeはリポジトリを直接読めるので、以下を**実ファイルで確認**してからREADMEを書くこと。
推測で書かず、実物に合わせること。

1. **Dockerfileのファイル名**を確認：`Dockerfile.mobile` と `Dockerfile.outcomes` で正しいか。
   もし別名（例：`Dockerfile.pc` など）なら実名に合わせる。
2. 各Dockerfileの **CMD** を確認し、どのStreamlitファイルを起動しているか
   （モバイル版＝どのpy、PC版＝どのpy）を把握。ポートが `$PORT` 経由で 8080 になるかも確認。
3. **設定ファイルの有無と中身**を確認：
   - `railway.json`（モバイル版用。`Dockerfile.mobile` を指しているはず）
   - `railway.outcomes.json`（PC版用。存在するか？ 中身は `Dockerfile.outcomes` を指しているか？）
   - これらから「PC版サービスがどうやって Dockerfile.outcomes を選ぶか」を確定する。
4. 上記3の結果で、**PC版のDockerfile指定方法**を一つに絞ってREADMEに書く：
   - もし `railway.outcomes.json` が存在するなら
     → 「PC版サービスの Config-as-code（Railway Config File）に `railway.outcomes.json` を指定」を正式手順にする。
   - もし存在せず、ダッシュボードのBuilderドロップダウンで選ぶ方式なら
     → 「Build → Builder で `Dockerfile.outcomes` を選択」を正式手順にする。
   - ※ 現状の未解決点はここだけ。実ファイルを見れば確定できる。

---

## READMEに必ず入れる手順（確認済みの正しい流れ）

**STEP 0. フォーク**
- GitHubで `soomorita/japan-cvd-risk-simulator-meds` を開き、Fork → 自分のアカウントにコピー。
- 以降は自分のフォークを使う。

**STEP 1. Railwayにサインイン**
- `https://railway.com` → Login → Continue with GitHub。
- 初回は「Configure GitHub App」で対象リポジトリにチェックして許可。

**STEP 2. 1つ目のサービス（モバイル版）**
1. New Project → Deploy from GitHub repo → 自分のリポジトリを選ぶ。
2.【最重要】Settings → Source の Branch を `main` → **`deploy/railway`** に変更。
   （mainのままだとビルド失敗。よくある失敗原因なので強調する）
3. Build → Builder が **`Dockerfile.mobile`** になっているか確認。
4. Deployments タブでビルド完了（Success／Online）を待つ（数分）。
5. Settings → Networking → **Generate Domain** を1回クリック → 公開URL発行（自動でポート8080）。

**STEP 3. 2つ目のサービス（PC版）**
1. 同じプロジェクトで ＋New → GitHub Repo → **同じリポジトリ**を選ぶ（モバイル版サービスは残す）。
2. Settings → Source の Branch を **`deploy/railway`** に変更。
3. **PC版のDockerfileを使う指定**（上記「確定してほしいこと」の4で決めた方法で書く）。
4. ビルド完了を待つ → Networking → **Generate Domain** → PC版の公開URL発行。

---

## READMEの体裁・トーン
- 読者は非技術者。専門用語は避け、必要なら一言で補足。
- 「画面のこのボタンを押す」レベルの粒度。ボタン名は実際の表記（英語UIならその英語）で書く。
- 冒頭に「1フォークから2アプリを別URLで公開する」全体像を1〜2文で。
- 末尾に「うまくいかないとき（ログの赤い行を共有／ブランチ指定忘れが多い）」「料金（$5/30日、
  Serverlessで節約可）」「更新時は deploy/railway にpushで自動再デプロイ」の補足を入れる。

## 配置場所（要判断）
- 手順書なので、リポジトリ直下に `DEPLOY.md` などの独立ファイルとして置くのが無難
  （メインの `README.md` を上書きしないこと）。ファイル名は既存構成を見て衝突しないものにする。

---

## 補足
- Railway/Railpackの仕様は変わりやすいので、Generate Domainやconfig-as-code周りで挙動が
  想定と違ったら公式ドキュメント（docs.railway.com）を一度確認する。
- 既に人間側でモバイル版のデプロイ成功まで検証済み。PC版のDockerfile指定方法の確定が
  残っている唯一の実質的な作業。