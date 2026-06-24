"""
Baostock 数据源 - 免费A股历史K线

支持日/周/月/分钟K线，无需API Key。
实测速度: 3-4s (作为备选数据源)

API: http://baostock.com/baostock/index.php
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

_login_lock = threading.Lock()
_logged_in = False


def _ensure_login() -> bool:
    """确保Baostock已登录（线程安全）"""
    global _logged_in
    with _login_lock:
        if _logged_in:
            return True
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code == '0':
                _logged_in = True
                logger.debug("Baostock登录成功")
                return True
            else:
                logger.debug(f"Baostock登录失败: {lg.error_msg}")
                return False
        except Exception as e:
            logger.debug(f"Baostock登录异常: {e}")
            return False


def _tencent_to_baostock(code: str) -> str:
    """腾讯代码 -> Baostock代码 (sh600519 -> sh.600519)"""
    c = (code or "").strip().lower()
    if c.startswith("sh"):
        return f"sh.{c[2:]}"
    if c.startswith("sz"):
        return f"sz.{c[2:]}"
    if c.isdigit() and len(c) == 6:
        return f"sh.{c}" if c.startswith("6") else f"sz.{c}"
    return c


def _get_timeout(default: int = 8) -> int:
    try:
        v = os.getenv("BAOSTOCK_TIMEOUT")
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


# 时间周期映射
_TF_TO_FREQ = {
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1H": "60",
    "1D": "d",
    "1W": "w",
    "1M": "m",
}


def fetch_baostock_kline(
    code: str,
    timeframe: str,
    limit: int = 300,
    before_time: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    从Baostock获取K线数据

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)
        timeframe: 标准时间周期 (5m/15m/30m/1H/1D/1W/1M)
        limit: 返回条数
        before_time: 截止时间戳

    Returns:
        K线数据列表 [{time, open, high, low, close, volume}, ...]
    """
    freq = _TF_TO_FREQ.get(timeframe)
    if freq is None:
        return []

    if not _ensure_login():
        return []

    bs_code = _tencent_to_baostock(code)
    timeout = _get_timeout(8)

    # 计算日期范围
    end_date = datetime.now().strftime("%Y-%m-%d")
    if before_time:
        end_date = datetime.fromtimestamp(before_time).strftime("%Y-%m-%d")

    # 日/周/月线：取最近1年数据
    if freq in ("d", "w", "m"):
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        fields = "date,open,high,low,close,volume"
    else:
        # 分钟线：取最近7天数据
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        fields = "date,time,open,high,low,close,volume"

    try:
        import baostock as bs

        rs = bs.query_history_k_data_plus(
            bs_code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency=freq,
            adjustflag="2",  # 前复权
        )

        if rs.error_code != '0':
            logger.debug(f"Baostock查询失败: {rs.error_msg}")
            return []

        out: List[Dict[str, Any]] = []
        while (rs.error_code == '0') and rs.next():
            row = rs.get_row_data()
            try:
                if freq in ("d", "w", "m"):
                    # 日/周/月线: [date, open, high, low, close, volume]
                    ts = int(datetime.strptime(row[0], "%Y-%m-%d").timestamp())
                    out.append({
                        "time": ts,
                        "open": round(float(row[1]), 4),
                        "high": round(float(row[2]), 4),
                        "low": round(float(row[3]), 4),
                        "close": round(float(row[4]), 4),
                        "volume": round(float(row[5]), 2) if row[5] else 0,
                    })
                else:
                    # 分钟线: [date, time, open, high, low, close, volume]
                    # time格式: YYYYMMDDHHMMSS000
                    time_str = row[1]
                    dt = datetime.strptime(time_str[:14], "%Y%m%d%H%M%S")
                    ts = int(dt.timestamp())
                    out.append({
                        "time": ts,
                        "open": round(float(row[2]), 4),
                        "high": round(float(row[3]), 4),
                        "low": round(float(row[4]), 4),
                        "close": round(float(row[5]), 4),
                        "volume": round(float(row[6]), 2) if row[6] else 0,
                    })
            except (ValueError, IndexError):
                continue

        # 只返回最后 limit 条
        if limit and len(out) > limit:
            out = out[-limit:]
        return out
    except Exception as e:
        logger.debug(f"Baostock K线获取失败 {code} {timeframe}: {e}")
        return []


# ---------------------------------------------------------------------------
# 东方财富实时行情 (push2.eastmoney.com)
# ---------------------------------------------------------------------------

def fetch_em_quote(code: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
    """
    从东方财富获取实时行情

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)

    Returns:
        行情字典
    """
    import requests

    if timeout <= 0:
        timeout = _get_timeout(4)

    c = (code or "").strip().lower()
    if c.startswith("sh"):
        secid = f"1.{c[2:]}"
    elif c.startswith("sz"):
        secid = f"0.{c[2:]}"
    elif c.isdigit() and len(c) == 6:
        secid = f"1.{c}" if c.startswith("6") else f"0.{c}"
    else:
        return None

    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": secid,
        "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f170",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }

    try:
        resp = requests.get(url, params=params, timeout=timeout, headers=headers)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not isinstance(data, dict) or data.get("rc") != 0:
            return None

        d = data.get("data") or {}
        if not d:
            return None

        # f43=最新价, f44=最高, f45=最低, f46=开盘, f60=昨收, f170=涨跌幅, f58=名称
        # 注意: 东方财富价格字段单位是"分"，需要除以100
        last = float(d.get("f43", 0)) / 100 if d.get("f43") else 0
        high = float(d.get("f44", 0)) / 100 if d.get("f44") else 0
        low = float(d.get("f45", 0)) / 100 if d.get("f45") else 0
        open_price = float(d.get("f46", 0)) / 100 if d.get("f46") else 0
        prev_close = float(d.get("f60", 0)) / 100 if d.get("f60") else 0
        change_pct = float(d.get("f170", 0)) / 100 if d.get("f170") else 0
        name = d.get("f58", "")

        if last <= 0:
            return None

        change = round(last - prev_close, 4) if prev_close else 0

        return {
            "name": name,
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
        logger.debug(f"东方财富实时行情获取失败 {code}: {e}")
        return None


# ---------------------------------------------------------------------------
# 腾讯财经 gu.qq.com 实时行情
# ---------------------------------------------------------------------------

def fetch_tencent_gu_quote(code: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
    """
    从腾讯财经gu.qq.com获取实时行情（备用端点）

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)

    Returns:
        行情字典
    """
    import re
    import requests

    if timeout <= 0:
        timeout = _get_timeout(4)

    c = (code or "").strip().lower()
    if not c:
        return None

    url = f"https://gu.qq.com/{c}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
        if resp.status_code != 200:
            return None

        text = resp.text or ""
        # 从HTML中解析数据
        # 查找 last, open, high, low, prev_close
        def _extract(pattern):
            m = re.search(pattern, text)
            return float(m.group(1)) if m else 0

        last = _extract(r'"last":([\d.]+)')
        open_price = _extract(r'"open":([\d.]+)')
        high = _extract(r'"high":([\d.]+)')
        low = _extract(r'"low":([\d.]+)')
        prev_close = _extract(r'"prevClose":([\d.]+)')

        if last <= 0:
            return None

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
        logger.debug(f"腾讯gu.qq.com实时行情获取失败 {code}: {e}")
        return None
