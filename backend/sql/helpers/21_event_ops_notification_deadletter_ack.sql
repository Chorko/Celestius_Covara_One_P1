-- ============================================================================
-- 21_event_ops_notification_deadletter_ack.sql
--
-- Purpose:
--   Clear noisy Event Ops dead-letter errors caused by external notification
--   provider rate limits (Twilio trial quota / HTTP 429).
--
-- Safe behavior:
--   - Only touches auto_claim_notification_consumer rows
--   - Only rows currently in dead_letter
--   - Only when last_error indicates provider rate limiting
--   - Marks them succeeded with explicit acknowledgement payload
--
-- Run in Supabase SQL Editor when Event Ops shows large dead-letter counts from
-- notification rate limits.
-- ============================================================================

begin;

update public.event_consumer_ledger
set
  status = 'succeeded',
  processed_at = coalesce(processed_at, now()),
  dead_lettered_at = null,
  last_error = 'acknowledged: non-production notification provider limitation',
  result_payload = coalesce(result_payload, '{}'::jsonb) || jsonb_build_object(
    'acknowledged', true,
    'reason', 'notification_provider_limitation_non_production',
    'source', 'sql_event_ops_cleanup',
    'acknowledged_at', now()
  )
where consumer_name = 'auto_claim_notification_consumer'
  and status = 'dead_letter'
  and (
    coalesce(last_error, '') ilike '%HTTP 429%'
    or coalesce(last_error, '') ilike '%status code: 429%'
    or coalesce(last_error, '') ilike '%too many requests%'
    or coalesce(last_error, '') ilike '%rate limit%'
    or coalesce(last_error, '') ilike '%exceeded the 50%'
    or coalesce(last_error, '') ilike '%21608%'
    or coalesce(last_error, '') ilike '%trial account%'
    or coalesce(last_error, '') ilike '%whatsapp sandbox%'
  );

commit;

-- Verification
select
  status,
  count(*) as cnt
from public.event_consumer_ledger
group by status
order by status;

select
  count(*) as remaining_notification_dead_letters
from public.event_consumer_ledger
where consumer_name = 'auto_claim_notification_consumer'
  and status = 'dead_letter';
