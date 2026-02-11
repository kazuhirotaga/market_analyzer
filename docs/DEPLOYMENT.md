# デプロイガイド (Deployment Guide)

このプロジェクトはローカル（Windowsタスクスケジューラ）だけでなく、クラウド環境（Render, GitHub Actions）でも自動実行可能です。

---

## 🚀 オプション A: Render (推奨環境)

Render の **Cron Job** 機能を使用します（有料プラン推奨）。PostgreSQLデータベースを永続化する場合に適しています。

### 手順
1. **GitHubリポジトリを作成**し、このコードをプッシュします。
2. **Render ダッシュボード** (https://dashboard.render.com/) にアクセスします。
3. "New +" から **Blueprint** を選択し、リポジトリを連携します。
4. 自動的に `render.yaml` が読み込まれ、Cron Job (と必要ならDatabase) の設定が表示されます。
5. **Environment Variables** (環境変数) を設定します：
   - `GEMINI_API_KEY`: Gemini APIキー
   - `NEWSAPI_KEY`: NewsAPIキー
   - `NEWSDATA_KEY`: NewsData.ioキー
   - `MARKETAUX_KEY`: Marketauxキー
   - `SMTP_HOST`: `smtp.gmail.com`
   - `SMTP_PORT`: `587`
   - `SMTP_USER`: 送信元Gmailアドレス
   - `SMTP_PASSWORD`: アプリパスワード
   - `SMTP_RECIPIENT`: 受信者メールアドレス
6. **Apply** をクリックしてデプロイします。毎日日本時間18:00に実行されます。

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
