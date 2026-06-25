import json
import os
from dotenv import load_dotenv
load_dotenv()
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'
from app.utils.db import get_db_connection

with get_db_connection() as db:
    cur = db.cursor()
    
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'qd_strategies_trading'")
    cols = cur.fetchall()
    print('表结构:', [c.get('column_name') for c in cols])
    
    cur.execute('SELECT * FROM qd_strategies_trading WHERE id = %s', (75,))
    row = cur.fetchone()
    if row:
        print('=== 策略配置 ===')
        for k, v in row.items():
            print(f'  {k}: {v}')
    else:
        print('策略 id75 不存在')
    
    print()
    print('=== 最近的 pending_orders 记录 ===')
    cur.execute('''
        SELECT id, strategy_id, signal_type, symbol, status, execution_mode, 
               created_at, updated_at, processed_at, dispatch_note, last_error,
               attempts, max_attempts, payload_json
        FROM pending_orders 
        WHERE strategy_id = 75 
        ORDER BY id DESC 
        LIMIT 10
    ''')
    rows = cur.fetchall()
    for r in rows:
        print('--- Order ID:', r.get('id'), '---')
        print('  Signal Type:', r.get('signal_type'))
        print('  Symbol:', r.get('symbol'))
        print('  Status:', r.get('status'))
        print('  Mode:', r.get('execution_mode'))
        print('  Created:', r.get('created_at'))
        print('  Updated:', r.get('updated_at'))
        print('  Processed:', r.get('processed_at'))
        print('  Note:', r.get('dispatch_note'))
        print('  Error:', r.get('last_error'))
        print('  Attempts:', r.get('attempts'), '/', r.get('max_attempts'))
        payload = r.get('payload_json')
        if payload:
            try:
                p = json.loads(payload)
                print('  Payload signal_type:', p.get('signal_type'))
                print('  Payload notification_config:', p.get('notification_config'))
            except Exception as e:
                print('  Payload parse error:', e)
    
    print()
    print('=== 最近的策略日志 ===')
    cur.execute('''
        SELECT timestamp, level, message 
        FROM qd_strategy_logs 
        WHERE strategy_id = 75 
        ORDER BY timestamp DESC 
        LIMIT 20
    ''')
    rows = cur.fetchall()
    for r in rows:
        print(r.get('timestamp'), '[', r.get('level'), ']', r.get('message'))
    
    print()
    print('=== 浏览器通知记录 ===')
    cur.execute('''
        SELECT id, signal_type, channels, title, message, created_at 
        FROM qd_strategy_notifications 
        WHERE strategy_id = 75 
        ORDER BY id DESC 
        LIMIT 10
    ''')
    rows = cur.fetchall()
    for r in rows:
        print(r.get('created_at'), '[', r.get('signal_type'), '] channels=', r.get('channels'), ' title=', r.get('title'))
    
    cur.close()
