"""全機能テストスクリプト

各モジュールを個別にテストして結果を報告する。
"""

import sys
import os
import warnings
import logging
import traceback
from pathlib import Path

# 警告を抑制
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["PYTHONWARNINGS"] = "ignore"

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("yfinance").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from src.database.models import init_db

results = {}


def test(name):
    """テストデコレータ"""
    def decorator(func):
        def wrapper():
            print(f"\n{'='*60}")
            print(f"🧪 テスト: {name}")
            print(f"{'='*60}")
            try:
                func()
                results[name] = "✅ PASS"
                print(f"\n✅ {name}: PASS")
            except Exception as e:
                results[name] = f"❌ FAIL: {e}"
                print(f"\n❌ {name}: FAIL — {e}")
                traceback.print_exc()
        return wrapper
    return decorator


@test("1. DB初期化")
def test_db():
    engine = init_db()
    print(f"  DB URL: {engine.url}")


@test("2. 株価データ収集 (yfinance)")
def test_stock():
    from src.collectors.stock_collector import StockCollector
    sc = StockCollector(tickers=["7203.T"])

    sc.collect_stock_info()
    print("  ✓ 銘柄情報取得OK (トヨタ)")

    sc.collect_price_history(period="5d")
    print("  ✓ 株価履歴取得OK (5日分)")

    indices = sc.get_market_indices()
    print(f"  ✓ 市場指数: {list(indices.keys())}")
    for sym, data in indices.items():
        print(f"    {data.get('name','?')}: {data.get('close',0):,.2f} ({data.get('change_pct',0):+.2f}%)")


@test("3. マクロ経済指標収集")
def test_macro():
    from src.collectors.macro_collector import MacroCollector
    mc = MacroCollector()

    indicators = mc.collect()
    print(f"  ✓ USD/JPY: {indicators.usdjpy}")
    print(f"  ✓ 日経225: {indicators.nikkei225}")
    print(f"  ✓ S&P500:  {indicators.sp500}")
    print(f"  ✓ VIX:     {indicators.vix}")
    print(f"  ✓ 米10年債: {indicators.us10y_yield}")
    print(f"  ✓ 原油:    {indicators.oil_price}")
    print(f"  ✓ 金:      {indicators.gold_price}")

    score = mc.calculate_macro_score(indicators)
    print(f"  ✓ マクロスコア: {score:.1f} / 100")


@test("4. ニュース収集")
def test_news():
    from src.collectors.news_collector import NewsCollector
    nc = NewsCollector()

    articles = nc.collect_all()
    print(f"  ✓ 収集記事数: {len(articles)}")

    from src.database.models import get_session, NewsArticle
    session = get_session()
    total = session.query(NewsArticle).count()
    session.close()
    print(f"  ✓ DB内の総記事数: {total}")


@test("5. センチメント分析 (FinBERT)")
def test_sentiment():
    from src.analyzers.sentiment_analyzer import SentimentAnalyzer
    sa = SentimentAnalyzer()

    test_cases = [
        ("ソニーの決算が好調で増収増益を達成", "ポジティブ想定"),
        ("景気後退の懸念が広がり株価下落", "ネガティブ想定"),
        ("東京証券取引所の取引時間が変更", "ニュートラル想定"),
    ]

    for text, expected in test_cases:
        result = sa.analyze_text(text)
        score = result.get("score", 0)
        label = result.get("label", "?")
        print(f"  ✓ [{expected}] スコア={score:+.3f} ラベル={label} — 「{text[:20]}...」")


@test("6. テクニカル分析")
def test_technical():
    from src.analyzers.technical_analyzer import TechnicalAnalyzer
    ta = TechnicalAnalyzer()

    result = ta.analyze("7203.T")
    cs = result.get('composite_score', 0)
    print(f"  ✓ 総合スコア: {cs:.1f}")
    print(f"  ✓ トレンド:   {result.get('trend_score', 0):.3f}")
    print(f"  ✓ モメンタム: {result.get('momentum_score', 0):.3f}")
    print(f"  ✓ ボラティリティ: {result.get('volatility_score', 0):.3f}")
    print(f"  ✓ 出来高:     {result.get('volume_score', 0):.3f}")

    signals = result.get("signals", [])
    for s in signals[:3]:
        print(f"    📊 {s}")


