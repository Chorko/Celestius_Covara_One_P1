-- ══════════════════════════════════════════════════════════════════════
-- Covara One — Migration 14
-- Review Assignment + SLA workflow foundations
-- ══════════════════════════════════════════════════════════════════════

alter table public.manual_claims
  add column if not exists assigned_reviewer_profile_id uuid references public.insurer_profiles(profile_id) on delete set null;

alter table public.manual_claims
  add column if not exists assignment_state text;

alter table public.manual_claims
  add column if not exists assigned_at timestamptz;

alter table public.manual_claims
  add column if not exists review_due_at timestamptz;

alter table public.manual_claims
  add column if not exists first_reviewed_at timestamptz;

alter table public.manual_claims
  add column if not exists last_reviewed_at timestamptz;

alter table public.manual_claims
  add column if not exists escalated_at timestamptz;

alter table public.manual_claims
  add column if not exists escalation_reason text;

update public.manual_claims
set assignment_state = 'unassigned'
where assignment_state is null;

alter table public.manual_claims
  alter column assignment_state set default 'unassigned';

alter table public.manual_claims
  drop constraint if exists manual_claims_assignment_state_check;

alter table public.manual_claims
  add constraint manual_claims_assignment_state_check
  check (assignment_state in (
    'unassigned', 'assigned', 'in_review', 'escalated', 'resolved'
  ));

create index if not exists idx_manual_claims_assigned_reviewer
  on public.manual_claims(assigned_reviewer_profile_id)
  where assigned_reviewer_profile_id is not null;

create index if not exists idx_manual_claims_review_due
  on public.manual_claims(review_due_at)
  where claim_status in ('submitted', 'soft_hold_verification', 'fraud_escalated_review');
