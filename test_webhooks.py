import os
import json
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

webhook_secret = os.getenv('PAYOUT_PROVIDER_WEBHOOK_SECRET')

claim_ids = [
    '4c9423dd-50ab-4d38-8358-c418888b2e88',
    '4f8d2c95-8a17-4a83-a281-b336d33d74e8',
    'b0b6a6d5-95c0-40f9-8ce2-fd4b0e68a8f1'
]

results = []

for cid in claim_ids:
    payload = {
        'provider_event_id': f'evt_auto_{cid[:8]}',
        'claim_id': cid,
        'status': 'settled',
        'event_type': 'payout.settlement.updated'
    }
    body = json.dumps(payload, separators=(',', ':'))
    signature = hmac.new(
        webhook_secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()
    
    try:
        resp = requests.post(
            'http://127.0.0.1:8000/payouts/webhooks/simulated_gateway',
            data=body,
            headers={'X-Payout-Signature': signature, 'Content-Type': 'application/json'},
            timeout=5
        )
        try:
            w_res = resp.json()
        except:
            w_res = resp.text
        results.append({
            'claim_id': cid,
            'status_code': resp.status_code,
            'response': w_res
        })
    except Exception as e:
        results.append({'claim_id': cid, 'error': str(e)})

print(json.dumps(results))
