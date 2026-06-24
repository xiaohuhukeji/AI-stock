import os
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'

from app.utils.db import get_db_connection

with get_db_connection() as db:
    cur = db.cursor()
    cur.execute("SELECT id, strategy_name, market_category, symbol FROM qd_strategies_trading WHERE id = 13")
    rows = cur.fetchall()
    print("策略13配置:")
    for r in rows:
        print(f"ID={r.get('id')}, 名称={r.get('strategy_name')}, market_category={r.get('market_category')}, 标的={r.get('symbol')}")
    
    cur.execute("SELECT id, strategy_id, level, message, timestamp FROM qd_strategy_logs WHERE strategy_id = 13 AND (message LIKE '%market_category%' OR message LIKE '%CNStock%' OR message LIKE '%cnstock%') ORDER BY id DESC")
    rows = cur.fetchall()
    print("\n策略13 market_category相关日志:")
    for r in rows:
        print(f"{r.get('timestamp')} [{r.get('level')}] {r.get('message')}")