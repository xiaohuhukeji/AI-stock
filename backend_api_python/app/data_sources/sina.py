"""
新浪财经数据源 (免费，无需API Key)

支持所有时间周期：
- 分钟线: 5m/15m/30m/1H
- 日/周线: 1D/1W

API: https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData
实测速度: 0.4-1.1s (比腾讯财经更快)
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from app.data_sources.rate_limiter import get_request_headers
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _is_sina_enabled() -> bool:
    """检查新浪财经数据源是否启用"""
    v = (os.getenv("SINA_FINANCE_ENABLED", "true") or "true").strip().lower()
    if v in ("false", "0", "no", "off", "disable", "disabled"):
        return False
    return True


def _get_sina_timeout(default: int = 4) -> int:
    """获取新浪财经请求超时时间（默认4秒）"""
    try:
        v = os.getenv("SINA_FINANCE_TIMEOUT")
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


# 时间周期到新浪scale的映射
_TF_TO_SCALE = {
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1H": 60,
    "4H": 240,      # 4小时 = 240分钟
    "1D": 240,      # 日线用240分钟scale
    "1W": 1680,     # 周线 = 7*240 = 1680分钟
}


def fetch_sina_kline(
    code: str,
    timeframe: str,
    limit: int = 300,
    timeout: int = 0,
) -> List[Dict[str, Any]]:
    """
    从新浪财经获取K线数据

    Args:
        code: 腾讯格式代码 (sh600519 / sz000001)
        timeframe: 标准时间周期 (5m/15m/30m/1H/4H/1D/1W)
        limit: 返回条数
        timeout: 超时秒数

    Returns:
        K线数据列表 [{time, open, high, low, close, volume}, ...]
    """
    if not _is_sina_enabled():
        return []

    if timeout <= 0:
        timeout = _get_sina_timeout(4)

    c = (code or "").strip().lower()
    if not c:
        return []

    scale = _TF_TO_SCALE.get(timeframe)
    if scale is None:
        logger.debug(f"新浪财经不支持的时间周期: {timeframe}")
        return []

    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {
        "symbol": c,
        "scale": scale,
        "datalen": int(limit),
    }

    try:
        resp = requests.get(
            url,
            params=params,
            headers=get_request_headers(referer="https://finance.sina.com.cn/"),
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.debug(f"新浪财经HTTP {resp.status_code}")
            return []

        text = (resp.text or "").strip()
        if not text or text == "[]":
            return []

        data = json.loads(text)
        if not isinstance(data, list) or not data:
            return []

        return _parse_sina_klines(data)
    except Exception as e:
        logger.debug(f"新浪财经K线获取失败 {code} {timeframe}: {e}")
        return []


def _parse_sina_klines(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将新浪财经K线数据转换为标准格式"""
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        day_str = r.get("day") or ""
        ts = _parse_sina_time(day_str)
        if ts is None:
            continue
        try:
            out.append({
                "time": ts,
                "open": round(float(r.get("open", 0)), 4),
                "high": round(float(r.get("high", 0)), 4),
                "low": round(float(r.get("low", 0)), 4),
                "close": round(float(r.get("close", 0)), 4),
                "volume": round(float(r.get("volume", 0)), 2),
            })
        except (TypeError, ValueError):
            continue
    return out


def _parse_sina_time(ds: str) -> Optional[int]:
    """解析新浪财经时间字符串为Unix秒"""
    raw = str(ds or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    return None
