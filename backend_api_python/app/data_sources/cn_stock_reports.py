"""
A股研报数据源适配器

提供多数据源的研报数据，支持：
1. 东方财富研报 API (reportapi)
2. AkShare 东方财富研报 (stock_research_report_em)

配置项（设置面板 → 数据源）:
- CN_REPORT_ENABLED: 是否启用研报数据源（默认 True）
- CN_REPORT_TIMEOUT: 请求超时时间（秒，默认 10）
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from app.data_sources.rate_limiter import retry_with_backoff
from app.data_sources.cn_hk_fundamentals import _bypass_proxy
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _is_enabled() -> bool:
    v = (os.getenv("CN_REPORT_ENABLED", "true") or "true").strip().lower()
    if v in ("false", "0", "no", "off", "disable", "disabled"):
        return False
    return True


def _get_timeout(default: int = 10) -> int:
    try:
        v = os.getenv("CN_REPORT_TIMEOUT")
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


# ==================== 东方财富研报 API ====================


@retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=5.0, exceptions=(Exception,))
def fetch_eastmoney_reports(
    symbol: str,
    limit: int = 20,
    report_type: str = "all",
) -> List[Dict[str, Any]]:
    if not _is_enabled():
        return []

    code = symbol.lower().replace(".sh", "").replace(".sz", "").zfill(6)
    market = "SH" if code.startswith("6") else "SZ"

    try:
        with _bypass_proxy():
            url = "https://reportapi.eastmoney.com/report/jg"
            params = {
                "cb": "datatable5706290",
                "pageSize": limit,
                "pageNo": 1,
                "secid": f"{1 if market == 'SH' else 0}.{code}",
                "fields": "SECODE,SEC_NAME,ORG_CODE,ORG_NAME,REPORT_DATE,TITLE,INDUSTRY,ENCODE,REPORT_TYPE",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Referer": "https://data.eastmoney.com/report/",
                "Origin": "https://data.eastmoney.com",
            }

            resp = requests.get(url, params=params, headers=headers, timeout=_get_timeout(10))

            text = resp.text
            match = re.search(r"datatable5706290\((.*?)\);", text)
            if not match:
                return []

            import json

            data = json.loads(match.group(1))
            result = []

            for item in (data.get("data") or []):
                result.append(
                    {
                        "source": "eastmoney",
                        "title": item.get("TITLE", ""),
                        "symbol": code,
                        "stock_name": item.get("SEC_NAME", ""),
                        "institute": item.get("ORG_NAME", ""),
                        "institute_code": item.get("ORG_CODE", ""),
                        "report_date": item.get("REPORT_DATE", ""),
                        "industry": item.get("INDUSTRY", ""),
                        "report_type": item.get("REPORT_TYPE", ""),
                        "url": f"https://data.eastmoney.com/report/{item.get('ENCODE', '')}.html"
                        if item.get("ENCODE")
                        else "",
                    }
                )

            logger.debug(f"Eastmoney reports for {code}: {len(result)} items")
            return result

    except Exception as e:
        logger.warning(f"Eastmoney reports fetch failed for {code}: {e}")
        return []


# ==================== AkShare 东方财富研报 ====================


@retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=5.0, exceptions=(Exception,))
def fetch_akshare_reports(symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
    if not _is_enabled():
        return []

    code = symbol.lower().replace(".sh", "").replace(".sz", "").zfill(6)

    try:
        import akshare as ak  # type: ignore

        with _bypass_proxy():
            df = ak.stock_research_report_em(symbol=code)

        if df is None or df.empty:
            return []

        result = []
        for _, row in df.head(limit).iterrows():
            cols = df.columns.tolist()
            result.append(
                {
                    "source": "akshare",
                    "title": str(row[cols[3]]),
                    "symbol": str(row[cols[1]]).zfill(6),
                    "stock_name": str(row[cols[2]]),
                    "institute": str(row[cols[5]]),
                    "rating": str(row[cols[4]]),
                    "report_date": str(row[cols[14]]),
                    "industry": str(row[cols[13]]),
                    "url": str(row[cols[15]]),
                }
            )

        logger.debug(f"AkShare reports for {code}: {len(result)} items")
        return result

    except ImportError:
        logger.debug("akshare not installed, reports unavailable")
        return []
    except Exception as e:
        logger.warning(f"AkShare reports fetch failed for {code}: {e}")
        return []


# ==================== 综合研报接口 ====================


def fetch_cn_stock_reports(
    symbol: str,
    limit: int = 20,
    report_type: str = "all",
) -> List[Dict[str, Any]]:
    code = symbol.lower().replace(".sh", "").replace(".sz", "").zfill(6)

    reports: List[Dict[str, Any]] = []

    em_reports = fetch_eastmoney_reports(code, limit=limit, report_type=report_type)
    reports.extend(em_reports)

    if len(reports) < limit:
        ak_reports = fetch_akshare_reports(code, limit=limit - len(reports))
        reports.extend(ak_reports)

    seen_titles = set()
    unique_reports = []
    for r in reports:
        title = r.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_reports.append(r)

    unique_reports.sort(
        key=lambda x: x.get("report_date", ""),
        reverse=True,
    )

    return unique_reports[:limit]


def fetch_cn_stock_recent_reports(
    symbol: str,
    days: int = 7,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    reports = fetch_cn_stock_reports(symbol, limit=limit * 2)

    if not reports:
        return []

    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    recent_reports = [
        r
        for r in reports
        if r.get("report_date", "") >= cutoff_date
    ]

    return recent_reports[:limit]


# ==================== 行业研报 ====================


@retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=5.0, exceptions=(Exception,))
def fetch_eastmoney_industry_reports(
    industry: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    if not _is_enabled():
        return []

    try:
        with _bypass_proxy():
            url = "https://reportapi.eastmoney.com/report/zybg"
            params = {
                "cb": "datatable5706290",
                "pageSize": limit,
                "pageNo": 1,
                "industry": industry,
                "fields": "SECODE,SEC_NAME,ORG_CODE,ORG_NAME,REPORT_DATE,TITLE,INDUSTRY,ENCODE",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Referer": "https://data.eastmoney.com/report/",
                "Origin": "https://data.eastmoney.com",
            }

            resp = requests.get(url, params=params, headers=headers, timeout=_get_timeout(10))

            text = resp.text
            match = re.search(r"datatable5706290\((.*?)\);", text)
            if not match:
                return []

            import json

            data = json.loads(match.group(1))
            result = []

            for item in (data.get("data") or []):
                result.append(
                    {
                        "source": "eastmoney_industry",
                        "title": item.get("TITLE", ""),
                        "symbol": str(item.get("SECODE", "")).zfill(6),
                        "stock_name": item.get("SEC_NAME", ""),
                        "institute": item.get("ORG_NAME", ""),
                        "institute_code": item.get("ORG_CODE", ""),
                        "report_date": item.get("REPORT_DATE", ""),
                        "industry": item.get("INDUSTRY", ""),
                        "url": f"https://data.eastmoney.com/report/{item.get('ENCODE', '')}.html"
                        if item.get("ENCODE")
                        else "",
                    }
                )

            logger.debug(f"Eastmoney industry reports for '{industry}': {len(result)} items")
            return result

    except Exception as e:
        logger.warning(f"Eastmoney industry reports fetch failed for '{industry}': {e}")
        return []
