"""多因子スコアリングエンジン

各分析結果を統合し、銘柄ごとの総合スコアを算出する。
"""

import logging
from datetime import date
from typing import Optional

from src.config import config
from src.database.models import get_session, AnalysisResult

logger = logging.getLogger(__name__)


# レーティング定義
RATING_MAP = [
    (80, "Strong Buy",  "🟢"),
    (60, "Buy",         "🔵"),
    (40, "Hold",        "⚪"),
    (20, "Sell",        "🟠"),
    (0,  "Strong Sell", "🔴"),
]


def get_rating(score: float) -> tuple[str, str]:
    """スコアからレーティングとアイコンを返す"""
    for threshold, label, icon in RATING_MAP:
        if score >= threshold:
            return label, icon
    return "Strong Sell", "🔴"


class Scorer:
    """多因子スコアリングクラス"""

    def __init__(self, weights: Optional[dict] = None):
        if weights:
            self.weights = weights
        else:
            w = config.scoring_weights
            self.weights = {
                "sentiment": w.sentiment,
                "technical": w.technical,
                "fundamental": w.fundamental,
                "macro": w.macro,
                "risk": w.risk,
            }

    def score(
        self,
        ticker: str,
        sentiment_result: dict,
        technical_result: dict,
        fundamental_result: dict,
        macro_score: float,
    ) -> dict:
        """全分析結果を統合して総合スコアを算出

        Args:
            ticker: 銘柄コード
            sentiment_result: センチメント分析結果
            technical_result: テクニカル分析結果
            fundamental_result: ファンダメンタル分析結果
            macro_score: マクロ経済スコア (0〜100)

        Returns:
            {
                "ticker": str,
                "total_score": float (0〜100),
                "rating": str,
                "rating_icon": str,
                "scores": {
                    "sentiment": float (0〜100),
                    "technical": float (0〜100),
                    "fundamental": float (0〜100),
                    "macro": float (0〜100),
                    "risk": float (0〜100),
                },
                "signals": list[str],
                "details": dict,
            }
        """

        # --- 各スコアを 0〜100 にマッピング ---

        # センチメント: -1.0〜1.0 → 0〜100
        raw_sentiment = sentiment_result.get("sentiment_score", 0)
        sentiment_score = (raw_sentiment + 1) / 2 * 100

        # テクニカル: 既に 0〜100
        technical_score = technical_result.get("composite_score", 50)

        # ファンダメンタル: 既に 0〜100
        fundamental_score = fundamental_result.get("composite_score", 50)

        # マクロ: 既に 0〜100
        macro_s = macro_score

        # リスクスコア: テクニカルのvolatility (高い=安定=低リスク) を反転
        volatility = technical_result.get("volatility_score", 0.5)
        risk_score = (1 - volatility) * 100  # 高ボラ = 高リスクスコア

        # --- 加重スコア計算 ---
        # リスクスコアは逆指標 (リスクが高いほど減点)
        weighted = (
            sentiment_score * self.weights["sentiment"] +
            technical_score * self.weights["technical"] +
            fundamental_score * self.weights["fundamental"] +
            macro_s * self.weights["macro"] +
            (100 - risk_score) * self.weights["risk"]  # リスクを反転
        )

        total_score = max(0, min(100, round(weighted, 1)))
        rating, icon = get_rating(total_score)

        # シグナル統合
        signals = []
        signals.extend(technical_result.get("signals", []))
        signals.extend(fundamental_result.get("signals", []))

        # センチメント要約
        art_count = sentiment_result.get("article_count", 0)
        if art_count > 0:
            pos = sentiment_result.get("positive_count", 0)
            neg = sentiment_result.get("negative_count", 0)
            signals.append(
                f"📰 ニュース {art_count}件 (ポジティブ:{pos} / ネガティブ:{neg})"
            )

        result = {
            "ticker": ticker,
            "total_score": total_score,
            "rating": rating,
            "rating_icon": icon,
            "scores": {
                "sentiment": round(sentiment_score, 1),
                "technical": round(technical_score, 1),
                "fundamental": round(fundamental_score, 1),
                "macro": round(macro_s, 1),
                "risk": round(risk_score, 1),
            },
            "signals": signals,
            "details": {
                "sentiment": sentiment_result,
                "technical_indicators": technical_result.get("indicators", {}),
                "fundamental_metrics": fundamental_result.get("metrics", {}),
            },
        }

        return result

    def save_result(self, result: dict):
        """分析結果をDBに保存"""
        session = get_session()
        try:
            today = date.today()
            ticker = result["ticker"]

            existing = (
                session.query(AnalysisResult)
                .filter_by(ticker=ticker, analysis_date=today)
                .first()
            )

            scores = result["scores"]

            if existing:
                existing.sentiment_score = scores["sentiment"]
                existing.technical_score = scores["technical"]
                existing.fundamental_score = scores["fundamental"]
                existing.macro_score = scores["macro"]
                existing.risk_score = scores["risk"]
                existing.total_score = result["total_score"]
                existing.rating = result["rating"]
                existing.details = result["details"]
            else:
                ar = AnalysisResult(
                    ticker=ticker,
                    analysis_date=today,
                    sentiment_score=scores["sentiment"],
                    technical_score=scores["technical"],
                    fundamental_score=scores["fundamental"],
                    macro_score=scores["macro"],
                    risk_score=scores["risk"],
                    total_score=result["total_score"],
                    rating=result["rating"],
                    details=result["details"],
                )
                session.add(ar)

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 分析結果保存エラー ({result.get('ticker')}): {e}")
        finally:
            session.close()
