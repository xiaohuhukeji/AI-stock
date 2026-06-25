import os
from dotenv import load_dotenv
load_dotenv()
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'

from app.utils.db import get_db_connection

with get_db_connection() as db:
    cur = db.cursor()
    
    print('=== qd_strategy_notifications 表结构 ===')
    cur.execute('''
        SELECT column_name, data_type, character_maximum_length, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'qd_strategy_notifications'
        ORDER BY ordinal_position
    ''')
    rows = cur.fetchall()
    for r in rows:
        print(f"  {r.get('column_name')}: {r.get('data_type')} (nullable={r.get('is_nullable')}, max_len={r.get('character_maximum_length')})")
    
    print()
    print('=== 测试插入一条通知 ===')
    test_payload = {
        "event": "qd.signal",
        "version": 1,
        "timestamp": 1719285833,
        "strategy": {"id": 75, "name": "Test Strategy"},
        "instrument": {"symbol": "159995"},
        "signal": {"type": "close_long", "action": "close", "side": "long"},
        "order": {"ref_price": 3.072, "stake_amount": 614.4},
        "trace": {"pending_order_id": 60, "mode": "signal"},
        "extra": {},
    }
    
    import json
    try:
        cur.execute(
            """
            INSERT INTO qd_strategy_notifications
            (user_id, strategy_id, symbol, signal_type, channels, title, message, payload_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                1,
                75,
                "159995",
                "close_long",
                "browser,email",
                "QD信号 | 159995 | CLOSE LONG",
                "Test message",
                json.dumps(test_payload, ensure_ascii=False),
            ),
        )
        db.commit()
        print('插入成功！')
    except Exception as e:
        print(f'插入失败: {e}')
    
    cur.close()
