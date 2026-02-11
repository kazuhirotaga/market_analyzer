"""株価データ収集モジュール

yfinanceを使用して日本株式の株価データを取得し、データベースに保存する。
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from src.config import config
from src.database.models import get_session, Stock, PriceHistory

logger = logging.getLogger(__name__)


class StockCollector:
    """株価データ収集クラス"""

    def __init__(self, tickers: Optional[list[str]] = None):
        self.tickers = tickers or config.target_tickers

    def collect_stock_info(self) -> list[dict]:
        """全対象銘柄の基本情報を取得してDBに保存"""
        results = []
        session = get_session()

        try:
            for ticker_code in self.tickers:
                try:
                    info = self._fetch_stock_info(ticker_code)
                    if info:
                        # Upsert: 既存なら更新、なければ挿入
                        existing = session.query(Stock).filter_by(ticker=ticker_code).first()
                        if existing:
                            existing.name = info["name"]
                            existing.sector = info.get("sector")
                            existing.industry = info.get("industry")
                            existing.market_cap = info.get("market_cap")
                            existing.updated_at = datetime.utcnow()
                        else:
                            stock = Stock(
                                ticker=ticker_code,
                                name=info["name"],
                                sector=info.get("sector"),
                                industry=info.get("industry"),
                                market_cap=info.get("market_cap"),
                            )
                            session.add(stock)

                        results.append(info)
                        logger.info(f"✅ 銘柄情報取得成功: {ticker_code} ({info['name']})")
                except Exception as e:
                    logger.warning(f"⚠️ 銘柄情報取得失敗: {ticker_code} - {e}")

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 銘柄情報保存中にエラー: {e}")
            raise
        finally:
            session.close()

        logger.info(f"📊 銘柄情報取得完了: {len(results)}/{len(self.tickers)} 件")
        return results

    def collect_price_history(
        self,
        period: str = "3mo",
        interval: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, pd.DataFrame]:
        """全対象銘柄の株価履歴を取得してDBに保存"""
        all_data = {}
        session = get_session()

        try:
            for ticker_code in self.tickers:
                try:
                    df = self._fetch_price_data(
                        ticker_code, period=period, interval=interval,
                        start=start_date, end=end_date
                    )
                    if df is not None and not df.empty:
                        self._save_price_data(session, ticker_code, df)
                        all_data[ticker_code] = df
                        logger.info(f"✅ 株価データ取得成功: {ticker_code} ({len(df)} 件)")
                except Exception as e:
                    logger.warning(f"⚠️ 株価データ取得失敗: {ticker_code} - {e}")

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 株価データ保存中にエラー: {e}")
            raise
        finally:
            session.close()

        logger.info(f"📈 株価データ取得完了: {len(all_data)}/{len(self.tickers)} 銘柄")
        return all_data

    def get_latest_prices(self) -> dict[str, dict]:
        """全対象銘柄の最新株価を取得（DB保存なし、リアルタイム用）"""
        results = {}
        for ticker_code in self.tickers:
            try:
                ticker = yf.Ticker(ticker_code)
                fast_info = ticker.fast_info
                results[ticker_code] = {
                    "ticker": ticker_code,
                    "last_price": getattr(fast_info, "last_price", None),
                    "previous_close": getattr(fast_info, "previous_close", None),
                    "market_cap": getattr(fast_info, "market_cap", None),
                    "day_high": getattr(fast_info, "day_high", None),
                    "day_low": getattr(fast_info, "day_low", None),
                }
                change = None
                if results[ticker_code]["last_price"] and results[ticker_code]["previous_close"]:
                    prev = results[ticker_code]["previous_close"]
                    if prev > 0:
                        change = (results[ticker_code]["last_price"] - prev) / prev * 100
                results[ticker_code]["change_pct"] = change
            except Exception as e:
                logger.warning(f"⚠️ 最新株価取得失敗: {ticker_code} - {e}")

        return results

    def get_market_indices(self) -> dict[str, dict]:
        """主要指数を取得"""
        indices = {
            "^N225": "日経225",
            "^TPX": "TOPIX",
            "USDJPY=X": "USD/JPY",
            "^VIX": "VIX指数",
            "^GSPC": "S&P 500",
        }
        results = {}
        for symbol, name in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                if not hist.empty:
                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2] if len(hist) > 1 else latest
                    close_val = float(latest["Close"])
                    prev_close = float(prev["Close"])
                    change_pct = ((close_val - prev_close) / prev_close * 100) if prev_close > 0 else 0
                    results[symbol] = {
                        "name": name,
                        "close": round(close_val, 2),
                        "change_pct": round(change_pct, 2),
                    }
            except Exception as e:
                logger.warning(f"⚠️ 指数取得失敗: {symbol} ({name}) - {e}")

        return results

    # --- Private Methods ---

    def _fetch_stock_info(self, ticker_code: str) -> Optional[dict]:
        """yfinanceから銘柄情報を取得"""
        ticker = yf.Ticker(ticker_code)
        info = ticker.info

        if not info or "shortName" not in info:
            return None

        return {
            "ticker": ticker_code,
            "name": info.get("shortName", info.get("longName", ticker_code)),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "roe": info.get("returnOnEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "operating_margin": info.get("operatingMargins"),
        }

    def _fetch_price_data(
        self,
        ticker_code: str,
        period: str = "3mo",
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """yfinanceから株価データを取得"""
        ticker = yf.Ticker(ticker_code)

        if start and end:
            df = ticker.history(start=start, end=end, interval=interval)
        else:
            df = ticker.history(period=period, interval=interval)

        if df.empty:
            return None

        df = df.reset_index()
        return df

    def _save_price_data(self, session, ticker_code: str, df: pd.DataFrame):
        """株価データをDBに保存（upsert）"""
        for _, row in df.iterrows():
            row_date = row["Date"]
            if isinstance(row_date, pd.Timestamp):
                row_date = row_date.date()

            existing = (
                session.query(PriceHistory)
                .filter_by(ticker=ticker_code, date=row_date)
                .first()
            )

            if existing:
                existing.open = float(row["Open"])
                existing.high = float(row["High"])
                existing.low = float(row["Low"])
                existing.close = float(row["Close"])
                existing.volume = int(row["Volume"])
            else:
                price = PriceHistory(
                    ticker=ticker_code,
                    date=row_date,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
                session.add(price)

    def get_price_dataframe(self, ticker_code: str, days: int = 90) -> Optional[pd.DataFrame]:
        """DBから株価データをDataFrameとして取得"""
        session = get_session()
        try:
            cutoff = date.today() - timedelta(days=days)
            rows = (
                session.query(PriceHistory)
                .filter(PriceHistory.ticker == ticker_code)
                .filter(PriceHistory.date >= cutoff)
                .order_by(PriceHistory.date)
                .all()
            )

            if not rows:
                return None

            data = [{
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            } for r in rows]

            df = pd.DataFrame(data)
            df.set_index("date", inplace=True)
            return df
        finally:
            session.close()
