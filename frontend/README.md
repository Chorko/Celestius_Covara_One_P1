# Frontend — Dashboards & Worker Experience

> The frontend makes the entire insurance journey understandable for two personas: **gig workers** and **insurer operations reviewers**. The UI is not just for beauty — it is part of the explanation layer for judges.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| Next.js 16 App Router setup | ✅ Implemented |
| Supabase Auth integration (Google OAuth + email/password) | ✅ Implemented |
| Role-based routing (worker/admin) | ✅ Implemented |
| Worker dashboard (profile, chart, alerts, quote) | ✅ Implemented |
| Worker claims page (submit + history) | ✅ Implemented |
| Admin dashboard (KPI cards, trigger mix chart) | ✅ Implemented |
| Admin review queue (claim detail, AI summary, approve/reject) | ✅ Implemented |
| Admin trigger engine (live feed, mock injection) | ✅ Implemented |
| Client-side route guards | ✅ Implemented |
| SSR middleware route protection | 📋 Planned |

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Framework | Next.js 16 (App Router) | Server components, file-based routing, SSR-ready |
| Styling | Tailwind CSS | Rapid prototyping, consistent design tokens |
| Charts | Recharts | React-native charting for earnings and analytics |
| Auth | Supabase SSR | Cookie-based auth with server-side session exchange |
| Icons | Lucide React | Consistent icon set |

---

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000

---

## Page Inventory

### Worker Side

| Page | Route | What it shows | Status |
|------|-------|--------------|--------|
| Login/Home | `/` | Google OAuth + email login, role detection, auto-redirect | ✅ Implemented |
| OAuth Callback | `/auth/callback` | Exchange auth code for session, error handling | ✅ Implemented |
| Worker Dashboard | `/worker/dashboard` | Profile summary, 14-day earnings chart, zone trigger alerts, policy quote with activation | ✅ Implemented |
| Worker Claims | `/worker/claims` | Claim submission form (GPS + photo evidence upload), claim history with 8 status states | ✅ Implemented |
| Pricing & Plans | `/worker/pricing` | Essential (₹3,000/week, core parametric cover, 5-layer fraud, standard 24-48h processing) / Plus (₹4,500/week, T15 composite events, Gemini AI reports, priority <12h queue, proportional multi-day, regional fast-lane) plan comparison, weekly premium calculation, plan activation | ✅ Implemented |

### Admin/Insurer Side

| Page | Route | What it shows | Status |
|------|-------|--------------|--------|
| Admin Dashboard | `/admin/dashboard` | KPI cards (total claims, avg payout, fraud rate), trigger mix pie chart | ✅ Implemented |
| Review Queue | `/admin/reviews` | Claim list, worker profile card (name, email, city, platform, trust score), claim detail panel with payout recommendation, fraud scores, Gemini AI summary, approve/hold/reject/escalate actions, post-approval flag with trust penalty (−0.15) and legal escalation (−0.30), 8 claim states | ✅ Implemented |
| Trigger Engine | `/admin/triggers` | Live trigger feed, mock trigger injection for testing | ✅ Implemented |

---

## Auth Flow

```
Google OAuth / Email Login
  → Supabase Auth → session cookie
  → /auth/callback → exchangeCodeForSession
  → Fetch profile role from profiles table
  → Role-based redirect:
      worker → /worker/dashboard
      insurer → /admin/dashboard
```

Route guards in `worker/layout.tsx` and `admin/layout.tsx` check session and role client-side, redirecting unauthorized users.

---

## API Integration

All backend calls use `fetch()` with the Supabase access token in the `Authorization` header:

```typescript
const { data: session } = await supabase.auth.getSession()
const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/endpoint`, {
  headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
})
```

| Frontend Feature | Backend Endpoint |
|-----------------|-----------------|
| Worker profile + stats | `GET /workers/profile`, `GET /workers/stats` |
| Earnings chart data | `GET /workers/stats` |
| Zone trigger alerts | `GET /triggers/live` |
| Policy quote | `GET /policies/quote` |
| Policy activation | `POST /policies/activate` |
| Claim submission | `POST /claims` + Supabase Storage upload |
| Claim history | `GET /claims` |
| Admin KPI metrics | `GET /analytics/summary` |
| Admin claim list | `GET /claims` |
| Claim detail + AI summary | `GET /claims/{id}` |
| Review action | `POST /claims/{id}/review` |
| Post-approval fraud flag | `POST /claims/{id}/flag` |
| Live trigger feed | `GET /triggers/live` |
| Mock trigger injection | `POST /triggers/inject` |
