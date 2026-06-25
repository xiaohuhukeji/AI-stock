"""
A-share stock screener service.
Combines fundamental and technical filters to screen A-share stocks.
"""

from __future__ import annotations

import time
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.utils.logger import get_logger
from app.data_sources.cn_stock import CNStockDataSource
from app.data_sources.cn_hk_fundamentals import (
    fetch_cn_fundamental_akshare,
    fetch_cn_financial_indicators,
)

logger = get_logger(__name__)

UNIVERSE_PRESETS = {
    'hs300': [
        '600519', '000858', '300750', '601318', '000333',
        '600036', '002594', '601899', '000651', '600276',
        '601398', '600028', '601288', '600030', '600887',
        '000001', '000002', '600000', '600050', '600104',
    ],
    'sz50': [
        '600519', '601318', '600036', '601398', '600028',
        '601288', '600030', '600050', '600104', '601088',
        '601628', '600031', '600690', '600276', '600887',
        '601166', '601328', '600000', '600048', '600340',
    ],
    'zz500': [
        '002415', '300059', '002475', '300124', '002352',
        '002008', '300142', '002714', '300015', '002304',
        '300347', '000661', '002027', '300433', '002602',
        '002032', '300017', '002129', '300033', '000100',
    ],
    'cyb': [
        '300750', '300059', '300124', '300142', '300347',
        '300015', '300433', '300017', '300033', '300031',
        '300136', '300274', '300450', '300408', '300144',
        '300058', '300188', '300296', '300413', '300014',
    ],
}

SECTOR_MAP = {
    '银行': ['601398', '601288', '600036', '600000', '000001', '601166', '601328', '600015', '601818', '600030'],
    '保险': ['601318', '601628', '601336', '601601', '601601'],
    '证券': ['600030', '601211', '600837', '000776', '600999', '601688', '600109'],
    '白酒': ['600519', '000858', '000568', '600809', '002304', '600779', '600559'],
    '医药': ['600276', '300347', '300142', '000661', '600196', '600436', '002007', '300003'],
    '新能源': ['300750', '002594', '601012', '300274', '002129', '600438', '002459'],
    '半导体': ['688981', '002371', '300661', '002049', '603501', '688012', '300782'],
    '人工智能': ['002415', '300033', '002230', '600570', '300496', '688111', '000977'],
    '房地产': ['000002', '600048', '001979', '600340', '000671', '601155'],
    '基建': ['601668', '601390', '601186', '600585', '600019', '600528'],
    '消费': ['600887', '000333', '000651', '600690', '002032', '002241'],
    '家电': ['000333', '000651', '600690', '002032', '002241', '000100'],
    '汽车': ['002594', '600104', '601633', '000625', '600006', '000550'],
    '有色金属': ['601899', '600489', '600547', '000831', '000630', '600362'],
    '煤炭': ['601088', '601898', '600188', '600123', '600395', '600508'],
    '石油': ['600028', '601857', '601808', '600688', '000554'],
}


