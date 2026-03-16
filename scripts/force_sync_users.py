import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client, Client

def force_sync_users():
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    sb: Client = create_client(url, key)
    
    # Get all users from auth.users via admin API
    try:
        users = sb.auth.admin.list_users()
        for u in users:
            uid = u.id
            email = u.email
            
            # Upsert into basic profiles
            role = 'worker'
            if email == 'admin@demo.com':
                role = 'insurer_admin'
                
            print(f"Syncing profile for {email} ({uid}) as {role}")
            
            name = "Demo Worker" if role == "worker" else "Demo Admin"
            sb.table("profiles").upsert({
                "id": uid,
                "role": role,
                "full_name": name,
                "created_at": "2024-01-01T00:00:00Z"
            }).execute()
            
            # Upsert specific extension tables
            if role == "worker":
                sb.table("worker_profiles").upsert({
                    "profile_id": uid,
                    "platform_name": "Test Platform",
                    "city": "Test City",
                    "avg_hourly_income_inr": 85.0,
                    "trust_score": 0.9,
                    "gps_consent": True
                }).execute()
            else:
                sb.table("insurer_profiles").upsert({
                    "profile_id": uid,
                    "company_name": "DEVTrails Inc",
                    "job_title": "Risk Admin"
                }).execute()
                
        print("Successfully synced all auth users into public tables.")
    except Exception as e:
        print(f"Error syncing users: {e}")

if __name__ == "__main__":
    force_sync_users()
