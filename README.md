# 🏦 Market Analyzer — 日本株式市場分析 & おすすめ銘柄選別システム

株価・株式ニュース・経済ニュース・政治ニュースを統合的に分析し、おすすめ銘柄を選別するシステムです。

## 🚀 クイックスタート

### 1. 環境セットアップ

```bash
# 仮想環境の作成
python -m venv .venv
.venv\Scripts\activate    # Windows

# 依存パッケージのインストール
pip install -e ".[dev]"
```

### 2. 環境変数の設定

```bash
# .envファイルを作成
copy .env.example .env

# .envファイルを編集し、APIキーを設定
# - NEWSAPI_KEY: https://newsapi.org/ で取得
# - GEMINI_API_KEY: Google AI Studio で取得
# (ニュースAPIキーがなくても株価分析は動作します)
```

### 3. データベース初期化

```bash
python scripts/setup_db.py
```

### 4. 分析実行

```bash
# デイリー分析 (フルパイプライン)
python scripts/run_daily.py

# オプション
python scripts/run_daily.py -n 20       # Top20を表示
python scripts/run_daily.py -v          # 詳細ログ
```

## 📊 システム構成

```
市場データ収集 → 分析エンジン → スコアリング → おすすめ銘柄レポート
```

### データ収集
- **株価データ**: yfinance (日経225主要銘柄 + 半導体関連)
- **ニュースデータ**: NewsAPI / NewsData.io / marketaux
- **マクロ指標**: 日経225, TOPIX, USD/JPY, VIX, 米10年債, 原油, 金

### 分析エンジン
- **センチメント分析**: 日本語FinBERT + キーワード分析
- **テクニカル分析**: SMA, EMA, MACD, RSI, ストキャスティクス, ボリンジャーバンド, ATR, OBV
- **ファンダメンタル分析**: PER, PBR, ROE, 営業利益率, 売上成長率, 配当利回り

### スコアリング (重み)
| 因子 | 重み |
|---|---|
| テクニカル | 30% |
| センチメント | 25% |
| ファンダメンタル | 25% |
| マクロ環境 | 10% |
| リスク | 10% |

### レーティング
| スコア | レーティング |
|---|---|
| 80-100 | 🟢 Strong Buy |
| 60-79 | 🔵 Buy |
| 40-59 | ⚪ Hold |
| 20-39 | 🟠 Sell |
| 0-19 | 🔴 Strong Sell |

## 📁 プロジェクト構成

```
market_analyzer/
├── src/
│   ├── config.py                   # 設定管理
│   ├── collectors/                 # データ収集
│   │   ├── stock_collector.py      # 株価データ
│   │   ├── news_collector.py       # ニュース
│   │   └── macro_collector.py      # マクロ経済指標
│   ├── analyzers/                  # 分析エンジン
│   │   ├── sentiment_analyzer.py   # センチメント分析
│   │   ├── technical_analyzer.py   # テクニカル分析
│   │   └── fundamental_analyzer.py # ファンダメンタル分析
│   ├── scoring/                    # スコアリング
│   │   ├── scorer.py               # 多因子スコアリング
│   │   └── recommender.py          # おすすめ銘柄生成
│   ├── reports/                    # レポート
│   │   └── report_generator.py     # CLIレポート出力
│   └── database/                   # データベース
│       └── models.py               # SQLAlchemy モデル
├── scripts/
│   ├── run_daily.py                # デイリー分析実行
│   └── setup_db.py                 # DB初期化
├── tests/
├── pyproject.toml
├── .env.example
└── README.md
```

## ⚠️ 免責事項

このシステムは情報提供のみを目的としており、投資助言ではありません。投資判断は自己責任で行ってください。
