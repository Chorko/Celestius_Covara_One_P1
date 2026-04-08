"use client"

import { useCallback, useEffect, useMemo, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { backendGet, backendPost, BackendApiError } from '@/lib/backendApi'
import {
  Coins,
  Gift,
  Ticket,
  CalendarCheck,
  TrendingUp,
  Clock,
  RefreshCw,
  Sparkles,
  AlertTriangle,
} from 'lucide-react'

interface RewardsBalanceResponse {
  balance: number
  redemption_options: {
    discount: {
      coins_required: number
      value_inr: number
      available: boolean
    }
    free_week: {
      coins_required: number
      available: boolean
    }
  }
}

interface RewardsTransaction {
  id: string
  activity: string
  coins: number
  description: string
  created_at: string
}

interface RewardsHistoryResponse {
  balance: number
  transactions: RewardsTransaction[]
}

function toDisplayActivity(activity: string): string {
  return activity.replaceAll('_', ' ').replace(/\b\w/g, (ch) => ch.toUpperCase())
}

function formatError(error: unknown): string {
  if (error instanceof BackendApiError) {
    if (error.status === 401) {
      return 'Session expired. Please sign in again.'
    }

    return error.detail
  }

  return error instanceof Error ? error.message : 'Request failed'
}

export default function WorkerRewardsPage() {
  const supabase = createClient()
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<'checkin' | 'discount' | 'free-week' | null>(null)
  const [balanceData, setBalanceData] = useState<RewardsBalanceResponse | null>(null)
  const [history, setHistory] = useState<RewardsTransaction[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadRewards = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [balanceResp, historyResp] = await Promise.all([
        backendGet<RewardsBalanceResponse>(supabase, '/rewards/balance'),
        backendGet<RewardsHistoryResponse>(supabase, '/rewards/history?limit=30'),
      ])

      setBalanceData(balanceResp)
      setHistory(historyResp.transactions || [])
    } catch (e: unknown) {
      setError(formatError(e))
    } finally {
      setLoading(false)
    }
  }, [supabase])

  useEffect(() => {
    void loadRewards()
  }, [loadRewards])

  const streakHint = useMemo(() => {
    const loginEntries = history.filter((tx) => tx.activity === 'weekly_login')
    return loginEntries.length
  }, [history])

  const runAction = async (action: 'checkin' | 'discount' | 'free-week') => {
    setActionLoading(action)
    setMessage(null)
    setError(null)

    const endpoint =
      action === 'checkin'
        ? '/rewards/check-in'
        : action === 'discount'
          ? '/rewards/redeem/discount'
          : '/rewards/redeem/free-week'

    try {
      const result = await backendPost<Record<string, unknown>>(supabase, endpoint)

      if (action === 'checkin') {
        const awarded = result.awarded
        setMessage(awarded === false ? 'Weekly check-in already claimed.' : 'Check-in successful. Coins credited.')
      } else if (action === 'discount') {
        setMessage('Discount redeemed successfully.')
      } else {
        setMessage('Free week redeemed successfully.')
      }

      await loadRewards()
    } catch (e: unknown) {
      setError(formatError(e))
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen page-mesh">
        <div className="p-6 md:p-10 pb-28 max-w-5xl mx-auto space-y-5">
          <div className="card p-6">Loading rewards...</div>
        </div>
      </div>
    )
  }

  const balance = balanceData?.balance ?? 0
  const discountOption = balanceData?.redemption_options.discount
  const freeWeekOption = balanceData?.redemption_options.free_week

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-5xl mx-auto space-y-6">
        <section className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-1">
            <div className="p-2.5 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
              <Coins size={22} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>Rewards & Coins</h1>
              <p className="text-sm mt-0.5" style={{ color: 'var(--text-tertiary)' }}>Earn coins for healthy behavior and redeem insurance benefits.</p>
            </div>
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
            <Sparkles size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--success)' }} />
            <p className="text-sm" style={{ color: 'var(--success)' }}>{message}</p>
          </div>
        )}

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card p-5" style={{ borderLeft: '3px solid var(--accent)' }}>
            <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Current Balance</p>
            <p className="text-3xl font-bold mt-2" style={{ color: 'var(--text-primary)' }}>{balance}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>coins available</p>
          </div>

          <div className="card p-5" style={{ borderLeft: '3px solid var(--warning)' }}>
            <div className="flex items-center gap-2 mb-2">
              <Ticket size={16} style={{ color: 'var(--warning)' }} />
              <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Discount Goal</p>
            </div>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              {discountOption?.coins_required ?? 100} coins for ₹{discountOption?.value_inr ?? 5} off
            </p>
            <p className="text-xs mt-2" style={{ color: discountOption?.available ? 'var(--success)' : 'var(--text-tertiary)' }}>
              {discountOption?.available ? 'Redeem available now' : 'Keep earning to unlock'}
            </p>
          </div>

          <div className="card p-5" style={{ borderLeft: '3px solid var(--success)' }}>
            <div className="flex items-center gap-2 mb-2">
              <Gift size={16} style={{ color: 'var(--success)' }} />
              <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Free Week Goal</p>
            </div>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              {freeWeekOption?.coins_required ?? 500} coins for a free week
            </p>
            <p className="text-xs mt-2" style={{ color: freeWeekOption?.available ? 'var(--success)' : 'var(--text-tertiary)' }}>
              {freeWeekOption?.available ? 'Redeem available now' : 'Build streak and clean claims'}
            </p>
          </div>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            type="button"
            className="card p-5 text-left transition-all"
            onClick={() => runAction('checkin')}
            disabled={actionLoading !== null}
            style={{ opacity: actionLoading === null || actionLoading === 'checkin' ? 1 : 0.6 }}
          >
            <div className="flex items-center justify-between mb-2">
              <CalendarCheck size={18} style={{ color: 'var(--accent)' }} />
              {actionLoading === 'checkin' && <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--text-tertiary)' }} />}
            </div>
            <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>Weekly Check-In</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Claim your periodic coin bonus.</p>
          </button>

          <button
            type="button"
            className="card p-5 text-left transition-all"
            onClick={() => runAction('discount')}
            disabled={!discountOption?.available || actionLoading !== null}
            style={{ opacity: discountOption?.available && actionLoading === null ? 1 : 0.6 }}
          >
            <div className="flex items-center justify-between mb-2">
              <TrendingUp size={18} style={{ color: 'var(--warning)' }} />
              {actionLoading === 'discount' && <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--text-tertiary)' }} />}
            </div>
            <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>Redeem Discount</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Use coins for a premium discount.</p>
          </button>

          <button
            type="button"
            className="card p-5 text-left transition-all"
            onClick={() => runAction('free-week')}
            disabled={!freeWeekOption?.available || actionLoading !== null}
            style={{ opacity: freeWeekOption?.available && actionLoading === null ? 1 : 0.6 }}
          >
            <div className="flex items-center justify-between mb-2">
              <Gift size={18} style={{ color: 'var(--success)' }} />
              {actionLoading === 'free-week' && <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--text-tertiary)' }} />}
            </div>
            <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>Redeem Free Week</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Convert coins into one free coverage week.</p>
          </button>
        </section>

        <section className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Clock size={16} style={{ color: 'var(--text-tertiary)' }} /> Recent Transactions
            </h2>
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Weekly check-ins tracked: {streakHint}
            </span>
          </div>

          {history.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No rewards activity yet.</p>
          ) : (
            <div className="space-y-2">
              {history.map((tx) => {
                const positive = tx.coins >= 0
                return (
                  <div key={tx.id} className="rounded-lg p-3" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{toDisplayActivity(tx.activity)}</p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{tx.description || 'Reward activity'}</p>
                        <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                          {new Date(tx.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                      <span className="text-sm font-semibold" style={{ color: positive ? 'var(--success)' : 'var(--danger)' }}>
                        {positive ? '+' : ''}{tx.coins}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
