import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure we load the .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from backend.app.supabase_client import get_supabase_admin

def seed_test_users():
    sb = get_supabase_admin()
    
    users = [
        {"email": "worker@demo.com", "password": "DevTrails@123", "role": "worker", "name": "Demo Worker"},
        {"email": "admin@demo.com", "password": "DevTrails@123", "role": "insurer_admin", "name": "Demo Admin"}
    ]
    
    for u in users:
        print(f"Ensuring user {u['email']} exists...")
        try:
            # Check if user exists (we can't easily query auth.users, so we try to sign in or create)
            # Acutally with admin client we can create users via admin api
            res = sb.auth.admin.create_user({
                "email": u["email"],
                "password": u["password"],
                "email_confirm": True,
                "user_metadata": {"full_name": u["name"]}
            })
            user_id = res.user.id
            print(f"Created {u['email']} with ID: {user_id}")
            
            # Since the trigger might default them to 'worker', let's manually overwrite role for admin
            sb.table("profiles").update({"role": u["role"]}).eq("id", user_id).execute()
            
            if u["role"] == "worker":
                # Ensure worker_profile exists
                sb.table("worker_profiles").upsert({
                    "profile_id": user_id,
                    "platform_name": "Test Platform",
                    "city": "Test City",
                    "avg_hourly_income_inr": 85.0,
                    "trust_score": 0.9,
                    "gps_consent": True
                }).execute()
            elif u["role"] == "insurer_admin":
                # Ensure insurer_profile exists
                sb.table("insurer_profiles").upsert({
                    "profile_id": user_id,
                    "company_name": "DEVTrails Inc",
                    "job_title": "Risk Admin"
                }).execute()
                
        except Exception as e:
            if "already been registered" in str(e) or "already exists" in str(e):
                print(f"User {u['email']} already exists. Updating role to {u['role']} to be safe...")
                try:
                    # To update, we'd need their ID. Since we are using demo accounts, let's just attempt login to get ID.
                    log_res = sb.auth.sign_in_with_password({"email": u["email"], "password": u["password"]})
                    user_id = log_res.user.id
                    sb.table("profiles").update({"role": u["role"]}).eq("id", user_id).execute()
                    print(f"Successfully updated role for {u['email']}.")
                except Exception as inner_e:
                    print(f"Could not update existing user: {inner_e}")
            else:
                print(f"Failed to create {u['email']}: {e}")

if __name__ == "__main__":
    seed_test_users()
