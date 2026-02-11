"""メール通知テスト

SMTP接続テスト → ダミーレポートでHTML生成テスト → 実送信テスト
"""
import warnings
warnings.filterwarnings("ignore")
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

from src.config import config
from src.reports.email_notifier import EmailNotifier


def main():
    print("=" * 55)
    print(" 📧 メール通知機能テスト")
    print("=" * 55)

    # 1. SMTP設定チェック
    smtp = config.smtp
    print("\n--- SMTP設定 ---")
    print("  Host:      {}".format(smtp.host or "(未設定)"))
    print("  Port:      {}".format(smtp.port))
    print("  User:      {}".format(smtp.user or "(未設定)"))
    print("  Password:  {}".format("***" if smtp.password else "(未設定)"))
    print("  Recipient: {}".format(smtp.recipient or "(未設定)"))
    print("  TLS:       {}".format(smtp.use_tls))
    print("  Configured: {}".format(smtp.is_configured))

    if not smtp.is_configured:
        print("\n❌ SMTP設定が不完全です。.envファイルを確認してください:")
        print("   SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_RECIPIENT")
        return

    notifier = EmailNotifier()

    # 2. ダミーレポートでHTML生成テスト
    print("\n--- HTML生成テスト ---")
    dummy_report = {
        "report_date": "2026-02-11",
        "report_type": "daily",
        "market_summary": {
            "indices": {
                "^N225": {"name": "日経平均", "close": 39256.80, "change_pct": 1.23},
                "^TPX": {"name": "TOPIX", "close": 2745.12, "change_pct": 0.89},
            },
            "macro_score": 62.5,
            "market_sentiment": "やや強気",
            "key_themes": ["半導体需要回復", "日銀金融政策", "円安進行"],
        },
        "recommendations": [
            {
                "ticker": "8035.T", "name": "東京エレクトロン",
                "sector": "半導体", "total_score": 78.5,
                "rating": "Strong Buy", "rating_icon": "🟢",
                "scores": {"sentiment": 80, "technical": 75, "fundamental": 82},
                "signals": ["RSI上昇トレンド", "SMA25突破", "PER割安水準"],
            },
            {
                "ticker": "6758.T", "name": "ソニーグループ",
                "sector": "電機", "total_score": 72.3,
                "rating": "Buy", "rating_icon": "🟡",
                "scores": {"sentiment": 70, "technical": 68, "fundamental": 77},
                "signals": ["MACD買いシグナル", "好決算"],
            },
            {
                "ticker": "7203.T", "name": "トヨタ自動車",
                "sector": "自動車", "total_score": 65.1,
                "rating": "Hold", "rating_icon": "⚪",
                "scores": {"sentiment": 55, "technical": 70, "fundamental": 68},
                "signals": ["ボリンジャーバンド中立圏"],
            },
        ],
        "sector_analysis": {
            "bullish_sectors": ["半導体", "金融"],
            "bearish_sectors": ["不動産"],
        },
        "risk_warnings": [
            "VIXが20を超えて上昇中 — ボラティリティ上昇に注意",
            "🤖 米中貿易摩擦の再燃リスク",
        ],
    }

    html = notifier._build_html(dummy_report)
    text = notifier._build_plain_text(dummy_report)
    subject = notifier._build_subject(dummy_report)

    print("  ✓ 件名: {}".format(subject))
    print("  ✓ HTML: {} bytes".format(len(html)))
    print("  ✓ Text: {} bytes".format(len(text)))

    # HTMLをファイルに保存（確認用）
    preview_path = os.path.join(os.path.dirname(__file__), "..", "data", "email_preview.html")
    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ HTMLプレビュー保存: {}".format(os.path.abspath(preview_path)))

    # 3. テストメール送信
    print("\n--- テストメール送信 ---")
    success = notifier.send_report(dummy_report)
    if success:
        print("  ✅ テストメール送信成功!")
        print("  → {} の受信箱を確認してください".format(smtp.recipient))
    else:
        print("  ❌ テストメール送信失敗")

    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
