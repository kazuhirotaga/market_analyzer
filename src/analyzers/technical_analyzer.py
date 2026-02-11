"""テクニカル分析モジュール

pandas-ta を使用してテクニカル指標を計算し、
複合テクニカルスコアを算出する。
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

from src.config import config
from src.collectors.stock_collector import StockCollector

logger = logging.getLogger(__name__)

# pandas-ta を遅延インポート (import 時間の短縮)
_ta_loaded = False


def _ensure_ta():
    global _ta_loaded
    if not _ta_loaded:
        try:
            import pandas_ta  # noqa: F401
            _ta_loaded = True
        except ImportError:
            logger.warning("⚠️ pandas-ta 未インストール。pip install pandas-ta で導入してください。")
            raise


class TechnicalAnalyzer:
    """テクニカル分析クラス"""

    def __init__(self):
        self.params = config.technical_params
        self.stock_collector = StockCollector()

    def analyze(self, ticker: str, df: Optional[pd.DataFrame] = None) -> dict:
        """指定銘柄のテクニカル分析を実行

        Args:
            ticker: 銘柄コード
            df: 株価DataFrame (None の場合はDBから取得)

        Returns:
            {
                "ticker": str,
                "trend_score": float,       # -1.0 〜 1.0
                "momentum_score": float,    # -1.0 〜 1.0
                "volatility_score": float,  # 0.0 〜 1.0 (高い = 安定)
                "volume_score": float,      # -1.0 〜 1.0
                "composite_score": float,   # 0 〜 100
                "signals": list[str],       # シグナルの説明
                "indicators": dict          # 各指標の値
            }
        """
        _ensure_ta()
        import pandas_ta as ta

        if df is None:
            df = self.stock_collector.get_price_dataframe(ticker, days=120)

        if df is None or len(df) < 30:
            logger.warning(f"⚠️ {ticker}: データ不足 (>30日必要)")
            return self._empty_result(ticker)

        # DataFrameのカラム名を正規化
        df.columns = [c.lower() for c in df.columns]

        indicators = {}
        signals = []

        # --- トレンド指標 ---
        trend_score = self._calc_trend_score(df, ta, indicators, signals)

        # --- モメンタム指標 ---
        momentum_score = self._calc_momentum_score(df, ta, indicators, signals)

        # --- ボラティリティ指標 ---
        volatility_score = self._calc_volatility_score(df, ta, indicators, signals)

        # --- 出来高指標 ---
        volume_score = self._calc_volume_score(df, ta, indicators, signals)

        # --- 複合スコア (0〜100) ---
        # 各スコアを 0〜100 にマッピングして加重平均
        composite = (
            (trend_score + 1) / 2 * 100 * 0.35 +
            (momentum_score + 1) / 2 * 100 * 0.30 +
            volatility_score * 100 * 0.15 +
            (volume_score + 1) / 2 * 100 * 0.20
        )
        composite = max(0, min(100, round(composite, 1)))

        return {
            "ticker": ticker,
            "trend_score": round(trend_score, 4),
            "momentum_score": round(momentum_score, 4),
            "volatility_score": round(volatility_score, 4),
            "volume_score": round(volume_score, 4),
            "composite_score": composite,
            "signals": signals,
            "indicators": indicators,
        }

    def _calc_trend_score(self, df: pd.DataFrame, ta, indicators: dict, signals: list) -> float:
        """トレンドスコアを計算 (-1.0 〜 1.0)"""
        scores = []

        # SMA クロス判定
        sma_periods = self.params["sma_periods"]
        for period in sma_periods:
            sma = ta.sma(df["close"], length=period)
            if sma is not None and len(sma) > 0:
                indicators[f"sma_{period}"] = round(float(sma.iloc[-1]), 2) if pd.notna(sma.iloc[-1]) else None

        if all(f"sma_{p}" in indicators and indicators[f"sma_{p}"] is not None for p in sma_periods):
            current_price = float(df["close"].iloc[-1])
            sma_short = indicators[f"sma_{sma_periods[0]}"]
            sma_mid = indicators[f"sma_{sma_periods[1]}"]
            sma_long = indicators[f"sma_{sma_periods[2]}"]

            # 価格と移動平均線の位置関係
            above_count = sum([
                current_price > sma_short,
                current_price > sma_mid,
                current_price > sma_long,
                sma_short > sma_mid,
                sma_mid > sma_long,
            ])
            sma_score = (above_count / 5) * 2 - 1  # 0〜5 → -1〜1
            scores.append(sma_score)

            if sma_short > sma_mid > sma_long:
                signals.append("🟢 パーフェクトオーダー (上昇トレンド)")
            elif sma_short < sma_mid < sma_long:
                signals.append("🔴 逆パーフェクトオーダー (下降トレンド)")

        # MACD
        fast, slow, signal_period = self.params["macd_params"]
        macd_result = ta.macd(df["close"], fast=fast, slow=slow, signal=signal_period)
        if macd_result is not None and not macd_result.empty:
            macd_cols = macd_result.columns.tolist()
            macd_val = float(macd_result[macd_cols[0]].iloc[-1]) if pd.notna(macd_result[macd_cols[0]].iloc[-1]) else 0
            macd_signal = float(macd_result[macd_cols[2]].iloc[-1]) if pd.notna(macd_result[macd_cols[2]].iloc[-1]) else 0
            macd_hist = float(macd_result[macd_cols[1]].iloc[-1]) if pd.notna(macd_result[macd_cols[1]].iloc[-1]) else 0

            indicators["macd"] = round(macd_val, 4)
            indicators["macd_signal"] = round(macd_signal, 4)
            indicators["macd_hist"] = round(macd_hist, 4)

            # MACDヒストグラムの符号でスコア
            if macd_hist > 0:
                scores.append(min(1.0, macd_hist / abs(macd_val + 0.001)))
                if macd_val > macd_signal and len(macd_result) > 1:
                    prev_macd = float(macd_result[macd_cols[0]].iloc[-2]) if pd.notna(macd_result[macd_cols[0]].iloc[-2]) else 0
                    prev_signal = float(macd_result[macd_cols[2]].iloc[-2]) if pd.notna(macd_result[macd_cols[2]].iloc[-2]) else 0
                    if prev_macd <= prev_signal:
                        signals.append("🟢 MACDゴールデンクロス")
            else:
                scores.append(max(-1.0, macd_hist / abs(macd_val + 0.001)))

        return np.mean(scores) if scores else 0.0

    def _calc_momentum_score(self, df: pd.DataFrame, ta, indicators: dict, signals: list) -> float:
        """モメンタムスコアを計算 (-1.0 〜 1.0)"""
        scores = []

        # RSI
        rsi_period = self.params["rsi_period"]
        rsi = ta.rsi(df["close"], length=rsi_period)
        if rsi is not None and len(rsi) > 0 and pd.notna(rsi.iloc[-1]):
            rsi_val = float(rsi.iloc[-1])
            indicators["rsi"] = round(rsi_val, 2)

            # RSI 0-100 → -1〜1 のスコア
            # RSI=50 が中立(0)、30以下は売られすぎ(反発期待で高スコア)、70以上は過熱(低スコア)
            if rsi_val < 30:
                rsi_score = 0.8  # 売られすぎ → 買いシグナル
                signals.append(f"🟢 RSI={rsi_val:.0f} (売られすぎ圏)")
            elif rsi_val > 70:
                rsi_score = -0.8  # 過熱 → 売りシグナル
                signals.append(f"🔴 RSI={rsi_val:.0f} (過熱圏)")
            else:
                rsi_score = (50 - rsi_val) / 50 * -1  # 50中心で線形
            scores.append(rsi_score)

        # ストキャスティクス
        k_period, d_period, smooth = self.params["stoch_params"]
        stoch = ta.stoch(df["high"], df["low"], df["close"], k=k_period, d=d_period, smooth_k=smooth)
        if stoch is not None and not stoch.empty:
            stoch_cols = stoch.columns.tolist()
            k_val = float(stoch[stoch_cols[0]].iloc[-1]) if pd.notna(stoch[stoch_cols[0]].iloc[-1]) else 50
            d_val = float(stoch[stoch_cols[1]].iloc[-1]) if pd.notna(stoch[stoch_cols[1]].iloc[-1]) else 50

            indicators["stoch_k"] = round(k_val, 2)
            indicators["stoch_d"] = round(d_val, 2)

            if k_val < 20:
                scores.append(0.6)
            elif k_val > 80:
                scores.append(-0.6)
            else:
                scores.append((50 - k_val) / 50 * -0.5)

        return np.mean(scores) if scores else 0.0

    def _calc_volatility_score(self, df: pd.DataFrame, ta, indicators: dict, signals: list) -> float:
        """ボラティリティスコアを計算 (0.0 〜 1.0, 高い = 安定)"""
        scores = []

        # ボリンジャーバンド
        bb_period = self.params["bb_period"]
        bb_std = self.params["bb_std"]
        bbands = ta.bbands(df["close"], length=bb_period, std=bb_std)
        if bbands is not None and not bbands.empty:
            bb_cols = bbands.columns.tolist()
            bb_lower = float(bbands[bb_cols[0]].iloc[-1]) if pd.notna(bbands[bb_cols[0]].iloc[-1]) else 0
            bb_mid = float(bbands[bb_cols[1]].iloc[-1]) if pd.notna(bbands[bb_cols[1]].iloc[-1]) else 0
            bb_upper = float(bbands[bb_cols[2]].iloc[-1]) if pd.notna(bbands[bb_cols[2]].iloc[-1]) else 0

            indicators["bb_lower"] = round(bb_lower, 2)
            indicators["bb_mid"] = round(bb_mid, 2)
            indicators["bb_upper"] = round(bb_upper, 2)

            current_price = float(df["close"].iloc[-1])
            bb_width = bb_upper - bb_lower
            if bb_width > 0:
                # バンド幅が狭いほど安定 → 高スコア
                bb_pct = bb_width / bb_mid if bb_mid > 0 else 0
                stability = max(0, 1 - bb_pct * 10)  # 幅10%以上で0
                scores.append(stability)

                if current_price <= bb_lower:
                    signals.append("🟢 ボリンジャーバンド下限タッチ (買いシグナル)")
                elif current_price >= bb_upper:
                    signals.append("🔴 ボリンジャーバンド上限タッチ (売りシグナル)")

        # ATR
        atr_period = self.params["atr_period"]
        atr = ta.atr(df["high"], df["low"], df["close"], length=atr_period)
        if atr is not None and len(atr) > 0 and pd.notna(atr.iloc[-1]):
            atr_val = float(atr.iloc[-1])
            current_price = float(df["close"].iloc[-1])
            atr_pct = atr_val / current_price if current_price > 0 else 0
            indicators["atr"] = round(atr_val, 2)
            indicators["atr_pct"] = round(atr_pct * 100, 2)

            # ATR%が低いほど安定
            stability = max(0, 1 - atr_pct * 20)
            scores.append(stability)

        return np.mean(scores) if scores else 0.5

    def _calc_volume_score(self, df: pd.DataFrame, ta, indicators: dict, signals: list) -> float:
        """出来高スコアを計算 (-1.0 〜 1.0)"""
        scores = []

        if "volume" in df.columns and len(df) > 20:
            # 直近出来高 vs 20日平均出来高
            vol_20ma = df["volume"].rolling(20).mean().iloc[-1]
            current_vol = df["volume"].iloc[-1]

            if pd.notna(vol_20ma) and vol_20ma > 0:
                vol_ratio = current_vol / vol_20ma
                indicators["volume_ratio"] = round(vol_ratio, 2)

                # 出来高増加 + 株価上昇 = 強気
                price_change = (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) if len(df) > 1 else 0

                if vol_ratio > 1.5 and price_change > 0:
                    scores.append(0.8)
                    signals.append(f"🟢 出来高急増 ({vol_ratio:.1f}倍) + 株価上昇")
                elif vol_ratio > 1.5 and price_change < 0:
                    scores.append(-0.8)
                    signals.append(f"🔴 出来高急増 ({vol_ratio:.1f}倍) + 株価下落")
                elif vol_ratio > 1.0:
                    scores.append(0.2 if price_change > 0 else -0.2)
                else:
                    scores.append(0.0)

            # OBV (On-Balance Volume)
            obv = ta.obv(df["close"], df["volume"])
            if obv is not None and len(obv) > 5:
                obv_sma5 = obv.rolling(5).mean()
                if pd.notna(obv_sma5.iloc[-1]) and pd.notna(obv_sma5.iloc[-5]):
                    obv_trend = 1 if obv.iloc[-1] > obv_sma5.iloc[-1] else -1
                    scores.append(obv_trend * 0.3)

        return np.mean(scores) if scores else 0.0

    def _empty_result(self, ticker: str) -> dict:
        """データ不足時の空結果"""
        return {
            "ticker": ticker,
            "trend_score": 0.0,
            "momentum_score": 0.0,
            "volatility_score": 0.5,
            "volume_score": 0.0,
            "composite_score": 50.0,
            "signals": ["⚠️ データ不足のため分析不可"],
            "indicators": {},
        }
