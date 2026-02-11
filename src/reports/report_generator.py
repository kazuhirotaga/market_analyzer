"""CLIレポート生成モジュール

Rich ライブラリを使用してターミナルに美しいレポートを出力する。
"""

import logging
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box

logger = logging.getLogger(__name__)
console = Console()


class ReportGenerator:
    """CLIレポート生成クラス"""

    def print_report(self, report: dict):
        """フルレポートをCLIに出力"""
        console.print()
        self._print_header(report)
        self._print_market_summary(report.get("market_summary", {}))
        
        self._print_top_news(report.get("top_news", []))

        self._print_recommendations(report.get("recommendations", []))
        
        llm_data = report.get("market_summary", {}).get("llm_analysis")


    def _print_top_news(self, news_list: list[dict]):
        """重要ニュース詳細出力"""
        if not news_list:
            return

        console.print("\n[bold cyan][News] 今日の重要ニュース (AI分析)[/bold cyan]")
        
        for i, news in enumerate(news_list, 1):
            title = news.get("title", "")
            summary = news.get("summary") or "要約なし"
            impact = news.get("impact", "N/A")
            reason = news.get("reasoning", "")
            sentiment = news.get("sentiment", 0)
            
            # インパクトの色
            impact_color = "red" if impact == "high" else "yellow" if impact == "medium" else "white"
            
            console.print(Panel(
                f"[bold]{title}[/bold]\n"
                f"{summary}\n\n"
                f"[dim]影響度: [{impact_color}]{impact.upper()}[/{impact_color}] | "
                f"スコア: {self._color_score(sentiment)}[/dim]\n"
                f"[italic]理由: {reason}[/italic]",
                border_style="blue",
                title=f"News #{i}"
            ))



    def _print_header(self, report: dict):
        """ヘッダー出力"""
        report_date = report.get("report_date", "N/A")
        console.print(Panel(
            f"[bold white][STATS] Market Analyzer - デイリーレポート[/bold white]\n"
            f"[dim]{report_date}[/dim]",
            style="bold blue",
            box=box.DOUBLE,
            padding=(1, 2),
        ))

    def _print_market_summary(self, summary: dict):
        """マーケットサマリー出力"""
        console.print("\n[bold cyan][GLOBAL] マーケットサマリー[/bold cyan]")

        # 指数テーブル
        indices = summary.get("indices", {})
        if indices:
            table = Table(box=box.ROUNDED, show_header=True)
            table.add_column("指数", style="white", width=16)
            table.add_column("終値", justify="right", width=12)
            table.add_column("前日比", justify="right", width=12)

            for symbol, data in indices.items():
                name = data.get("name", symbol)
                close = data.get("close", 0)
                change = data.get("change_pct", 0)

                change_style = "green" if change >= 0 else "red"
                change_str = f"[{change_style}]{change:+.2f}%[/{change_style}]"

                table.add_row(name, f"{close:,.2f}", change_str)

            console.print(table)

        # マクロスコア
        macro_score = summary.get("macro_score", 50)
        sentiment = summary.get("market_sentiment", "中立")
        macro_color = "green" if macro_score >= 55 else "yellow" if macro_score >= 45 else "red"
        console.print(
            f"  マクロ環境スコア: [{macro_color}]{macro_score:.1f}[/{macro_color}] "
            f"| 市場センチメント: [bold]{sentiment}[/bold]"
        )

        # LLM分析結果
        if "llm_analysis" in summary:
            self._print_llm_report(summary["llm_analysis"])

    def _print_llm_report(self, llm_data: dict):
        """LLM分析レポート出力"""
        console.print("\n[bold cyan][AI] AI市場分析 (Gemini)[/bold cyan]")
        
        # サマリー
        summary_text = llm_data.get("summary", "")
        if summary_text:
            console.print(Panel(summary_text, title="市場概況", border_style="cyan"))

        # キーテーマ
        themes = llm_data.get("key_themes", [])
        if themes:
            console.print(f"  [bold]注目テーマ:[/bold] {', '.join(themes)}")

        # リスク要因
        risks = llm_data.get("risk_factors", [])
        if risks:
            console.print(f"  [bold red]リスク要因:[/bold red] {', '.join(risks)}")


    def _print_recommendations(self, recommendations: list[dict]):
        """おすすめ銘柄テーブル出力"""
        if not recommendations:
            console.print("\n[yellow]おすすめ銘柄データがありません[/yellow]")
            return

        console.print("\n[bold cyan]* おすすめ銘柄 Top {0}[/bold cyan]".format(len(recommendations)))

        table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
        table.add_column("#", justify="center", width=3)
        table.add_column("銘柄コード", width=10)
        table.add_column("銘柄名", width=20)
        table.add_column("セクター", width=15)
        table.add_column("総合スコア", justify="center", width=10)
        table.add_column("レーティング", justify="center", width=14)
        table.add_column("センチ", justify="center", width=7)
        table.add_column("テクニカル", justify="center", width=10)
        table.add_column("ファンダ", justify="center", width=8)

        for i, rec in enumerate(recommendations, 1):
            scores = rec.get("scores", {})
            icon = rec.get("rating_icon", "(-)")
            total = rec.get("total_score", 0)
            rating = rec.get("rating", "N/A")

            # スコアに色をつける
            total_color = "green" if total >= 60 else "yellow" if total >= 40 else "red"

            table.add_row(
                str(i),
                rec.get("ticker", ""),
                rec.get("name", "")[:18],
                (rec.get("sector", "") or "")[:13],
                f"[{total_color}]{total:.1f}[/{total_color}]",
                f"{icon} {rating}",
                self._color_score(scores.get("sentiment", 50)),
                self._color_score(scores.get("technical", 50)),
                self._color_score(scores.get("fundamental", 50)),
            )

        console.print(table)

        # 上位銘柄のシグナル詳細
        console.print("\n[bold cyan][Memo] 上位銘柄のシグナル[/bold cyan]")
        for i, rec in enumerate(recommendations[:5], 1):
            ticker = rec.get("ticker", "")
            name = rec.get("name", "")
            signals = rec.get("signals", [])
            if signals:
                console.print(f"\n  [bold]{i}. {ticker} ({name})[/bold]")
                for sig in signals[:5]:
                    console.print(f"    {sig}")

    def _print_sector_analysis(self, sector_data: dict):
        """セクター分析出力"""
        if not sector_data:
            return

        console.print("\n[bold cyan][Sector] セクター分析[/bold cyan]")

        bullish = sector_data.get("bullish_sectors", [])
        bearish = sector_data.get("bearish_sectors", [])

    def _print_sector_analysis(self, sector_data: dict, llm_data: dict = None):
        """セクター分析出力"""
        if not sector_data:
            return

        console.print("\n[bold cyan][Sector] セクター分析[/bold cyan]")

        # 定量分析（スコアベース）
        bullish = sector_data.get("bullish_sectors", [])
        bearish = sector_data.get("bearish_sectors", [])

        if bullish:
            console.print(f"  [green]強気セクター (スコア): {', '.join(bullish)}[/green]")
        if bearish:
            console.print(f"  [red]弱気セクター (スコア): {', '.join(bearish)}[/red]")

        # 定性分析（LLMベース）
        if llm_data:
            llm_bullish = llm_data.get("bullish_sectors", [])
            llm_bearish = llm_data.get("bearish_sectors", [])
            if llm_bullish:
                console.print(f"  [green]強気セクター (AI予測): {', '.join(llm_bullish)}[/green]")
            if llm_bearish:
                console.print(f"  [red]弱気セクター (AI予測): {', '.join(llm_bearish)}[/red]")

        # セクタースコア表
        scores = sector_data.get("sector_scores", {})
        if scores:
            table = Table(box=box.SIMPLE, show_header=True)
            table.add_column("セクター", width=25)
            table.add_column("平均スコア", justify="right", width=12)

            for sector, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                table.add_row(sector, self._color_score(score))

            console.print(table)

    def _print_risk_warnings(self, warnings: list[str]):
        """リスク警告出力"""
        if not warnings:
            return

        console.print("\n[bold red][!] リスク警告[/bold red]")
        for w in warnings:
            console.print(f"  {w}")

    def _print_all_scores(self, results: list[dict]):
        """全銘柄スコア一覧"""
        if not results:
            return

        console.print("\n[bold cyan][Data] 全銘柄スコア一覧[/bold cyan]")

        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("銘柄", width=10)
        table.add_column("銘柄名", width=18)
        table.add_column("総合", justify="center", width=7)
        table.add_column("評価", justify="center", width=13)
        table.add_column("セン", justify="center", width=6)
        table.add_column("テク", justify="center", width=6)
        table.add_column("ファ", justify="center", width=6)
        table.add_column("マク", justify="center", width=6)
        table.add_column("リス", justify="center", width=6)

        for r in results:
            scores = r.get("scores", {})
            total = r.get("total_score", 0)
            icon = r.get("rating_icon", "(-)")
            rating = r.get("rating", "N/A")
            total_color = "green" if total >= 60 else "yellow" if total >= 40 else "red"

            table.add_row(
                r.get("ticker", ""),
                (r.get("name", "") or "")[:16],
                f"[{total_color}]{total:.0f}[/{total_color}]",
                f"{icon} {rating}",
                self._color_score_short(scores.get("sentiment", 50)),
                self._color_score_short(scores.get("technical", 50)),
                self._color_score_short(scores.get("fundamental", 50)),
                self._color_score_short(scores.get("macro", 50)),
                self._color_score_short(scores.get("risk", 50)),
            )

        console.print(table)

    def _color_score(self, score: float) -> str:
        """スコアに色をつけた文字列を返す"""
        if score >= 65:
            return f"[green]{score:.1f}[/green]"
        elif score >= 45:
            return f"[yellow]{score:.1f}[/yellow]"
        else:
            return f"[red]{score:.1f}[/red]"

    def _color_score_short(self, score: float) -> str:
        """スコアに色をつけた短い文字列"""
        if score >= 65:
            return f"[green]{score:.0f}[/green]"
        elif score >= 45:
            return f"[yellow]{score:.0f}[/yellow]"
        else:
            return f"[red]{score:.0f}[/red]"
