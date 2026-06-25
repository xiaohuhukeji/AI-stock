import os
from dotenv import load_dotenv
load_dotenv()
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'
from app.utils.db import get_db_connection

with get_db_connection() as db:
    cur = db.cursor()
    
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'qd_strategy_trades'")
    cols = cur.fetchall()
    print('qd_strategy_trades 表结构:', [c.get('column_name') for c in cols])
    
    print()
    print('=== 策略 75 的交易记录 ===')
    cur.execute('SELECT * FROM qd_strategy_trades WHERE strategy_id = 75 ORDER BY id DESC LIMIT 10')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(r)
    else:
        print('无交易记录')
    
    print()
    print('=== 策略 75 的持仓记录 ===')
    cur.execute('SELECT * FROM qd_strategy_positions WHERE strategy_id = 75')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(r)
    else:
        print('无持仓记录')
    
    cur.close()
