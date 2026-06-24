"""
中国A股数据源 — 多层 fallback (10层数据源，确保稳定性)

数据源优先级（按实测速度排序）：
  K线数据:
    1. 腾讯财经 (1.5s, 免费，日/周/分钟线稳定)
    2. 新浪财经 (0.4-1.1s, 免费，全周期支持，速度快)
    3. 同花顺 (0.5s, 免费，日K线稳定)
    4. 东方财富分时线 (0.3s, 免费，分时线，聚合为分钟K线)
    5. AkShare (免费，东方财富数据)
    6. yfinance (免费，Yahoo 数据)
    7. Baostock (3-4s, 免费，全周期支持)
    8. Twelve Data (付费，最稳定)
    9. 通达信 mootdx (免费，国内直连，但实测65秒超时不可用)

  实时行情:
    1. 新浪实时行情 (0.89s, 最快)
    2. 同花顺实时行情 (0.98s)
    3. 腾讯财经 (1.70s)
    4. 东方财富实时行情 (0.40s, 但不稳定)
    5. 通达信 (65s超时, 仅作最后兜底)
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional

from app.data_sources.base import BaseDataSource
from app.data_sources.tencent import (
    normalize_cn_code, 
    fetch_quote, 
    parse_quote_to_ticker, 
    fetch_kline, 
    tencent_kline_rows_to_dicts,
    fetch_minute_data,
    minute_data_to_klines,
)
from app.data_sources.sina import fetch_sina_kline
from app.data_sources.cn_extra_sources import (
    fetch_ths_daily_kline,
    fetch_em_minute_trends,
    em_minute_trends_to_klines,
    fetch_sina_quote,
    fetch_ths_quote,
)
from app.data_sources.baostock_source import (
    fetch_baostock_kline,
    fetch_em_quote,
    fetch_tencent_gu_quote,
)
from app.data_sources.mootdx_source import (
    fetch_tdx_quote,
    fetch_tdx_bars,
    fetch_tdx_minute_bars,
    get_cn_stock_quote_tdx,
    get_cn_stock_kline_tdx,
)
from app.data_sources.asia_stock_kline import (
    normalize_chart_timeframe,
    fetch_twelvedata_klines,
    fetch_yfinance_klines,
    fetch_akshare_minute_klines,
    fetch_akshare_weekly_klines,
)
from app.data_sources.cn_stock_reports import (
    fetch_cn_stock_reports,
    fetch_cn_stock_recent_reports,
    fetch_eastmoney_industry_reports,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CNStockDataSource(BaseDataSource):
    """A股数据源（TwelveData + Mootdx + Tencent + yfinance + AkShare）"""

    name = "CNStock/multi-source"

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        code = normalize_cn_code(symbol)

        # Tier 1: 新浪实时行情 (实测0.89s，最快)
        sina_q = fetch_sina_quote(code)
        if sina_q and sina_q.get("last", 0) > 0:
            return {
                "last": sina_q.get("last", 0),
                "change": sina_q.get("change", 0),
                "changePercent": sina_q.get("changePercent", 0),
                "high": sina_q.get("high", 0),
                "low": sina_q.get("low", 0),
                "open": sina_q.get("open", 0),
                "previousClose": sina_q.get("previousClose", 0),
                "name": sina_q.get("name", ""),
                "symbol": code,
            }

        # Tier 2: 同花顺实时行情 (实测0.98s)
        ths_q = fetch_ths_quote(code)
        if ths_q and ths_q.get("last", 0) > 0:
            return {
                "last": ths_q.get("last", 0),
                "change": ths_q.get("change", 0),
                "changePercent": ths_q.get("changePercent", 0),
                "high": ths_q.get("high", 0),
                "low": ths_q.get("low", 0),
                "open": ths_q.get("open", 0),
                "previousClose": ths_q.get("previousClose", 0),
                "name": ths_q.get("name", ""),
                "symbol": code,
            }

        # Tier 3: 腾讯财经行情 (实测1.70s)
        parts = fetch_quote(code)
        if parts:
            t = parse_quote_to_ticker(parts)
            if t.get("last", 0) > 0:
                return {
                    "last": t.get("last", 0),
                    "change": t.get("change", 0),
                    "changePercent": t.get("changePercent", 0),
                    "high": t.get("high", 0),
                    "low": t.get("low", 0),
                    "open": t.get("open", 0),
                    "previousClose": t.get("previousClose", 0),
                    "name": t.get("name", ""),
                    "symbol": code,
                }

        # Tier 4: 东方财富实时行情 (实测0.40s，但不稳定)
        em_q = fetch_em_quote(code)
        if em_q and em_q.get("last", 0) > 0:
            return {
                "last": em_q.get("last", 0),
                "change": em_q.get("change", 0),
                "changePercent": em_q.get("changePercent", 0),
                "high": em_q.get("high", 0),
                "low": em_q.get("low", 0),
                "open": em_q.get("open", 0),
                "previousClose": em_q.get("previousClose", 0),
                "name": em_q.get("name", ""),
                "symbol": code,
            }

        # Tier 5: 通达信实时行情 (实测65s超时，仅作最后兜底)
        tdx_quote = fetch_tdx_quote(code)
        if tdx_quote and tdx_quote.get("last", 0) > 0:
            return {
                "last": tdx_quote.get("last", 0),
                "change": tdx_quote.get("change", 0),
                "changePercent": tdx_quote.get("changePercent", 0),
                "high": tdx_quote.get("high", 0),
                "low": tdx_quote.get("low", 0),
                "open": tdx_quote.get("open", 0),
                "previousClose": tdx_quote.get("previousClose", 0),
                "name": tdx_quote.get("name", ""),
                "symbol": code,
            }

        return {"last": 0, "symbol": code}

    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None,
        after_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        code = normalize_cn_code(symbol)
        tf = normalize_chart_timeframe(timeframe)
        lim = max(int(limit or 300), 1)

        # ===== Tier 1: 新浪财经 (实测0.4-1.1s，全周期支持，可返回完整历史数据) =====
        try:
            sina_rows = fetch_sina_kline(code, timeframe=tf, limit=lim)
            if sina_rows:
                logger.info(f"从新浪财经获取到 {len(sina_rows)} 条 {tf} K线数据")
                return self.filter_and_limit(
                    sina_rows,
                    limit=lim,
                    before_time=before_time,
                    after_time=after_time,
                    truncate=(after_time is None),
                )
        except Exception as e:
            logger.debug(f"新浪财经数据获取失败: {e}")

        # ===== Tier 2: 腾讯财经 (实测最快 1.5s) =====
        # 分钟数据 (15m, 30m, 60m) - 仅作为新浪财经的补充
        if tf in ("15m", "30m", "1H") and after_time is None:
            tf_minutes = {"15m": 15, "30m": 30, "1H": 60}.get(tf, 15)
            code_lower = code.lower()
            if code_lower.startswith(('sh', 'sz')):
                tencent_code = code_lower
            else:
                tencent_code = f"sh{code_lower}"
            try:
                minute_data = fetch_minute_data(tencent_code)
                if minute_data and minute_data.get("data"):
                    rows = minute_data_to_klines(minute_data["data"], tf_minutes)
                    if rows:
                        logger.info(f"从腾讯财经获取到 {len(rows)} 条 {tf} 分钟K线数据")
                        return self.filter_and_limit(
                            rows,
                            limit=lim,
                            before_time=before_time,
                            after_time=after_time,
                            truncate=True,
                        )
            except Exception as e:
                logger.debug(f"腾讯财经分钟数据获取失败: {e}")

        # 日/周线
        if tf in ("1D", "1W"):
            tf_map = {"1D": "day", "1W": "week"}
            period = tf_map.get(tf, "day")
            try:
                raw_rows = fetch_kline(code, period=period, count=lim, adj="qfq")
                out = tencent_kline_rows_to_dicts(raw_rows)
                if out:
                    logger.info(f"从腾讯财经获取到 {len(out)} 条 {tf} K线数据")
                    return self.filter_and_limit(
                        out,
                        limit=lim,
                        before_time=before_time,
                        after_time=after_time,
                        truncate=(after_time is None),
                    )
            except Exception as e:
                logger.debug(f"腾讯财经日/周线数据获取失败: {e}")

        # ===== Tier 3: 同花顺 (实测0.5s，日K线稳定) =====
        if tf == "1D" and after_time is None:
            try:
                ths_rows = fetch_ths_daily_kline(code, limit=lim)
                if ths_rows:
                    logger.info(f"从同花顺获取到 {len(ths_rows)} 条 {tf} K线数据")
                    return self.filter_and_limit(
                        ths_rows,
                        limit=lim,
                        before_time=before_time,
                        after_time=after_time,
                        truncate=(after_time is None),
                    )
            except Exception as e:
                logger.debug(f"同花顺数据获取失败: {e}")

        # ===== Tier 4: 东方财富分时线 (实测0.3s，聚合为分钟K线) =====
        if tf in ("5m", "15m", "30m", "1H") and after_time is None:
            tf_minutes = {"5m": 5, "15m": 15, "30m": 30, "1H": 60}.get(tf, 15)
            try:
                trends = fetch_em_minute_trends(code, ndays=1)
                if trends:
                    em_rows = em_minute_trends_to_klines(trends, timeframe=tf_minutes)
                    if em_rows:
                        logger.info(f"从东方财富分时线聚合到 {len(em_rows)} 条 {tf} K线数据")
                        return self.filter_and_limit(
                            em_rows,
                            limit=lim,
                            before_time=before_time,
                            after_time=after_time,
                            truncate=True,
                        )
            except Exception as e:
                logger.debug(f"东方财富分时线数据获取失败: {e}")

        # ===== Tier 5: AkShare =====
        try:
            if tf in ("1m", "5m", "15m", "30m", "1H", "4H"):
                rows = fetch_akshare_minute_klines(
                    is_hk=False, tencent_code=code, timeframe=tf, limit=lim, before_time=before_time
                )
            elif tf == "1W":
                rows = fetch_akshare_weekly_klines(
                    is_hk=False, tencent_code=code, limit=lim, before_time=before_time
                )
            else:
                rows = []
            if rows:
                return self.filter_and_limit(
                    rows,
                    limit=lim,
                    before_time=before_time,
                    after_time=after_time,
                    truncate=(after_time is None),
                )
        except Exception as e:
            logger.debug(f"AkShare数据获取失败: {e}")

        # ===== Tier 6: yfinance =====
        try:
            rows = fetch_yfinance_klines(
                is_hk=False, tencent_code=code, timeframe=tf, limit=lim, before_time=before_time
            )
            if rows:
                return self.filter_and_limit(
                    rows,
                    limit=lim,
                    before_time=before_time,
                    after_time=after_time,
                    truncate=(after_time is None),
                )
        except Exception as e:
            logger.debug(f"yfinance数据获取失败: {e}")

        # ===== Tier 7: Baostock (3-4s，全周期支持) =====
        try:
            bao_rows = fetch_baostock_kline(code, timeframe=tf, limit=lim, before_time=before_time)
            if bao_rows:
                logger.info(f"从Baostock获取到 {len(bao_rows)} 条 {tf} K线数据")
                return self.filter_and_limit(
                    bao_rows,
                    limit=lim,
                    before_time=before_time,
                    after_time=after_time,
                    truncate=(after_time is None),
                )
        except Exception as e:
            logger.debug(f"Baostock数据获取失败: {e}")

        # ===== Tier 8: Twelve Data =====
        try:
            rows = fetch_twelvedata_klines(
                is_hk=False, tencent_code=code, timeframe=tf, limit=lim, before_time=before_time
            )
            if rows:
                return self.filter_and_limit(
                    rows,
                    limit=lim,
                    before_time=before_time,
                    after_time=after_time,
                    truncate=(after_time is None),
                )
        except Exception as e:
            logger.debug(f"Twelve Data数据获取失败: {e}")

        # ===== Tier 9: 通达信 mootdx (实测65秒超时，仅作最后兜底) =====
        try:
            tdx_rows = fetch_tdx_bars(code, timeframe=tf, limit=lim, end=before_time)
            if tdx_rows:
                logger.info(f"从通达信获取到 {len(tdx_rows)} 条 {tf} K线数据")
                return self.filter_and_limit(
                    tdx_rows,
                    limit=lim,
                    before_time=before_time,
                    after_time=after_time,
                    truncate=(after_time is None),
                )
        except Exception as e:
            logger.debug(f"通达信数据获取失败: {e}")

        return []

    def get_reports(
        self,
        symbol: str,
        limit: int = 20,
        report_type: str = "all",
    ) -> List[Dict[str, Any]]:
        code = normalize_cn_code(symbol)
        return fetch_cn_stock_reports(code, limit=limit, report_type=report_type)

    def get_recent_reports(
        self,
        symbol: str,
        days: int = 7,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        code = normalize_cn_code(symbol)
        return fetch_cn_stock_recent_reports(code, days=days, limit=limit)

    def get_industry_reports(
        self,
        industry: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return fetch_eastmoney_industry_reports(industry, limit=limit)
