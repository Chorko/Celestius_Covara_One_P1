import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from backend.app.supabase_client import get_supabase_admin, get_supabase_anon

def check_db():
    sb_admin = get_supabase_admin()
    sb_anon = get_supabase_anon()
    
    # 1. Check with admin (should bypass RLS and tell us if table exists)
    try:
        res = sb_admin.table("profiles").select("*").limit(1).execute()
        print("Admin fetch success. Table exists.", res.data)
    except Exception as e:
        print("Admin fetch failed! Table missing or other config error:")
        print(e)
        
    # 2. Try with anon
    try:
        res = sb_anon.table("profiles").select("*").limit(1).execute()
        print("Anon fetch success.", res.data)
    except Exception as e:
        print("Anon fetch failed:")
        print(e)
        
if __name__ == "__main__":
    check_db()
