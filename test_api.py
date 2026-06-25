import sys
sys.path.insert(0, '/app')

import logging
logging.disable(logging.CRITICAL)

from app import create_app
app = create_app()
with app.test_client() as client:
    with app.app_context():
        from app.models import User
        from app.utils.token import create_token
        u = User.query.first()
        token = create_token(u.id, u.username)
        resp = client.get('/api/strategies/reference-price?strategyId=82', headers={'Authorization': f'Bearer {token}'})
        import json
        data = resp.get_json()
        print('Status:', resp.status_code)
        print('take_profit:', data.get('data', {}).get('take_profit'))
        print('stop_loss:', data.get('data', {}).get('stop_loss'))
        print('buy_price:', data.get('data', {}).get('buy_price'))
        print('current_price:', data.get('data', {}).get('current_price'))
        print('sell_price:', data.get('data', {}).get('sell_price'))