@test("7. ファンダメンタル分析")
def test_fundamental():
    from src.analyzers.fundamental_analyzer import FundamentalAnalyzer
    fa = FundamentalAnalyzer()

    result = fa.analyze("7203.T")
    cs = result.get('composite_score', 0)
    print(f"  ✓ 総合スコア: {cs:.1f}")

    metrics = result.get("metrics", {})
    for key, val in list(metrics.items())[:6]:
        print(f"    {key}: {val}")

    signals = result.get("signals", [])
    for s in signals[:3]:
        print(f"    📋 {s}")


@test("8. Gemini LLM 分析")
def test_llm():
    from src.config import config
    if not config.api_keys.gemini:
        print("  ⏭️ GEMINI_API_KEY 未設定 — スキップ")
        results["8. Gemini LLM 分析"] = "⏭️ SKIP (APIキー未設定)"
        return

    from src.analyzers.llm_analyzer import LLMAnalyzer
    llm = LLMAnalyzer()

    # 単一記事テスト
    result = llm.analyze_article(
        title="トヨタ自動車、EV戦略を加速 2026年に新型モデル10車種投入へ",
        content="トヨタ自動車は次世代EV戦略を発表し、2026年までに10車種の新型EVを投入する計画を明らかにした。"
    )
    if result:
        print(f"  ✓ 記事分析OK")
        print(f"    要約: {result.get('summary', 'N/A')}")
        print(f"    センチメント: {result.get('sentiment_score', 'N/A')}")
        print(f"    影響度: {result.get('impact_magnitude', 'N/A')}")
        print(f"    影響銘柄: {result.get('affected_tickers', [])}")
    else:
        raise Exception("記事分析: 結果なし")

    # 市場センチメントテスト
    headlines = [
        "日経平均が大幅反発、半導体関連株が堅調",
        "日銀、マイナス金利解除を見送り",
        "米国雇用統計が予想上回る",
    ]
    market = llm.analyze_market_sentiment(headlines)
    if market:
        print(f"  ✓ 市場分析OK")
        print(f"    見通し: {market.get('market_outlook', 'N/A')}")
        print(f"    センチメント: {market.get('overall_sentiment', 'N/A')}")
        print(f"    テーマ: {market.get('key_themes', [])}")
    else:
        raise Exception("市場分析: 結果なし")


@test("9. スコアリングエンジン")
def test_scoring():
    from src.scoring.scorer import Scorer

    scorer = Scorer()
    result = scorer.score(
        ticker="7203.T",
        sentiment_result={"sentiment_score": 0.3, "article_count": 5, "positive_count": 3, "negative_count": 1},
        technical_result={"composite_score": 65, "volatility_score": 0.4, "signals": ["RSI 中立圏"]},
        fundamental_result={"composite_score": 70, "signals": ["PER 割安"], "metrics": {}},
        macro_score=60.0,
    )
    print(f"  ✓ 総合スコア: {result['total_score']}")
    print(f"  ✓ レーティング: {result['rating_icon']} {result['rating']}")
    print(f"  ✓ 各スコア: {result['scores']}")
    assert result['total_score'] > 0, "スコアが0"


# ===== メイン実行 =====
if __name__ == "__main__":
    print("\n" + "🔬" * 30)
    print("  Market Analyzer — 全機能テスト")
    print("🔬" * 30)

    test_db()
    test_stock()
    test_macro()
    test_news()
    test_sentiment()
    test_technical()
    test_fundamental()
    test_llm()
    test_scoring()

    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    for name, status in results.items():
        print(f"  {status}")

    passed = sum(1 for v in results.values() if "PASS" in v or "SKIP" in v)
    failed = sum(1 for v in results.values() if "FAIL" in v)
    total = len(results)
    print(f"\n  合計: {passed} pass / {failed} fail / {total} total")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
