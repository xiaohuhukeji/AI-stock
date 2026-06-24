import os
import sys
sys.path.insert(0, '.')
os.environ['DATABASE_URL'] = 'postgresql://quantdinger:quantdinger123@localhost:5432/quantdinger'
os.environ['REDIS_HOST'] = 'localhost'

from app.services.user_service import get_user_service

user_service = get_user_service()
user = user_service.get_user_by_username('1577504153')
if user:
    print(f'Found user: {user["id"]}')
    result = user_service.reset_password(user['id'], 'huhu1105..')
    if result:
        print('Password updated successfully!')
    else:
        print('Failed to update password!')
else:
    print('User not found!')
