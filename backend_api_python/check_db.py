import psycopg2

conn = psycopg2.connect('postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger')
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = [t[0] for t in cur.fetchall()]
print('Tables:', tables)

cur.execute('SELECT COUNT(*) FROM qd_users')
print('Users:', cur.fetchone()[0])

cur.execute('SELECT COUNT(*) FROM qd_strategies_trading')
print('Strategies:', cur.fetchone()[0])

cur.execute('SELECT COUNT(*) FROM qd_exchange_credentials')
print('Credentials:', cur.fetchone()[0])

cur.execute('SELECT COUNT(*) FROM qd_watchlist')
print('Watchlist:', cur.fetchone()[0])

cur.execute('SELECT COUNT(*) FROM qd_market_symbols')
print('Market Symbols:', cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM qd_settings WHERE key LIKE 'data_source_%'")
print('Data Source Settings:', cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM qd_settings")
print('Total Settings:', cur.fetchone()[0])

cur.execute("SELECT key, value FROM qd_settings WHERE key LIKE 'data_source_%'")
print("\nData Source Settings:")
for row in cur.fetchall():
    print(f"  {row[0]} = {row[1]}")

conn.close()
