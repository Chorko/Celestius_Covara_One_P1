import os, json, hmac, hashlib, requests, time
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()
U="http://127.0.0.1:8000/payouts/webhooks/simulated_gateway"
S="dev-payout-webhook-secret"
C=["4c9423dd-50ab-4d38-8358-c418888b2e88","4f8d2c95-8a17-4a83-a281-b336d33d74e8","b0b6a6d5-95c0-40f9-8ce2-fd4b0e68a8f1"]
R=[]
for i in C:
  p={"provider_event_id":f"ev_{int(time.time())}_{i[:4]}","claim_id":i,"status":"settled","event_type":"payout.settlement.updated"}
  j=json.dumps(p,separators=(',',':'))
  s=hmac.new(S.encode(),j.encode(),hashlib.sha256).hexdigest()
  try:
    r=requests.post(U,data=j,headers={"Content-Type":"application/json","X-Payout-Signature":s},timeout=5)
    try: b=r.json()
    except: b=r.text
    R.append({"cid":i,"code":r.status_code,"body":b})
  except Exception as e: R.append({"cid":i,"err":str(e)})
sb_u=os.getenv("SUPABASE_URL") or "https://aptgddoivrzpvpmydfyh.supabase.co"
sb_k=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
sb=create_client(sb_u,sb_k)
cl=sb.table("manual_claims").select("id,claim_status").in_("id",C).execute().data
# Use correct column name: settlement_date (not settled_at)
py=sb.table("payout_requests").select("id,claim_id,status,provider_key,updated_at").in_("claim_id",C).execute().data
print(json.dumps({"webhooks":R,"claims":cl,"payouts":py},indent=2))
