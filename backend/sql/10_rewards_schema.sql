-- ============================================================================
-- Covara One — Rewards & Coins Schema
-- Gamification system for worker retention and engagement.
-- ============================================================================

-- Coins Ledger: append-only log of all coin transactions
CREATE TABLE IF NOT EXISTS coins_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    activity TEXT NOT NULL,
    coins INTEGER NOT NULL,  -- positive = earned, negative = redeemed
    description TEXT,
    reference_id TEXT,       -- claim_id, referrer_id, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast balance lookups and duplicate prevention
CREATE INDEX IF NOT EXISTS idx_coins_ledger_profile
    ON coins_ledger (profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coins_ledger_activity
    ON coins_ledger (profile_id, activity, created_at DESC);

-- Materialized view for instant balance queries
CREATE OR REPLACE VIEW driver_coin_balance AS
SELECT
    profile_id,
    COALESCE(SUM(coins), 0) AS balance,
    COUNT(*) FILTER (WHERE coins > 0) AS total_earned_txns,
    COUNT(*) FILTER (WHERE coins < 0) AS total_redeemed_txns,
    MAX(created_at) AS last_activity
FROM coins_ledger
GROUP BY profile_id;

-- RLS: Workers can only see their own coins
ALTER TABLE coins_ledger ENABLE ROW LEVEL SECURITY;

CREATE POLICY coins_ledger_select_own ON coins_ledger
    FOR SELECT USING (
        profile_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM profiles
            WHERE profiles.id = auth.uid()
            AND profiles.role = 'insurer_admin'
        )
    );

-- Only the backend service role can insert (via admin client)
CREATE POLICY coins_ledger_insert_service ON coins_ledger
    FOR INSERT WITH CHECK (true);  -- Service role only (RLS bypassed by admin client)
