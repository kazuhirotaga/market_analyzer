"""メール通知モジュール

分析レポートをHTML形式のメールで送信する。
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from typing import Optional

from src.config import config

logger = logging.getLogger(__name__)


class EmailNotifier:
    """メール通知クラス"""

    def __init__(self):
        self.smtp_config = config.smtp

    def send_report(self, report: dict) -> bool:
        """分析レポートをメール送信

        Args:
            report: Recommender.run_full_analysis() の戻り値

        Returns:
            送信成功: True / 失敗: False
        """
        if not self.smtp_config.is_configured:
            logger.warning("⚠️ SMTP設定が未完了です。メール送信をスキップします。")
            return False

        try:
            subject = self._build_subject(report)
            html_body = self._build_html(report)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_config.user
            msg["To"] = self.smtp_config.recipient

            # プレーンテキスト (フォールバック用)
            text_body = self._build_plain_text(report)
            msg.attach(MIMEText(text_body, "plain", "utf-8"))

            # HTML
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # SMTP送信
            with smtplib.SMTP(self.smtp_config.host, self.smtp_config.port) as server:
                if self.smtp_config.use_tls:
                    server.starttls()
                server.login(self.smtp_config.user, self.smtp_config.password)
                server.send_message(msg)

            logger.info(f"📧 レポートメール送信完了 → {self.smtp_config.recipient}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP認証エラー: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP送信エラー: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ メール送信エラー: {e}")
            return False

    def send_alert(self, title: str, message: str) -> bool:
        """緊急アラートメールを送信

        Args:
            title: アラートタイトル
            message: アラート内容

        Returns:
            送信成功: True / 失敗: False
        """
        if not self.smtp_config.is_configured:
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚨 Market Analyzer Alert: {title}"
            msg["From"] = self.smtp_config.user
            msg["To"] = self.smtp_config.recipient

            html = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 24px; border: 1px solid #0f3460;">
                    <h2 style="color: #e94560; margin-top: 0;">🚨 {title}</h2>
                    <p style="font-size: 16px; line-height: 1.6;">{message}</p>
                    <hr style="border: 1px solid #0f3460; margin: 20px 0;">
                    <p style="color: #888; font-size: 12px;">Market Analyzer — 自動アラート通知</p>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(message, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP(self.smtp_config.host, self.smtp_config.port) as server:
                if self.smtp_config.use_tls:
                    server.starttls()
                server.login(self.smtp_config.user, self.smtp_config.password)
                server.send_message(msg)

            logger.info(f"🚨 アラートメール送信完了: {title}")
            return True
        except Exception as e:
            logger.error(f"❌ アラートメール送信エラー: {e}")
            return False

    def _build_subject(self, report: dict) -> str:
        """メール件名を生成"""
        report_date = report.get("report_date", date.today().isoformat())
        recs = report.get("recommendations", [])
        top_ticker = recs[0].get("ticker", "") if recs else ""
        top_name = recs[0].get("name", "") if recs else ""
        top_score = recs[0].get("total_score", 0) if recs else 0
        top_icon = recs[0].get("rating_icon", "") if recs else ""

        return (
            f"📊 Market Analyzer [{report_date}] "
            f"Top: {top_icon} {top_name}({top_ticker}) {top_score:.0f}pt"
        )

    def _build_html(self, report: dict) -> str:
        """HTML形式のレポートを生成"""
        report_date = report.get("report_date", "N/A")
        market = report.get("market_summary", {})
        recs = report.get("recommendations", [])
        sector = report.get("sector_analysis", {})
        warnings = report.get("risk_warnings", [])

        # マーケットサマリー
        macro_score = market.get("macro_score", 50)
        sentiment = market.get("market_sentiment", "中立")
        macro_color = "#4caf50" if macro_score >= 55 else "#ff9800" if macro_score >= 45 else "#f44336"

        # LLMテーマ
        themes = market.get("key_themes", [])
        themes_html = ""
        if themes:
            tags = "".join(
                f'<span style="background: #0f3460; padding: 4px 10px; border-radius: 12px; '
                f'font-size: 13px; margin: 2px;">{t}</span> '
                for t in themes[:5]
            )
            themes_html = f'<div style="margin-top: 8px;">🏷️ {tags}</div>'

        # 指数テーブル
        indices_html = ""
        indices = market.get("indices", {})
        if indices:
            rows = ""
            for sym, data in indices.items():
                name = data.get("name", sym)
                close = data.get("close", 0)
                change = data.get("change_pct", 0)
                color = "#4caf50" if change >= 0 else "#f44336"
                rows += f"""
                <tr>
                    <td style="padding: 6px 12px;">{name}</td>
                    <td style="padding: 6px 12px; text-align: right;">{close:,.2f}</td>
                    <td style="padding: 6px 12px; text-align: right; color: {color};">{change:+.2f}%</td>
                </tr>"""
            indices_html = f"""
            <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                <tr style="background: #0f3460;">
                    <th style="padding: 8px 12px; text-align: left;">指数</th>
                    <th style="padding: 8px 12px; text-align: right;">終値</th>
                    <th style="padding: 8px 12px; text-align: right;">前日比</th>
                </tr>
                {rows}
            </table>"""

        # おすすめ銘柄テーブル
        rec_rows = ""
        for i, r in enumerate(recs, 1):
            scores = r.get("scores", {})
            total = r.get("total_score", 0)
            icon = r.get("rating_icon", "⚪")
            rating = r.get("rating", "N/A")
            total_color = "#4caf50" if total >= 60 else "#ff9800" if total >= 40 else "#f44336"

            signals = r.get("signals", [])[:3]
            signals_text = "<br>".join(f"• {s}" for s in signals) if signals else ""

            rec_rows += f"""
            <tr style="border-bottom: 1px solid #0f3460;">
                <td style="padding: 10px 8px; text-align: center; font-weight: bold;">{i}</td>
                <td style="padding: 10px 8px;">
                    <strong>{r.get('ticker', '')}</strong><br>
                    <span style="color: #aaa; font-size: 13px;">{r.get('name', '')}</span>
                </td>
                <td style="padding: 10px 8px; color: #aaa; font-size: 13px;">{r.get('sector', '') or ''}</td>
                <td style="padding: 10px 8px; text-align: center;">
                    <span style="font-size: 20px; font-weight: bold; color: {total_color};">{total:.0f}</span>
                </td>
                <td style="padding: 10px 8px; text-align: center;">{icon} {rating}</td>
                <td style="padding: 10px 8px; font-size: 12px; color: #ccc;">{signals_text}</td>
            </tr>"""

        # リスク警告
        warnings_html = ""
        if warnings:
            items = "".join(f"<li style='margin: 4px 0;'>{w}</li>" for w in warnings)
            warnings_html = f"""
            <div style="background: #2d1b1b; border: 1px solid #e94560; border-radius: 8px; padding: 12px; margin-top: 16px;">
                <h3 style="color: #e94560; margin-top: 0;">⚠️ リスク警告</h3>
                <ul style="margin: 0; padding-left: 20px;">{items}</ul>
            </div>"""

        # セクター
        sector_html = ""
        bullish = sector.get("bullish_sectors", [])
        bearish = sector.get("bearish_sectors", [])
        if bullish or bearish:
            sector_html = '<div style="margin-top: 16px;">'
            if bullish:
                sector_html += f'<p>🟢 <strong>強気セクター:</strong> {", ".join(bullish)}</p>'
            if bearish:
                sector_html += f'<p>🔴 <strong>弱気セクター:</strong> {", ".join(bearish)}</p>'
            sector_html += "</div>"

        html = f"""
        <html>
        <body style="font-family: 'Segoe UI', 'Hiragino Sans', Arial, sans-serif; background: #0a0a1a; color: #e0e0e0; margin: 0; padding: 20px;">
            <div style="max-width: 700px; margin: 0 auto;">

                <!-- ヘッダー -->
                <div style="background: linear-gradient(135deg, #0f3460, #16213e); border-radius: 12px; padding: 24px; margin-bottom: 16px; border: 1px solid #1a3a6e;">
                    <h1 style="margin: 0; font-size: 22px; color: #fff;">📊 Market Analyzer</h1>
                    <p style="margin: 4px 0 0; color: #88a0cc;">デイリーレポート — {report_date}</p>
                </div>

                <!-- マーケットサマリー -->
                <div style="background: #16213e; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid #0f3460;">
                    <h2 style="margin-top: 0; font-size: 18px;">🌐 マーケットサマリー</h2>
                    {indices_html}
                    <p>マクロ環境スコア: <span style="color: {macro_color}; font-weight: bold; font-size: 18px;">{macro_score:.1f}</span> / 100 | 市場センチメント: <strong>{sentiment}</strong></p>
                    {themes_html}
                </div>

                <!-- おすすめ銘柄 -->
                <div style="background: #16213e; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid #0f3460;">
                    <h2 style="margin-top: 0; font-size: 18px;">⭐ おすすめ銘柄 Top {len(recs)}</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background: #0f3460; font-size: 13px;">
                            <th style="padding: 8px; width: 30px;">#</th>
                            <th style="padding: 8px; text-align: left;">銘柄</th>
                            <th style="padding: 8px; text-align: left;">セクター</th>
                            <th style="padding: 8px; text-align: center;">スコア</th>
                            <th style="padding: 8px; text-align: center;">評価</th>
                            <th style="padding: 8px; text-align: left;">シグナル</th>
                        </tr>
                        {rec_rows}
                    </table>
                </div>

                <!-- セクター & リスク -->
                {sector_html}
                {warnings_html}

                <!-- フッター -->
                <div style="text-align: center; margin-top: 24px; padding: 16px; color: #666; font-size: 12px;">
                    <p>Market Analyzer — 自動生成レポート</p>
                    <p>⚠️ 本レポートは情報提供のみを目的としており、投資助言ではありません。</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def _build_plain_text(self, report: dict) -> str:
        """プレーンテキスト形式のレポート"""
        report_date = report.get("report_date", "N/A")
        recs = report.get("recommendations", [])
        market = report.get("market_summary", {})
        warnings = report.get("risk_warnings", [])

        lines = [
            f"=== Market Analyzer デイリーレポート [{report_date}] ===",
            "",
            f"市場センチメント: {market.get('market_sentiment', 'N/A')}",
            f"マクロスコア: {market.get('macro_score', 0):.1f}/100",
            "",
            f"--- おすすめ銘柄 Top {len(recs)} ---",
        ]

        for i, r in enumerate(recs, 1):
            lines.append(
                f"{i}. {r.get('rating_icon', '')} {r.get('ticker', '')} "
                f"({r.get('name', '')}) — "
                f"スコア: {r.get('total_score', 0):.0f} [{r.get('rating', '')}]"
            )
            for s in r.get("signals", [])[:2]:
                lines.append(f"   {s}")

        if warnings:
            lines.append("")
            lines.append("--- リスク警告 ---")
            for w in warnings:
                lines.append(f"  {w}")

        lines.append("")
        lines.append("⚠️ 本レポートは情報提供のみを目的としており、投資助言ではありません。")

        return "\n".join(lines)
