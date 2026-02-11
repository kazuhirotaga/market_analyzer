"""おすすめ銘柄レコメンデーションエンジン

全分析パイプラインを統合し、おすすめ銘柄リストを生成する。
"""

import logging
from datetime import date, datetime
from typing import Optional

from src.config import config
from src.collectors.stock_collector import StockCollector
from src.collectors.news_collector import NewsCollector
from src.collectors.macro_collector import MacroCollector
from src.analyzers.sentiment_analyzer import SentimentAnalyzer
from src.analyzers.technical_analyzer import TechnicalAnalyzer
from src.analyzers.fundamental_analyzer import FundamentalAnalyzer
from src.scoring.scorer import Scorer, get_rating
from src.database.models import get_session, Stock, Recommendation, NewsArticle

logger = logging.getLogger(__name__)


class Recommender:
    """おすすめ銘柄レコメンダー"""

    def __init__(self):
        self.stock_collector = StockCollector()
        self.news_collector = NewsCollector()
        self.macro_collector = MacroCollector()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.technical_analyzer = TechnicalAnalyzer()
        self.fundamental_analyzer = FundamentalAnalyzer()
        self.scorer = Scorer()

        # Gemini LLM 分析 (APIキーがあれば有効化)
        self.llm_analyzer = None
        if config.api_keys.gemini:
            try:
                from src.analyzers.llm_analyzer import LLMAnalyzer
                self.llm_analyzer = LLMAnalyzer()
            except Exception as e:
                logger.warning(f"⚠️ Gemini LLM 初期化失敗 (スキップします): {e}")

    def run_full_analysis(self, top_n: int | None = None) -> dict:
        """フルパイプライン実行: データ収集 → 分析 → スコアリング → おすすめ銘柄生成

        Returns:
            {
                "report_date": str,
                "market_summary": dict,
                "recommendations": list[dict],
                "sector_analysis": dict,
                "risk_warnings": list[str],
            }
        """
        if top_n is None:
            top_n = config.top_n_recommendations

        logger.info("=" * 60)
        logger.info("🚀 分析パイプライン開始")
        logger.info("=" * 60)

        # === Step 1: データ収集 ===
        logger.info("\n📊 Step 1: データ収集")
        logger.info("-" * 40)

        # 株価データ収集
        logger.info("株価データ収集中...")
        self.stock_collector.collect_stock_info()
        self.stock_collector.collect_price_history(period="3mo")

        # ニュース収集
        logger.info("ニュース収集中...")
        self.news_collector.collect_all()

        # マクロ指標収集
        logger.info("マクロ経済指標収集中...")
        macro_indicators = self.macro_collector.collect()
        macro_score = self.macro_collector.calculate_macro_score(macro_indicators)

        # マーケットサマリー
        market_indices = self.stock_collector.get_market_indices()

        # === Step 2: センチメント分析 ===
        logger.info("\n🧠 Step 2: センチメント分析 (FinBERT)")
        logger.info("-" * 40)
        self.sentiment_analyzer.analyze_articles()

        # === Step 2.5: Gemini LLM 高度分析 ===
        llm_market_result = None
        if self.llm_analyzer:
            logger.info("\n🤖 Step 2.5: Gemini LLM 高度分析")
            logger.info("-" * 40)

            # 未分析 or LLM未処理の記事を取得してバッチ分析
            session = get_session()
            try:
                recent_articles = (
                    session.query(NewsArticle)
                    .filter(NewsArticle.model_used.notlike("%gemini%"))
                    .order_by(NewsArticle.published_at.desc())
                    .limit(20)
                    .all()
                )
                if recent_articles:
                    articles_data = [
                        {"id": a.id, "title": a.title, "content": a.content or ""}
                        for a in recent_articles
                    ]
                    self.llm_analyzer.analyze_articles_batch(articles_data)

                    # 全見出しで市場全体センチメントも分析
                    headlines = [a.title for a in recent_articles if a.title]
                    llm_market_result = self.llm_analyzer.analyze_market_sentiment(headlines)
                else:
                    logger.info("  新規ニュースなし — LLM分析スキップ")
            except Exception as e:
                logger.warning(f"⚠️ Gemini LLM 分析エラー: {e}")
            finally:
                session.close()
        else:
            logger.info("\n⏭️ Gemini LLM 分析スキップ (APIキー未設定)")

        # === Step 3: 銘柄ごとの分析 & スコアリング ===
        logger.info("\n📈 Step 3: 銘柄分析 & スコアリング")
        logger.info("-" * 40)

        all_results = []
        for ticker in config.target_tickers:
            try:
                result = self._analyze_single_ticker(ticker, macro_score)
                all_results.append(result)
                logger.info(
                    f"  {result['rating_icon']} {ticker}: "
                    f"スコア={result['total_score']:.1f} "
                    f"({result['rating']})"
                )
            except Exception as e:
                logger.warning(f"  ⚠️ {ticker}: 分析失敗 - {e}")

        # === Step 4: ランキング & レポート生成 ===
        logger.info("\n📋 Step 4: レポート生成")
        logger.info("-" * 40)

        # スコア降順でソート
        all_results.sort(key=lambda x: x["total_score"], reverse=True)

        # おすすめ銘柄Top-N
        recommendations = all_results[:top_n]

        # セクター分析
        sector_analysis = self._analyze_sectors(all_results)

        # リスク警告
        risk_warnings = self._generate_risk_warnings(macro_indicators, all_results)

        # マーケットサマリー構築
        market_sentiment = self._determine_market_sentiment(macro_score, risk_warnings)
        market_summary = {
            "indices": market_indices,
            "macro_indicators": macro_indicators.to_dict(),
            "macro_score": macro_score,
            "market_sentiment": market_sentiment,
        }

        # LLM分析結果をマーケットサマリーに統合
        if llm_market_result:
            market_summary["llm_analysis"] = llm_market_result
            market_summary["market_sentiment"] = llm_market_result.get(
                "market_outlook", market_sentiment
            )
            market_summary["key_themes"] = llm_market_result.get("key_themes", [])
            # LLMのセクター分析をリスク警告に追加
            llm_risks = llm_market_result.get("risk_factors", [])
            for risk in llm_risks:
                risk_warnings.append(f"[AI] {risk}")

        # 重要ニュース（今日のニュースからインパクト大のものを抽出）
        top_news = []
        if self.llm_analyzer:
            session = get_session()
            try:
                # 今日の日付
                today_start = datetime.combine(date.today(), datetime.min.time())
                
                # インパクトが 'high' または 'medium' の記事を取得
                important_articles = (
                    session.query(NewsArticle)
                    .filter(NewsArticle.published_at >= today_start)
                    .filter(NewsArticle.model_used.like("%gemini%"))
                    .filter(NewsArticle.impact_llm.in_(["high", "medium"]))
                    .order_by(NewsArticle.sentiment_score.desc()) # スコア高い順（ポジティブ）、あるいは絶対値？一旦ポジティブ優先
                    .limit(5)
                    .all()
                )
                
                for a in important_articles:
                    top_news.append({
                        "title": a.title,
                        "summary": a.summary_llm,
                        "impact": a.impact_llm,
                        "sentiment": a.sentiment_score,
                        "reasoning": a.reasoning_llm,
                        "sectors": a.affected_sectors_llm,
                    })
            except Exception as e:
                logger.warning(f"⚠️ ニュース抽出エラー: {e}")
            finally:
                session.close()

        report = {
            "report_date": date.today().isoformat(),
            "report_type": "daily",
            "market_summary": market_summary,
            "top_news": top_news,  # 追加
            "recommendations": recommendations,
            "all_results": all_results,
            "sector_analysis": sector_analysis,
            "risk_warnings": risk_warnings,
        }

        # レポートをDBに保存
        self._save_report(report)

        # === Step 5: メール送信 ===
        if config.smtp.is_configured:
            logger.info("\n📧 Step 5: メール送信")
            logger.info("-" * 40)
            try:
                from src.reports.email_notifier import EmailNotifier
                notifier = EmailNotifier()
                notifier.send_report(report)
            except Exception as e:
                logger.warning(f"⚠️ メール送信失敗: {e}")
        else:
            logger.info("\n⏭️ メール送信スキップ (SMTP未設定)")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 分析パイプライン完了")
        logger.info("=" * 60)

        return report

    def _analyze_single_ticker(self, ticker: str, macro_score: float) -> dict:
        """単一銘柄の分析を実行"""

        # センチメント
        sentiment_result = self.sentiment_analyzer.get_ticker_sentiment(ticker)

        # テクニカル
        technical_result = self.technical_analyzer.analyze(ticker)

        # ファンダメンタル
        fundamental_result = self.fundamental_analyzer.analyze(ticker)

        # スコアリング
        result = self.scorer.score(
            ticker=ticker,
            sentiment_result=sentiment_result,
            technical_result=technical_result,
            fundamental_result=fundamental_result,
            macro_score=macro_score,
        )

        # 銘柄名を追加
        session = get_session()
        try:
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            result["name"] = stock.name if stock else ticker
            result["sector"] = stock.sector if stock else "N/A"
        finally:
            session.close()

        # DB保存
        self.scorer.save_result(result)

        return result

    def _analyze_sectors(self, results: list[dict]) -> dict:
        """セクター別分析"""
        sector_scores: dict[str, list[float]] = {}
        for r in results:
            sector = r.get("sector", "Unknown")
            if sector not in sector_scores:
                sector_scores[sector] = []
            sector_scores[sector].append(r["total_score"])

        sector_avg = {}
        for sector, scores in sector_scores.items():
            sector_avg[sector] = round(sum(scores) / len(scores), 1)

        # 上位/下位セクター
        sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)
        bullish = [s for s, _ in sorted_sectors[:3] if sector_avg[s] >= 55]
        bearish = [s for s, _ in sorted_sectors[-3:] if sector_avg[s] <= 45]

        return {
            "sector_scores": sector_avg,
            "bullish_sectors": bullish,
            "bearish_sectors": bearish,
        }

    def _generate_risk_warnings(self, macro, results: list[dict]) -> list[str]:
        """リスク警告を生成"""
        warnings = []

        # VIXが高い場合
        if macro.vix and macro.vix > 25:
            warnings.append(f"[!] VIX={macro.vix:.1f} - ボラティリティが高く、市場全体にリスクあり")

        # 円高急進
        if macro.usdjpy_change and macro.usdjpy_change < -1.0:
            warnings.append(f"[!] 急激な円高 ({macro.usdjpy_change:+.2f}%) - 輸出企業に注意")

        # 米国長期金利上昇
        if macro.us10y_change and macro.us10y_change > 3.0:
            warnings.append(f"[!] 米国10年債利回り急上昇 ({macro.us10y_change:+.2f}%) - グロース株に注意")

        # 原油急騰
        if macro.oil_change and macro.oil_change > 5.0:
            warnings.append(f"[!] 原油価格急騰 ({macro.oil_change:+.2f}%) - コスト増の影響に注意")

        # 全体的に低スコアの場合
        avg_score = sum(r["total_score"] for r in results) / len(results) if results else 50
        if avg_score < 40:
            warnings.append("[!] 全体的にスコアが低い - 市場環境の悪化に注意")

        return warnings

    def _determine_market_sentiment(self, macro_score: float, risk_warnings: list[str] = None) -> str:
        """マクロスコアから市場センチメントを判定"""
        base_sentiment = "中立"
        if macro_score >= 70:
            base_sentiment = "強気"
        elif macro_score >= 55:
            base_sentiment = "やや強気"
        elif macro_score >= 45:
            base_sentiment = "中立"
        elif macro_score >= 30:
            base_sentiment = "やや弱気"
        else:
            base_sentiment = "弱気"
            
        # 重大なリスク警告がある場合はセンチメントを下方修正
        if risk_warnings:
            # 円高急進やVIX急騰などのキーワードが含まれる場合
            critical_keywords = ["急激な", "急騰", "急上昇", "VIX", "ボラティリティ"]
            is_critical = any(k in w for w in risk_warnings for k in critical_keywords)
            
            if is_critical:
                if "強気" in base_sentiment:
                    return f"{base_sentiment} (要警戒)"
                elif base_sentiment == "中立":
                    return "中立 (弱気バイアス)"
                
        return base_sentiment

    def _save_report(self, report: dict):
        """レポートをDBに保存"""
        session = get_session()
        try:
            # recommendationsとall_resultsの詳細を整理
            recommendations_data = []
            for r in report["recommendations"]:
                recommendations_data.append({
                    "rank": len(recommendations_data) + 1,
                    "ticker": r["ticker"],
                    "name": r.get("name", ""),
                    "sector": r.get("sector", ""),
                    "total_score": r["total_score"],
                    "rating": r["rating"],
                    "scores": r["scores"],
                    "signals": r["signals"][:5],  # シグナルは上位5つ
                })

            rec = Recommendation(
                report_date=date.today(),
                report_type=report["report_type"],
                recommendations=recommendations_data,
                market_summary=report["market_summary"],
            )
            session.add(rec)
            session.commit()
            logger.info("💾 レポートをDBに保存しました")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ レポート保存エラー: {e}")
        finally:
            session.close()
