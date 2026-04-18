import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Map the environment variables precisely as they appear in .env
url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

claim_ids = [
    '4c9423dd-50ab-4d38-8358-c418888b2e88',
    '4f8d2c95-8a17-4a83-a281-b336d33d74e8',
    'b0b6a6d5-95c0-40f9-8ce2-fd4b0e68a8f1'
]

headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json'
}

# manual_claims
mc_url = f"{url}/rest/v1/manual_claims?id=in.({','.join(claim_ids)})&select=id,claim_status"
# payout_requests
pr_url = f"{url}/rest/v1/payout_requests?claim_id=in.({','.join(claim_ids)})&select=claim_id,status,provider_key"

mc_resp = requests.get(mc_url, headers=headers)
pr_resp = requests.get(pr_url, headers=headers)

print(json.dumps({
    'manual_claims': mc_resp.json() if mc_resp.status_code == 200 else mc_resp.text,
    'payout_requests': pr_resp.json() if pr_resp.status_code == 200 else pr_resp.text
}))
