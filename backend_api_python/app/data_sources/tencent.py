"""
Tencent market data helpers (no API key).

Provides:
- Quote: https://qt.gtimg.cn/q=sh600519 / sz000001 / hk00700
- Kline: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=CODE,PERIOD,,,COUNT,ADJ

This is used as a stable alternative when Yahoo/yfinance gets rate-limited.

配置项（设置面板 → 数据源）:
- TENCENT_FINANCE_ENABLED: 是否启用（默认 True）
- TENCENT_FINANCE_TIMEOUT: HTTP 超时（秒，默认 8）
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.data_sources.rate_limiter import get_request_headers, retry_with_backoff, get_tencent_limiter
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _is_tencent_enabled() -> bool:
    """检查腾讯财经数据源是否启用（可通过设置面板关闭）"""
    v = (os.getenv("TENCENT_FINANCE_ENABLED", "true") or "true").strip().lower()
    if v in ("false", "0", "no", "off", "disable", "disabled"):
        return False
    return True


def _get_tencent_timeout(default: int = 3) -> int:
    """获取腾讯财经请求超时时间（默认3秒，快速失败）"""
    try:
        v = os.getenv("TENCENT_FINANCE_TIMEOUT")
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


def normalize_cn_code(symbol: str) -> str:
    """
    Normalize A-share symbol to Tencent code: sh600519 / sz000001.
    Accepts:
    - 600519 / 600519.SH / 600519.SS
    - 000001 / 000001.SZ
    - SH600519 / SZ000001
    """
    s = (symbol or "").strip().upper()
    if not s:
        return s

    if s.startswith("SH") and len(s) == 8 and s[2:].isdigit():
        return s

    if s.startswith("SZ") and len(s) == 8 and s[2:].isdigit():
        return s

    if s.endswith(".SH"):
        s = s[:-3]
        return f"SH{s}"
    if s.endswith(".SS"):
        s = s[:-3]
        return f"SH{s}"
    if s.endswith(".SZ"):
        s = s[:-3]
        return f"SZ{s}"

    if s.isdigit() and len(s) == 6:
        return ("SH" + s) if s.startswith("6") else ("SZ" + s)

    return s


def normalize_hk_code(symbol: str) -> str:
    """
    Normalize HK stock symbol to Tencent code: hk00700 (5 digits).
    Accepts:
    - 700 / 0700 / 00700.HK / 0700.HK
    """
    s = (symbol or "").strip().upper()
    if not s:
        return s
    if s.endswith(".HK"):
        s = s[:-3]
    if s.isdigit():
        return "HK" + s.zfill(5)
    # If user already passed HKxxxxx
    if s.startswith("HK") and s[2:].isdigit():
        return "HK" + s[2:].zfill(5)
    return s


def _lower_code(code: str) -> str:
    return (code or "").strip().lower()


@retry_with_backoff(max_attempts=1, base_delay=1.0, max_delay=3.0, exceptions=(Exception,))
def fetch_quote(code: str, timeout: int = 0) -> Optional[List[str]]:
    """
    Returns the raw '~' split array from qt.gtimg.cn, or None.
    快速失败，不重试（通达信作为 Tier 1 会先尝试）
    """
    if not _is_tencent_enabled():
        return None
    if timeout <= 0:
        timeout = _get_tencent_timeout(3)
    c = _lower_code(code)
    if not c:
        return None

    limiter = get_tencent_limiter()
    limiter.wait()
    url = f"https://qt.gtimg.cn/q={c}"
    resp = requests.get(url, headers=get_request_headers(referer="https://qt.gtimg.cn/"), timeout=timeout)
    # Tencent quote is often GBK encoded
    try:
        resp.encoding = "gbk"
    except Exception:
        pass

    text = (resp.text or "").strip()
    if not text or "~" not in text:
        return None

    # Format: v_sh600519="1~NAME~CODE~LAST~PREV~OPEN~..."
    try:
        start = text.index('="') + 2
        end = text.rindex('"')
        payload = text[start:end]
    except Exception:
        return None

    parts = payload.split("~")
    return parts if len(parts) > 5 else None


def parse_quote_to_ticker(parts: List[str]) -> Dict[str, Any]:
    """
    Best-effort conversion to a unified ticker dict.
    """
    def _f(i: int, default: float = 0.0) -> float:
        try:
            v = parts[i]
            if v is None or v == "":
                return default
            return float(v)
        except Exception:
            return default

    name = (parts[1] or "").strip() if len(parts) > 1 else ""
    symbol = (parts[2] or "").strip() if len(parts) > 2 else ""
    last_ = _f(3, 0.0)
    prev = _f(4, 0.0)
    open_ = _f(5, 0.0)

    change = round(last_ - prev, 4) if prev else 0.0
    change_pct = round(change / prev * 100, 2) if prev else 0.0

    # Indices are not fully consistent across markets; keep conservative.
    high = _f(33, last_) if len(parts) > 33 else last_
    low = _f(34, last_) if len(parts) > 34 else last_

    return {
        "symbol": symbol,
        "name": name,
        "last": last_,
        "change": change,
        "changePercent": change_pct,
        "high": high,
        "low": low,
        "open": open_ or last_,
        "previousClose": prev,
        "raw": parts,
    }


def parse_tencent_kline_time(ds: str) -> Optional[int]:
    """Parse Tencent fqkline first column to Unix seconds (local parse, matches prior chart behavior)."""
    raw = str(ds or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    try:
        ts = int(float(raw))
        if ts > 10**12:
            ts = int(ts / 1000)
        return ts
    except Exception:
        return None


def tencent_kline_rows_to_dicts(rows: List[Any]) -> List[Dict[str, Any]]:
    """Convert raw fqkline rows to chart dicts; ignores corporate-action tail objects on HK rows."""
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, (list, tuple)) or len(r) < 6:
            continue
        ts = parse_tencent_kline_time(r[0])
        if ts is None:
            continue
        try:
            o, c, h, low, vol = float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "time": ts,
                "open": round(o, 4),
                "high": round(h, 4),
                "low": round(low, 4),
                "close": round(c, 4),
                "volume": round(vol, 2),
            }
        )
    return out


@retry_with_backoff(max_attempts=1, base_delay=1.0, max_delay=3.0, exceptions=(Exception,))
def fetch_kline(code: str, period: str, count: int = 300, adj: str = "qfq", timeout: int = 0) -> List[List[str]]:
    """
    Fetch kline arrays from Tencent.
    快速失败，不重试（通达信作为 Tier 1 会先尝试）

    period examples:
    - day, week, month (supported by Tencent fqkline)

    Note: Minute periods (m1/m5/…) return **bad params** on this endpoint; use AkShare in ``asia_stock_kline``.
    """
    if not _is_tencent_enabled():
        return []
    if timeout <= 0:
        timeout = _get_tencent_timeout(3)
    c = _lower_code(code)
    if not c:
        return []

    limiter = get_tencent_limiter()
    limiter.wait()

    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{c},{period},,,{int(count)},{adj}"}
    resp = requests.get(url, headers=get_request_headers(referer="https://gu.qq.com/"), params=params, timeout=timeout)
    data = resp.json() if resp.text else {}
    if not isinstance(data, dict) or int(data.get("code", 0)) != 0:
        return []
    root = (data.get("data") or {}).get(c)
    if not isinstance(root, dict):
        return []

    # Data key variants:
    # - A-share: qfqday / qfqweek / qfqm1 ...
    # - HK: day / week / m1 ...
    candidates = []
    if adj:
        candidates.append(f"{adj}{period}")
    candidates.append(period)

    for key in candidates:
        arr = root.get(key)
        if isinstance(arr, list) and arr:
            return arr

    # Fallback: search any key that endswith period and is a list
    for k, v in root.items():
        if isinstance(v, list) and v and str(k).lower().endswith(str(period).lower()):
            return v
    return []


@retry_with_backoff(max_attempts=1, base_delay=1.0, max_delay=3.0, exceptions=(Exception,))
def fetch_minute_data(code: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
    """
    Fetch minute-level data from Tencent (intra-day minute ticks).
    快速失败，不重试（通达信作为 Tier 1 会先尝试）
    
    Returns dict with:
    - name: stock name
    - data: list of ["HHMM price volume amount", ...]
    """
    if not _is_tencent_enabled():
        return None
    if timeout <= 0:
        timeout = _get_tencent_timeout(3)
    c = _lower_code(code)
    if not c:
        return None

    limiter = get_tencent_limiter()
    limiter.wait()
    
    url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={c}"
    resp = requests.get(url, headers=get_request_headers(referer="https://gu.qq.com/"), timeout=timeout)
    data = resp.json() if resp.text else {}
    
    if not isinstance(data, dict) or int(data.get("code", -1)) != 0:
        return None
    
    root = (data.get("data") or {}).get(c)
    if not isinstance(root, dict):
        return None
    
    qfq_data = root.get("data", {})
    if not qfq_data:
        return None
    
    return {
        "name": qfq_data.get("name", ""),
        "data": qfq_data.get("data", [])
    }


def minute_data_to_klines(minute_data: List[str], timeframe: int = 15, trade_date: str = None) -> List[Dict[str, Any]]:
    """
    Convert Tencent minute tick data to K-line format.
    
    Args:
        minute_data: list of "HHMM price volume amount" strings
        timeframe: aggregation period in minutes (default 15)
        trade_date: trading date in YYYYMMDD format (default: today)
    
    Returns:
        List of K-line dicts with time, open, high, low, close, volume
    """
    from datetime import date
    if not minute_data:
        return []
    
    if trade_date is None:
        trade_date = date.today().strftime("%Y%m%d")
    
    ticks = []
    for tick_str in minute_data:
        if not tick_str or ' ' not in tick_str:
            continue
        try:
            parts = tick_str.strip().split(' ')
            if len(parts) >= 3:
                time_str = parts[0]
                price = float(parts[1])
                volume = float(parts[2])
                ticks.append({"time": time_str, "price": price, "volume": volume})
        except (ValueError, IndexError):
            continue
    
    if not ticks:
        return []
    
    klines = []
    current_bar = None
    
    for tick in ticks:
        time_str = tick["time"]
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        bar_minute = (minute // timeframe) * timeframe
        bar_time_key = f"{hour:02d}{bar_minute:02d}"
        
        if current_bar is None or current_bar["time_key"] != bar_time_key:
            if current_bar is not None:
                klines.append({
                    "time": current_bar["timestamp"],
                    "open": current_bar["open"],
                    "high": current_bar["high"],
                    "low": current_bar["low"],
                    "close": current_bar["close"],
                    "volume": current_bar["volume"]
                })
            bar_datetime = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {bar_time_key[:2]}:{bar_time_key[2:]}:00"
            current_bar = {
                "time_key": bar_time_key,
                "timestamp": int(datetime.strptime(bar_datetime, "%Y-%m-%d %H:%M:%S").timestamp()),
                "open": tick["price"],
                "high": tick["price"],
                "low": tick["price"],
                "close": tick["price"],
                "volume": tick["volume"]
            }
        else:
            current_bar["high"] = max(current_bar["high"], tick["price"])
            current_bar["low"] = min(current_bar["low"], tick["price"])
            current_bar["close"] = tick["price"]
            current_bar["volume"] += tick["volume"]
    
    if current_bar is not None:
        klines.append({
            "time": current_bar["timestamp"],
            "open": current_bar["open"],
            "high": current_bar["high"],
            "low": current_bar["low"],
            "close": current_bar["close"],
            "volume": current_bar["volume"]
        })
    
    return klines

