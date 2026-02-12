"""設定管理モジュール"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class APIKeys:
    """APIキー設定"""
    newsapi: str = ""
    newsdata: str = ""
    marketaux: str = ""
    gemini: str = ""

    @classmethod
    def from_env(cls) -> "APIKeys":
        return cls(
            newsapi=os.getenv("NEWSAPI_KEY", ""),
            newsdata=os.getenv("NEWSDATA_KEY", ""),
            marketaux=os.getenv("MARKETAUX_KEY", ""),
            gemini=os.getenv("GEMINI_API_KEY", ""),
        )


@dataclass
class ScoringWeights:
    """スコアリング重み設定"""
    sentiment: float = 0.25
    technical: float = 0.30
    fundamental: float = 0.25
    macro: float = 0.10
    risk: float = 0.10

    def normalize(self) -> "ScoringWeights":
        """重みを正規化して合計1.0にする"""
        total = self.sentiment + self.technical + self.fundamental + self.macro + self.risk
        if total == 0:
            return ScoringWeights()
        return ScoringWeights(
            sentiment=self.sentiment / total,
            technical=self.technical / total,
            fundamental=self.fundamental / total,
            macro=self.macro / total,
            risk=self.risk / total,
        )


@dataclass
class SmtpConfig:
    """SMTP メール設定"""
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    recipient: str = ""
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "SmtpConfig":
        return cls(
            host=os.getenv("SMTP_HOST", ""),
            port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            recipient=os.getenv("SMTP_RECIPIENT", os.getenv("SMTP_USER", "")),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.password and self.recipient)


# JP Target Tickers
JP_TARGET_TICKERS = [
    # 大型株（日経225主要銘柄）
    "7203.T",  # トヨタ自動車
    "6758.T",  # ソニーグループ
    "6861.T",  # キーエンス
    "9984.T",  # ソフトバンクグループ
    "6501.T",  # 日立製作所
    "8306.T",  # 三菱UFJフィナンシャル・グループ
    "7974.T",  # 任天堂
    "6902.T",  # デンソー
    "4063.T",  # 信越化学工業
    "9433.T",  # KDDI
    "6098.T",  # リクルートホールディングス
    "4568.T",  # 第一三共
    "8035.T",  # 東京エレクトロン
    "6594.T",  # 日本電産
    "7741.T",  # HOYA
    "4519.T",  # 中外製薬
    "6367.T",  # ダイキン工業
    "9432.T",  # 日本電信電話 (NTT)
    "2914.T",  # 日本たばこ産業
    "6954.T",  # ファナック
    # テクノロジー・半導体
    "6857.T",  # アドバンテスト
    "6723.T",  # ルネサスエレクトロニクス
    "6146.T",  # ディスコ
    "7735.T",  # SCREENホールディングス
    "6920.T",  # レーザーテック
]

# US Target Tickers
US_TARGET_TICKERS = [
    # Technology (Magnificent 7 + others)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "AMD", "INTC", "CRM", "ORCL", "ADBE",
    # Finance
    "JPM", "BAC", "V", "MA", "GS", "MS",
    # Consumer / Retail
    "WMT", "COST", "KO", "PEP", "MCD", "DIS", "NKE",
    # Healthcare
    "JNJ", "LLY", "PFE", "UNH",
    # Industrial / Energy
    "XOM", "CVX", "GE", "BA", "CAT",
]

# JP News Keywords
JP_NEWS_KEYWORDS = {
    "stock": ["株式", "決算", "業績", "増収", "減収", "上方修正", "下方修正", "M&A", "新製品"],
    "economy": ["GDP", "CPI", "消費者物価", "雇用統計", "日銀", "金利", "為替", "貿易収支"],
    "politics": ["経済政策", "税制改正", "規制緩和", "防衛費", "外交", "選挙", "補正予算"],
    "global": ["米国株", "ナスダック", "FRB", "中国経済", "原油価格", "地政学リスク"],
}

# US News Keywords
US_NEWS_KEYWORDS = {
    "stock": ["stock", "earnings", "revenue", "profit", "merger", "acquisition", "IPO", "guidance"],
    "economy": ["GDP", "CPI", "inflation", "jobs", "unemployment", "Fed", "interest rate", "FOMC"],
    "politics": ["White House", "Congress", "policy", "regulation", "trade war", "election", "budget"],
    "global": ["China", "Europe", "geopolitics", "oil price", "supply chain", "dollar"],
}


@dataclass
class Config:
    """アプリケーション全体設定"""
    # API Keys
    api_keys: APIKeys = field(default_factory=APIKeys.from_env)

    # SMTP メール
    smtp: SmtpConfig = field(default_factory=SmtpConfig.from_env)

    # Database
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'market_analyzer.db'}")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # スコアリング重み
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)

    # テクニカル分析パラメータ
    technical_params: dict = field(default_factory=lambda: {
        "sma_periods": [5, 25, 75],
        "ema_periods": [12, 26],
        "rsi_period": 14,
        "macd_params": (12, 26, 9),
        "bb_period": 20,
        "bb_std": 2.0,
        "atr_period": 14,
        "stoch_params": (14, 3, 3),
    })

    # センチメント分析設定
    sentiment_window_days: int = 7
    sentiment_decay_factor: float = 0.9  # 時間減衰係数

    # レポート設定
    top_n_recommendations: int = 10

    @property
    def market(self) -> str:
        """ターゲット市場 (JP or US) - 環境変数から動的に取得"""
        return os.getenv("MARKET", "JP").upper()

    @property
    def target_tickers(self) -> list[str]:
        """対象銘柄プール - 現在の市場設定に基づいて返す"""
        if self.market == "US":
            # 環境変数で S&P 500 全銘柄取得モードが有効な場合
            if os.getenv("USE_SP500_FULL", "false").lower() == "true":
                try:
                    import pandas as pd
                    # WikipediaからS&P 500構成銘柄を取得
                    tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
                    df = tables[0]
                    tickers = df['Symbol'].tolist()
                    # '.' を '-' に置換 (BRK.B -> BRK-B) YFinance形式に合わせる
                    return [t.replace('.', '-') for t in tickers]
                except Exception as e:
                    print(f"⚠️ S&P 500 全銘柄取得失敗: {e} - デフォルトリストを使用します")
                    return US_TARGET_TICKERS
            return US_TARGET_TICKERS
        return JP_TARGET_TICKERS

    @property
    def news_keywords(self) -> dict[str, list[str]]:
        """ニュース検索キーワード - 現在の市場設定に基づいて返す"""
        if self.market == "US":
            return US_NEWS_KEYWORDS
        return JP_NEWS_KEYWORDS


# グローバル設定インスタンス
config = Config()
