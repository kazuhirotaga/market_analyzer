"""ファンダメンタル分析モジュール

yfinanceから取得したファンダメンタル指標を分析し、
銘柄のバリュエーションスコアを算出する。
"""

import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)


class FundamentalAnalyzer:
    """ファンダメンタル分析クラス"""

    # セクター別PER平均値 (目安)
    SECTOR_AVG_PER = {
        "Technology": 25.0,
        "Healthcare": 22.0,
        "Consumer Cyclical": 18.0,
        "Financial Services": 12.0,
        "Industrials": 16.0,
        "Consumer Defensive": 20.0,
        "Basic Materials": 14.0,
        "Communication Services": 20.0,
        "Energy": 10.0,
        "Utilities": 15.0,
        "Real Estate": 30.0,
    }
    DEFAULT_AVG_PER = 18.0

    def analyze(self, ticker: str) -> dict:
        """ファンダメンタル分析を実行

        Returns:
            {
                "ticker": str,
                "valuation_score": float,  # 0〜100 (割安度)
                "profitability_score": float,  # 0〜100 (収益性)
                "growth_score": float,     # 0〜100 (成長性)
                "dividend_score": float,   # 0〜100 (配当)
                "composite_score": float,  # 0〜100 (総合)
                "metrics": dict,           # 各指標の値
                "signals": list[str],      # シグナル
            }
        """
        try:
            info = self._fetch_fundamentals(ticker)
        except Exception as e:
            logger.warning(f"⚠️ {ticker}: ファンダメンタルデータ取得失敗 - {e}")
            return self._empty_result(ticker)

        if not info:
            return self._empty_result(ticker)

        metrics = {}
        signals = []

        # --- バリュエーション ---
        valuation_score = self._calc_valuation_score(info, metrics, signals)

        # --- 収益性 ---
        profitability_score = self._calc_profitability_score(info, metrics, signals)

        # --- 成長性 ---
        growth_score = self._calc_growth_score(info, metrics, signals)

        # --- 配当 ---
        dividend_score = self._calc_dividend_score(info, metrics, signals)

        # --- 総合スコア ---
        composite = (
            valuation_score * 0.30 +
            profitability_score * 0.30 +
            growth_score * 0.25 +
            dividend_score * 0.15
        )
        composite = round(composite, 1)

        return {
            "ticker": ticker,
            "valuation_score": round(valuation_score, 1),
            "profitability_score": round(profitability_score, 1),
            "growth_score": round(growth_score, 1),
            "dividend_score": round(dividend_score, 1),
            "composite_score": composite,
            "metrics": metrics,
            "signals": signals,
        }

    def _calc_valuation_score(self, info: dict, metrics: dict, signals: list) -> float:
        """バリュエーションスコア (0〜100)"""
        scores = []

        # PER
        per = info.get("trailingPE")
        if per and per > 0:
            metrics["per"] = round(per, 2)
            sector = info.get("sector", "")
            avg_per = self.SECTOR_AVG_PER.get(sector, self.DEFAULT_AVG_PER)

            # PERが平均より低いほど割安 → 高スコア
            ratio = per / avg_per
            
            # ソフトバンクG (9984.T) は投資会社のためPER評価は不適切
            is_investment_co = info.get("symbol") == "9984.T" 

            if ratio < 0.5:
                per_score = 95
                if not is_investment_co:
                    signals.append(f"🟢 PER={per:.1f} は同業種平均 {avg_per:.0f} 比で大幅割安")
            elif ratio < 0.8:
                per_score = 80
                if not is_investment_co:
                    signals.append(f"🟢 PER={per:.1f} は割安圏")
            elif ratio < 1.2:
                per_score = 55
            elif ratio < 1.5:
                per_score = 35
            else:
                per_score = 15
                if not is_investment_co:
                    signals.append(f"🔴 PER={per:.1f} は割高圏")
            scores.append(per_score)

        # PBR
        pbr = info.get("priceToBook")
        if pbr and pbr > 0:
            metrics["pbr"] = round(pbr, 2)
            if pbr < 1.0:
                pbr_score = 85
                signals.append(f"🟢 PBR={pbr:.2f} (1倍割れ — 資産価値以下)")
            elif pbr < 1.5:
                pbr_score = 65
            elif pbr < 3.0:
                pbr_score = 45
            else:
                pbr_score = 20
            scores.append(pbr_score)

        # EV/EBITDA
        ev_ebitda = info.get("enterpriseToEbitda")
        if ev_ebitda and ev_ebitda > 0:
            metrics["ev_ebitda"] = round(ev_ebitda, 2)
            if ev_ebitda < 8:
                scores.append(80)
            elif ev_ebitda < 12:
                scores.append(60)
            elif ev_ebitda < 18:
                scores.append(40)
            else:
                scores.append(20)

        return sum(scores) / len(scores) if scores else 50.0

    def _calc_profitability_score(self, info: dict, metrics: dict, signals: list) -> float:
        """収益性スコア (0〜100)"""
        scores = []

        # ROE
        roe = info.get("returnOnEquity")
        if roe is not None:
            roe_pct = roe * 100
            metrics["roe"] = round(roe_pct, 2)
            if roe_pct > 30:
                roe_score = 95
                signals.append(f"🟢 ROE={roe_pct:.1f}% (極めて高い - 特殊要因の可能性あり)")
            elif roe_pct > 20:
                roe_score = 95
                signals.append(f"🟢 ROE={roe_pct:.1f}% (高収益)")
            elif roe_pct > 15:
                roe_score = 80
            elif roe_pct > 10:
                roe_score = 65
            elif roe_pct > 5:
                roe_score = 45
            elif roe_pct > 0:
                roe_score = 25
            else:
                roe_score = 10
                signals.append(f"🔴 ROE={roe_pct:.1f}% (マイナス)")
            scores.append(roe_score)

        # 営業利益率
        op_margin = info.get("operatingMargins")
        if op_margin is not None:
            op_pct = op_margin * 100
            metrics["operating_margin"] = round(op_pct, 2)
            if op_pct > 20:
                scores.append(90)
            elif op_pct > 10:
                scores.append(70)
            elif op_pct > 5:
                scores.append(50)
            elif op_pct > 0:
                scores.append(30)
            else:
                scores.append(10)

        # 純利益率
        net_margin = info.get("profitMargins")
        if net_margin is not None:
            net_pct = net_margin * 100
            metrics["net_margin"] = round(net_pct, 2)
            if net_pct > 15:
                scores.append(85)
            elif net_pct > 8:
                scores.append(65)
            elif net_pct > 3:
                scores.append(45)
            elif net_pct > 0:
                scores.append(25)
            else:
                scores.append(10)

        return sum(scores) / len(scores) if scores else 50.0

    def _calc_growth_score(self, info: dict, metrics: dict, signals: list) -> float:
        """成長性スコア (0〜100)"""
        scores = []

        # 売上成長率
        rev_growth = info.get("revenueGrowth")
        if rev_growth is not None:
            rev_pct = rev_growth * 100
            metrics["revenue_growth"] = round(rev_pct, 2)
            if rev_pct > 20:
                rev_score = 95
                signals.append(f"🟢 売上成長率={rev_pct:.1f}% (高成長)")
            elif rev_pct > 10:
                rev_score = 75
            elif rev_pct > 5:
                rev_score = 60
            elif rev_pct > 0:
                rev_score = 45
            elif rev_pct > -5:
                rev_score = 30
            else:
                rev_score = 10
                signals.append(f"🔴 売上成長率={rev_pct:.1f}% (減収)")
            scores.append(rev_score)

        # 利益成長率
        earn_growth = info.get("earningsGrowth")
        if earn_growth is not None:
            earn_pct = earn_growth * 100
            metrics["earnings_growth"] = round(earn_pct, 2)
            if earn_pct > 30:
                scores.append(90)
            elif earn_pct > 15:
                scores.append(70)
            elif earn_pct > 5:
                scores.append(55)
            elif earn_pct > 0:
                scores.append(40)
            else:
                scores.append(15)

        return sum(scores) / len(scores) if scores else 50.0

    def _calc_dividend_score(self, info: dict, metrics: dict, signals: list) -> float:
        """配当スコア (0〜100)"""
        # 配当スコア
        div_yield = info.get("dividendYield")
        if div_yield is not None:
            # yfinanceのdividendYieldは既にパーセント単位（例: 3.45 = 3.45%）の場合と
            # 小数単位（例: 0.0345 = 3.45%）の場合が混在する可能性があるが
            # 最近の挙動ではパーセント単位で返ってくることが多い (3.45など)
            # しかし、念のため 0.05 (5%) 以下なら小数として扱い、それ以上なら%として扱うヒューリスティックを入れる
            # ※ AAPL 0.38% -> 0.38 と返ってくるので、単にそのまま使うのが安全
            #   (0.38を小数とみなして100倍すると38%になってしまうため)
            
            # 修正: yfinanceがパーセント値を返していると仮定し、そのまま使用する
            metrics["dividend_yield"] = round(div_yield, 2)
            
            if div_yield > 4.0:
                signals.append(f"🟢 配当利回り={div_yield:.2f}% (高配当)")
                return 90.0
            elif div_yield > 3.0:
                return 75.0
            elif div_yield > 2.0:
                return 60.0
            elif div_yield > 1.0:
                return 45.0
            else:
                return 30.0
        else:
            metrics["dividend_yield"] = 0.0
            return 20.0  # 無配

    def _fetch_fundamentals(self, ticker: str) -> Optional[dict]:
        """yfinanceからファンダメンタルデータを取得"""
        t = yf.Ticker(ticker)
        info = t.info
        if not info or "shortName" not in info:
            return None
        return info

    def _empty_result(self, ticker: str) -> dict:
        return {
            "ticker": ticker,
            "valuation_score": 50.0,
            "profitability_score": 50.0,
            "growth_score": 50.0,
            "dividend_score": 50.0,
            "composite_score": 50.0,
            "metrics": {},
            "signals": ["⚠️ ファンダメンタルデータ取得不可"],
        }
