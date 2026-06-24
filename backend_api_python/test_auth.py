import bcrypt

# 数据库中的密码哈希（quantdinger用户）
pw_hash = '$2b$12$lCizDh5P/io7D0UOu8XqbeJ'

# 尝试验证默认密码
test_passwords = ['123456', 'quantdinger', 'admin', 'password']

for pwd in test_passwords:
    try:
        result = bcrypt.checkpw(pwd.encode('utf-8'), pw_hash.encode('utf-8'))
        print(f"Password '{pwd}': {result}")
    except Exception as e:
        print(f"Password '{pwd}': Error - {e}")

# 也测试生成123456的哈希
new_hash = bcrypt.hashpw('123456'.encode('utf-8'), bcrypt.gensalt(rounds=12))
print(f"\nNew hash for '123456': {new_hash.decode('utf-8')}")
