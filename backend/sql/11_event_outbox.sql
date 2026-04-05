-- ============================================================================
-- Covara One - Event Outbox
-- Durable domain-event queue for retryable event delivery.
-- ============================================================================

CREATE TABLE IF NOT EXISTS event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    event_key TEXT,
    event_source TEXT NOT NULL,
    event_payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | failed | processed
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    CONSTRAINT event_outbox_status_chk CHECK (status IN ('pending', 'failed', 'processed'))
);

CREATE INDEX IF NOT EXISTS idx_event_outbox_status_available
    ON event_outbox (status, available_at, created_at);

CREATE INDEX IF NOT EXISTS idx_event_outbox_event_type
    ON event_outbox (event_type, created_at DESC);

ALTER TABLE event_outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY event_outbox_select_admin ON event_outbox
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM profiles
            WHERE profiles.id = auth.uid()
              AND profiles.role = 'insurer_admin'
        )
    );

-- Service-role writes bypass RLS; explicit policy included for completeness.
CREATE POLICY event_outbox_insert_service ON event_outbox
    FOR INSERT WITH CHECK (true);

CREATE POLICY event_outbox_update_service ON event_outbox
    FOR UPDATE USING (true) WITH CHECK (true);
