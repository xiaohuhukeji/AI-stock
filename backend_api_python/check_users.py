import psycopg2

conn = psycopg2.connect('postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger')
cur = conn.cursor()

cur.execute("SELECT id, username, email, password_hash, status, created_at FROM qd_users")
print('Users:')
for row in cur.fetchall():
    pw_hash = row[3] if row[3] else '(empty)'
    # 只显示前20个字符
    pw_preview = pw_hash[:30] + '...' if len(pw_hash) > 30 else pw_hash
    print(f"  ID={row[0]}, username={row[1]}, email={row[2]}, status={row[4]}")
    print(f"    password_hash={pw_preview}")

conn.close()
