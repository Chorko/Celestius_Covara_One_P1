-- ============================================================================
-- Covara One - Consumer Dead-Letter Hardening
-- Extends consumer ledger with dead-letter state and timestamps.
-- ============================================================================

ALTER TABLE public.event_consumer_ledger
    ADD COLUMN IF NOT EXISTS dead_lettered_at TIMESTAMPTZ;

ALTER TABLE public.event_consumer_ledger
    DROP CONSTRAINT IF EXISTS event_consumer_ledger_status_chk;

ALTER TABLE public.event_consumer_ledger
    ADD CONSTRAINT event_consumer_ledger_status_chk
    CHECK (status IN ('processing', 'succeeded', 'failed', 'dead_letter'));

CREATE INDEX IF NOT EXISTS idx_event_consumer_ledger_dead_letter
    ON public.event_consumer_ledger (consumer_name, dead_lettered_at DESC)
    WHERE status = 'dead_letter';