class CNStockScreenerService:
    """A股选股服务"""

    def __init__(self):
        self.cn_stock_ds = CNStockDataSource()
        self._quote_cache = {}
        self._cache_ttl = 60  # seconds

    def _get_universe_stocks(self, universe_type: str, custom_codes: Optional[List[str]] = None) -> List[str]:
        """获取股票池代码列表"""
        if universe_type == 'custom' and custom_codes:
            return custom_codes
        return UNIVERSE_PRESETS.get(universe_type, UNIVERSE_PRESETS['hs300'])

    def _filter_by_sector(self, stocks: List[str], sectors: List[str]) -> List[str]:
        """按行业板块过滤"""
        if not sectors:
            return stocks
        sector_codes = set()
        for sector in sectors:
            sector_codes.update(SECTOR_MAP.get(sector, []))
        return [s for s in stocks if s in sector_codes]

    def _get_quote_cached(self, code: str) -> Optional[Dict[str, Any]]:
        """获取行情（带缓存）"""
        now = time.time()
        cached = self._quote_cache.get(code)
        if cached and now - cached['ts'] < self._cache_ttl:
            return cached['data']
        try:
            quote = self.cn_stock_ds.get_ticker(code)
            self._quote_cache[code] = {'ts': now, 'data': quote}
            return quote
        except Exception as e:
            logger.debug(f"Failed to get quote for {code}: {e}")
            return None

    def _get_fundamentals_cached(self, code: str) -> Optional[Dict[str, Any]]:
        """获取基本面数据（带缓存）"""
        try:
            # 获取基础基本面数据
            basic = fetch_cn_fundamental_akshare(code) or {}
            # 获取财务指标
            financial = fetch_cn_financial_indicators(code) or {}

            result = {
                'pe_ratio': basic.get('pe_ratio') or basic.get('pe'),
                'pb_ratio': basic.get('pb_ratio') or basic.get('pb'),
                'roe': basic.get('roe') or financial.get('roe'),
                'market_cap': basic.get('market_cap'),
                'revenue': financial.get('revenue'),
                'net_income': financial.get('net_income'),
                'revenue_growth': financial.get('revenue_growth'),
                'net_income_growth': financial.get('net_income_growth'),
            }
            return result
        except Exception as e:
            logger.debug(f"Failed to get fundamentals for {code}: {e}")
            return None

    def _calculate_score(self, stock_data: Dict[str, Any]) -> int:
        """计算综合评分"""
        score = 50  # 基础分

        pe = stock_data.get('pe')
        pb = stock_data.get('pb')
        roe = stock_data.get('roe')
        change = stock_data.get('change', 0)
        revenue_growth = stock_data.get('revenue_growth')

        # PE 评分 (越低越好，但不能为负)
        if pe and pe > 0:
            if pe < 10:
                score += 15
            elif pe < 20:
                score += 10
            elif pe < 30:
                score += 5
            elif pe > 50:
                score -= 10

        # PB 评分
        if pb and pb > 0:
            if pb < 1.5:
                score += 10
            elif pb < 3:
                score += 5
            elif pb > 8:
                score -= 5

        # ROE 评分
        if roe:
            if roe > 20:
                score += 15
            elif roe > 15:
                score += 10
            elif roe > 10:
                score += 5
            elif roe < 5:
                score -= 5

        # 营收增长评分
        if revenue_growth:
            if revenue_growth > 30:
                score += 10
            elif revenue_growth > 20:
                score += 7
            elif revenue_growth > 10:
                score += 4
            elif revenue_growth < 0:
                score -= 5

        # 涨跌幅评分
        if change > 0:
            score += min(int(change), 5)
        else:
            score += max(int(change), -5)

        return max(0, min(100, score))

    def screen_stocks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行选股

        Args:
            params: 选股参数
                - universe: 股票池类型 (hs300, sz50, zz500, cyb, custom)
                - custom_codes: 自定义股票代码列表
                - pe_min/max: PE范围
                - pb_min/max: PB范围
                - roe_min: ROE最小值
                - revenue_growth_min: 营收增长率最小值
                - above_ma20/60: 均线过滤
                - volume_surged: 放量上涨
                - change_min: 涨跌幅最小值
                - sectors: 行业板块列表

        Returns:
            选股结果
        """
        universe_type = params.get('universe', 'hs300')
        sectors = params.get('sectors', [])

        # 1. 获取股票池
        stocks = self._get_universe_stocks(universe_type, params.get('custom_codes'))

        # 2. 按行业过滤
        stocks = self._filter_by_sector(stocks, sectors)

        # 3. 并行获取行情数据
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_code = {
                executor.submit(self._get_quote_cached, code): code
                for code in stocks
            }
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    quote = future.result()
                    if not quote:
                        continue

                    stock_data = {
                        'symbol': code,
                        'name': quote.get('name', code),
                        'price': quote.get('last', 0),
                        'change': quote.get('changePercent', 0),
                        'volume': self._format_volume(quote.get('volume', 0)),
                        'pe': 0,
                        'pb': 0,
                        'roe': 0,
                        'revenue_growth': 0,
                        'sector': self._guess_sector(code),
                    }

                    # 4. 基本面过滤
                    fundamentals = self._get_fundamentals_cached(code)
                    if fundamentals:
                        stock_data['pe'] = fundamentals.get('pe_ratio') or 0
                        stock_data['pb'] = fundamentals.get('pb_ratio') or 0
                        stock_data['roe'] = fundamentals.get('roe') or 0
                        stock_data['market_cap'] = fundamentals.get('market_cap')
                        stock_data['revenue'] = fundamentals.get('revenue')
                        stock_data['net_profit'] = fundamentals.get('net_income')
                        stock_data['revenue_growth'] = fundamentals.get('revenue_growth') or 0
                        stock_data['profit_growth'] = fundamentals.get('net_income_growth') or 0

                    # 应用过滤条件
                    if not self._pass_filters(stock_data, params):
                        continue

                    # 计算评分
                    stock_data['score'] = self._calculate_score(stock_data)

                    results.append(stock_data)

                except Exception as e:
                    logger.debug(f"Error processing {code}: {e}")
                    continue

        # 按评分排序
        results.sort(key=lambda x: x.get('score', 0), reverse=True)

        return {
            'total': len(results),
            'universe': universe_type,
            'stocks': results
        }

    def _pass_filters(self, stock: Dict[str, Any], params: Dict[str, Any]) -> bool:
        """检查是否通过过滤条件"""
        pe = stock.get('pe', 0)
        pb = stock.get('pb', 0)
        roe = stock.get('roe', 0)
        change = stock.get('change', 0)
        revenue_growth = stock.get('revenue_growth', 0)

        # PE 过滤
        if params.get('pe_min') is not None and pe and pe < params['pe_min']:
            return False
        if params.get('pe_max') is not None and pe and pe > params['pe_max']:
            return False

        # PB 过滤
        if params.get('pb_min') is not None and pb and pb < params['pb_min']:
            return False
        if params.get('pb_max') is not None and pb and pb > params['pb_max']:
            return False

        # ROE 过滤
        if params.get('roe_min') is not None and roe and roe < params['roe_min']:
            return False

        # 营收增长过滤
        if params.get('revenue_growth_min') is not None and revenue_growth and revenue_growth < params['revenue_growth_min']:
            return False

        # 涨跌幅过滤
        if params.get('change_min') is not None and change < params['change_min']:
            return False

        return True

    def _format_volume(self, volume: float) -> str:
        """格式化成交量"""
        if volume >= 100000000:
            return f"{volume / 100000000:.1f}亿"
        elif volume >= 10000:
            return f"{volume / 10000:.1f}万"
        return str(volume)

    def _guess_sector(self, code: str) -> str:
        """根据股票代码猜测行业"""
        for sector, codes in SECTOR_MAP.items():
            if code in codes:
                return sector
        return '其他'


_screener_service: Optional[CNStockScreenerService] = None


def get_stock_screener_service() -> CNStockScreenerService:
    """获取选股服务单例"""
    global _screener_service
    if _screener_service is None:
        _screener_service = CNStockScreenerService()
    return _screener_service
