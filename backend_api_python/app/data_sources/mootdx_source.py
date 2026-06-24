"""
通达信数据源 (mootdx)

使用 mootdx 库获取 A 股实时行情和 K 线数据。
免费，国内直连，速度快。

环境变量:
  MOOTDX_ENABLED: 是否启用 (默认 True)
  MOOTDX_SERVER_PREFERENCE: 服务器偏好 (default/fast/slow/cheap/stock)
  MOOTDX_TIMEOUT: 请求超时秒数 (默认 5)
"""

from __future__ import annotations

import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)

# 全局客户端缓存
_std_client = None
_ext_client = None


def _is_enabled() -> bool:
    """检查是否启用通达信数据源"""
    return os.getenv("MOOTDX_ENABLED", "true").lower() in ("true", "1", "yes")


def _get_timeout() -> int:
    """获取请求超时时间"""
    return int(os.getenv("MOOTDX_TIMEOUT", "3"))


def _get_server_preference() -> str:
    """获取服务器偏好"""
    return os.getenv("MOOTDX_SERVER_PREFERENCE", "default").lower()


def _get_server_list() -> List[Tuple[str, int]]:
    """根据用户偏好返回通达信服务器列表"""
    pref = _get_server_preference()
    
    server_groups = {
        "fast": [
            ("115.238.56.198", 7721),
            ("115.238.56.198", 7723),
            ("180.153.18.170", 7721),
            ("123.125.108.14", 7721),
        ],
        "slow": [
            ("115.238.56.198", 7723),
            ("218.6.170.47", 7721),
            ("123.125.108.90", 7721),
        ],
        "cheap": [
            ("115.238.56.198", 7721),
            ("180.153.18.170", 7721),
            ("60.12.136.250", 7721),
        ],
        "stock": [
            ("115.238.56.198", 7721),
            ("218.108.98.244", 7721),
            ("123.125.108.14", 7721),
        ],
        "default": [
            ("115.238.56.198", 7721),
            ("180.153.18.170", 7721),
            ("123.125.108.14", 7721),
        ],
    }
    return server_groups.get(pref, server_groups["default"])


def _get_std_client(force_retry: bool = False):
    """获取标准行情客户端（延迟初始化，支持多服务器重试）"""
    global _std_client
    if _std_client is None or force_retry:
        if not _is_enabled():
            logger.info("通达信数据源已被配置禁用 (MOOTDX_ENABLED=false)")
            return None
        try:
            from mootdx.quotes import Quotes

            servers = _get_server_list()
            for i, server in enumerate(servers):
                try:
                    _std_client = Quotes.factory(market="std", server=server)
                    logger.info(f"通达信标准行情客户端初始化成功，使用服务器: {server}")
                    return _std_client
                except Exception as e:
                    logger.warning(f"通达信服务器 {server} 连接失败 ({i+1}/{len(servers)}): {e}")
                    continue
            
            _std_client = Quotes.factory(market="std")
            logger.info("通达信标准行情客户端初始化成功（自动选择服务器）")
            return _std_client
        except ImportError:
            logger.warning("mootdx库未安装，跳过通达信数据源")
            return None
        except Exception as e:
            logger.error(f"通达信客户端初始化失败: {e}")
            return None
    return _std_client


def _get_ext_client():
    """获取扩展行情客户端（延迟初始化）"""
    global _ext_client
    if _ext_client is None:
        if not _is_enabled():
            return None
        try:
            from mootdx.quotes import Quotes

            servers = _get_server_list()
            if servers and len(servers) > 0:
                _ext_client = Quotes.factory(market="ext", server=servers[0])
            else:
                _ext_client = Quotes.factory(market="ext")
            logger.info("通达信扩展行情客户端初始化成功")
        except ImportError:
            return None
        except Exception as e:
            logger.error(f"通达信扩展客户端初始化失败: {e}")
            return None
    return _ext_client


def _normalize_code(code: str) -> Tuple[str, int]:
    """
    标准化股票代码，返回 (code, market)
    market: 0=深市, 1=沪市
    """
    code = str(code or "").strip().upper()
    
    # 移除前缀
    if '.' in code:
        code = code.split('.')[0]
    if ':' in code:
        code = code.split(':', 1)[-1]
    
    # 移除市场前缀
    if code.startswith(('SH', 'SZ')):
        prefix = code[:2]
        code = code[2:]
        market = 1 if prefix == 'SH' else 0
    elif code.startswith('6'):
        market = 1  # 沪市
    else:
        market = 0  # 深市
    
    return code, market


