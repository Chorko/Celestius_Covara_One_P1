-- ============================================================================
-- Covara One - Event Reliability Hardening
-- Adds transactional claim+outbox persistence and consumer idempotency ledger.
-- ============================================================================

-- Extend outbox status model with dead-letter support.
ALTER TABLE public.event_outbox
    ADD COLUMN IF NOT EXISTS dead_lettered_at TIMESTAMPTZ;

ALTER TABLE public.event_outbox
    DROP CONSTRAINT IF EXISTS event_outbox_status_chk;

ALTER TABLE public.event_outbox
    ADD CONSTRAINT event_outbox_status_chk
    CHECK (status IN ('pending', 'failed', 'processed', 'dead_letter'));

CREATE INDEX IF NOT EXISTS idx_event_outbox_dead_letter
    ON public.event_outbox (status, dead_lettered_at DESC)
    WHERE status = 'dead_letter';


-- Idempotency ledger for event consumers.
CREATE TABLE IF NOT EXISTS public.event_consumer_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consumer_name TEXT NOT NULL,
    event_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    event_key TEXT,
    status TEXT NOT NULL DEFAULT 'processing', -- processing | succeeded | failed
    attempt_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    last_error TEXT,
    result_payload JSONB,
    CONSTRAINT event_consumer_ledger_status_chk
        CHECK (status IN ('processing', 'succeeded', 'failed')),
    CONSTRAINT event_consumer_ledger_consumer_event_uniq
        UNIQUE (consumer_name, event_id)
);

CREATE INDEX IF NOT EXISTS idx_event_consumer_ledger_status
    ON public.event_consumer_ledger (consumer_name, status, last_attempt_at DESC);

CREATE INDEX IF NOT EXISTS idx_event_consumer_ledger_event
    ON public.event_consumer_ledger (event_id, consumer_name);

ALTER TABLE public.event_consumer_ledger ENABLE ROW LEVEL SECURITY;

CREATE POLICY event_consumer_ledger_select_admin ON public.event_consumer_ledger
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM public.profiles
            WHERE profiles.id = auth.uid()
              AND profiles.role = 'insurer_admin'
        )
    );

-- Service-role writes bypass RLS; explicit policies included for completeness.
CREATE POLICY event_consumer_ledger_insert_service ON public.event_consumer_ledger
    FOR INSERT WITH CHECK (true);

CREATE POLICY event_consumer_ledger_update_service ON public.event_consumer_ledger
    FOR UPDATE USING (true) WITH CHECK (true);


-- Atomic write: claim + payout recommendation + outbox event.
CREATE OR REPLACE FUNCTION public.persist_claim_with_outbox(
    p_claim JSONB,
    p_payout JSONB,
    p_event_type TEXT,
    p_event_key TEXT DEFAULT NULL,
    p_event_source TEXT DEFAULT 'backend',
    p_event_payload JSONB DEFAULT '{}'::JSONB
)
RETURNS TABLE (
    claim_id UUID,
    event_id UUID,
    duplicate_skipped BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_claim_id UUID;
    v_event_id UUID := gen_random_uuid();
    v_constraint_name TEXT;
BEGIN
    BEGIN
        INSERT INTO public.manual_claims (
            worker_profile_id,
            trigger_event_id,
            claim_mode,
            claim_reason,
            stated_lat,
            stated_lng,
            claimed_at,
            shift_id,
            claim_status
        )
        VALUES (
            (p_claim ->> 'worker_profile_id')::UUID,
            NULLIF(p_claim ->> 'trigger_event_id', '')::UUID,
            COALESCE(NULLIF(p_claim ->> 'claim_mode', ''), 'manual'),
            COALESCE(NULLIF(p_claim ->> 'claim_reason', ''), 'Claim submitted'),
            NULLIF(p_claim ->> 'stated_lat', '')::NUMERIC,
            NULLIF(p_claim ->> 'stated_lng', '')::NUMERIC,
            COALESCE(NULLIF(p_claim ->> 'claimed_at', '')::TIMESTAMPTZ, now()),
            NULLIF(p_claim ->> 'shift_id', '')::UUID,
            COALESCE(NULLIF(p_claim ->> 'claim_status', ''), 'submitted')
        )
        RETURNING id INTO v_claim_id;
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS v_constraint_name = CONSTRAINT_NAME;

        IF COALESCE(p_claim ->> 'claim_mode', '') = 'trigger_auto'
           AND (
               COALESCE(v_constraint_name, '') ILIKE '%idx_unique_worker_event%'
               OR COALESCE(v_constraint_name, '') ILIKE '%worker_profile_id%trigger_event%'
           )
        THEN
            RETURN QUERY
            SELECT NULL::UUID, NULL::UUID, TRUE;
            RETURN;
        END IF;

        RAISE;
    END;

    INSERT INTO public.payout_recommendations (
        claim_id,
        covered_weekly_income_b,
        claim_probability_p,
        severity_score_s,
        exposure_score_e,
        confidence_score_c,
        fraud_holdback_fh,
        outlier_uplift_u,
        payout_cap,
        expected_payout,
        gross_premium,
        recommended_payout,
        explanation_json,
        created_at
    )
    VALUES (
        v_claim_id,
        COALESCE(NULLIF(p_payout ->> 'covered_weekly_income_b', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'claim_probability_p', '')::NUMERIC, 0.15),
        COALESCE(NULLIF(p_payout ->> 'severity_score_s', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'exposure_score_e', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'confidence_score_c', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'fraud_holdback_fh', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'outlier_uplift_u', '')::NUMERIC, 1.0),
        COALESCE(NULLIF(p_payout ->> 'payout_cap', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'expected_payout', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'gross_premium', '')::NUMERIC, 0),
        COALESCE(NULLIF(p_payout ->> 'recommended_payout', '')::NUMERIC, 0),
        COALESCE(p_payout -> 'explanation_json', '{}'::JSONB),
        COALESCE(NULLIF(p_payout ->> 'created_at', '')::TIMESTAMPTZ, now())
    );

    INSERT INTO public.event_outbox (
        event_id,
        event_type,
        event_key,
        event_source,
        event_payload,
        status,
        retry_count,
        available_at,
        created_at
    )
    VALUES (
        v_event_id,
        p_event_type,
        p_event_key,
        COALESCE(NULLIF(p_event_source, ''), 'backend'),
        COALESCE(p_event_payload, '{}'::JSONB) || jsonb_build_object('claim_id', v_claim_id),
        'pending',
        0,
        now(),
        now()
    );

    RETURN QUERY
    SELECT v_claim_id, v_event_id, FALSE;
END;
$$;

GRANT EXECUTE ON FUNCTION public.persist_claim_with_outbox(JSONB, JSONB, TEXT, TEXT, TEXT, JSONB)
    TO authenticated, service_role;
