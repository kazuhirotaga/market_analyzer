"""簡易テスト — 各モジュールの動作確認"""
import warnings
warnings.filterwarnings("ignore")
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("yfinance").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from src.database.models import init_db
init_db()

results = {}

def run(name, fn):
    try:
        msg = fn()
        results[name] = ("PASS", msg or "")
    except Exception as e:
        results[name] = ("FAIL", str(e))

def t1():
    from src.collectors.stock_collector import StockCollector
    sc = StockCollector(tickers=["7203.T"])
    sc.collect_stock_info()
    sc.collect_price_history(period="5d")
    idx = sc.get_market_indices()
    return f"{len(idx)} indices"
run("1. Stock Collection", t1)

def t2():
    from src.collectors.macro_collector import MacroCollector
    mc = MacroCollector()
    ind = mc.collect()
    score = mc.calculate_macro_score(ind)
    return "USD/JPY={} VIX={} Score={:.1f}".format(ind.usdjpy, ind.vix, score)
run("2. Macro Indicators", t2)

def t3():
    from src.collectors.news_collector import NewsCollector
    nc = NewsCollector()
    arts = nc.collect_all()
    return "{} articles".format(len(arts))
run("3. News Collection", t3)

def t4():
    from src.analyzers.sentiment_analyzer import SentimentAnalyzer
    sa = SentimentAnalyzer()
    r = sa.analyze_text("ソニーの決算が好調で増収増益を達成")
    return "score={:+.2f} label={}".format(r["score"], r["label"])
run("4. Sentiment (FinBERT)", t4)

def t5():
    from src.analyzers.technical_analyzer import TechnicalAnalyzer
    ta = TechnicalAnalyzer()
    r = ta.analyze("7203.T")
    return "composite={:.1f}".format(r["composite_score"])
run("5. Technical Analysis", t5)

def t6():
    from src.analyzers.fundamental_analyzer import FundamentalAnalyzer
    fa = FundamentalAnalyzer()
    r = fa.analyze("7203.T")
    return "composite={:.1f}".format(r["composite_score"])
run("6. Fundamental Analysis", t6)

def t7():
    from src.config import config
    if not config.api_keys.gemini:
        return "SKIP (no API key)"
    from src.analyzers.llm_analyzer import LLMAnalyzer
    llm = LLMAnalyzer()
    r = llm.analyze_article(title="トヨタEV戦略加速", content="10車種投入")
    if r:
        return "sentiment={} impact={}".format(r.get("sentiment_score"), r.get("impact_magnitude"))
    return "FAIL: empty"
run("7. Gemini LLM Analysis", t7)

def t8():
    from src.scoring.scorer import Scorer
    s = Scorer()
    r = s.score("7203.T",
        {"sentiment_score": 0.3, "article_count": 5, "positive_count": 3, "negative_count": 1},
        {"composite_score": 65, "volatility_score": 0.4, "signals": []},
        {"composite_score": 70, "signals": [], "metrics": {}},
        60.0)
    return "score={} rating={}".format(r["total_score"], r["rating"])
run("8. Scoring Engine", t8)

print()
print("=" * 55)
print(" TEST RESULTS")
print("=" * 55)
fail_count = 0
for name, (status, msg) in results.items():
    icon = "✅" if status == "PASS" else "❌"
    if "SKIP" in msg:
        icon = "⏭️"
    if status == "FAIL":
        fail_count += 1
    print("  {} {} — {}".format(icon, name, msg))
passed = len(results) - fail_count
print()
print("  Total: {}/{} passed".format(passed, len(results)))
print("=" * 55)
sys.exit(0 if fail_count == 0 else 1)
