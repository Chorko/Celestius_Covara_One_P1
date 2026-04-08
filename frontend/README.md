# Frontend — Dashboards & Worker Experience

> The frontend makes the entire insurance journey understandable for two personas: **gig workers** and **insurer operations reviewers**. The UI is not just for beauty — it is part of the explanation layer for judges.

---

## Engineering Snapshot (2026-04-05)

- Admin dashboard now includes a live `ZoneRiskMap` (`Leaflet`) with active-trigger overlays and DBSCAN suspicious-claim cluster visualization.
- Frontend API integration remains role-token based, now paired with stronger backend protections (rate limits, security headers, signed mobile context verification).
- Event operations endpoints (`/events/outbox/*`, `/events/consumers/*`) are available for insurer/admin observability and dead-letter requeue workflows.
- Dependency updates include `leaflet` and `@types/leaflet` for map rendering support.

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
| SSR middleware route protection | ✅ Implemented (`frontend/src/middleware.ts` — Edge-level Supabase session check, blocks `/worker/*` and `/admin/*` for unauthenticated users) |

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
| Worker Rewards | `/worker/rewards` | Coin balance, transaction history, weekly check-in, discount/free-week redemption | ✅ Implemented |
| Pricing & Plans | `/worker/pricing` | Essential (₹3,000/week) / Plus (₹4,500/week) plan comparison, weekly premium calculation, plan activation | ✅ Implemented |

### Admin/Insurer Side

| Page | Route | What it shows | Status |
|------|-------|--------------|--------|
| Admin Dashboard | `/admin/dashboard` | KPI cards (total claims, avg payout, fraud rate), trigger mix pie chart | ✅ Implemented |
| Review Queue | `/admin/reviews` | Claim list, claim detail panel with payout recommendation, fraud scores, Gemini AI summary, approve/hold/reject/flag actions, 8 claim states | ✅ Implemented |
| Event Operations | `/admin/events` | Outbox status, consumer status, dead-letter triage, relay/requeue controls | ✅ Implemented |
| Trigger Engine | `/admin/triggers` | Live trigger feed, mock trigger injection for testing | ✅ Implemented |
| User Management | `/admin/users` | Worker lookup by name/email/city, worker profile viewer with trust score and claim history | ✅ Implemented |

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

Route protection operates at two levels:
1. **Edge (SSR):** `frontend/src/middleware.ts` intercepts all requests to `/worker/*` and `/admin/*` using `@supabase/ssr`. Runs at the Next.js Edge runtime before the page renders — no client-side flash.
2. **Client-side:** `worker/layout.tsx` and `admin/layout.tsx` perform a secondary session check and role validation after hydration, redirecting unauthorized users with full state-awareness.

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
| Rewards balance | `GET /rewards/balance` |
| Rewards history | `GET /rewards/history` |
| Weekly check-in | `POST /rewards/check-in` |
| Redeem discount | `POST /rewards/redeem/discount` |
| Redeem free week | `POST /rewards/redeem/free-week` |
| Admin KPI metrics | `GET /analytics/summary` |
| Admin claim list | `GET /claims` |
| Claim detail + AI summary | `GET /claims/{id}` |
| Review action | `POST /claims/{id}/review` |
| Post-approval fraud flag | `POST /claims/{id}/flag` |
| Outbox status | `GET /events/outbox/status` |
| Outbox relay | `POST /events/outbox/relay` |
| Outbox dead-letter list/requeue | `GET /events/outbox/dead-letter`, `POST /events/outbox/dead-letter/requeue` |
| Consumer status | `GET /events/consumers/status` |
| Consumer dead-letter list/requeue | `GET /events/consumers/dead-letter`, `POST /events/consumers/dead-letter/requeue` |
| Live trigger feed | `GET /triggers/live` |
| Mock trigger injection | `POST /triggers/inject` |
