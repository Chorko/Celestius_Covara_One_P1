-- Covara Post-Run Hotfix: persist_claim_with_outbox RPC contract
-- Apply after SUPABASE_UNIFIED_ENTERPRISE_PATCH_2026_04_12.sql

begin;

-- Remove incompatible overload introduced by older patch drafts.
drop function if exists public.persist_claim_with_outbox(
  uuid,
  uuid,
  uuid,
  numeric,
  numeric,
  text,
  numeric,
  numeric,
  jsonb,
  text[],
  text[],
  jsonb
);

create or replace function public.persist_claim_with_outbox(
  p_claim jsonb,
  p_payout jsonb,
  p_event_type text,
  p_event_key text default null,
  p_event_source text default 'backend',
  p_event_payload jsonb default '{}'::jsonb
)
returns table (
  claim_id uuid,
  event_id uuid,
  duplicate_skipped boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_claim_id uuid;
  v_event_id uuid := gen_random_uuid();
  v_constraint_name text;
begin
  begin
    insert into public.manual_claims (
      worker_profile_id,
      trigger_event_id,
      claim_mode,
      claim_reason,
      stated_lat,
      stated_lng,
      claimed_at,
      shift_id,
      claim_status,
      assignment_state,
      review_due_at
    )
    values (
      (p_claim ->> 'worker_profile_id')::uuid,
      nullif(p_claim ->> 'trigger_event_id', '')::uuid,
      coalesce(nullif(p_claim ->> 'claim_mode', ''), 'manual'),
      coalesce(nullif(p_claim ->> 'claim_reason', ''), 'Claim submitted'),
      nullif(p_claim ->> 'stated_lat', '')::numeric,
      nullif(p_claim ->> 'stated_lng', '')::numeric,
      coalesce(nullif(p_claim ->> 'claimed_at', '')::timestamptz, now()),
      nullif(p_claim ->> 'shift_id', '')::uuid,
      coalesce(nullif(p_claim ->> 'claim_status', ''), 'submitted'),
      coalesce(nullif(p_claim ->> 'assignment_state', ''), 'unassigned'),
      nullif(p_claim ->> 'review_due_at', '')::timestamptz
    )
    returning id into v_claim_id;
  exception when unique_violation then
    get stacked diagnostics v_constraint_name = constraint_name;

    if coalesce(p_claim ->> 'claim_mode', '') = 'trigger_auto'
       and (
         coalesce(v_constraint_name, '') ilike '%idx_unique_worker_event%'
         or coalesce(v_constraint_name, '') ilike '%worker_profile_id%trigger_event%'
       )
    then
      return query
      select null::uuid, null::uuid, true;
      return;
    end if;

    raise;
  end;

  insert into public.payout_recommendations (
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
  values (
    v_claim_id,
    coalesce(nullif(p_payout ->> 'covered_weekly_income_b', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'claim_probability_p', '')::numeric, 0.15),
    coalesce(nullif(p_payout ->> 'severity_score_s', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'exposure_score_e', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'confidence_score_c', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'fraud_holdback_fh', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'outlier_uplift_u', '')::numeric, 1.0),
    coalesce(nullif(p_payout ->> 'payout_cap', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'expected_payout', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'gross_premium', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'recommended_payout', '')::numeric, 0),
    coalesce(p_payout -> 'explanation_json', '{}'::jsonb),
    coalesce(nullif(p_payout ->> 'created_at', '')::timestamptz, now())
  );

  insert into public.event_outbox (
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
  values (
    v_event_id,
    p_event_type,
    p_event_key,
    coalesce(nullif(p_event_source, ''), 'backend'),
    coalesce(p_event_payload, '{}'::jsonb) || jsonb_build_object('claim_id', v_claim_id),
    'pending',
    0,
    now(),
    now()
  );

  return query
  select v_claim_id, v_event_id, false;
end;
$$;

grant execute on function public.persist_claim_with_outbox(
  jsonb,
  jsonb,
  text,
  text,
  text,
  jsonb
) to authenticated, service_role;

notify pgrst, 'reload schema';

commit;
