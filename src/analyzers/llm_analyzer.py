"""Gemini LLM 分析モジュール

Gemini Flash 3.0 を使用して、ニュース記事の高度な分析を行う。
- ニュース記事の要約
- 影響を受けるセクター・銘柄の推定
- センチメントスコアの算出
- 影響度・影響期間の判定
"""

import json
import logging
from typing import Optional

import google.generativeai as genai

from src.config import config
from src.database.models import get_session, NewsArticle, NewsTickerLink

logger = logging.getLogger(__name__)

# モデル設定
GEMINI_MODEL = "gemini-2.0-flash"

# --- Dynamic Prompts ---

def get_analysis_prompt(title: str, content: str) -> str:
    """市場に応じた分析プロンプトを生成"""
    if config.market == "US":
        return f"""You are a professional analyst for the US stock market (S&P 500, NASDAQ, etc.).
Analyze the following news article and provide the impact on the stock market in JSON format.

【Article Title】
{title}

【Article Content】
{content}

【Response Format】
You must respond in JSON format ONLY. No explanation text.
{{
    "summary": "Summary of the article (within 100 characters, in Japanese)",
    "affected_sectors": ["List of affected sectors (in Japanese)"],
    "affected_tickers": ["List of potentially affected US ticker symbols (e.g., AAPL)"],
    "sentiment_score": 0.0,
    "impact_magnitude": "high/medium/low",
    "impact_timeframe": "short/medium/long",
    "reasoning": "Reasoning for the judgment (within 200 characters, in Japanese)"
}}

Notes:
- sentiment_score: -1.0 (Very Negative) to 1.0 (Very Positive)
- affected_tickers: US stock tickers only (without .T suffix)
- impact_timeframe: short=within 1 week, medium=within 1 month, long=longer
"""
    else:
        return f"""あなたは日本株式市場の専門アナリストです。
以下のニュース記事を分析し、株式投資への影響をJSON形式で回答してください。

【記事タイトル】
{title}

【記事内容】
{content}

【回答形式】必ず以下のJSON形式のみで回答してください。説明文は不要です。
{{
    "summary": "記事の要約（50字以内、日本語）",
    "affected_sectors": ["影響を受けるセクター名（日本語）"],
    "affected_tickers": ["影響を受ける可能性のある東証銘柄コード（例: 6758.T）"],
    "sentiment_score": 0.0,
    "impact_magnitude": "high/medium/low",
    "impact_timeframe": "short/medium/long",
    "reasoning": "判断理由（100字以内、日本語）"
}}

注意事項:
- sentiment_score は -1.0（非常にネガティブ）〜 1.0（非常にポジティブ）の範囲
- affected_tickers は東証上場銘柄のティッカーコードのみ（末尾に.T付き）
- impact_timeframe: short=1週間以内, medium=1ヶ月以内, long=それ以上
"""

def get_batch_prompt(headlines_text: str) -> str:
    """市場に応じたバッチ分析プロンプトを生成"""
    if config.market == "US":
        return f"""You are a professional analyst for the US stock market.
Analyze the following list of news headlines and provide a comprehensive overview of the market impact in JSON format.

【News Headlines】
{headlines_text}

【Response Format】
You must respond in JSON format ONLY.
{{
    "market_outlook": "Bullish/Slightly Bullish/Neutral/Slightly Bearish/Bearish",
    "key_themes": ["Current key themes (Japanese, max 5)"],
    "bullish_sectors": ["Sectors expected to perform well (Japanese)"],
    "bearish_sectors": ["Sectors expected to underperform (Japanese)"],
    "risk_factors": ["Risk factors to watch (Japanese, max 3)"],
    "overall_sentiment": 0.0,
    "summary": "Summary of market outlook (within 200 characters, in Japanese)"
}}

Note: overall_sentiment should be between -1.0 and 1.0.
"""
    else:
        return f"""あなたは日本株式市場の専門アナリストです。
以下の複数のニュース見出しを分析し、日本株式市場全体への総合的な影響をJSON形式で回答してください。

【ニュース見出し一覧】
{headlines_text}

【回答形式】必ず以下のJSON形式のみで回答してください。
{{
    "market_outlook": "強気/やや強気/中立/やや弱気/弱気",
    "key_themes": ["現在の主要テーマ（日本語、最大5つ）"],
    "bullish_sectors": ["好影響が期待されるセクター"],
    "bearish_sectors": ["悪影響が懸念されるセクター"],
    "risk_factors": ["注意すべきリスク要因（日本語、最大3つ）"],
    "overall_sentiment": 0.0,
    "summary": "市場全体の見通し要約（100字以内、日本語）"
}}

注意: overall_sentiment は -1.0〜1.0 の範囲で回答してください。
"""


