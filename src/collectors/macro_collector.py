"""マクロ経済指標収集モジュール

yfinance と公開データから主要マクロ経済指標を取得する。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class MacroIndicators:
    """マクロ経済指標データ"""
    usdjpy: float | None = None
    usdjpy_change: float | None = None
    nikkei225: float | None = None
    nikkei225_change: float | None = None
    topix: float | None = None
    topix_change: float | None = None
    sp500: float | None = None
    sp500_change: float | None = None
    vix: float | None = None
    vix_change: float | None = None
    us10y_yield: float | None = None
    us10y_change: float | None = None
    oil_price: float | None = None
    oil_change: float | None = None
    gold_price: float | None = None
    gold_change: float | None = None
    collected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "usdjpy": {"value": self.usdjpy, "change_pct": self.usdjpy_change},
            "nikkei225": {"value": self.nikkei225, "change_pct": self.nikkei225_change},
            "topix": {"value": self.topix, "change_pct": self.topix_change},
            "sp500": {"value": self.sp500, "change_pct": self.sp500_change},
            "vix": {"value": self.vix, "change_pct": self.vix_change},
            "us10y_yield": {"value": self.us10y_yield, "change_pct": self.us10y_change},
            "oil": {"value": self.oil_price, "change_pct": self.oil_change},
            "gold": {"value": self.gold_price, "change_pct": self.gold_change},
            "collected_at": self.collected_at,
        }


class MacroCollector:
    """マクロ経済指標収集クラス"""

    SYMBOLS = {
        "USDJPY=X":  ("usdjpy", "usdjpy_change"),
        "^N225":     ("nikkei225", "nikkei225_change"),
        "^TPX":      ("topix", "topix_change"),
        "^GSPC":     ("sp500", "sp500_change"),
        "^VIX":      ("vix", "vix_change"),
        "^TNX":      ("us10y_yield", "us10y_change"),
        "CL=F":      ("oil_price", "oil_change"),
        "GC=F":      ("gold_price", "gold_change"),
    }

    def collect(self) -> MacroIndicators:
        """全マクロ指標を一括取得"""
        indicators = MacroIndicators()

        for symbol, (val_attr, chg_attr) in self.SYMBOLS.items():
            try:
                value, change = self._fetch_latest(symbol)
                setattr(indicators, val_attr, value)
                setattr(indicators, chg_attr, change)
                logger.debug(f"✅ {symbol}: {value} ({change:+.2f}%)" if change else f"✅ {symbol}: {value}")
            except Exception as e:
                logger.warning(f"⚠️ マクロ指標取得失敗 {symbol}: {e}")

        logger.info("🌐 マクロ経済指標取得完了")
        return indicators

    def calculate_macro_score(self, indicators: MacroIndicators | None = None) -> float:
        """マクロ経済環境のスコアを計算 (0〜100)

        高スコア = 好調な経済環境 (株式にプラス)
        低スコア = 不調な経済環境 (株式にマイナス)
        """
        if indicators is None:
            indicators = self.collect()

        scores = []
        weights = []

        # VIX: 低いほど安定 → 高スコア
        if indicators.vix is not None:
            if indicators.vix < 15:
                vix_score = 90
            elif indicators.vix < 20:
                vix_score = 70
            elif indicators.vix < 25:
                vix_score = 50
            elif indicators.vix < 30:
                vix_score = 30
            else:
                vix_score = 10
            scores.append(vix_score)
            weights.append(0.2)

        # 日経225の前日比: プラスなら高スコア
        if indicators.nikkei225_change is not None:
            n225_score = max(0, min(100, 50 + indicators.nikkei225_change * 10))
            scores.append(n225_score)
            weights.append(0.2)

        # S&P 500の前日比: 米国市場の影響
        if indicators.sp500_change is not None:
            sp_score = max(0, min(100, 50 + indicators.sp500_change * 10))
            scores.append(sp_score)
            weights.append(0.15)

        # USD/JPY変化: 円安は輸出企業にプラス (やや高スコア)
        if indicators.usdjpy_change is not None:
            fx_score = max(0, min(100, 50 + indicators.usdjpy_change * 5))
            scores.append(fx_score)
            weights.append(0.15)

        # 米国10年債利回り変化: 急上昇は株にマイナス
        if indicators.us10y_change is not None:
            bond_score = max(0, min(100, 50 - indicators.us10y_change * 15))
            scores.append(bond_score)
            weights.append(0.15)

        # 原油価格変化: 急騰はコスト増でマイナス
        if indicators.oil_change is not None:
            oil_score = max(0, min(100, 50 - indicators.oil_change * 5))
            scores.append(oil_score)
            weights.append(0.15)

        if not scores:
            return 50.0  # データなしは中立

        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

        return round(weighted_score, 1)

    def _fetch_latest(self, symbol: str) -> tuple[float | None, float | None]:
        """yfinanceから最新値と前日比変化率を取得"""
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")

        if hist.empty:
            return None, None

        latest_close = float(hist["Close"].iloc[-1])

        change_pct = None
        if len(hist) > 1:
            prev_close = float(hist["Close"].iloc[-2])
            if prev_close > 0:
                change_pct = round((latest_close - prev_close) / prev_close * 100, 2)

        return round(latest_close, 2), change_pct
