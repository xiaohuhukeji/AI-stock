import os
import sys
import re
sys.path.insert(0, '.')
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'
os.environ['REDIS_HOST'] = 'localhost'

from app.utils.db import get_db_connection
from app.services.symbol_name import resolve_symbol_name

# 匹配策略名格式：基础名-代码
NAME_RE = re.compile(r'^(.*?)-([A-Za-z0-9]+)$')

def main():
    updated = 0
    skipped = 0
    failed = 0
    with get_db_connection() as db:
        cur = db.cursor()
        cur.execute("SELECT id, strategy_name, market_category FROM qd_strategies_trading")
        rows = cur.fetchall()
        cur.close()
        print(f"Found {len(rows)} strategies")

        for row in rows:
            sid = row['id']
            sname = row['strategy_name']
            mcat = row['market_category']

            # 已经有括号了，跳过
            if '(' in sname and ')' in sname:
                print(f"  [skip] id={sid} name={sname} already has name")
                skipped += 1
                continue

            m = NAME_RE.match(sname)
            if not m:
                print(f"  [skip] id={sid} name={sname} no match")
                skipped += 1
                continue

            base = m.group(1)
            symbol = m.group(2)
            # 把 SZ000977 还原成 000977
            if symbol.startswith(('SH', 'SZ')):
                symbol = symbol[2:]

            display_name = resolve_symbol_name(mcat, symbol) or ''
            if not display_name or display_name == symbol:
                print(f"  [skip] id={sid} symbol={symbol} no name resolved")
                skipped += 1
                continue

            new_name = f"{base}-{symbol}({display_name})"
            try:
                cur = db.cursor()
                cur.execute("UPDATE qd_strategies_trading SET strategy_name = %s WHERE id = %s", (new_name, sid))
                db.commit()
                cur.close()
                print(f"  [ok]   id={sid} {sname} -> {new_name}")
                updated += 1
            except Exception as e:
                print(f"  [err]  id={sid} {sname}: {e}")
                failed += 1

    print(f"\nDone. updated={updated} skipped={skipped} failed={failed}")

if __name__ == '__main__':
    main()
