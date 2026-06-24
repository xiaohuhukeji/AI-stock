"""
中国A股额外数据源 — 同花顺 + 东方财富 + 新浪实时行情

提供更多备选数据源，增强K线和分时线获取的稳定性。

数据源：
  1. 同花顺 (10jqka) - 日K线，实测0.5s
  2. 东方财富 (eastmoney) - 分时线，实测0.3s（有时不稳定）
  3. 新浪实时行情 (sina hq) - 实时价格，实测0.6s
  4. 同花顺实时行情 (10jqka) - 实时价格，实测0.4s
"""

from __future__ import annotations

import os
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from app.data_sources.rate_limiter import get_request_headers
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_timeout(default: int = 4) -> int:
    try:
        v = os.getenv("CN_EXTRA_TIMEOUT")
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# 同花顺 (10jqka) - 日K线
# ---------------------------------------------------------------------------

def _ths_code_from_tencent(code: str) -> str:
    """腾讯代码 -> 同花顺代码 (sh600519 -> hs_600519)"""
    c = (code or "").strip().lower()
    if c.startswith("sh"):
        return f"hs_{c[2:]}"
    if c.startswith("sz"):
        return f"hs_{c[2:]}"
    if c.isdigit() and len(c) == 6:
        return f"hs_{c}"
    return c


