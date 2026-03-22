"""
DEVTrails — Synthetic Pack Seed Loader (Excel)

Reads DEVTrails_Synthetic_Seed_Pack.xlsx, creates real
Supabase Auth users, remaps the template UUIDs to the new real UUIDs,
and imports all 14 sheets preserving referential integrity.
"""

import math
import os
import pandas as pd
from backend.app.supabase_client import get_supabase_admin


def is_nan(val):
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    return False


def clean_row(row_dict):
    """Remove NaN values to prevent Supabase/JSON serialization errors."""
    return {k: v for k, v in row_dict.items() if not is_nan(v)}


def run_excel_seed(file_path: str):
    print(f"Loading Excel file: {file_path}")
    xls = pd.ExcelFile(file_path)

    sb = get_supabase_admin()

    # --- 1. Map Users and Create Auth Identities ---
    print("\n--- 1. Creating Auth Users ---")
    auth_df = xls.parse("auth_users_template")
    uuid_map = {}  # old_uuid -> new_uuid

    # We also need the profiles sheet to map the original generated UUID to
    # the new Auth UUID
    profiles_df = xls.parse("profiles")
    email_to_old_uuid = dict(zip(profiles_df["email"], profiles_df["id"]))

    for _, row in auth_df.iterrows():
        email = row["email"]
        password = row["password"]

        # Check if user already exists in auth
        try:
            old_uuid = email_to_old_uuid.get(email)
            if not old_uuid:
                print(f"Warning: {email} not found in profiles sheet.")
                continue

            # Does user exist in profiles table?
            existing = (
                sb.table("profiles")
                .select("id")
                .eq("email", email)
                .maybe_single()
                .execute()
            )
            if existing.data:  # type: ignore
                print(f"User {email} already exists in DB. Re-using ID.")
                uuid_map[old_uuid] = existing.data["id"]  # type: ignore
                continue

            # Create user in Auth
            print(f"Creating Auth User: {email}")
            user_auth = sb.auth.admin.create_user(
                {"email": email, "password": password, "email_confirm": True}
            )
            new_uuid = user_auth.user.id
            uuid_map[old_uuid] = new_uuid

        except Exception as e:
            print(f"Failed to create user {email}: {e}")

    print(f"\nCreated/Mapped {len(uuid_map)} Auth Users.")

    # Helper to remap UUIDs in a row
    def remap_uuids(row_dict, columns_to_remap):
        for col in columns_to_remap:
            if col in row_dict and not is_nan(row_dict[col]):
                old_val = row_dict[col]
                # If it's a known profile UUID, map it
                if old_val in uuid_map:
                    row_dict[col] = uuid_map[old_val]
        return row_dict

    # Define import sequence and fk columns to remap
    import_sequence = [
        ("reference_sources", []),
        ("zones", []),
        ("profiles", ["id"]),
        ("worker_profiles", ["profile_id", "preferred_zone_id"]),
        ("insurer_profiles", ["profile_id"]),
        ("worker_shifts", ["worker_profile_id", "zone_id"]),
        # table name: platform_worker_daily_stats
        ("daily_stats", ["worker_profile_id"]),
        # table name: platform_order_events
        (
            "order_events",
            ["worker_profile_id", "pickup_zone_id", "drop_zone_id"],
        ),
        ("trigger_events", ["zone_id"]),
        (
            "manual_claims",
            ["worker_profile_id", "trigger_event_id", "shift_id"],
        ),
        ("claim_evidence", ["claim_id"]),
        ("claim_reviews", ["claim_id", "reviewer_profile_id"]),
        ("payout_recommendations", ["claim_id"]),
    ]

    # Map sheet names to actual table names
    table_name_map = {
        "daily_stats": "platform_worker_daily_stats",
        "order_events": "platform_order_events",
    }

    print("\n--- 2. Importing Data Sheets ---")
    for sheet_name, fk_cols in import_sequence:
        if sheet_name not in xls.sheet_names:
            print(f"Sheet {sheet_name} not found, skipping.")
            continue

        table_name = table_name_map.get(sheet_name, sheet_name)
        df = xls.parse(sheet_name)

        # Replace NaN with None
        df = df.where(pd.notnull(df), None)

        records_to_insert = []
        for _, row in df.iterrows():
            row_dict = clean_row(row.to_dict())

            # Special handling for JSON column explanation_json
            if (
                sheet_name == "payout_recommendations"
                and "explanation_json" in row_dict
            ):
                import json

                if isinstance(row_dict["explanation_json"], str):
                    try:
                        row_dict["explanation_json"] = json.loads(
                            row_dict["explanation_json"]
                        )
                    except BaseException:
                        pass

            row_dict = remap_uuids(row_dict, fk_cols)
            records_to_insert.append(row_dict)

        if not records_to_insert:
            print(f"No records to insert for {table_name}.")
            continue

        # Insert in chunks of 100
        chunk_size = 100
        total_inserted = 0

        record_count = len(records_to_insert)
        print(f"Importing {record_count} records into '{table_name}'...")
        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i : i + chunk_size]
            try:
                # Upsert to handle re-runs gracefully (assuming 'id' or
                # 'ref_id' is present)
                sb.table(table_name).upsert(chunk).execute()
                total_inserted += len(chunk)
            except Exception as e:
                print(f"Error inserting chunk into {table_name}: {e}")
                # Print the failing chunk for debugging
                if "duplicate key value" not in str(e):
                    print("Failing chunk:", chunk[0])

        print(
            f"  -> Successfully imported {total_inserted} rows into {table_name}."
        )


if __name__ == "__main__":
    file_path = "d:/Celestius_DEVTrails_P1/TEMP_WILL_BE_DELETED/DEVTrails_Synthetic_Seed_Pack.xlsx"
    if not os.path.exists(file_path):
        print(f"Error: Could not find {file_path}")
    else:
        run_excel_seed(file_path)
