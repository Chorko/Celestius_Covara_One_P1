import os
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

sb = create_client(
    os.getenv('NEXT_PUBLIC_SUPABASE_URL'), 
    os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')
)

resp = sb.auth.sign_in_with_password({"email": "worker@demo.com", "password": "DevTrails@123"})
token = resp.session.access_token

print("Got Token. Calling API...")

api_resp = requests.get(
    "http://127.0.0.1:8000/workers/me/stats",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"Stats HTTP {api_resp.status_code}")
print(api_resp.text)

api_resp_post = requests.post(
    "http://127.0.0.1:8000/claims/",
    headers={"Authorization": f"Bearer {token}"},
    json={"claim_reason": "test"}
)
print(f"Claims POST HTTP {api_resp_post.status_code}")
print(api_resp_post.text)
