"""
A股策略自动启停服务。

根据A股交易时段自动管理A股策略的启停：
- 周一早上 9:00 开启所有A股策略
- 周五下午 15:30 关闭所有A股策略
- 每个交易日早上 9:00 发送参考价格邮件

A股交易时段：
- 周一至周五（工作日）
- 上午：9:30-11:30
- 下午：13:00-15:00

策略在周一9:00开启后，会持续运行直到周五15:30关闭。
"""
import time
import threading
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd

from app.utils.logger import get_logger
from app.utils.db import get_db_connection
from app.services.indicator_params import StrategyConfigParser

logger = get_logger(__name__)


class CNStockScheduler:
    """A股策略自动启停调度器。"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._executor = None
        self._check_interval = 60
        self._last_actions = {}
        
        self.DAILY_EMAIL_TIME = (9, 0)
        self.MONDAY_OPEN_TIME = (9, 0)
        self.FRIDAY_CLOSE_TIME = (15, 30)
        
        logger.info("CNStockScheduler initialized")
    
    def set_executor(self, executor):
        self._executor = executor
        logger.info("CNStockScheduler: TradingExecutor reference set")
    
    def start(self):
        if self._running:
            logger.warning("CNStockScheduler already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="CNStockScheduler", daemon=True)
        self._thread.start()
        
        self._check_initial_state()
        
        logger.info("CNStockScheduler started")
    
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("CNStockScheduler stopped")
    
    def _check_initial_state(self):
        now = datetime.now()
        day_of_week = now.weekday()
        hour = now.hour
        minute = now.minute
        
        is_weekend = day_of_week >= 5
        is_after_close_time = day_of_week == 4 and (hour > 15 or (hour == 15 and minute >= 30))
        
        if is_weekend or is_after_close_time:
            logger.info(f"CNStockScheduler: 当前为非交易时段(周末={is_weekend}, 周五收盘后={is_after_close_time})，等待策略恢复完成后关闭A股策略")
            
            time.sleep(5)
            
            logger.info(f"CNStockScheduler: 开始关闭所有A股策略")
            self._execute_close_all_cnstock_strategies()
    
    def _run_loop(self):
        logger.info("CNStockScheduler loop started")
        
        while self._running:
            try:
                self._check_and_execute()
            except Exception as e:
                logger.error(f"CNStockScheduler check failed: {e}")
            
            time.sleep(self._check_interval)
        
        logger.info("CNStockScheduler loop ended")
    
    def _check_and_execute(self):
        now = datetime.now()
        day_of_week = now.weekday()
        hour = now.hour
        minute = now.minute
        
        current_time_key = (hour, minute)
        current_date_str = now.strftime("%Y-%m-%d")
        
        is_trading_day = 0 <= day_of_week <= 4
        
        if day_of_week == 0 and current_time_key == self.MONDAY_OPEN_TIME:
            action_key = f"{current_date_str}_monday_open"
            if self._last_actions.get('monday_open') != action_key:
                logger.info(f"CNStockScheduler: 周一早上9:00，开启所有A股策略")
                self._execute_open_all_cnstock_strategies()
                self._last_actions['monday_open'] = action_key
        
        if day_of_week == 4 and current_time_key == self.FRIDAY_CLOSE_TIME:
            action_key = f"{current_date_str}_friday_close"
            if self._last_actions.get('friday_close') != action_key:
                logger.info(f"CNStockScheduler: 周五下午15:30，关闭所有A股策略")
                self._execute_close_all_cnstock_strategies()
                self._last_actions['friday_close'] = action_key
        
        if is_trading_day and current_time_key == self.DAILY_EMAIL_TIME:
            action_key = f"{current_date_str}_daily_email"
            if self._last_actions.get('daily_email') != action_key:
                logger.info(f"CNStockScheduler: 交易日早上9:00，发送参考价格邮件")
                self._send_daily_reference_price_email()
                self._last_actions['daily_email'] = action_key
    
    def _get_all_cnstock_strategies(self) -> List[Dict[str, Any]]:
        strategies = []
        
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute("""
                    SELECT id, user_id, strategy_name, trading_config, market_category, 
                           market_type, indicator_config, symbol
                    FROM qd_strategies_trading
                    WHERE status = 'running'
                    AND (
                        market_category = 'CNStock'
                        OR market_type = 'CNStock'
                        OR trading_config LIKE '%"market_type":"CNStock"%'
                        OR trading_config LIKE '%"market_category":"CNStock"%'
                        OR symbol LIKE '%%.SH'
                        OR symbol LIKE '%%.SZ'
                        OR symbol ~ '^[0-9]{6}$'
                    )
                """)
                rows = cur.fetchall()
                cur.close()
                
                for row in rows:
                    trading_config_str = row.get('trading_config') or ''
                    trading_config = {}
                    if trading_config_str:
                        try:
                            trading_config = json.loads(trading_config_str)
                        except:
                            pass
                    
                    indicator_config_str = row.get('indicator_config') or ''
                    indicator_config = {}
                    if indicator_config_str:
                        try:
                            indicator_config = json.loads(indicator_config_str)
                        except:
                            pass
                    
                    market_category = row.get('market_category') or trading_config.get('market_category') or ''
                    market_type = row.get('market_type') or trading_config.get('market_type') or ''
                    symbol = row.get('symbol') or trading_config.get('symbol') or ''
                    
                    is_cnstock = (
                        market_category.lower() == 'cnstock' or
                        market_type.lower() == 'cnstock' or
                        symbol.endswith('.SH') or
                        symbol.endswith('.SZ') or
                        (len(symbol) == 6 and symbol.isdigit())
                    )
                    
                    if is_cnstock:
                        strategies.append({
                            'id': row['id'],
                            'user_id': row['user_id'],
                            'strategy_name': row.get('strategy_name') or '',
                            'symbol': symbol,
                            'trading_config': trading_config,
                            'indicator_config': indicator_config,
                            'market_category': market_category or 'CNStock',
                        })
        
        except Exception as e:
            logger.error(f"Failed to get CNStock strategies: {e}")
        
        return strategies
    
    def _get_user_email(self, user_id: int) -> str:
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute("SELECT email, notification_settings FROM qd_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                cur.close()
                
                if row:
                    email = (row.get('email') or '').strip()
                    settings_str = row.get('notification_settings') or ''
                    if settings_str:
                        try:
                            settings = json.loads(settings_str)
                            notify_email = (settings.get('email') or '').strip()
                            if notify_email:
                                return notify_email
                        except:
                            pass
                    return email
        except Exception as e:
            logger.error(f"Failed to get user email: {e}")
        
        return ''
    
    def _calculate_reference_price(self, strategy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._executor:
            return None
        
        try:
            trading_config = strategy.get('trading_config') or {}
            indicator_config = strategy.get('indicator_config') or {}
            symbol = strategy.get('symbol') or ''
            market_category = strategy.get('market_category') or 'CNStock'
            timeframe = trading_config.get('timeframe') or trading_config.get('timeFrame') or '1D'
            indicator_code = indicator_config.get('indicator_code') or ''
            
            if not symbol or not indicator_code:
                return None
            
            klines = self._executor._fetch_latest_kline(
                symbol=symbol,
                timeframe=timeframe,
                limit=200,
                market_category=market_category,
                exchange_id=None,
                market_type=None
            )
            
            if not klines:
                return None
            
            df = pd.DataFrame(klines)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)
            
            executed_df, exec_env = self._executor._execute_indicator_df(
                indicator_code=indicator_code,
                df=df,
                trading_config=trading_config
            )
            
            if executed_df is None or len(executed_df) == 0:
                return None
            
            current_price = float(klines[-1].get('close') or klines[-1].get('price') or 0)
            
            pending_signals = []
            if all(col in executed_df.columns for col in ['open_long', 'close_long', 'open_short', 'close_short']):
                last_close = float(executed_df['close'].iloc[-1])
                if executed_df['open_long'].iloc[-1]:
                    pending_signals.append({'type': 'open_long', 'trigger_price': last_close})
                if executed_df['close_long'].iloc[-1]:
                    pending_signals.append({'type': 'close_long', 'trigger_price': last_close})
            elif all(col in executed_df.columns for col in ['buy', 'sell']):
                last_close = float(executed_df['close'].iloc[-1])
                td = str((trading_config or {}).get('trade_direction', 'both')).lower()
                if td == 'long' and executed_df['buy'].iloc[-1]:
                    pending_signals.append({'type': 'open_long', 'trigger_price': last_close})
                elif td == 'long' and executed_df['sell'].iloc[-1]:
                    pending_signals.append({'type': 'close_long', 'trigger_price': last_close})
            
            reference_prices = {
                'current_price': round(current_price, 2),
                'buy_price': None,
                'sell_price': None,
                'stop_loss': None,
                'take_profit': None,
                'signals': [],
            }
            
            for signal in pending_signals:
                signal_type = signal.get('signal_type') or signal.get('type') or ''
                price = signal.get('price') or signal.get('trigger_price')
                if price:
                    price = round(float(price), 2)
                
                if signal_type in ('open_long', 'buy'):
                    reference_prices['buy_price'] = price or current_price
                elif signal_type in ('close_long', 'sell'):
                    reference_prices['sell_price'] = price or current_price
                
                reference_prices['signals'].append({
                    'type': signal_type,
                    'price': price,
                })
            
            if reference_prices['buy_price'] is None:
                reference_prices['buy_price'] = round(current_price, 2)
            if reference_prices['sell_price'] is None:
                reference_prices['sell_price'] = round(current_price, 2)
            
            strategy_cfg = StrategyConfigParser.parse(indicator_code or "")
            indicator_stop_pct = float(strategy_cfg.get('stopLossPct') or 0) * 100
            indicator_tp_pct = float(strategy_cfg.get('takeProfitPct') or 0) * 100
            
            stop_loss_pct = indicator_stop_pct
            take_profit_pct = indicator_tp_pct
            
            if stop_loss_pct <= 0:
                stop_loss_pct = float((trading_config or {}).get('stop_loss_pct') or 0)
            if take_profit_pct <= 0:
                take_profit_pct = float((trading_config or {}).get('take_profit_pct') or 0)
            
            base_price = reference_prices['buy_price'] or current_price
            if stop_loss_pct > 0:
                reference_prices['stop_loss'] = round(base_price * (1 - stop_loss_pct / 100), 2)
            if take_profit_pct > 0:
                reference_prices['take_profit'] = round(base_price * (1 + take_profit_pct / 100), 2)
            
            return reference_prices
        
        except Exception as e:
            logger.error(f"Failed to calculate reference price for strategy {strategy.get('id')}: {e}")
            return None
    
    def _send_daily_reference_price_email(self):
        strategies = self._get_all_cnstock_strategies()
        
        if not strategies:
            logger.info("CNStockScheduler: 没有A股策略，跳过发送参考价格邮件")
            return
        
        user_strategies: Dict[int, List[Dict[str, Any]]] = {}
        for st in strategies:
            user_id = st['user_id']
            if user_id not in user_strategies:
                user_strategies[user_id] = []
            user_strategies[user_id].append(st)
        
        sent_count = 0
        
        for user_id, user_st_list in user_strategies.items():
            try:
                email = self._get_user_email(user_id)
                if not email:
                    logger.warning(f"CNStockScheduler: 用户 {user_id} 没有设置邮箱，跳过")
                    continue
                
                strategy_data = []
                for st in user_st_list:
                    ref_price = self._calculate_reference_price(st)
                    if ref_price:
                        strategy_data.append({
                            'strategy_name': st['strategy_name'],
                            'symbol': st['symbol'],
                            **ref_price
                        })
                
                if not strategy_data:
                    continue
                
                success = self._send_reference_price_email(email, strategy_data)
                if success:
                    sent_count += 1
                    logger.info(f"CNStockScheduler: 已向用户 {user_id} ({email}) 发送 {len(strategy_data)} 个策略的参考价格邮件")
                else:
                    logger.warning(f"CNStockScheduler: 向用户 {user_id} ({email}) 发送参考价格邮件失败")
                
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"CNStockScheduler: 发送用户 {user_id} 邮件异常: {e}")
        
        logger.info(f"CNStockScheduler: 本次共向 {sent_count} 个用户发送参考价格邮件")
    
    def _send_reference_price_email(self, to_email: str, strategy_data: List[Dict[str, Any]]) -> bool:
        try:
            from app.services.email_service import get_email_service
            
            email_service = get_email_service()
            if not email_service or not email_service.email_enabled:
                logger.warning("CNStockScheduler: 邮件服务未启用")
                return False
            
            today = datetime.now().strftime("%Y-%m-%d")
            
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1890ff; border-bottom: 2px solid #1890ff; padding-bottom: 10px;">
                    📊 A股策略每日参考价格 - {today}
                </h2>
                <p style="color: #666; font-size: 14px;">早上好！以下是您所有A股策略今日的参考价格：</p>
            """
            
            for idx, data in enumerate(strategy_data, 1):
                signal_text = '-'
                if data.get('signals') and len(data['signals']) > 0:
                    signal_map = {
                        'open_long': '开多',
                        'close_long': '平多',
                        'open_short': '开空',
                        'close_short': '平空',
                        'buy': '买入',
                        'sell': '卖出'
                    }
                    signals = []
                    for sig in data['signals']:
                        sig_name = signal_map.get(sig.get('type', ''), sig.get('type', ''))
                        sig_price = sig.get('price', '-')
                        signals.append(f"{sig_name} {sig_price}")
                    signal_text = ', '.join(signals)
                
                buy_price = data.get('buy_price', '-')
                sell_price = data.get('sell_price', '-')
                stop_loss = data.get('stop_loss', '-')
                take_profit = data.get('take_profit', '-')
                current_price = data.get('current_price', '-')
                
                html_body += f"""
                <div style="background: #f9f9f9; border-radius: 8px; padding: 15px; margin: 15px 0; border-left: 4px solid #1890ff;">
                    <h3 style="margin: 0 0 10px 0; color: #333;">
                        #{idx} {data.get('strategy_name', '未知策略')}
                        <span style="color: #999; font-size: 14px; font-weight: normal;">{data.get('symbol', '')}</span>
                    </h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 15px; margin: 10px 0;">
                        <div style="flex: 1; min-width: 120px; background: #fff; padding: 10px; border-radius: 6px; text-align: center; border: 1px solid #e8e8e8;">
                            <div style="color: #52c41a; font-size: 12px; margin-bottom: 5px;">💰 当前价格</div>
                            <div style="color: #333; font-size: 18px; font-weight: bold;">{current_price}</div>
                        </div>
                        <div style="flex: 1; min-width: 120px; background: #fff; padding: 10px; border-radius: 6px; text-align: center; border: 1px solid #e8e8e8;">
                            <div style="color: #52c41a; font-size: 12px; margin-bottom: 5px;">📈 买入参考价</div>
                            <div style="color: #52c41a; font-size: 18px; font-weight: bold;">{buy_price}</div>
                        </div>
                        <div style="flex: 1; min-width: 120px; background: #fff; padding: 10px; border-radius: 6px; text-align: center; border: 1px solid #e8e8e8;">
                            <div style="color: #f5222d; font-size: 12px; margin-bottom: 5px;">📉 卖出参考价</div>
                            <div style="color: #f5222d; font-size: 18px; font-weight: bold;">{sell_price}</div>
                        </div>
                        <div style="flex: 1; min-width: 120px; background: #fff; padding: 10px; border-radius: 6px; text-align: center; border: 1px solid #e8e8e8;">
                            <div style="color: #fa8c16; font-size: 12px; margin-bottom: 5px;">⚠️ 止损参考价</div>
                            <div style="color: #fa8c16; font-size: 18px; font-weight: bold;">{stop_loss}</div>
                        </div>
                        <div style="flex: 1; min-width: 120px; background: #fff; padding: 10px; border-radius: 6px; text-align: center; border: 1px solid #e8e8e8;">
                            <div style="color: #1890ff; font-size: 12px; margin-bottom: 5px;">🎯 止盈参考价</div>
                            <div style="color: #1890ff; font-size: 18px; font-weight: bold;">{take_profit}</div>
                        </div>
                    </div>
                    <div style="margin-top: 10px; padding: 8px 12px; background: #e6f7ff; border-radius: 4px; font-size: 13px;">
                        <strong>当前信号：</strong>
                        <span style="color: #1890ff;">{signal_text}</span>
                    </div>
                </div>
                """
            
            html_body += f"""
                <div style="margin-top: 20px; padding: 15px; background: #fffbe6; border-radius: 6px; font-size: 13px; color: #fa8c16;">
                    <strong>⚠️ 风险提示：</strong>以上参考价格仅供参考，不构成投资建议。股市有风险，投资需谨慎。
                </div>
                <div style="margin-top: 20px; text-align: center; color: #999; font-size: 12px;">
                    <p>此邮件由 QuantDinger A股策略调度系统自动发送</p>
                    <p>{today}</p>
                </div>
            </div>
            """
            
            subject = f"【QuantDinger】A股策略每日参考价格 - {today}"
            success, msg = email_service.send_email(to_email, subject, html_body)
            return success
        
        except Exception as e:
            logger.error(f"CNStockScheduler: 发送邮件异常: {e}")
            return False
    
    def _execute_open_all_cnstock_strategies(self):
        if not self._executor:
            logger.warning("CNStockScheduler: TradingExecutor not set, cannot open strategies")
            return
        
        strategies = self._get_all_cnstock_strategies()
        opened_count = 0
        
        for st in strategies:
            strategy_id = st['id']
            strategy_name = st['strategy_name']
            
            try:
                success = self._executor.start_strategy(strategy_id)
                if success:
                    opened_count += 1
                    logger.info(f"CNStockScheduler: 开启A股策略 [{strategy_id}] {strategy_name} 成功")
                else:
                    logger.warning(f"CNStockScheduler: 开启A股策略 [{strategy_id}] {strategy_name} 失败")
            except Exception as e:
                logger.error(f"CNStockScheduler: 开启A股策略 [{strategy_id}] {strategy_name} 异常: {e}")
        
        logger.info(f"CNStockScheduler: 本次共开启 {opened_count} 个A股策略")
    
    def _execute_close_all_cnstock_strategies(self):
        if not self._executor:
            logger.warning("CNStockScheduler: TradingExecutor not set, cannot close strategies")
            return
        
        running_cnstock_ids = []
        
        if hasattr(self._executor, 'running_strategies'):
            for strategy_id, thread in self._executor.running_strategies.items():
                try:
                    with get_db_connection() as db:
                        cur = db.cursor()
                        cur.execute(
                            "SELECT trading_config, market_category, market_type, symbol FROM qd_strategies_trading WHERE id = %s",
                            (strategy_id,)
                        )
                        row = cur.fetchone()
                        cur.close()
                        
                        if row:
                            trading_config_str = row.get('trading_config') or ''
                            trading_config = {}
                            if trading_config_str:
                                try:
                                    trading_config = json.loads(trading_config_str)
                                except:
                                    pass
                            
                            market_category = row.get('market_category') or trading_config.get('market_category') or ''
                            market_type = row.get('market_type') or trading_config.get('market_type') or ''
                            symbol = row.get('symbol') or trading_config.get('symbol') or ''
                            
                            is_cnstock = (
                                market_category.lower() == 'cnstock' or
                                market_type.lower() == 'cnstock' or
                                symbol.endswith('.SH') or
                                symbol.endswith('.SZ') or
                                (len(symbol) == 6 and symbol.isdigit())
                            )
                            
                            if is_cnstock:
                                running_cnstock_ids.append(strategy_id)
                except Exception as e:
                    logger.error(f"CNStockScheduler: 查询策略 {strategy_id} 信息失败: {e}")
        
        closed_count = 0
        
        for strategy_id in running_cnstock_ids:
            try:
                self._executor.stop_strategy(strategy_id)
                closed_count += 1
                logger.info(f"CNStockScheduler: 关闭A股策略 [{strategy_id}] 成功")
            except Exception as e:
                logger.error(f"CNStockScheduler: 关闭A股策略 [{strategy_id}] 异常: {e}")
        
        logger.info(f"CNStockScheduler: 本次共关闭 {closed_count} 个A股策略")


_cnstock_scheduler: Optional[CNStockScheduler] = None


def get_cnstock_scheduler() -> CNStockScheduler:
    global _cnstock_scheduler
    if _cnstock_scheduler is None:
        _cnstock_scheduler = CNStockScheduler()
    return _cnstock_scheduler


def start_cnstock_scheduler(executor=None):
    scheduler = get_cnstock_scheduler()
    if executor:
        scheduler.set_executor(executor)
    scheduler.start()
    return scheduler