def fetch_ths_daily_kline(
    code: str,
    limit: int = 300,
    timeout: int = 0,
) -> List[Dict[str, Any]]:
    """
    从同花顺获取日K线数据

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)
        limit: 返回条数
        timeout: 超时秒数

    Returns:
        K线数据列表 [{time, open, high, low, close, volume}, ...]
    """
    if timeout <= 0:
        timeout = _get_timeout(4)

    ths_code = _ths_code_from_tencent(code)
    url = f"https://d.10jqka.com.cn/v6/line/{ths_code}/01/last.js"
    headers = {
        **get_request_headers(referer="https://d.10jqka.com.cn/"),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
        if resp.status_code != 200 or not resp.text:
            return []

        # 解析JSONP: quotebridge_v6_line_hs_600519_01_last({...})
        m = re.search(r"quotebridge_v6_line_\w+_\d+_last\((.*)\)", resp.text)
        if not m:
            return []

        data = json.loads(m.group(1))
        raw = data.get("data", "")
        if not raw or not isinstance(raw, str):
            return []

        # 格式: 20251119,1450.04,1455.57,1446.00,1447.05,2204537,3249449200.00,0.176,,,0;...
        out: List[Dict[str, Any]] = []
        parts = raw.split(";")
        for part in parts:
            if not part:
                continue
            fields = part.split(",")
            if len(fields) < 6:
                continue
            try:
                date_str = fields[0]  # YYYYMMDD
                ts = int(datetime.strptime(date_str, "%Y%m%d").timestamp())
                out.append({
                    "time": ts,
                    "open": round(float(fields[1]), 4),
                    "high": round(float(fields[2]), 4),
                    "low": round(float(fields[3]), 4),
                    "close": round(float(fields[4]), 4),
                    "volume": round(float(fields[5]), 2),
                })
            except (ValueError, IndexError):
                continue

        # 只返回最后 limit 条
        if limit and len(out) > limit:
            out = out[-limit:]
        return out
    except Exception as e:
        logger.debug(f"同花顺日K线获取失败 {code}: {e}")
        return []


# ---------------------------------------------------------------------------
# 东方财富 (eastmoney) - 分时线
# ---------------------------------------------------------------------------

def _em_secid_from_tencent(code: str) -> str:
    """腾讯代码 -> 东方财富secid (sh600519 -> 1.600519, sz000001 -> 0.000001)"""
    c = (code or "").strip().lower()
    if c.startswith("sh"):
        return f"1.{c[2:]}"
    if c.startswith("sz"):
        return f"0.{c[2:]}"
    if c.isdigit() and len(c) == 6:
        return f"1.{c}" if c.startswith("6") else f"0.{c}"
    return c


def fetch_em_minute_trends(
    code: str,
    ndays: int = 1,
    timeout: int = 0,
) -> List[Dict[str, Any]]:
    """
    从东方财富获取分时线数据（当日分时）

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)
        ndays: 天数 (1=当日, 5=5日)
        timeout: 超时秒数

    Returns:
        分时数据列表 [{time, price, avg_price, volume}, ...]
    """
    if timeout <= 0:
        timeout = _get_timeout(4)

    secid = _em_secid_from_tencent(code)
    url = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "iscr": "0",
        "ndays": str(ndays),
    }
    headers = {
        **get_request_headers(referer="https://quote.eastmoney.com/"),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    try:
        resp = requests.get(url, params=params, timeout=timeout, headers=headers)
        if resp.status_code != 200:
            return []

        data = resp.json()
        if not isinstance(data, dict) or data.get("rc") != 0:
            return []

        trends = (data.get("data") or {}).get("trends") or []
        out: List[Dict[str, Any]] = []
        for t in trends:
            # 格式: 2026-06-18 09:30,1240.00,1240.00,1235.00,100,1235.00,...
            fields = t.split(",")
            if len(fields) < 6:
                continue
            try:
                ts = int(datetime.strptime(fields[0], "%Y-%m-%d %H:%M").timestamp())
                out.append({
                    "time": ts,
                    "price": float(fields[1]),
                    "avg_price": float(fields[2]),
                    "volume": float(fields[4]) if len(fields) > 4 else 0,
                })
            except (ValueError, IndexError):
                continue
        return out
    except Exception as e:
        logger.debug(f"东方财富分时线获取失败 {code}: {e}")
        return []


def em_minute_trends_to_klines(
    trends: List[Dict[str, Any]],
    timeframe: int = 15,
) -> List[Dict[str, Any]]:
    """
    将东方财富分时线数据聚合为K线

    Args:
        trends: fetch_em_minute_trends 返回的分时数据
        timeframe: 聚合周期（分钟）

    Returns:
        K线数据列表
    """
    if not trends:
        return []

    from collections import defaultdict

    bars: Dict[int, Dict[str, Any]] = {}
    for t in trends:
        ts = t["time"]
        price = t["price"]
        vol = t.get("volume", 0)

        dt = datetime.fromtimestamp(ts)
        bar_minute = (dt.minute // timeframe) * timeframe
        bar_ts = int(datetime(dt.year, dt.month, dt.day, dt.hour, bar_minute).timestamp())

        if bar_ts not in bars:
            bars[bar_ts] = {
                "time": bar_ts,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": vol,
            }
        else:
            bar = bars[bar_ts]
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] += vol

    return sorted(bars.values(), key=lambda x: x["time"])


# ---------------------------------------------------------------------------
# 新浪实时行情 (sina hq)
# ---------------------------------------------------------------------------

def fetch_sina_quote(code: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
    """
    从新浪获取实时行情

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)

    Returns:
        行情字典 {last, open, high, low, prev_close, name, symbol}
    """
    if timeout <= 0:
        timeout = _get_timeout(4)

    c = (code or "").strip().lower()
    if not c:
        return None

    url = f"https://hq.sinajs.cn/list={c}"
    headers = {
        **get_request_headers(referer="https://finance.sina.com.cn/"),
        "User-Agent": "Mozilla/5.0",
    }

    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
        if resp.status_code != 200:
            return None

        resp.encoding = "gbk"
        text = resp.text or ""
        # var hq_str_sh600519="贵州茅台,1235.000,1240.000,1215.000,1238.870,..."
        m = re.search(r'="([^"]*)"', text)
        if not m:
            return None

        parts = m.group(1).split(",")
        if len(parts) < 10:
            return None

        # 0:名称, 1:今开, 2:昨收, 3:当前价, 4:最高, 5:最低, ...
        name = parts[0]
        open_price = float(parts[1]) if parts[1] else 0
        prev_close = float(parts[2]) if parts[2] else 0
        last = float(parts[3]) if parts[3] else 0
        high = float(parts[4]) if parts[4] else 0
        low = float(parts[5]) if parts[5] else 0

        change = round(last - prev_close, 4) if prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        return {
            "name": name,
            "symbol": c,
            "last": last,
            "open": open_price,
            "high": high,
            "low": low,
            "previousClose": prev_close,
            "change": change,
            "changePercent": change_pct,
        }
    except Exception as e:
        logger.debug(f"新浪实时行情获取失败 {code}: {e}")
        return None


# ---------------------------------------------------------------------------
# 同花顺实时行情 (10jqka)
# ---------------------------------------------------------------------------

def fetch_ths_quote(code: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
    """
    从同花顺获取实时行情

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)

    Returns:
        行情字典 {last, open, high, low, prev_close, name, symbol}
    """
    if timeout <= 0:
        timeout = _get_timeout(4)

    ths_code = _ths_code_from_tencent(code)
    url = f"https://d.10jqka.com.cn/v6/realhead/{ths_code}/last.js"
    headers = {
        **get_request_headers(referer="https://d.10jqka.com.cn/"),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
        if resp.status_code != 200:
            return None

        # 解析JSONP
        m = re.search(r"quotebridge_v6_realhead_\w+_last\((.*)\)", resp.text)
        if not m:
            return None

        data = json.loads(m.group(1))
        items = data.get("items", {})
        if not items:
            return None

        # 字段映射: 10=最新价, 7=开盘, 8=最高, 9=最低, 4=昨收, 2=名称?
        last = float(items.get("10", 0))
        open_price = float(items.get("7", 0))
        high = float(items.get("8", 0))
        low = float(items.get("9", 0))
        prev_close = float(items.get("4", 0))

        change = round(last - prev_close, 4) if prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        return {
            "name": "",
            "symbol": code,
            "last": last,
            "open": open_price,
            "high": high,
            "low": low,
            "previousClose": prev_close,
            "change": change,
            "changePercent": change_pct,
        }
    except Exception as e:
        logger.debug(f"同花顺实时行情获取失败 {code}: {e}")
        return None