class LLMAnalyzer:
    """Gemini LLM 分析クラス"""

    def __init__(self):
        api_key = config.api_keys.gemini
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY が未設定です。.env ファイルに設定してください。"
            )
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                max_output_tokens=2048,
                response_mime_type="application/json",
            ),
        )
        logger.info(f"✅ Gemini LLM 初期化完了 (モデル: {GEMINI_MODEL})")

    def analyze_article(self, title: str, content: str = "") -> Optional[dict]:
        """単一ニュース記事を分析
        
        Returns:
            {
                "summary": str,
                "affected_sectors": list[str],
                "affected_tickers": list[str],
                "sentiment_score": float,
                "impact_magnitude": str,
                "impact_timeframe": str,
                "reasoning": str,
            }
        """
        if not title:
            return None

        prompt = get_analysis_prompt(
            title=title,
            content=content[:1000] if content else "（本文なし）",
        )

        try:
            response = self.model.generate_content(prompt)
            result = self._parse_json_response(response.text)
            if result:
                logger.debug(f"✅ LLM分析完了: {title[:30]}...")
            return result
        except Exception as e:
            logger.warning(f"⚠️ LLM分析失敗: {title[:30]}... - {e}")
            return None

    def analyze_articles_batch(self, articles: list[dict]) -> list[dict]:
        """複数記事を個別に分析してDBに保存
        
        Args:
            articles: [{"id": int, "title": str, "content": str}, ...]
        
        Returns:
            分析結果のリスト
        """
        results = []
        session = get_session()

        try:
            for article in articles:
                article_id = article.get("id")
                title = article.get("title", "")
                content = article.get("content", "")

                result = self.analyze_article(title, content)
                if not result:
                    continue

                # DB更新: センチメントスコアと詳細分析を保存
                if article_id:
                    row = session.query(NewsArticle).filter_by(id=article_id).first()
                    if row:
                        row.sentiment_score = result["sentiment_score"]
                        row.confidence = 0.85  # LLM分析は信頼度高め
                        row.model_used = f"gemini:{GEMINI_MODEL}"

                        # 詳細分析結果の保存
                        row.summary_llm = result.get("summary")
                        row.impact_llm = result.get("impact_magnitude")
                        row.reasoning_llm = result.get("reasoning")
                        
                        sectors = result.get("affected_sectors", [])
                        if sectors:
                            row.affected_sectors_llm = ",".join(sectors)

                        # 銘柄紐付け
                        for ticker in result.get("affected_tickers", []):
                            # US銘柄の場合は.Tが付かないことを考慮
                            # 必要ならここで銘柄コードの検証や正規化を行う
                            existing_link = (
                                session.query(NewsTickerLink)
                                .filter_by(article_id=article_id, ticker=ticker)
                                .first()
                            )
                            if not existing_link:
                                link = NewsTickerLink(
                                    article_id=article_id,
                                    ticker=ticker,
                                    relevance_score=0.8,
                                )
                                session.add(link)

                result["article_id"] = article_id
                result["title"] = title
                results.append(result)

            session.commit()
            logger.info(f"🤖 Gemini LLM 分析完了: {len(results)}/{len(articles)} 件")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ LLM バッチ分析エラー: {e}")
        finally:
            session.close()

        return results

    def analyze_market_sentiment(self, headlines: list[str]) -> Optional[dict]:
        """複数ニュース見出しから市場全体のセンチメントを分析
        
        Returns:
            {
                "market_outlook": str,
                "key_themes": list[str],
                "bullish_sectors": list[str],
                "bearish_sectors": list[str],
                "risk_factors": list[str],
                "overall_sentiment": float,
                "summary": str,
            }
        """
        if not headlines:
            return None

        headlines_text = "\n".join(f"- {h}" for h in headlines[:30])
        prompt = get_batch_prompt(headlines_text)

        try:
            response = self.model.generate_content(prompt)
            result = self._parse_json_response(response.text)
            if result:
                logger.info(f"🌐 市場センチメント分析完了: {result.get('market_outlook', 'N/A')}")
            return result
        except Exception as e:
            logger.warning(f"⚠️ 市場センチメント分析失敗: {e}")
            return None

    def _parse_json_response(self, text: str) -> Optional[dict]:
        """LLMレスポンスからJSONを抽出・パース"""
        if not text:
            return None

        # コードブロック内のJSONを抽出
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        # 先頭/末尾の余分なテキストを除去してJSON部分だけ取り出す
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            cleaned = cleaned[start:end]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON パースエラー: {e}\nResponse: {text[:200]}")
            return None
