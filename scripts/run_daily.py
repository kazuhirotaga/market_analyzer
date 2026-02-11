"""デイリー分析実行スクリプト

メインのエントリーポイント。全パイプラインを実行し、CLIレポートを出力する。
"""

import sys
import logging
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import init_db
from src.scoring.recommender import Recommender
from src.reports.report_generator import ReportGenerator


def setup_logging(verbose: bool = False):
    """ロギング設定"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # yfinance の不要なログを抑制
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description="Market Analyzer — 日本株式市場分析 & おすすめ銘柄選別"
    )
    parser.add_argument(
        "-n", "--top-n",
        type=int, default=10,
        help="おすすめ銘柄の表示件数 (default: 10)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細ログを出力"
    )
    parser.add_argument(
        "--skip-collection",
        action="store_true",
        help="データ収集をスキップ (既存データで分析のみ)"
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # DB初期化
    logger.info("🗄️ データベース初期化中...")
    init_db()

    try:
        # 分析パイプライン実行
        recommender = Recommender()

        if args.skip_collection:
            logger.info("⏭️ データ収集をスキップします")
            # TODO: 既存データのみで分析する簡易モード
            report = recommender.run_full_analysis(top_n=args.top_n)
        else:
            report = recommender.run_full_analysis(top_n=args.top_n)

        # CLIレポート出力
        report_gen = ReportGenerator()
        report_gen.print_report(report)

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logger.error(f"❌ 致命的なエラーが発生しました:\n{error_msg}")

        # エラー通知メール送信
        try:
            from src.reports.email_notifier import EmailNotifier
            notifier = EmailNotifier()
            notifier.send_alert("Market Analyzer 実行エラー", f"分析パイプライン実行中にエラーが発生しました。\n\n{error_msg}")
        except Exception as mail_err:
            logger.error(f"❌ エラーメール送信失敗: {mail_err}")
            
        sys.exit(1)


if __name__ == "__main__":
    main()
