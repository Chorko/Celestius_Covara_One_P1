-- ══════════════════════════════════════════════════════════════════════
-- DEVTrails — Claim State Machine Expansion (Gap §4.2)
-- ══════════════════════════════════════════════════════════════════════
-- Purpose:
--   Expand claim_status to support soft-hold verification and
--   fraud-escalated review paths. No partial payouts — soft hold
--   delays money movement until verification finishes.
--
-- WARNING: Do NOT apply this file if you have already applied
--   13_unified_extensions.sql. That file supersedes this script and
--   running both will cause duplicate-object errors.
--
-- New states:
--   submitted               → initial intake
--   auto_approved            → parametric auto-approve (low fraud)
--   soft_hold_verification   → silent verification, no money movement
--   fraud_escalated_review   → fraud-driven human/AI review
--   approved                 → verified and cleared for payout
--   rejected                 → denied (with 48h appeal window)
--   paid                     → payout executed
--   post_approval_flagged    → later fraud evidence appeared (Gap §4.4)
-- ══════════════════════════════════════════════════════════════════════

-- Drop the old check constraint first
alter table public.manual_claims
  drop constraint if exists manual_claims_claim_status_check;

-- ── DATA MIGRATION ──────────────────────────────────────────────────
-- Convert existing rows from old states to new states BEFORE
-- adding the new constraint. Order matters:
--   'held'      → 'soft_hold_verification'  (was a generic hold)
--   'approved'  → 'auto_approved'           (for trigger-auto claims)
--   'submitted' → 'submitted'               (unchanged)
--   'rejected'  → 'rejected'                (unchanged)
--   'paid'      → 'paid'                    (unchanged)
-- ────────────────────────────────────────────────────────────────────
update public.manual_claims
  set claim_status = 'soft_hold_verification'
  where claim_status = 'held';

-- Only convert 'approved' → 'auto_approved' for trigger-auto claims.
-- Manually-reviewed approvals (claim_mode = 'manual') remain as 'approved',
-- preserving the semantic difference between auto-triggered and admin-approved.
update public.manual_claims
  set claim_status = 'auto_approved'
  where claim_status = 'approved'
    and claim_mode = 'trigger_auto';

-- Now add the expanded constraint (all old values are converted)
alter table public.manual_claims
  add constraint manual_claims_claim_status_check
  check (claim_status in (
    'submitted',
    'auto_approved',
    'soft_hold_verification',
    'fraud_escalated_review',
    'approved',
    'rejected',
    'paid',
    'post_approval_flagged'
  ));

-- Also expand the review decision options
alter table public.claim_reviews
  drop constraint if exists claim_reviews_decision_check;

alter table public.claim_reviews
  add constraint claim_reviews_decision_check
  check (decision in (
    'approve',
    'hold',
    'escalate',
    'reject',
    'flag_post_approval',
    'downgrade_trust'
  ));

comment on constraint manual_claims_claim_status_check on public.manual_claims is
  'Expanded claim lifecycle: submitted → auto_approved/soft_hold/fraud_escalated → approved → paid. '
  'post_approval_flagged for Gap §4.4 post-payout fraud detection.';

-- Reload PostgREST schema cache
notify pgrst, 'reload schema';
