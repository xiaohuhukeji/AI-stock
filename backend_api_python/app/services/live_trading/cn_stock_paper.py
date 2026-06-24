"""
A股模拟交易客户端 (CNStock Paper Trading Client)

提供A股市场的模拟交易功能，支持：
- 模拟买入/卖出
- 模拟持仓管理
- 模拟资金管理
- 交易记录持久化

使用场景：
- 策略测试验证
- 模拟盘交易
- 学习和演示
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from app.services.live_trading.base import BaseRestClient, LiveOrderResult, LiveTradingError

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    """模拟持仓"""
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    current_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def profit_loss(self) -> float:
        return (self.current_price - self.avg_price) * self.quantity
    
    @property
    def profit_loss_pct(self) -> float:
        if self.avg_price <= 0:
            return 0.0
        return (self.current_price - self.avg_price) / self.avg_price * 100


@dataclass
class PaperOrder:
    """模拟订单"""
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    status: str = 'filled'  # 模拟交易直接成交
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    commission: float = 0.0
    timestamp: str = ''
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.filled_quantity == 0.0:
            self.filled_quantity = self.quantity
        if self.filled_price == 0.0:
            self.filled_price = self.price


@dataclass
class PaperAccount:
    """模拟账户"""
    cash: float = 100000.0  # 初始资金10万
    initial_cash: float = 100000.0
    positions: Dict[str, PaperPosition] = field(default_factory=dict)
    orders: List[PaperOrder] = field(default_factory=list)
    total_commission: float = 0.0
    
    @property
    def total_assets(self) -> float:
        """总资产 = 现金 + 持仓市值"""
        position_value = sum(p.market_value for p in self.positions.values())
        return self.cash + position_value
    
    @property
    def total_profit_loss(self) -> float:
        """总盈亏"""
        return self.total_assets - self.initial_cash
    
    @property
    def total_profit_loss_pct(self) -> float:
        """总收益率"""
        if self.initial_cash <= 0:
            return 0.0
        return (self.total_assets - self.initial_cash) / self.initial_cash * 100


class CNStockPaperClient(BaseRestClient):
    """
    A股模拟交易客户端
    
    特点：
    1. 纯内存模拟，不需要真实交易所连接
    2. 支持买入、卖出、查询持仓、查询余额
    3. 自动计算手续费（默认万分之三）
    4. 支持T+1规则（可选）
    5. 支持涨跌停限制（可选）
    """
    
    # A股交易手续费率（默认万分之三）
    DEFAULT_COMMISSION_RATE = 0.0003
    # 印花税率（卖出时收取，千分之一）
    STAMP_DUTY_RATE = 0.001
    # 最低手续费
    MIN_COMMISSION = 5.0
    
    # 涨跌停幅度
    PRICE_LIMIT_PCT = 0.10  # 10%涨跌停（主板）
    PRICE_LIMIT_ST_PCT = 0.05  # 5%涨跌停（ST股）
    PRICE_LIMIT_GEM_PCT = 0.20  # 20%涨跌停（创业板/科创板）
    
    def __init__(
        self,
        *,
        initial_cash: float = 100000.0,
        commission_rate: float = None,
        enable_t1: bool = True,
        enable_price_limit: bool = True,
        account_id: str = "default",
        persist_dir: str = None,
        **kwargs
    ):
        """
        初始化A股模拟交易客户端
        
        Args:
            initial_cash: 初始资金
            commission_rate: 手续费率，默认万分之三
            enable_t1: 是否启用T+1规则
            enable_price_limit: 是否启用涨跌停限制
            account_id: 账户ID
            persist_dir: 持久化目录，如果设置则账户状态会保存到文件
        """
        super().__init__(base_url="paper://cnstock", timeout_sec=5.0)
        
        self.account_id = account_id
        self.commission_rate = commission_rate or self.DEFAULT_COMMISSION_RATE
        self.enable_t1 = enable_t1
        self.enable_price_limit = enable_price_limit
        self.persist_dir = persist_dir
        
        # 账户状态
        self._account = PaperAccount(cash=initial_cash, initial_cash=initial_cash)
        self._lock = Lock()
        
        # 订单ID计数器
        self._order_id_counter = 0
        
        # 当日买入的股票（用于T+1检查）
        self._today_buys: Dict[str, float] = {}
        
        # 最后一次交易日期（用于T+1自动重置）
        self._last_date = datetime.now().date()
        
        # 持久化
        if persist_dir:
            self._load_state()
    
    def _generate_order_id(self) -> str:
        """生成订单ID"""
        self._order_id_counter += 1
        return f"CN{int(time.time() * 1000)}{self._order_id_counter:06d}"
    
    def _check_date_reset(self):
        """检查日期变化并自动重置当日买入记录"""
        today = datetime.now().date()
        if today > self._last_date:
            self._today_buys.clear()
            self._last_date = today
            logger.info(f"[CNStock Paper] Date changed from {self._last_date} to {today}, cleared today's buy records")
    
    def _calculate_commission(self, amount: float, is_sell: bool = False) -> float:
        """
        计算手续费
        
        Args:
            amount: 成交金额
            is_sell: 是否为卖出（卖出需加印花税）
        
        Returns:
            总手续费
        """
        # 佣金
        commission = amount * self.commission_rate
        commission = max(commission, self.MIN_COMMISSION)
        
        # 印花税（仅卖出）
        if is_sell:
            commission += amount * self.STAMP_DUTY_RATE
        
        return round(commission, 2)
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        symbol = str(symbol or "").strip().upper()
        if '.' in symbol:
            symbol = symbol.split('.')[0]
        if ':' in symbol:
            symbol = symbol.split(':', 1)[-1]
        if symbol.isdigit() and len(symbol) == 6:
            return symbol
        return symbol
    
    def _is_gem_or_star(self, symbol: str) -> bool:
        """判断是否为创业板或科创板"""
        symbol = self._normalize_symbol(symbol)
        # 创业板: 300xxx, 301xxx
        # 科创板: 688xxx, 689xxx
        return symbol.startswith(('300', '301', '688', '689'))
    
    def _is_st(self, symbol: str) -> bool:
        """判断是否为ST股票（简化判断）"""
        # 实际应用中应该从数据源获取
        return False
    
    def _get_price_limit_pct(self, symbol: str) -> float:
        """获取涨跌停幅度"""
        if self._is_st(symbol):
            return self.PRICE_LIMIT_ST_PCT
        if self._is_gem_or_star(symbol):
            return self.PRICE_LIMIT_GEM_PCT
        return self.PRICE_LIMIT_PCT
    
    def _save_state(self):
        """保存账户状态"""
        if not self.persist_dir:
            return
        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            state_file = os.path.join(self.persist_dir, f"cnstock_paper_{self.account_id}.json")
            
            state = {
                'cash': self._account.cash,
                'initial_cash': self._account.initial_cash,
                'total_commission': self._account.total_commission,
                'positions': {
                    sym: {
                        'quantity': pos.quantity,
                        'avg_price': pos.avg_price,
                        'current_price': pos.current_price
                    }
                    for sym, pos in self._account.positions.items()
                },
                'today_buys': self._today_buys,
                'last_date': self._last_date.isoformat(),
                'order_id_counter': self._order_id_counter,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save paper account state: {e}")
    
    def _load_state(self):
        """加载账户状态"""
        if not self.persist_dir:
            return
        try:
            state_file = os.path.join(self.persist_dir, f"cnstock_paper_{self.account_id}.json")
            if not os.path.exists(state_file):
                return
            
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            self._account.cash = state.get('cash', self._account.initial_cash)
            self._account.initial_cash = state.get('initial_cash', self._account.initial_cash)
            self._account.total_commission = state.get('total_commission', 0.0)
            
            for sym, pos_data in (state.get('positions') or {}).items():
                self._account.positions[sym] = PaperPosition(
                    symbol=sym,
                    quantity=pos_data.get('quantity', 0),
                    avg_price=pos_data.get('avg_price', 0),
                    current_price=pos_data.get('current_price', 0)
                )
            
            self._today_buys = state.get('today_buys', {})
            last_date_str = state.get('last_date')
            if last_date_str:
                self._last_date = datetime.fromisoformat(last_date_str).date()
            self._order_id_counter = state.get('order_id_counter', 0)
            
            logger.info(f"Loaded paper account state: cash={self._account.cash}, positions={len(self._account.positions)}")
        except Exception as e:
            logger.warning(f"Failed to load paper account state: {e}")
    
    # ==================== 交易接口 ====================
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = None,
        order_type: str = "market"
    ) -> LiveOrderResult:
        """
        下单
        
        Args:
            symbol: 股票代码
            side: 'buy' 或 'sell'
            quantity: 数量（股）
            price: 价格（限价单需要）
            order_type: 'market' 或 'limit'
        
        Returns:
            LiveOrderResult
        """
        symbol = self._normalize_symbol(symbol)
        side = str(side or "").strip().lower()
        quantity = float(quantity or 0)
        price = float(price or 0)
        
        if side not in ('buy', 'sell'):
            raise LiveTradingError(f"Invalid side: {side}, must be 'buy' or 'sell'")
        
        if quantity <= 0:
            raise LiveTradingError(f"Invalid quantity: {quantity}")
        
        if quantity != int(quantity):
            raise LiveTradingError(f"A股数量必须为整数，当前: {quantity}")
        
        quantity = int(quantity)
        
        # A股最小交易单位为100股（1手）
        if quantity < 100:
            raise LiveTradingError(f"A股最小交易单位为100股，当前: {quantity}")
        
        if quantity % 100 != 0:
            raise LiveTradingError(f"A股交易数量必须是100的整数倍，当前: {quantity}")
        
        with self._lock:
            # 检查日期变化，自动重置当日买入记录（T+1规则）
            self._check_date_reset()
            
            order_id = self._generate_order_id()
            
            # 执行交易
            if side == 'buy':
                result = self._execute_buy(symbol, quantity, price, order_id)
            else:
                result = self._execute_sell(symbol, quantity, price, order_id)
            
            # 保存状态
            self._save_state()
            
            return result
    
    def _execute_buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        order_id: str
    ) -> LiveOrderResult:
        """执行买入"""
        # 计算所需资金
        amount = quantity * price
        commission = self._calculate_commission(amount, is_sell=False)
        total_cost = amount + commission
        
        # 检查资金是否充足
        if self._account.cash < total_cost:
            raise LiveTradingError(
                f"资金不足: 需要 {total_cost:.2f} 元，可用 {self._account.cash:.2f} 元"
            )
        
        # 扣除资金
        self._account.cash -= total_cost
        self._account.total_commission += commission
        
        # 更新持仓
        if symbol in self._account.positions:
            pos = self._account.positions[symbol]
            total_quantity = pos.quantity + quantity
            total_cost_basis = pos.avg_price * pos.quantity + price * quantity
            pos.quantity = total_quantity
            pos.avg_price = total_cost_basis / total_quantity
            pos.current_price = price
        else:
            self._account.positions[symbol] = PaperPosition(
                symbol=symbol,
                quantity=quantity,
                avg_price=price,
                current_price=price
            )
        
        # 记录当日买入（用于T+1检查）
        if symbol not in self._today_buys:
            self._today_buys[symbol] = 0
        self._today_buys[symbol] += quantity
        
        # 记录订单
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            side='buy',
            quantity=quantity,
            price=price,
            filled_quantity=quantity,
            filled_price=price,
            commission=commission
        )
        self._account.orders.append(order)
        
        logger.info(
            f"[CNStock Paper] BUY {symbol} {quantity}股 @ {price:.2f} "
            f"成交额 {amount:.2f} 手续费 {commission:.2f}"
        )
        
        return LiveOrderResult(
            exchange_id="cnstock_paper",
            exchange_order_id=order_id,
            filled=float(quantity),
            avg_price=price,
            raw={
                'symbol': symbol,
                'side': 'buy',
                'quantity': quantity,
                'price': price,
                'amount': amount,
                'commission': commission,
                'timestamp': order.timestamp
            }
        )
    
    def _execute_sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        order_id: str
    ) -> LiveOrderResult:
        """执行卖出"""
        # 检查持仓
        if symbol not in self._account.positions:
            raise LiveTradingError(f"没有 {symbol} 的持仓")
        
        pos = self._account.positions[symbol]
        
        # T+1检查
        if self.enable_t1 and symbol in self._today_buys:
            available = pos.quantity - self._today_buys[symbol]
            if quantity > available:
                raise LiveTradingError(
                    f"T+1限制: {symbol} 当日买入的股票不能当日卖出，"
                    f"可卖 {available} 股，请求卖出 {quantity} 股"
                )
        
        # 检查持仓数量
        if pos.quantity < quantity:
            raise LiveTradingError(
                f"持仓不足: {symbol} 持有 {pos.quantity} 股，请求卖出 {quantity} 股"
            )
        
        # 计算收入
        amount = quantity * price
        commission = self._calculate_commission(amount, is_sell=True)
        net_income = amount - commission
        
        # 增加资金
        self._account.cash += net_income
        self._account.total_commission += commission
        
        # 更新持仓
        pos.quantity -= quantity
        pos.current_price = price
        if pos.quantity <= 0:
            del self._account.positions[symbol]
        
        # 记录订单
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            side='sell',
            quantity=quantity,
            price=price,
            filled_quantity=quantity,
            filled_price=price,
            commission=commission
        )
        self._account.orders.append(order)
        
        logger.info(
            f"[CNStock Paper] SELL {symbol} {quantity}股 @ {price:.2f} "
            f"成交额 {amount:.2f} 手续费 {commission:.2f}"
        )
        
        return LiveOrderResult(
            exchange_id="cnstock_paper",
            exchange_order_id=order_id,
            filled=float(quantity),
            avg_price=price,
            raw={
                'symbol': symbol,
                'side': 'sell',
                'quantity': quantity,
                'price': price,
                'amount': amount,
                'commission': commission,
                'timestamp': order.timestamp
            }
        )
    
    # ==================== 查询接口 ====================
    
    def get_balance(self) -> Dict[str, Any]:
        """
        查询账户余额
        
        Returns:
            {
                'cash': 可用资金,
                'total_assets': 总资产,
                'profit_loss': 总盈亏,
                'profit_loss_pct': 收益率,
                'total_commission': 总手续费
            }
        """
        with self._lock:
            return {
                'cash': round(self._account.cash, 2),
                'total_assets': round(self._account.total_assets, 2),
                'profit_loss': round(self._account.total_profit_loss, 2),
                'profit_loss_pct': round(self._account.total_profit_loss_pct, 2),
                'total_commission': round(self._account.total_commission, 2),
                'initial_cash': round(self._account.initial_cash, 2)
            }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        查询持仓
        
        Returns:
            [{
                'symbol': 股票代码,
                'quantity': 持仓数量,
                'avg_price': 成本价,
                'current_price': 当前价,
                'market_value': 市值,
                'profit_loss': 盈亏,
                'profit_loss_pct': 盈亏比例
            }]
        """
        with self._lock:
            return [
                {
                    'symbol': sym,
                    'quantity': pos.quantity,
                    'avg_price': round(pos.avg_price, 3),
                    'current_price': round(pos.current_price, 3),
                    'market_value': round(pos.market_value, 2),
                    'profit_loss': round(pos.profit_loss, 2),
                    'profit_loss_pct': round(pos.profit_loss_pct, 2)
                }
                for sym, pos in self._account.positions.items()
            ]
    
    def get_orders(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        查询订单历史
        
        Args:
            limit: 返回数量限制
        
        Returns:
            [{
                'order_id': 订单ID,
                'symbol': 股票代码,
                'side': 买卖方向,
                'quantity': 数量,
                'price': 价格,
                'filled_quantity': 成交数量,
                'filled_price': 成交价格,
                'commission': 手续费,
                'timestamp': 时间
            }]
        """
        with self._lock:
            orders = self._account.orders[-limit:] if limit else self._account.orders
            return [
                {
                    'order_id': o.order_id,
                    'symbol': o.symbol,
                    'side': o.side,
                    'quantity': o.quantity,
                    'price': round(o.price, 3),
                    'filled_quantity': o.filled_quantity,
                    'filled_price': round(o.filled_price, 3),
                    'commission': round(o.commission, 2),
                    'timestamp': o.timestamp
                }
                for o in orders
            ]
    
    def update_position_prices(self, prices: Dict[str, float]):
        """
        更新持仓价格（用于计算市值和盈亏）
        
        Args:
            prices: {股票代码: 当前价格}
        """
        with self._lock:
            for symbol, price in prices.items():
                symbol = self._normalize_symbol(symbol)
                if symbol in self._account.positions:
                    self._account.positions[symbol].current_price = float(price or 0)
    
    def reset_day(self):
        """
        重置日内状态（每日开盘时调用）
        
        - 清空当日买入记录（T+1检查用）
        """
        with self._lock:
            self._today_buys.clear()
            logger.info("[CNStock Paper] Day reset: cleared today's buy records")
    
    def reset_account(self, initial_cash: float = None):
        """
        重置账户
        
        Args:
            initial_cash: 新的初始资金，默认使用原来的
        """
        with self._lock:
            cash = initial_cash if initial_cash is not None else self._account.initial_cash
            self._account = PaperAccount(cash=cash, initial_cash=cash)
            self._today_buys.clear()
            self._order_id_counter = 0
            self._save_state()
            logger.info(f"[CNStock Paper] Account reset: initial_cash={cash}")
    
    # ==================== 兼容接口 ====================
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """查询单个持仓"""
        symbol = self._normalize_symbol(symbol)
        with self._lock:
            if symbol in self._account.positions:
                pos = self._account.positions[symbol]
                return {
                    'symbol': symbol,
                    'quantity': pos.quantity,
                    'avg_price': round(pos.avg_price, 3),
                    'current_price': round(pos.current_price, 3),
                    'market_value': round(pos.market_value, 2),
                    'profit_loss': round(pos.profit_loss, 2),
                    'profit_loss_pct': round(pos.profit_loss_pct, 2)
                }
        return None
    
    def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """查询未成交订单（模拟交易直接成交，所以总是返回空）"""
        return []
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单（模拟交易直接成交，不支持取消）"""
        return False
    
    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取交易记录（与 get_orders 相同，用于兼容其他客户端接口）
        
        Args:
            limit: 返回数量限制
        
        Returns:
            交易记录列表
        """
        return self.get_orders(limit)


# 用于工厂函数的别名
CNStockClient = CNStockPaperClient
