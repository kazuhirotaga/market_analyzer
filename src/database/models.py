"""データベースモデル定義"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Text, Date, DateTime,
    BigInteger, JSON, ForeignKey, UniqueConstraint, Index, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session, sessionmaker

from src.config import config


class Base(DeclarativeBase):
    pass


class Stock(Base):
    """銘柄マスター"""
    __tablename__ = "stocks"

    ticker = Column(String(20), primary_key=True)
    name = Column(String(100), nullable=False)
    sector = Column(String(50))
    industry = Column(String(50))
    market_cap = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    price_history = relationship("PriceHistory", back_populates="stock", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="stock", cascade="all, delete-orphan")
    news_links = relationship("NewsTickerLink", back_populates="stock", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Stock(ticker={self.ticker}, name={self.name})>"


class PriceHistory(Base):
    """株価履歴"""
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), ForeignKey("stocks.ticker"), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    adjusted_close = Column(Float)

    # Relationships
    stock = relationship("Stock", back_populates="price_history")

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_price_ticker_date"),
        Index("ix_price_ticker_date", "ticker", "date"),
    )

    def __repr__(self):
        return f"<PriceHistory(ticker={self.ticker}, date={self.date}, close={self.close})>"


class NewsArticle(Base):
    """ニュース記事"""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    url = Column(String(1000))
    source = Column(String(100))
    category = Column(String(50))   # stock, economy, politics, global
    published_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)
    sentiment_score = Column(Float)   # -1.0 〜 1.0
    confidence = Column(Float)        # 0.0 〜 1.0
    model_used = Column(String(50))   # finbert, gemini, etc.
    
    # LLM Analysis Details
    summary_llm = Column(Text)        # LLMによる要約
    impact_llm = Column(String(50))   # high, medium, low
    reasoning_llm = Column(Text)      # 判断理由
    affected_sectors_llm = Column(String(200)) # 影響セクター(カンマ区切り)

    # Relationships
    ticker_links = relationship("NewsTickerLink", back_populates="article", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_news_published", "published_at"),
        Index("ix_news_category", "category"),
    )

    def __repr__(self):
        return f"<NewsArticle(id={self.id}, title={self.title[:30]}...)>"


class NewsTickerLink(Base):
    """ニュースと銘柄の関連付け"""
    __tablename__ = "news_ticker_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("news_articles.id"), nullable=False)
    ticker = Column(String(20), ForeignKey("stocks.ticker"), nullable=False)
    relevance_score = Column(Float, default=1.0)   # 0.0 〜 1.0

    # Relationships
    article = relationship("NewsArticle", back_populates="ticker_links")
    stock = relationship("Stock", back_populates="news_links")

    __table_args__ = (
        UniqueConstraint("article_id", "ticker", name="uq_news_ticker"),
    )


class AnalysisResult(Base):
    """分析結果"""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), ForeignKey("stocks.ticker"), nullable=False)
    analysis_date = Column(Date, nullable=False)
    sentiment_score = Column(Float)     # -1.0 〜 1.0 → 0〜100にマッピング
    technical_score = Column(Float)     # 0 〜 100
    fundamental_score = Column(Float)   # 0 〜 100
    macro_score = Column(Float)         # 0 〜 100
    risk_score = Column(Float)          # 0 〜 100 (高い=リスク大)
    total_score = Column(Float)         # 0 〜 100
    rating = Column(String(20))         # Strong Buy, Buy, Hold, Sell, Strong Sell
    details = Column(JSON)             # 詳細分析結果

    # Relationships
    stock = relationship("Stock", back_populates="analysis_results")

    __table_args__ = (
        UniqueConstraint("ticker", "analysis_date", name="uq_analysis_ticker_date"),
        Index("ix_analysis_date", "analysis_date"),
        Index("ix_analysis_score", "total_score"),
    )

    def __repr__(self):
        return f"<AnalysisResult(ticker={self.ticker}, date={self.analysis_date}, score={self.total_score})>"


class Recommendation(Base):
    """おすすめ銘柄レポート"""
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(Date, nullable=False)
    report_type = Column(String(20), nullable=False)   # daily, weekly, alert
    recommendations = Column(JSON)     # おすすめ銘柄リスト
    market_summary = Column(JSON)      # マーケットサマリー
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_report_date_type", "report_date", "report_type"),
    )


# --- Database Engine & Session ---

def get_engine():
    """SQLAlchemyエンジンを取得"""
    db_url = config.database_url
    return create_engine(db_url, echo=False)


def init_db():
    """データベースを初期化（テーブル作成）"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    """データベースセッションを取得"""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