def fetch_tdx_quote(code: str) -> Optional[Dict[str, Any]]:
    """
    获取实时行情
    
    Args:
        code: 股票代码 (如 603616, sh603616, SZ000001)
    
    Returns:
        行情数据字典或 None
    """
    client = _get_std_client()
    if client is None:
        return None
    
    try:
        symbol, market = _normalize_code(code)
        resp = client.quotes(symbol=[symbol], market=market)
        
        if resp is None or not hasattr(resp, 'data') or resp.data is None:
            return None
        
        data = resp.data
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            last = float(item.get('price', 0) or 0)
            prev_close = float(item.get('last_close', 0) or 0)
            change = last - prev_close if last > 0 and prev_close > 0 else 0
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
            
            return {
                'last': last,
                'open': float(item.get('open', 0) or 0),
                'high': float(item.get('high', 0) or 0),
                'low': float(item.get('low', 0) or 0),
                'volume': float(item.get('volume', 0) or 0),
                'amount': float(item.get('amount', 0) or 0),
                'previousClose': prev_close,
                'change': change,
                'changePercent': change_pct,
                'name': item.get('name', ''),
                'symbol': symbol,
            }
        return None
    except Exception as e:
        logger.debug(f"通达信行情获取失败 {code}: {e}")
        return None


def _timeframe_to_category(timeframe: str) -> int:
    """
    将时间周期转换为通达信 category 参数
    
    0: 5分钟  1: 15分钟  2: 30分钟  3: 1小时
    4: 日线   5: 周线    6: 月线    7: 1分钟
    8: 1分钟  9: 日线    10: 季线   11: 年线
    """
    tf_map = {
        '1m': 8,
        '5m': 0,
        '15m': 1,
        '30m': 2,
        '1h': 3,
        '1d': 4,
        '1w': 5,
        '1M': 6,
    }
    return tf_map.get(timeframe.lower().replace(' ', ''), 4)


def fetch_tdx_bars(code: str, timeframe: str = '1d', limit: int = 100, end: int = None) -> List[Dict[str, Any]]:
    """
    获取 K 线数据
    
    Args:
        code: 股票代码
        timeframe: 时间周期 (1m, 5m, 15m, 30m, 1h, 1d, 1w)
        limit: 数据条数
        end: 结束时间戳 (未使用)
    
    Returns:
        K 线数据列表
    """
    global _std_client
    
    def _do_fetch():
        client = _get_std_client()
        if client is None:
            return []
        
        try:
            symbol, market = _normalize_code(code)
            category = _timeframe_to_category(timeframe)
            
            resp = client.bars(symbol=symbol, market=market, category=category, offset=0, count=limit)
            
            if resp is None or not hasattr(resp, 'data') or resp.data is None:
                return []
            
            data = resp.data
            if not isinstance(data, list):
                return []
            
            result = []
            for item in data:
                try:
                    dt_str = item.get('datetime', '')
                    if dt_str:
                        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                        timestamp = int(dt.timestamp())
                    else:
                        continue
                    
                    result.append({
                        'time': timestamp,
                        'open': float(item.get('open', 0) or 0),
                        'high': float(item.get('high', 0) or 0),
                        'low': float(item.get('low', 0) or 0),
                        'close': float(item.get('close', 0) or 0),
                        'volume': float(item.get('volume', 0) or 0),
                    })
                except (ValueError, KeyError) as e:
                    logger.debug(f"通达信K线数据解析失败: {e}")
                    continue
            
            return result
        except Exception as e:
            logger.debug(f"通达信K线获取失败 {code}: {e}")
            return []
    
    result = _do_fetch()
    if not result:
        logger.debug(f"通达信K线获取失败 {code}，将由后续数据源兜底")
        _std_client = None
    
    return result


def fetch_tdx_minute_bars(code: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取分钟 K 线数据 (兼容旧接口)
    """
    return fetch_tdx_bars(code, timeframe='1m', limit=limit)


def get_cn_stock_quote_tdx(code: str) -> Optional[Dict[str, Any]]:
    """获取 A 股实时行情 (兼容旧接口)"""
    return fetch_tdx_quote(code)


def get_cn_stock_kline_tdx(code: str, timeframe: str = '1d', limit: int = 100) -> List[Dict[str, Any]]:
    """获取 A 股 K 线 (兼容旧接口)"""
    return fetch_tdx_bars(code, timeframe=timeframe, limit=limit)
