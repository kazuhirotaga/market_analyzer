"""ニュースデータ収集モジュール

NewsAPI, NewsData.io, marketaux を使用してニュース記事を取得する。
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import requests

from src.config import config
from src.database.models import get_session, NewsArticle

logger = logging.getLogger(__name__)


class NewsCollector:
    """ニュース収集クラス"""

    NEWSAPI_BASE = "https://newsapi.org/v2"
    NEWSDATA_BASE = "https://newsdata.io/api/1"
    MARKETAUX_BASE = "https://api.marketaux.com/v1"

    def __init__(self):
        self.api_keys = config.api_keys
        self.keywords = config.news_keywords
        self._seen_hashes: set[str] = set()

    def collect_all(self) -> list[dict]:
        """全ソースからニュースを収集"""
        all_articles = []

        # NewsAPI
        if self.api_keys.newsapi:
            articles = self._collect_from_newsapi()
            all_articles.extend(articles)
            logger.info(f"📰 NewsAPI: {len(articles)} 件取得")
        else:
            logger.warning("⚠️ NewsAPI キーが未設定です")

        # NewsData.io
        if self.api_keys.newsdata:
            articles = self._collect_from_newsdata()
            all_articles.extend(articles)
            logger.info(f"📰 NewsData.io: {len(articles)} 件取得")
        else:
            logger.warning("⚠️ NewsData キーが未設定です")

        # marketaux
        if self.api_keys.marketaux:
            articles = self._collect_from_marketaux()
            all_articles.extend(articles)
            logger.info(f"📰 marketaux: {len(articles)} 件取得")
        else:
            logger.warning("⚠️ marketaux キーが未設定です")

        # 重複排除
        unique_articles = self._deduplicate(all_articles)
        logger.info(f"📰 ニュース収集完了: {len(unique_articles)} 件 (重複排除後)")

        # DB保存
        saved = self._save_articles(unique_articles)
        logger.info(f"💾 DB保存: {saved} 件")

        return unique_articles

    def collect_for_category(self, category: str) -> list[dict]:
        """指定カテゴリのニュースを収集"""
        keywords = self.keywords.get(category, [])
        if not keywords:
            logger.warning(f"⚠️ カテゴリ '{category}' のキーワードが未定義です")
            return []

        articles = []
        query = " OR ".join(keywords)

        if self.api_keys.newsapi:
            articles.extend(self._search_newsapi(query, category))

        unique_articles = self._deduplicate(articles)
        self._save_articles(unique_articles)
        return unique_articles

    # --- NewsAPI ---

    def _collect_from_newsapi(self) -> list[dict]:
        """NewsAPIからニュースを収集"""
        articles = []
        for category, keywords in self.keywords.items():
            query = " OR ".join(keywords[:5])  # APIのクエリ長制限
            articles.extend(self._search_newsapi(query, category))
        return articles

    def _search_newsapi(self, query: str, category: str) -> list[dict]:
        """NewsAPIでニュース検索"""
        try:
            params = {
                "q": query,
                "language": "jp",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": self.api_keys.newsapi,
            }

            response = requests.get(
                f"{self.NEWSAPI_BASE}/everything",
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data.get("articles", []):
                articles.append({
                    "title": item.get("title", ""),
                    "content": item.get("description", "") or item.get("content", ""),
                    "url": item.get("url", ""),
                    "source": f"newsapi:{item.get('source', {}).get('name', 'unknown')}",
                    "category": category,
                    "published_at": self._parse_datetime(item.get("publishedAt")),
                })

            return articles
        except Exception as e:
            logger.warning(f"⚠️ NewsAPI検索エラー ({category}): {e}")
            return []

    # --- NewsData.io ---

    def _collect_from_newsdata(self) -> list[dict]:
        """NewsData.ioからニュースを収集"""
        articles = []
        for category, keywords in self.keywords.items():
            query = " OR ".join(keywords[:3])
            try:
                params = {
                    "apikey": self.api_keys.newsdata,
                    "q": query,
                    "country": "jp",
                    "language": "ja",
                    "category": "business",
                }

                response = requests.get(
                    f"{self.NEWSDATA_BASE}/latest",
                    params=params,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()

                for item in data.get("results", []):
                    articles.append({
                        "title": item.get("title", ""),
                        "content": item.get("description", "") or item.get("content", ""),
                        "url": item.get("link", ""),
                        "source": f"newsdata:{item.get('source_id', 'unknown')}",
                        "category": category,
                        "published_at": self._parse_datetime(item.get("pubDate")),
                    })

            except Exception as e:
                logger.warning(f"⚠️ NewsData検索エラー ({category}): {e}")

        return articles

    # --- marketaux ---

    def _collect_from_marketaux(self) -> list[dict]:
        """marketauxからニュースを収集"""
        articles = []
        try:
            # 日本市場関連の銘柄シンボルを対象
            params = {
                "api_token": self.api_keys.marketaux,
                "countries": "jp",
                "filter_entities": "true",
                "limit": 50,
            }

            response = requests.get(
                f"{self.MARKETAUX_BASE}/news/all",
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("data", []):
                # marketauxにはセンチメントが含まれる場合がある
                sentiment = None
                entities = item.get("entities", [])
                if entities:
                    sentiments = [
                        e.get("sentiment_score") for e in entities
                        if e.get("sentiment_score") is not None
                    ]
                    if sentiments:
                        sentiment = sum(sentiments) / len(sentiments)

                articles.append({
                    "title": item.get("title", ""),
                    "content": item.get("description", "") or item.get("snippet", ""),
                    "url": item.get("url", ""),
                    "source": f"marketaux:{item.get('source', 'unknown')}",
                    "category": "stock",
                    "published_at": self._parse_datetime(item.get("published_at")),
                    "sentiment_score": sentiment,
                    "model_used": "marketaux" if sentiment is not None else None,
                })

        except Exception as e:
            logger.warning(f"⚠️ marketaux検索エラー: {e}")

        return articles

    # --- ユーティリティ ---

    def _deduplicate(self, articles: list[dict]) -> list[dict]:
        """タイトルベースで重複排除"""
        unique = []
        for article in articles:
            title = article.get("title", "")
            if not title:
                continue
            h = hashlib.md5(title.encode("utf-8")).hexdigest()
            if h not in self._seen_hashes:
                self._seen_hashes.add(h)
                unique.append(article)
        return unique

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """日時文字列をパース"""
        if not dt_str:
            return None
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except (ValueError, TypeError):
                continue
        return None

    def _save_articles(self, articles: list[dict]) -> int:
        """記事をDBに保存"""
        session = get_session()
        saved = 0
        try:
            for article in articles:
                title = article.get("title", "")
                if not title:
                    continue

                # 既存チェック (タイトル + ソースで重複判定)
                existing = (
                    session.query(NewsArticle)
                    .filter_by(title=title, source=article.get("source", ""))
                    .first()
                )
                if existing:
                    continue

                news = NewsArticle(
                    title=title,
                    content=article.get("content"),
                    url=article.get("url"),
                    source=article.get("source"),
                    category=article.get("category"),
                    published_at=article.get("published_at"),
                    sentiment_score=article.get("sentiment_score"),
                    confidence=article.get("confidence"),
                    model_used=article.get("model_used"),
                )
                session.add(news)
                saved += 1

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 記事保存エラー: {e}")
        finally:
            session.close()

        return saved

    def get_recent_articles(
        self,
        category: Optional[str] = None,
        days: int = 7,
        limit: int = 100,
    ) -> list[dict]:
        """DBから直近N日間の記事を取得"""
        session = get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = session.query(NewsArticle).filter(
                NewsArticle.collected_at >= cutoff
            )

            if category:
                query = query.filter(NewsArticle.category == category)

            query = query.order_by(NewsArticle.published_at.desc()).limit(limit)
            rows = query.all()

            return [{
                "id": r.id,
                "title": r.title,
                "content": r.content,
                "url": r.url,
                "source": r.source,
                "category": r.category,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "sentiment_score": r.sentiment_score,
                "confidence": r.confidence,
                "model_used": r.model_used,
            } for r in rows]
        finally:
            session.close()
