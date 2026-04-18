"use client"

import { useCallback, useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { backendGet, backendPost, BackendApiError } from '@/lib/backendApi'
import {
  Activity,
  AlertTriangle,
  Database,
  RefreshCw,
  RotateCcw,
  Server,
  ShieldAlert,
} from 'lucide-react'

interface OutboxStatusResponse {
  counts: Record<string, number>
}

interface ConsumerStatusResponse {
  counts: Record<string, number>
}

interface OutboxDeadLetterEvent {
  event_id: string
  event_type: string
  event_source: string
  retry_count: number
  last_error?: string
  dead_lettered_at?: string
}

interface ConsumerDeadLetterEntry {
  id: string
  consumer_name: string
  event_type: string
  attempt_count: number
  last_error?: string
  dead_lettered_at?: string
}

interface OutboxDeadLetterResponse {
  events: OutboxDeadLetterEvent[]
}

interface ConsumerDeadLetterResponse {
  entries: ConsumerDeadLetterEntry[]
}

interface RelayResponse {
  fetched: number
  processed: number
  failed: number
  dead_lettered: number
}

function formatError(error: unknown): string {
  if (error instanceof BackendApiError) {
    if (error.status === 401) {
      return 'Session expired. Please sign in again.'
    }

    if (error.status === 403) {
      return 'Insurer admin role required for event operations.'
    }

    return error.detail
  }

  return error instanceof Error ? error.message : 'Request failed'
}

function countValue(counts: Record<string, number> | null, key: string): number {
  if (!counts) {
    return 0
  }

  return Number(counts[key] || 0)
}

export default function AdminEventsPage() {
  const supabase = createClient()

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [outboxCounts, setOutboxCounts] = useState<Record<string, number> | null>(null)
  const [consumerCounts, setConsumerCounts] = useState<Record<string, number> | null>(null)
  const [outboxDeadLetters, setOutboxDeadLetters] = useState<OutboxDeadLetterEvent[]>([])
  const [consumerDeadLetters, setConsumerDeadLetters] = useState<ConsumerDeadLetterEntry[]>([])

  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const loadEventOps = useCallback(async () => {
    setRefreshing(true)
    setError(null)

    try {
      const [outboxStatus, consumerStatus, outboxDead, consumerDead] = await Promise.all([
        backendGet<OutboxStatusResponse>(supabase, '/events/outbox/status'),
        backendGet<ConsumerStatusResponse>(supabase, '/events/consumers/status'),
        backendGet<OutboxDeadLetterResponse>(supabase, '/events/outbox/dead-letter?limit=30'),
        backendGet<ConsumerDeadLetterResponse>(supabase, '/events/consumers/dead-letter?limit=30'),
      ])

      setOutboxCounts(outboxStatus.counts || {})
      setConsumerCounts(consumerStatus.counts || {})
      setOutboxDeadLetters(outboxDead.events || [])
      setConsumerDeadLetters(consumerDead.entries || [])
    } catch (e: unknown) {
      setError(formatError(e))
    } finally {
      setRefreshing(false)
      setLoading(false)
    }
  }, [supabase])

  useEffect(() => {
    void loadEventOps()
  }, [loadEventOps])

  const runAction = async (action: 'relay' | 'requeue-outbox' | 'requeue-consumers') => {
    setActionLoading(action)
    setError(null)
    setMessage(null)

    try {
      if (action === 'relay') {
        const relay = await backendPost<RelayResponse>(supabase, '/events/outbox/relay?limit=100')
        setMessage(`Relay complete: fetched=${relay.fetched}, processed=${relay.processed}, failed=${relay.failed}, dead_lettered=${relay.dead_lettered}`)
      } else if (action === 'requeue-outbox') {
        const result = await backendPost<{ selected: number; requeued: number }>(
          supabase,
          '/events/outbox/dead-letter/requeue?limit=100',
        )
        setMessage(`Outbox dead-letter requeue complete: ${result.requeued}/${result.selected}`)
      } else {
        const result = await backendPost<{ selected: number; ledger_requeued: number; outbox_requeued: number }>(
          supabase,
          '/events/consumers/dead-letter/requeue?limit=100',
        )
        setMessage(`Consumer dead-letter requeue complete: ledger=${result.ledger_requeued}, outbox=${result.outbox_requeued}, selected=${result.selected}`)
      }

      await loadEventOps()
    } catch (e: unknown) {
      setError(formatError(e))
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-6">
        <section className="animate-fade-in-up">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                <Database size={22} style={{ color: 'var(--accent)' }} />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>Event Operations</h1>
                <p className="text-sm mt-0.5" style={{ color: 'var(--text-tertiary)' }}>Outbox and consumer dead-letter triage + replay controls.</p>
              </div>
            </div>

            <button
              onClick={() => loadEventOps()}
              className="btn-secondary px-4 py-2 text-sm flex items-center gap-2"
              disabled={refreshing}
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </section>

        {error && (
          <div className="card p-4 flex items-start gap-2" style={{ background: 'var(--danger-muted)', border: '1px solid var(--danger)' }}>
            <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--danger)' }} />
            <p className="text-sm" style={{ color: 'var(--danger)' }}>{error}</p>
          </div>
        )}

        {message && (
          <div className="card p-4 flex items-start gap-2" style={{ background: 'var(--success-muted)', border: '1px solid var(--success)' }}>
            <Activity size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--success)' }} />
            <p className="text-sm" style={{ color: 'var(--success)' }}>{message}</p>
          </div>
        )}

        {loading ? (
          <div className="card p-6">Loading event operations...</div>
        ) : (
          <>
            <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
              <div className="card p-5" style={{ borderLeft: '3px solid var(--accent)' }}>
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Outbox Pending</p>
                <p className="text-2xl font-bold mt-2" style={{ color: 'var(--text-primary)' }}>{countValue(outboxCounts, 'pending')}</p>
              </div>
              <div className="card p-5" style={{ borderLeft: '3px solid var(--warning)' }}>
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Outbox Failed</p>
                <p className="text-2xl font-bold mt-2" style={{ color: 'var(--text-primary)' }}>{countValue(outboxCounts, 'failed')}</p>
              </div>
              <div className="card p-5" style={{ borderLeft: '3px solid var(--danger)' }}>
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Outbox Dead Letter</p>
                <p className="text-2xl font-bold mt-2" style={{ color: 'var(--text-primary)' }}>{countValue(outboxCounts, 'dead_letter')}</p>
              </div>
              <div className="card p-5" style={{ borderLeft: '3px solid var(--success)' }}>
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Outbox Processed</p>
                <p className="text-2xl font-bold mt-2" style={{ color: 'var(--success)' }}>{countValue(outboxCounts, 'processed')}</p>
              </div>
              <div className="card p-5" style={{ borderLeft: '3px solid var(--accent)' }}>
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Consumer Succeeded</p>
                <p className="text-2xl font-bold mt-2" style={{ color: 'var(--success)' }}>{countValue(consumerCounts, 'succeeded')}</p>
              </div>
              <div className="card p-5" style={{ borderLeft: '3px solid var(--info)' }}>
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Consumer Dead Letter</p>
                <p className="text-2xl font-bold mt-2" style={{ color: 'var(--text-primary)' }}>{countValue(consumerCounts, 'dead_letter')}</p>
              </div>
            </section>

            <section className="card p-5 space-y-3">
              <h2 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>Operations</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <button
                  type="button"
                  className="btn-secondary py-3 flex items-center justify-center gap-2"
                  onClick={() => runAction('relay')}
                  disabled={actionLoading !== null}
                >
                  {actionLoading === 'relay' ? <RefreshCw size={14} className="animate-spin" /> : <Server size={14} />}
                  Relay Pending Outbox
                </button>
                <button
                  type="button"
                  className="btn-secondary py-3 flex items-center justify-center gap-2"
                  onClick={() => runAction('requeue-outbox')}
                  disabled={actionLoading !== null}
                >
                  {actionLoading === 'requeue-outbox' ? <RefreshCw size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                  Requeue Outbox Dead Letters
                </button>
                <button
                  type="button"
                  className="btn-secondary py-3 flex items-center justify-center gap-2"
                  onClick={() => runAction('requeue-consumers')}
                  disabled={actionLoading !== null}
                >
                  {actionLoading === 'requeue-consumers' ? <RefreshCw size={14} className="animate-spin" /> : <ShieldAlert size={14} />}
                  Requeue Consumer Dead Letters
                </button>
              </div>
            </section>

            <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <div className="card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Outbox Dead Letters</h3>
                {outboxDeadLetters.length === 0 ? (
                  <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No outbox dead-letter events.</p>
                ) : (
                  <div className="space-y-2 max-h-[420px] overflow-auto pr-1">
                    {outboxDeadLetters.map((event) => (
                      <div key={event.event_id} className="rounded-lg p-3" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                        <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{event.event_type}</p>
                        <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>source: {event.event_source} | retries: {event.retry_count}</p>
                        <p className="text-[11px] mt-1" style={{ color: 'var(--danger)' }}>{event.last_error || 'No error detail'}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Consumer Dead Letters</h3>
                {consumerDeadLetters.length === 0 ? (
                  <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No consumer dead-letter entries.</p>
                ) : (
                  <div className="space-y-2 max-h-[420px] overflow-auto pr-1">
                    {consumerDeadLetters.map((entry) => (
                      <div key={entry.id} className="rounded-lg p-3" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                        <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{entry.consumer_name}</p>
                        <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>event: {entry.event_type} | attempts: {entry.attempt_count}</p>
                        <p className="text-[11px] mt-1" style={{ color: 'var(--danger)' }}>{entry.last_error || 'No error detail'}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
