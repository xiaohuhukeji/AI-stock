import os
from dotenv import load_dotenv
load_dotenv()
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'
import json
from app.utils.db import get_db_connection

with get_db_connection() as db:
    cur = db.cursor()
    
    print('=== qd_strategy_notifications 表结构 ===')
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'qd_strategy_notifications'")
    cols = cur.fetchall()
    for c in cols:
        print(f'  {c.get("column_name")}: {c.get("data_type")}')
    
    print()
    print('=== 所有浏览器通知记录 ===')
    cur.execute('SELECT id, strategy_id, user_id, signal_type, channels, title, message, created_at FROM qd_strategy_notifications ORDER BY id DESC LIMIT 20')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f'{r.get("created_at")} [sid={r.get("strategy_id")}] {r.get("signal_type")} channels={r.get("channels")}')
    else:
        print('无记录')
    
    print()
    print('=== 检查策略 75 的用户通知记录 ===')
    cur.execute('SELECT id, strategy_id, user_id, signal_type, channels, title, message, created_at FROM qd_strategy_notifications WHERE strategy_id = 75')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f'{r.get("created_at")} [sid={r.get("strategy_id")}] {r.get("signal_type")} channels={r.get("channels")}')
    else:
        print('策略 75 无浏览器通知记录')
    
    cur.close()
