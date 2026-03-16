# DEVTrails — Open Issues & Diagnosis

_Last updated: 2026-03-16_

---

## CRITICAL — "Database error querying schema" on every login

### Status
**Unresolved.** Blocks all app functionality.

### Symptom
Every login attempt (worker or admin) fails immediately after authentication with:

```
Database error querying schema
```

The login itself succeeds (Supabase Auth returns a valid session), but the
subsequent `profiles` table query fails, the session is signed out, and the
error is displayed to the user.

### Root Cause — Confirmed

The `db_verification_results.txt` verification run returned **PGRST205 for
every custom table**, including `profiles`, `worker_profiles`, `zones`,
`manual_claims`, all of them:

```
profiles:                  PGRST205 — Could not find the table 'public.profiles' in the schema cache
worker_profiles:           PGRST205 — Could not find the table 'public.worker_profiles' in the schema cache
insurer_profiles:          PGRST205 — ...
zones:                     PGRST205 — ...
worker_shifts:             PGRST205 — ...
platform_worker_daily_stats: PGRST205 — ...
platform_order_events:     PGRST205 — ...
trigger_events:            PGRST205 — ...
manual_claims:             PGRST205 — ...
claim_evidence:            PGRST205 — ...
claim_reviews:             PGRST205 — ...
payout_recommendations:    PGRST205 — ...
reference_sources:         PGRST205 — ...
```

**PGRST205 means the table does not exist in the PostgREST schema cache.**
This is not a permissions issue. The tables themselves have never been created
in the live Supabase project.

### Why Previous Fixes Failed

The following were tried and did NOT fix it because they address the wrong layer:
- `NOTIFY pgrst, 'reload schema'` — tells PostgREST to reload, but there is nothing to load
- `GRANT USAGE ON SCHEMA public` — grants access to tables that don't exist
- `07_grant_patch.sql` — same as above; permissions fix for an empty schema

There is nothing a permissions fix can do if the tables were never created.

### Fix Required

All SQL migration files must be run in order in the **Supabase SQL Editor**
(`https://supabase.com/dashboard/project/<project-ref>/sql`).

Run each file completely, in this order, one at a time. Wait for each to
succeed before running the next:

| Step | File | What it does |
|------|------|--------------|
| 1 | `backend/sql/01_supabase_platform_schema.sql` | Creates all custom tables + GRANTs + NOTIFY |
| 2 | `backend/sql/02_auth_triggers.sql` | Creates `handle_new_user` trigger for auto-profile creation |
| 3 | `backend/sql/03_rls_policies.sql` | Adds Row Level Security policies |
| 4 | `backend/sql/04_storage_policies.sql` | Storage bucket policies |
| 5 | `backend/sql/06_synthetic_seed.sql` | Seeds demo users, zones, claims, payout data + NOTIFY |
| 6 | `backend/sql/07_grant_patch.sql` | Final grant + NOTIFY pass (run last as a safety net) |

> Skip `05_rls_rollback.sql` — that is a rollback/undo script, not a setup script.

### Verification After Applying

After running all files, verify in the SQL Editor:

```sql
-- Should return 13+ rows
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Should return 2 rows (worker and admin demo accounts)
SELECT id, email FROM auth.users WHERE email IN ('worker@demo.com', 'admin@demo.com');

-- Should return 2 rows
SELECT id, role, full_name FROM public.profiles;
```

Then reload the app at `http://localhost:3000` and attempt login with:
- Worker: `worker@demo.com` / `demo1234`
- Admin:  `admin@demo.com`  / `demo1234`

### Known Sub-issue: Auth Users

The `db_verification_results.txt` also shows:
```
Auth Users Error: 'list' object has no attribute 'users'
```
This is a Python script bug in `verify_db.py` — the admin SDK response format
changed. It does not affect the app. Auth users can be checked via the
Supabase Dashboard → Authentication → Users.

---

## MINOR — `verify_db.py` Auth Users query crashes

### Status
Low priority. Does not affect the application.

### Symptom
`TEMP_WILL_BE_DELETED/verify_db.py` throws `AttributeError: 'list' object has no attribute 'users'`
when enumerating auth users via the admin SDK.

### Cause
The Supabase Python admin client `list_users()` returns a list directly in
newer SDK versions, not an object with a `.users` attribute.

### Fix
Change `response.users` to just `response` in `verify_db.py`, or use:
```python
users = supabase_admin.auth.admin.list_users()
for user in users:
    print(user.email)
```

---

## ENVIRONMENT

- Supabase project URL: `https://aptgddoivrzpvpmydfyh.supabase.co`
- Frontend: Next.js 16 (Turbopack), `http://localhost:3000`
- Demo credentials once DB is seeded:
  - Worker: `worker@demo.com` / `demo1234`
  - Admin:  `admin@demo.com`  / `demo1234`
