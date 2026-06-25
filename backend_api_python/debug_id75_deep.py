import os
import json
from dotenv import load_dotenv
load_dotenv()
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'

from app.utils.db import get_db_connection

with get_db_connection() as db:
    cur = db.cursor()
    
    print('=== 策略 id75 的详细配置 ===')
    cur.execute('SELECT * FROM qd_strategies_trading WHERE id = %s', (75,))
    row = cur.fetchone()
    if row:
        print(f"  id: {row.get('id')}")
        print(f"  user_id: {row.get('user_id')}")
        print(f"  execution_mode: {row.get('execution_mode')}")
        print(f"  status: {row.get('status')}")
        print(f"  notification_config: {row.get('notification_config')}")
        print(f"  risk_config: {row.get('risk_config')}")
        print(f"  market_type: {row.get('market_type')}")
        print(f"  market_category: {row.get('market_category')}")
    
    print()
    print('=== pending_orders 最近记录 (id75) ===')
    cur.execute('''
        SELECT id, strategy_id, signal_type, symbol, status, execution_mode, 
               created_at, updated_at, processed_at, dispatch_note, last_error,
               attempts, max_attempts, payload_json, price, amount
        FROM pending_orders 
        WHERE strategy_id = 75 
        ORDER BY id DESC 
        LIMIT 10
    ''')
    rows = cur.fetchall()
    for r in rows:
        print(f'--- Order ID: {r.get("id")} ---')
        print(f'  Signal Type: {r.get("signal_type")}')
        print(f'  Symbol: {r.get("symbol")}')
        print(f'  Status: {r.get("status")}')
        print(f'  Mode: {r.get("execution_mode")}')
        print(f'  Created: {r.get("created_at")}')
        print(f'  Updated: {r.get("updated_at")}')
        print(f'  Processed: {r.get("processed_at")}')
        print(f'  Note: {r.get("dispatch_note")}')
        print(f'  Error: {r.get("last_error")}')
        print(f'  Attempts: {r.get("attempts")}/{r.get("max_attempts")}')
        print(f'  Price: {r.get("price")}')
        print(f'  Amount: {r.get("amount")}')
        payload = r.get('payload_json')
        if payload:
            try:
                p = json.loads(payload)
                print(f'  Payload signal_type: {p.get("signal_type")}')
                print(f'  Payload notification_config: {p.get("notification_config")}')
                print(f'  Payload strategy_id: {p.get("strategy_id")}')
                print(f'  Payload strategy_name: {p.get("strategy_name")}')
            except Exception as e:
                print(f'  Payload parse error: {e}')
    
    print()
    print('=== qd_strategy_notifications 记录 (user_id=1) ===')
    cur.execute('''
        SELECT id, strategy_id, user_id, symbol, signal_type, channels, title, 
               created_at, payload_json
        FROM qd_strategy_notifications 
        WHERE user_id = 1
        ORDER BY id DESC 
        LIMIT 20
    ''')
    rows = cur.fetchall()
    print(f'总记录数: {len(rows)}')
    for r in rows:
        print(f'--- ID: {r.get("id")} ---')
        print(f'  strategy_id: {r.get("strategy_id")}')
        print(f'  user_id: {r.get("user_id")}')
        print(f'  symbol: {r.get("symbol")}')
        print(f'  signal_type: {r.get("signal_type")}')
        print(f'  channels: {r.get("channels")}')
        print(f'  title: {r.get("title")}')
        print(f'  created_at: {r.get("created_at")}')
    
    print()
    print('=== qd_strategy_notifications 记录 (strategy_id=75) ===')
    cur.execute('''
        SELECT id, strategy_id, user_id, symbol, signal_type, channels, title, 
               created_at, payload_json
        FROM qd_strategy_notifications 
        WHERE strategy_id = 75
        ORDER BY id DESC 
        LIMIT 20
    ''')
    rows = cur.fetchall()
    print(f'总记录数: {len(rows)}')
    for r in rows:
        print(f'--- ID: {r.get("id")} ---')
        print(f'  strategy_id: {r.get("strategy_id")}')
        print(f'  user_id: {r.get("user_id")}')
        print(f'  symbol: {r.get("symbol")}')
        print(f'  signal_type: {r.get("signal_type")}')
        print(f'  channels: {r.get("channels")}')
        print(f'  title: {r.get("title")}')
        print(f'  created_at: {r.get("created_at")}')
    
    print()
    print('=== qd_strategy_positions (id75) ===')
    cur.execute('''
        SELECT id, strategy_id, symbol, side, size, entry_price, 
               created_at, updated_at
        FROM qd_strategy_positions 
        WHERE strategy_id = 75
        ORDER BY id DESC 
        LIMIT 10
    ''')
    rows = cur.fetchall()
    for r in rows:
        print(f'--- ID: {r.get("id")} ---')
        print(f'  symbol: {r.get("symbol")}')
        print(f'  side: {r.get("side")}')
        print(f'  size: {r.get("size")}')
        print(f'  entry_price: {r.get("entry_price")}')
        print(f'  updated_at: {r.get("updated_at")}')
    
    print()
    print('=== qd_strategy_trades (id75) ===')
    cur.execute('''
        SELECT id, strategy_id, symbol, trade_type, price, amount, 
               profit, created_at, fill_source, pending_order_id
        FROM qd_strategy_trades 
        WHERE strategy_id = 75
        ORDER BY id DESC 
        LIMIT 10
    ''')
    rows = cur.fetchall()
    for r in rows:
        print(f'--- ID: {r.get("id")} ---')
        print(f'  symbol: {r.get("symbol")}')
        print(f'  trade_type: {r.get("trade_type")}')
        print(f'  price: {r.get("price")}')
        print(f'  amount: {r.get("amount")}')
        print(f'  profit: {r.get("profit")}')
        print(f'  created_at: {r.get("created_at")}')
        print(f'  fill_source: {r.get("fill_source")}')
        print(f'  pending_order_id: {r.get("pending_order_id")}')
    
    cur.close()
