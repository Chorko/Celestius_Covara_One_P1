-- ============================================================
-- 18_performance_indexes.sql
-- Covara One — Performance Indexes
--
-- Run AFTER all migration and seed scripts.
-- Adds indexes for the most critical query patterns identified
-- during the Phase 1 technical audit.
--
-- Safe to re-run (CREATE INDEX IF NOT EXISTS).
-- ============================================================

-- ── Claims lookup by worker (dashboard, worker history) ──
CREATE INDEX IF NOT EXISTS idx_manual_claims_worker
  ON public.manual_claims (worker_profile_id);

-- ── Claims filtered by status (pipeline counts, queue views) ──
CREATE INDEX IF NOT EXISTS idx_manual_claims_status
  ON public.manual_claims (claim_status);

-- ── Claims ordered by submission time (recent activity) ──
CREATE INDEX IF NOT EXISTS idx_manual_claims_claimed_at
  ON public.manual_claims (claimed_at DESC);

-- ── Trigger events by zone (zone risk queries) ──
CREATE INDEX IF NOT EXISTS idx_trigger_events_zone
  ON public.trigger_events (zone_id);

-- ── Trigger events by start time (live/active queries) ──
CREATE INDEX IF NOT EXISTS idx_trigger_events_started
  ON public.trigger_events (started_at DESC);

-- ── Trigger events: active triggers (ended_at IS NULL) ──
CREATE INDEX IF NOT EXISTS idx_trigger_events_active
  ON public.trigger_events (ended_at)
  WHERE ended_at IS NULL;

-- ── Policies by worker (active coverage lookup) ──
CREATE INDEX IF NOT EXISTS idx_policies_worker
  ON public.policies (worker_profile_id);

-- ── Policies by status (active count queries) ──
CREATE INDEX IF NOT EXISTS idx_policies_status
  ON public.policies (status);

-- ── Payout requests by claim (traceability) ──
CREATE INDEX IF NOT EXISTS idx_payout_requests_claim
  ON public.payout_requests (claim_id);

-- ── Worker shifts by worker (shift overlap queries) ──
CREATE INDEX IF NOT EXISTS idx_worker_shifts_worker
  ON public.worker_shifts (worker_profile_id);

-- ── Daily stats by worker + date (earnings/activity queries) ──
CREATE INDEX IF NOT EXISTS idx_platform_stats_worker_date
  ON public.platform_worker_daily_stats (worker_profile_id, stat_date);

-- ── Evidence by claim (claim detail view) ──
CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim
  ON public.claim_evidence (claim_id);

-- ── Reviews by claim (review history) ──
CREATE INDEX IF NOT EXISTS idx_claim_reviews_claim
  ON public.claim_reviews (claim_id);

-- ── Audit events by entity (entity history) ──
CREATE INDEX IF NOT EXISTS idx_audit_events_entity
  ON public.audit_events (entity_type, entity_id);

-- ── Event outbox: pending events for relay ──
CREATE INDEX IF NOT EXISTS idx_event_outbox_pending
  ON public.event_outbox (status)
  WHERE status = 'pending';

-- ── Coins ledger by profile (rewards balance) ──
CREATE INDEX IF NOT EXISTS idx_coins_ledger_profile
  ON public.coins_ledger (profile_id);

-- ── Validated regional incidents by city (incident dashboard) ──
CREATE INDEX IF NOT EXISTS idx_validated_incidents_city
  ON public.validated_regional_incidents (city);
