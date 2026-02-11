# デプロイガイド (Deployment Guide)

このプロジェクトはローカル（Windowsタスクスケジューラ）だけでなく、クラウド環境（Render, GitHub Actions）でも自動実行可能です。

---

## 🚀 オプション A: Render (推奨環境)

Render の **Cron Job** 機能を使用します（有料プラン推奨）。PostgreSQLデータベースを永続化する場合に適しています。

### 手順
1. **GitHubリポジトリを作成**し、このコードをプッシュします。
2. **Render ダッシュボード** (https://dashboard.render.com/) にアクセスします。
3. "New +" から **Blueprint** を選択し、リポジトリを連携します。
   - **Root Directory**: 空欄（デフォルト）でOKです。
4. 自動的に `render.yaml` が読み込まれ、設定画面が表示されます。
5. **Environment Variables** (環境変数) の入力欄が自動表示されるので、値を入力してください：
   - `GEMINI_API_KEY`: Gemini APIキー
   - `NEWSAPI_KEY`: NewsAPIキー
   - `NEWSDATA_KEY`: NewsData.ioキー
   - `MARKETAUX_KEY`: Marketauxキー
   - `SMTP_HOST`: `smtp.gmail.com`
   - `SMTP_PORT`: `587`
   - `SMTP_USER`: 送信元Gmailアドレス
   - `SMTP_PASSWORD`: アプリパスワード
   - `SMTP_RECIPIENT`: 受信者メールアドレス
6. **Apply** をクリックしてデプロイします。順次ビルドが開始されます。

> **注意**: メモリ不足でエラーになる場合は、Planを `Starter` 以上にアップグレードしてください。

---

## 🐙 オプション B: GitHub Actions (無料枠活用)

GitHub Actions を使用して、無料で毎日実行できます。ただし、データベース（SQLite）は毎回リセットされるため、過去データの蓄積には外部データベース（Neon, Supabase等）が必要です。

### 手順
1. リポジトリの **Settings > Secrets and variables > Actions** に移動します。
2. "New repository secret" から以下の環境変数を登録します：
   - `GEMINI_API_KEY`
   - `NEWSAPI_KEY`
   - `NEWSDATA_KEY`
   - `MARKETAUX_KEY`
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `SMTP_RECIPIENT`
   - `DATABASE_URL` (外部PostgreSQLを使う場合。例: `postgresql://user:pass@host/db`)

3. 設定完了後、自動的に毎日18:00に実行されます。「Actions」タブから手動実行も可能です。

---

## 🛠️ ローカル環境 (Windows)

Windowsタスクスケジューラを使用する場合：

1. PowerShellを管理者権限で開きます。
2. `scripts/register_task.ps1` を実行します。

```powershell
Set-ExecutionPolicy RemoteSigned -Scope Process
.\scripts\register_task.ps1
```

---

## 🗑️ プロジェクトの削除 (Render)

Render 上のリソースを削除したい場合の手順です。

1. **Render ダッシュボード** (https://dashboard.render.com/) にアクセスします。
2. 左メニューの **Blueprints** または **Services** から、対象のプロジェクトを選択します。
3. **Settings** タブをクリックします。
4. ページ最下部までスクロールし、**Delete Service** (または **Delete Blueprint**) ボタンをクリックします。
5. 確認画面でプロジェクト名を入力して削除を実行します。

> **注意**: Blueprintで作成した場合、Blueprint自体を削除すると関連するすべてのサービス（Cron Job, DB等）が一括で削除されます。

---

## ⚡ オプション C: Google Colab (メモリ不足回避)

Renderの無料枠でメモリ不足(OOM)になる場合、Google Colabを使用することをお勧めします。12GB以上のメモリが利用可能で、Google Driveにデータを永続化できます。

### 手順
1. **[Google Colab](https://colab.research.google.com/)** を開きます。
2. 「ノートブックを開く」→「GitHub」タブを選択します。
3. リポジトリURLを入力 (`https://github.com/ikaruga1123/market_analyzer`) し、表示される `notebooks/market_analyzer_colab.ipynb` を開きます。
4. ノートブックの指示に従って実行します：
   - Google Driveのマウント
   - 環境変数 (Secrets) の設定
   - 分析実行

### 🔒 プライベートリポジトリの場合
リポジトリがPrivateの場合は、以下を追加で設定してください：
1. GitHubで [Personal Access Token (Classic)](https://github.com/settings/tokens) を作成します（`repo` スコープを選択）。
2. Google Colabのサイドバー「🔑 (Secrets)」を開きます。
3. `GITHUB_TOKEN` という名前でトークンを追加し、「ノートブックからのアクセスを許可」を有効にします。

この方法なら、Renderのようなメモリ制限を気にせず実行可能です。
