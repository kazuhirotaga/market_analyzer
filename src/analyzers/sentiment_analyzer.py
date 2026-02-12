"""センチメント分析モジュール

日本語FinBERT (finance-sentiment-ja-base) を使用して
ニュース記事のセンチメントを分析する。
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from src.config import config
from src.database.models import get_session, NewsArticle, NewsTickerLink

logger = logging.getLogger(__name__)

# FinBERTモデル (遅延ロード)
_model = None
_tokenizer = None
_current_market_model = None  # 現在ロードされているモデルの市場 ("JP" or "US")


def _load_model():
    """FinBERTモデルを遅延ロード"""
    global _model, _tokenizer, _current_market_model
    if _model is not None:
        return

    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch

        if config.market == "US":
            model_name = "ProsusAI/finbert"
            _current_market_model = "US"
        else:
            model_name = "izumi-lab/bert-small-japanese-fin"
            _current_market_model = "JP"
            
        logger.info(f"🔄 センチメントモデルをロード中: {model_name}")

        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _model.eval()

        logger.info("✅ センチメントモデルのロード完了")
    except Exception as e:
        logger.error(f"❌ センチメントモデルのロード失敗: {e}")
        logger.info("💡 フォールバック: キーワードベースのセンチメント分析を使用します")


class SentimentAnalyzer:
    """センチメント分析クラス"""

    # キーワードベースのフォールバック辞書
    # キーワードベースのフォールバック辞書
    POSITIVE_KEYWORDS_JP = [
        "上昇", "増収", "増益", "好調", "堅調", "上方修正", "最高益",
        "増配", "回復", "成長", "拡大", "改善", "買い", "強気",
        "プラス", "急騰", "高値", "大幅増", "黒字", "好決算",
    ]

    NEGATIVE_KEYWORDS_JP = [
        "下落", "減収", "減益", "不振", "軟調", "下方修正", "赤字",
        "減配", "悪化", "縮小", "低迷", "売り", "弱気", "リスク",
        "マイナス", "急落", "安値", "大幅減", "損失", "悪決算",
        "破綻", "倒産", "不正", "撤退", "リストラ",
    ]

    POSITIVE_KEYWORDS_US = [
        "up", "rise", "gain", "growth", "jump", "surge", "climb", "rally",
        "profit", "positive", "bull", "bullish", "record", "beat", "strong",
        "upgrade", "buy", "dividend", "revenue up", "outperform"
    ]

    NEGATIVE_KEYWORDS_US = [
        "down", "fall", "drop", "decline", "slide", "crash", "plunge", "loss",
        "negative", "bear", "bearish", "miss", "weak", "downgrade", "sell",
        "cut", "revenue down", "underperform", "risk", "debt", "bankrupt"
    ]

    def __init__(self):
        self.use_model = False
        
        # 市場に応じてキーワードを設定
        if config.market == "US":
            self.POSITIVE_KEYWORDS = self.POSITIVE_KEYWORDS_US
            self.NEGATIVE_KEYWORDS = self.NEGATIVE_KEYWORDS_US
        else:
            self.POSITIVE_KEYWORDS = self.POSITIVE_KEYWORDS_JP
            self.NEGATIVE_KEYWORDS = self.NEGATIVE_KEYWORDS_JP

        try:
            _load_model()
            self.use_model = _model is not None
        except Exception:
            pass

    def analyze_text(self, text: str) -> dict:
        """テキストのセンチメントを分析

        Returns:
            {
                "score": float (-1.0 〜 1.0),
                "label": str ("positive", "neutral", "negative"),
                "confidence": float (0.0 〜 1.0),
                "method": str ("finbert" or "keyword")
            }
        """
        if not text or not text.strip():
            return {"score": 0.0, "label": "neutral", "confidence": 0.0, "method": "none"}

        if self.use_model:
            return self._analyze_with_model(text)
        else:
            return self._analyze_with_keywords(text)

    def analyze_articles(self, articles: list[dict] | None = None) -> list[dict]:
        """複数記事のセンチメントを一括分析してDBに保存

        Args:
            articles: 分析対象の記事リスト。Noneの場合はDBから未分析の記事を取得。

        Returns:
            分析結果のリスト
        """
        session = get_session()
        results = []

        try:
            if articles is None:
                # DBから未分析の記事を取得
                rows = (
                    session.query(NewsArticle)
                    .filter(NewsArticle.sentiment_score.is_(None))
                    .order_by(NewsArticle.published_at.desc())
                    .limit(200)
                    .all()
                )
            else:
                # 渡された記事リストから対応するDB行を取得
                titles = [a.get("title", "") for a in articles if a.get("title")]
                rows = (
                    session.query(NewsArticle)
                    .filter(NewsArticle.title.in_(titles))
                    .all()
                )

            for row in rows:
                text = f"{row.title} {row.content or ''}"
                result = self.analyze_text(text)

                # DB更新
                row.sentiment_score = result["score"]
                row.confidence = result["confidence"]
                row.model_used = result["method"]

                results.append({
                    "article_id": row.id,
                    "title": row.title,
                    **result,
                })

            session.commit()
            logger.info(f"🧠 センチメント分析完了: {len(results)} 件")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ センチメント分析エラー: {e}")
            raise
        finally:
            session.close()

        return results

    def get_ticker_sentiment(
        self,
        ticker: str,
        days: int | None = None,
    ) -> dict:
        """特定銘柄のセンチメントスコアを計算

        Args:
            ticker: 銘柄コード (例: "6758.T")
            days: 対象日数（Noneの場合はconfig設定値を使用）

        Returns:
            {
                "ticker": str,
                "sentiment_score": float (-1.0 〜 1.0),
                "article_count": int,
                "positive_count": int,
                "negative_count": int,
                "neutral_count": int,
                "latest_articles": list
            }
        """
        if days is None:
            days = config.sentiment_window_days

        session = get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            # 銘柄に紐付いた記事を取得
            rows = (
                session.query(NewsArticle)
                .join(NewsTickerLink, NewsArticle.id == NewsTickerLink.article_id)
                .filter(NewsTickerLink.ticker == ticker)
                .filter(NewsArticle.published_at >= cutoff)
                .filter(NewsArticle.sentiment_score.isnot(None))
                .order_by(NewsArticle.published_at.desc())
                .all()
            )

            if not rows:
                # 銘柄紐付けがない場合、銘柄名でタイトル検索
                stock_name = self._get_stock_name(session, ticker)
                if stock_name:
                    rows = (
                        session.query(NewsArticle)
                        .filter(NewsArticle.published_at >= cutoff)
                        .filter(NewsArticle.sentiment_score.isnot(None))
                        .filter(NewsArticle.title.contains(stock_name))
                        .order_by(NewsArticle.published_at.desc())
                        .limit(50)
                        .all()
                    )

            if not rows:
                return {
                    "ticker": ticker,
                    "sentiment_score": 0.0,
                    "article_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "neutral_count": 0,
                    "latest_articles": [],
                }

            # 時間減衰加重平均を計算
            now = datetime.utcnow()
            decay = config.sentiment_decay_factor
            weighted_sum = 0.0
            weight_total = 0.0
            pos = neg = neu = 0

            for row in rows:
                if row.published_at:
                    days_ago = (now - row.published_at).total_seconds() / 86400
                else:
                    days_ago = days / 2  # 日付不明は中間に

                time_weight = math.pow(decay, days_ago)
                conf_weight = row.confidence if row.confidence else 0.5
                w = time_weight * conf_weight

                weighted_sum += row.sentiment_score * w
                weight_total += w

                if row.sentiment_score > 0.1:
                    pos += 1
                elif row.sentiment_score < -0.1:
                    neg += 1
                else:
                    neu += 1

            avg_score = weighted_sum / weight_total if weight_total > 0 else 0.0

            latest = [{
                "title": r.title,
                "sentiment": r.sentiment_score,
                "date": r.published_at.isoformat() if r.published_at else None,
            } for r in rows[:5]]

            return {
                "ticker": ticker,
                "sentiment_score": round(avg_score, 4),
                "article_count": len(rows),
                "positive_count": pos,
                "negative_count": neg,
                "neutral_count": neu,
                "latest_articles": latest,
            }
        finally:
            session.close()

    # --- Private Methods ---

    def _analyze_with_model(self, text: str) -> dict:
        """FinBERTモデルでセンチメント分析"""
        # モデルの動的リロードチェック
        global _model, _tokenizer, _current_market_model

        target_model = "US" if config.market == "US" else "JP"
        
        # 現在ロードされているモデルがターゲット市場と異なる場合はリロード
        if _current_market_model != target_model:
            logger.info(f"🔄 市場変更検知 ({_current_market_model} -> {target_model}): モデルをリロードします")
            _model = None
            _tokenizer = None
            _load_model()

        if _model is None:
            return self._analyze_with_keywords(text)

        import torch

        try:
            # テキストを最大512トークンに制限
            inputs = _tokenizer(
                text, return_tensors="pt",
                truncation=True, max_length=512, padding=True
            )

            with torch.no_grad():
                outputs = _model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1)[0]

            # モデルのラベル順序に応じてマッピング
            labels = _model.config.id2label
            scores_dict = {}
            for idx, label_name in labels.items():
                scores_dict[label_name.lower()] = float(probs[idx])

            # スコア計算
            pos = scores_dict.get("positive", 0)
            neg = scores_dict.get("negative", 0)
            neu = scores_dict.get("neutral", 0)

            score = pos - neg  # -1.0 〜 1.0
            confidence = max(pos, neg, neu)

            if pos > neg and pos > neu:
                label = "positive"
            elif neg > pos and neg > neu:
                label = "negative"
            else:
                label = "neutral"

            return {
                "score": round(score, 4),
                "label": label,
                "confidence": round(confidence, 4),
                "method": "finbert",
            }
        except Exception as e:
            logger.warning(f"⚠️ モデル分析失敗、キーワード分析にフォールバック: {e}")
            return self._analyze_with_keywords(text)

    def _analyze_with_keywords(self, text: str) -> dict:
        """キーワードベースのセンチメント分析（フォールバック）"""
        # 市場に応じて適切なキーワードリストを選択
        if config.market == "US":
            keywords_pos = self.POSITIVE_KEYWORDS_US
            keywords_neg = self.NEGATIVE_KEYWORDS_US
        else:
            keywords_pos = self.POSITIVE_KEYWORDS_JP
            keywords_neg = self.NEGATIVE_KEYWORDS_JP

        pos_count = sum(1 for kw in keywords_pos if kw in text)
        neg_count = sum(1 for kw in keywords_neg if kw in text)
        total = pos_count + neg_count

        if total == 0:
            return {"score": 0.0, "label": "neutral", "confidence": 0.3, "method": "keyword"}

        score = (pos_count - neg_count) / total
        confidence = min(0.8, total * 0.1)  # キーワード数に応じた信頼度

        if score > 0.1:
            label = "positive"
        elif score < -0.1:
            label = "negative"
        else:
            label = "neutral"

        return {
            "score": round(score, 4),
            "label": label,
            "confidence": round(confidence, 4),
            "method": "keyword",
        }

    def _get_stock_name(self, session, ticker: str) -> str | None:
        """銘柄名を取得"""
        from src.database.models import Stock
        stock = session.query(Stock).filter_by(ticker=ticker).first()
        return stock.name if stock else None
