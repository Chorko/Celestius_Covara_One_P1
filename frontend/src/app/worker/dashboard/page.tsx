"use client"

import { useEffect, useState, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { backendGet } from '@/lib/backendApi'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import {
  ShieldCheck,
  CloudRain,
  AlertTriangle,
  IndianRupee,
  Activity,
  TrendingUp,
  MapPin,
  Truck,
  Sparkles,
  Zap,
  ClipboardList,
} from 'lucide-react'
import AnimatedCounter from '@/components/AnimatedCounter'
import Skeleton from '@/components/Skeleton'

interface ClaimStatusRow {
  claim_status: string
}

interface ClaimsSummaryResponse {
  claims: ClaimStatusRow[]
}

export default function WorkerDashboard() {
  const { profile } = useUserStore()
  const supabase = createClient()

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [workerDetails, setWorkerDetails] = useState<any>(null)
  const [stats, setStats] = useState<any[]>([])
  const [activeTriggers, setActiveTriggers] = useState<any[]>([])
  const [policyQuote, setPolicyQuote] = useState<any>(null)
  const [claimCounts, setClaimCounts] = useState<{ pending: number; approved: number; rejected: number; total: number }>({ pending: 0, approved: 0, rejected: 0, total: 0 })
  /* eslint-enable @typescript-eslint/no-explicit-any */
  const [activating, setActivating] = useState(false)
  const [activationMsg, setActivationMsg] = useState<string | null>(null)
  const [dashboardError, setDashboardError] = useState<string | null>(null)
  // Per-section loading flags for progressive rendering
  const [workerLoading, setWorkerLoading] = useState(true)
  const [claimsLoading, setClaimsLoading] = useState(true)
  const [quoteLoading, setQuoteLoading] = useState(true)

   
  const loadDashboardData = useCallback(async () => {
    const controller = new AbortController()
    const tid = setTimeout(() => controller.abort(), 10000)

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let wData: any = null
    try {
      const { data, error: wError } = await supabase
        .from('worker_profiles')
        .select('*, zones(zone_name)')
        .eq('profile_id', profile!.id)
        .abortSignal(controller.signal)
        .single()

      clearTimeout(tid)

      if (wError) {
        if (wError.code === 'PGRST205' || wError.message?.toLowerCase().includes('schema')) {
          setDashboardError('Database not set up — run SQL migration files 01–07 in the Supabase SQL Editor, then try again.')
        } else {
          setDashboardError(wError.message)
        }
        setWorkerLoading(false)
        setClaimsLoading(false)
        setQuoteLoading(false)
        return
      }
      wData = data
      setWorkerDetails(wData)
      setWorkerLoading(false)
    } catch (e: unknown) {
      clearTimeout(tid)
      if (controller.signal.aborted || (e instanceof Error && e.name === 'AbortError')) {
        setDashboardError('Cannot reach Supabase — request timed out. Check your network or try refreshing.')
      } else {
        setDashboardError(e instanceof Error ? e.message : 'Failed to load dashboard')
      }
      setWorkerLoading(false)
      setClaimsLoading(false)
      setQuoteLoading(false)
      return
    }

    // ── Fetch remaining sections in parallel so each updates immediately ──
    await Promise.allSettled([
      // Stats + Triggers
      (async () => {
        try {
          const { data: statsData } = await supabase
            .from('platform_worker_daily_stats')
            .select('stat_date, gross_earnings_inr, completed_orders, gps_consistency_score')
            .eq('worker_profile_id', wData.profile_id)
            .order('stat_date', { ascending: true })
            .limit(14)
          setStats(statsData || [])
        } catch(e) { console.error('Could not fetch dashboard stats', e) }

        if (wData?.preferred_zone_id) {
          try {
            const { data: tData } = await supabase
              .from('trigger_events')
              .select('*')
              .eq('zone_id', wData.preferred_zone_id)
              .order('started_at', { ascending: false })
              .limit(5)
            setActiveTriggers(tData || [])
          } catch(e) { console.error('Could not fetch triggers', e) }
        }
      })(),

      // Claims summary — per-section loading
      (async () => {
        try {
          const response = await backendGet<ClaimsSummaryResponse>(supabase, '/claims/')
          const claimData = response.claims || []

          if (claimData) {
            const pending = claimData.filter(c => ['submitted', 'soft_hold_verification', 'fraud_escalated_review'].includes(c.claim_status)).length
            const approved = claimData.filter(c => ['approved', 'auto_approved', 'paid'].includes(c.claim_status)).length
            const rejected = claimData.filter(c => ['rejected', 'post_approval_flagged'].includes(c.claim_status)).length
            setClaimCounts({ pending, approved, rejected, total: claimData.length })
          }
        } catch (e) { console.error('Could not load claim counts', e) }
        finally { setClaimsLoading(false) }
      })(),

      // Policy quote — per-section loading
      (async () => {
        try {
          let observed_weekly_gross: number | null = null
          try {
            const { data: recentStats } = await supabase
              .from('platform_worker_daily_stats')
              .select('gross_earnings_inr')
              .eq('worker_profile_id', wData.profile_id)
              .order('stat_date', { ascending: false })
              .limit(7)
            if (recentStats && recentStats.length >= 3) {
              const totalGross = recentStats.reduce((s, r) => s + (r.gross_earnings_inr || 0), 0)
              observed_weekly_gross = Math.round((totalGross / recentStats.length) * 6)
            }
          } catch { /* fallback below */ }

          const fallback_weekly_gross = Math.round((wData.avg_hourly_income_inr || 0) * 8 * 6)
          const weekly_gross = observed_weekly_gross ?? fallback_weekly_gross
          const B = Math.round(weekly_gross * 0.70)
          const raw_cap = Math.round(B * 0.75)
          const payout_cap = Math.min(raw_cap, 10000)
          const cityFactor: Record<string, number> = { Mumbai: 1.3, Delhi: 1.2, Bangalore: 1.25 }
          const C = cityFactor[wData.city] ?? 1.0
          const E = wData.trust_score ?? 0.8
          setPolicyQuote({
            weekly_premium_inr: Math.round(B * 0.035 * E * C),
            max_payout_cap_inr: payout_cap,
            observed_weekly_gross: weekly_gross,
            B, E: Math.round(E * 100) / 100, C,
          })
        } catch(e) { console.error('Could not compute policy quote', e) }
        finally { setQuoteLoading(false) }
      })(),
    ])
  }, [supabase, profile])

  useEffect(() => {
    if (!profile) return
    loadDashboardData()
  }, [profile, loadDashboardData])

  const activatePolicy = async () => {
    setActivating(true)
    setActivationMsg(null)
    // Simulate a payment processing delay (demo platform — no real backend needed)
    await new Promise(resolve => setTimeout(resolve, 1800))
    setActivating(false)
    setActivationMsg('Coverage Active!')
  }

  const totalEarnings = stats.reduce((sum, s) => sum + (s.gross_earnings_inr || 0), 0)
  const avgDailyOrders = stats.length
    ? Math.round(stats.reduce((sum, s) => sum + (s.completed_orders || 0), 0) / stats.length)
    : 0
  const avgGpsScore = stats.length
    ? Math.round(stats.reduce((sum, s) => sum + (s.gps_consistency_score || 0), 0) / stats.length * 100)
    : '--'

  if (dashboardError && !workerDetails) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="card p-8 max-w-md w-full text-center space-y-4">
          <AlertTriangle size={32} style={{ color: 'var(--warning)' }} className="mx-auto" />
          <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>Dashboard unavailable</p>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{dashboardError}</p>
        </div>
      </div>
    )
  }

  if (workerLoading) {
    return (
      <div className="min-h-screen page-mesh">
        <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-6">
          {/* Header skeleton */}
          <section className="animate-fade-in-up">
            <Skeleton width="280px" height="2.5rem" className="mb-3" />
            <Skeleton width="320px" height="0.875rem" />
          </section>
          {/* KPI skeletons */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="card p-5 space-y-3">
                <Skeleton width="40px" height="40px" />
                <Skeleton width="100px" height="1.75rem" />
                <Skeleton width="80px" height="0.625rem" />
              </div>
            ))}
          </section>
          {/* Claims Summary skeleton */}
          <section className="section-enter">
            <div className="card p-5 space-y-3">
              <Skeleton width="180px" height="1rem" />
              <Skeleton width="100%" height="10px" className="rounded-full" />
              <div className="flex gap-4">
                <Skeleton width="80px" height="0.75rem" />
                <Skeleton width="80px" height="0.75rem" />
                <Skeleton width="80px" height="0.75rem" />
              </div>
            </div>
          </section>
          {/* Streetwise Cover skeleton */}
          <section className="section-enter">
            <div className="card p-6 md:p-8" style={{ borderLeft: '3px solid var(--accent)' }}>
              <div className="space-y-3">
                <Skeleton width="160px" height="1.25rem" />
                <Skeleton width="220px" height="2.5rem" />
                <Skeleton width="280px" height="0.75rem" />
                <Skeleton width="180px" height="2.5rem" className="mt-4" />
              </div>
            </div>
          </section>
          {/* Chart + Triggers skeleton */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 card p-6">
              <Skeleton width="160px" height="1.25rem" className="mb-4" />
              <Skeleton width="100%" height="288px" />
            </div>
            <div className="card p-6">
              <Skeleton width="140px" height="1.25rem" className="mb-4" />
              <div className="space-y-3">
                {[1,2,3].map(i => <Skeleton key={i} width="100%" height="70px" />)}
              </div>
            </div>
          </section>
        </div>
      </div>
    )
  }

  const kpiCards = [
    { icon: <IndianRupee size={20} style={{ color: 'var(--success)' }} />, value: totalEarnings, prefix: '₹', label: 'Total Earnings (14d)', delay: 'delay-100', accent: 'var(--success)' },
    { icon: <ClipboardList size={20} style={{ color: 'var(--accent)' }} />, value: avgDailyOrders, prefix: '', label: 'Avg Daily Orders', delay: 'delay-200', accent: 'var(--accent)' },
    { icon: <Activity size={20} style={{ color: 'var(--info)' }} />, value: typeof avgGpsScore === 'number' ? avgGpsScore : 0, prefix: '', suffix: '%', label: 'GPS Score', delay: 'delay-300', accent: 'var(--info)' },
    { icon: <Sparkles size={20} style={{ color: 'var(--warning)' }} />, value: workerDetails.trust_score ? Math.round(workerDetails.trust_score * 100) : 0, prefix: '', suffix: '%', label: 'Trust Score', delay: 'delay-400', accent: 'var(--warning)' },
  ]

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-6">

        {/* ===== HEADER ===== */}
        <section className="animate-fade-in-up">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
                Welcome back, <span style={{ color: 'var(--accent)' }}>{profile?.full_name}</span>
              </h1>
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                Here is your performance snapshot and coverage status.
              </p>
            </div>

            <div className="card px-4 py-2.5 flex flex-wrap items-center gap-4 text-sm">
              <span className="flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
                <MapPin size={14} style={{ color: 'var(--accent)' }} />
                {workerDetails.city} &middot; {workerDetails.zones?.zone_name}
              </span>
              <span className="flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
                <Truck size={14} style={{ color: 'var(--info)' }} />
                {workerDetails.platform_name} &middot; {workerDetails.vehicle_type}
              </span>
              <span className="flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
                <Activity size={14} style={{ color: 'var(--warning)' }} />
                Trust&nbsp;<strong style={{ color: 'var(--text-primary)' }}>{workerDetails.trust_score}</strong>
              </span>
            </div>
          </div>
        </section>

        {/* ===== KPI CARDS ===== */}
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {kpiCards.map((c, i) => (
            <div key={i} className={`card p-5 flex flex-col gap-3 animate-fade-in-up ${c.delay}`} style={{ borderLeft: `3px solid ${c.accent}` }}>
              <div className="p-2 w-fit rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>{c.icon}</div>
              <span className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                <AnimatedCounter value={c.value} prefix={c.prefix} suffix={c.suffix || ''} />
              </span>
              <span className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{c.label}</span>
            </div>
          ))}
        </section>

        {/* ===== CLAIMS SUMMARY ===== */}
        <section className="section-enter">
          <div className="card p-5">
            {claimsLoading ? (
              <div className="space-y-3">
                <Skeleton width="180px" height="1rem" />
                <Skeleton width="100%" height="10px" className="rounded-full" />
                <div className="flex gap-4">
                  <Skeleton width="80px" height="0.75rem" />
                  <Skeleton width="80px" height="0.75rem" />
                  <Skeleton width="80px" height="0.75rem" />
                </div>
              </div>
            ) : claimCounts.total === 0 ? null : (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}>
                    <ClipboardList size={16} /> My Claims Summary
                  </h2>
                  <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{claimCounts.total} total</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 flex rounded-lg overflow-hidden h-2.5" style={{ background: 'var(--bg-tertiary)' }}>
                    {claimCounts.approved > 0 && (
                      <div className="h-full transition-all" style={{ width: `${(claimCounts.approved / claimCounts.total) * 100}%`, background: 'var(--success)' }} />
                    )}
                    {claimCounts.pending > 0 && (
                      <div className="h-full transition-all" style={{ width: `${(claimCounts.pending / claimCounts.total) * 100}%`, background: 'var(--warning)' }} />
                    )}
                    {claimCounts.rejected > 0 && (
                      <div className="h-full transition-all" style={{ width: `${(claimCounts.rejected / claimCounts.total) * 100}%`, background: 'var(--danger)' }} />
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-4 mt-3 text-xs">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: 'var(--success)' }} />
                    <span style={{ color: 'var(--text-tertiary)' }}>Approved</span>
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{claimCounts.approved}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: 'var(--warning)' }} />
                    <span style={{ color: 'var(--text-tertiary)' }}>Pending</span>
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{claimCounts.pending}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: 'var(--danger)' }} />
                    <span style={{ color: 'var(--text-tertiary)' }}>Rejected</span>
                    <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{claimCounts.rejected}</span>
                  </span>
                </div>
              </>
            )}
          </div>
        </section>

        {/* ===== COVERAGE QUOTE ===== */}
        <section className="section-enter">
          {quoteLoading ? (
            <div className="card p-6 md:p-8" style={{ borderLeft: '3px solid var(--accent)' }}>
              <div className="space-y-3">
                <Skeleton width="160px" height="1.25rem" />
                <Skeleton width="220px" height="2.5rem" />
                <Skeleton width="280px" height="0.75rem" />
                <Skeleton width="180px" height="2.5rem" className="mt-4" />
              </div>
            </div>
          ) : policyQuote ? (
            <div className="card p-6 md:p-8" style={{ borderLeft: '3px solid var(--accent)' }}>
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                <div className="space-y-3 flex-1">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={20} style={{ color: 'var(--accent)' }} />
                    <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Streetwise Cover</h2>
                  </div>
                  <div className="flex flex-wrap items-baseline gap-6">
                    <div>
                      <span className="text-3xl font-bold" style={{ color: 'var(--accent)' }}>₹{policyQuote.weekly_premium_inr}</span>
                      <span className="text-sm ml-1" style={{ color: 'var(--text-tertiary)' }}>/ week</span>
                    </div>
                    <div>
                      <span className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>₹{policyQuote.max_payout_cap_inr?.toLocaleString('en-IN')}</span>
                      <span className="text-sm ml-1" style={{ color: 'var(--text-tertiary)' }}>max payout</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {policyQuote.observed_weekly_gross != null && (
                      <span className="badge-info">Weekly Gross ≈ ₹{policyQuote.observed_weekly_gross?.toLocaleString('en-IN')}</span>
                    )}
                    {policyQuote.max_payout_cap_inr != null && (
                      <span className="badge-success">Max Payout ₹{policyQuote.max_payout_cap_inr?.toLocaleString('en-IN')}</span>
                    )}
                    <span className="badge-purple">IRDAI Micro-Insurance Plan</span>
                  </div>
                </div>
                <div className="md:w-56 flex-shrink-0">
                  {activationMsg ? (
                    <div className="w-full py-3 text-center font-semibold rounded-lg flex items-center justify-center gap-2" style={{ background: 'var(--success-muted)', color: 'var(--success)', border: '1px solid var(--success)' }}>
                      <ShieldCheck size={18} /> {activationMsg}
                    </div>
                  ) : (
                    <button onClick={activatePolicy} disabled={activating} className="btn-primary w-full py-3 text-base flex items-center justify-center gap-2">
                      <Zap size={18} />
                      {activating ? 'Activating...' : 'Activate Coverage'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </section>

        {/* ===== CHART + TRIGGERS ===== */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Earnings Chart */}
          <div className="lg:col-span-2 card p-6">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                  <TrendingUp size={18} style={{ color: 'var(--success)' }} />
                  14-Day Earnings
                </h2>
                <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                  Gross earnings trajectory from platform stats
                </p>
              </div>
            </div>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats}>
                  <defs>
                    <linearGradient id="earningsGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" vertical={false} />
                  <XAxis dataKey="stat_date" stroke="var(--text-tertiary)" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} tickFormatter={(v) => v.split('-')[2]} axisLine={false} tickLine={false} />
                  <YAxis stroke="var(--text-tertiary)" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} tickFormatter={(v) => `₹${v}`} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-secondary)', borderRadius: '8px', color: 'var(--text-primary)', boxShadow: 'var(--shadow-lg)' }}
                    itemStyle={{ color: 'var(--accent)' }}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Area type="monotone" dataKey="gross_earnings_inr" name="Gross (INR)" stroke="var(--accent)" strokeWidth={2} fill="url(#earningsGrad)" dot={{ r: 3, fill: 'var(--accent)', strokeWidth: 0 }} activeDot={{ r: 5, stroke: 'var(--accent)', strokeWidth: 2, fill: 'var(--bg-primary)' }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Zone Triggers */}
          <div className="card p-6 flex flex-col animate-fade-in-up delay-400">
            <div className="mb-5">
              <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <CloudRain size={18} style={{ color: 'var(--accent)' }} />
                Zone Trigger Alerts
              </h2>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Recent risks in your zone</p>
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto max-h-[340px] pr-1">
              {activeTriggers.length === 0 ? (
                <div className="p-6 text-center rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                  <CloudRain size={28} className="mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
                  <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No active triggers right now.</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Your zone is clear.</p>
                </div>
              ) : (
                activeTriggers.map((t) => (
                  <div key={t.id} className="p-4 rounded-lg transition-colors" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="pulse-live w-3 h-3 inline-block" />
                        <span className={t.severity_band === 'claim' ? 'badge-warning' : t.severity_band === 'escalation' ? 'badge-danger' : 'badge-info'}>
                          {t.severity_band}
                        </span>
                      </div>
                      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                        {new Date(t.started_at).toLocaleDateString()}
                      </span>
                    </div>
                    <h3 className="font-medium text-sm leading-snug" style={{ color: 'var(--text-secondary)' }}>
                      {t.trigger_code.replaceAll('_', ' ')}
                    </h3>
                    <p className="text-xs mt-1.5 flex items-center gap-1" style={{ color: 'var(--text-tertiary)' }}>
                      <AlertTriangle size={11} />
                      {t.official_threshold_label || t.product_threshold_value}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
