import psycopg2
import bcrypt

conn = psycopg2.connect('postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger')
cur = conn.cursor()

# 获取完整密码哈希
cur.execute("SELECT id, username, password_hash FROM qd_users WHERE username='quantdinger'")
row = cur.fetchone()
print(f"User: {row[1]}")
print(f"Current hash: {row[2]}")

# 生成新的123456哈希
new_hash = bcrypt.hashpw('123456'.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
print(f"New hash for '123456': {new_hash}")

# 更新密码为123456
cur.execute(
    "UPDATE qd_users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
    (new_hash, row[0])
)
conn.commit()
print("Password reset to '123456'")

conn.close()
