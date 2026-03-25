"use client"

import { useEffect, useState, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import {
  ShieldCheck,
  CloudRain,
  AlertTriangle,
  IndianRupee,
  Activity,
  Navigation2,
  TrendingUp,
  MapPin,
  Truck,
  Sparkles,
  Zap,
  ClipboardList,
} from 'lucide-react'
import AnimatedCounter from '@/components/AnimatedCounter'
import Skeleton from '@/components/Skeleton'

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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
        return
      }
      wData = data
      setWorkerDetails(wData)
    } catch (e: unknown) {
      clearTimeout(tid)
      if (controller.signal.aborted || (e instanceof Error && e.name === 'AbortError')) {
        setDashboardError('Cannot reach Supabase — request timed out. Check your network or try refreshing.')
      } else {
        setDashboardError(e instanceof Error ? e.message : 'Failed to load dashboard')
      }
      return
    }

    // Fetch Daily Stats directly from Supabase
    try {
      const { data: statsData } = await supabase
        .from('platform_worker_daily_stats')
        .select('stat_date, gross_earnings_inr, completed_orders, gps_consistency_score')
        .eq('worker_profile_id', wData.profile_id)
        .order('stat_date', { ascending: true })
        .limit(14)
      setStats(statsData || [])
    } catch(e) { console.error("Could not fetch dashboard stats", e) }

    // Fetch live triggers using our backend route pattern if we want, or supabase direct for prep
    // Direct supabase fetch of recently active triggers in their zone
    if (wData?.preferred_zone_id) {
       const { data: tData } = await supabase
         .from('trigger_events')
         .select('*')
         .eq('zone_id', wData.preferred_zone_id)
         .order('started_at', { ascending: false })
         .limit(5)
       setActiveTriggers(tData || [])
    }

    // Fetch claim counts
    try {
      const { data: claimData } = await supabase
        .from('manual_claims')
        .select('claim_status')
        .eq('worker_profile_id', wData.profile_id)
      if (claimData) {
        const pending = claimData.filter(c => ['submitted', 'soft_hold_verification', 'fraud_escalated_review'].includes(c.claim_status)).length
        const approved = claimData.filter(c => ['approved', 'auto_approved', 'paid'].includes(c.claim_status)).length
        const rejected = claimData.filter(c => ['rejected', 'post_approval_flagged'].includes(c.claim_status)).length
        setClaimCounts({ pending, approved, rejected, total: claimData.length })
      }
    } catch (e) { console.error('Could not load claim counts', e) }

    // Compute policy quote inline from worker profile
    // Use actual weekly gross from daily stats if available, else fallback
    try {
      // Try observed weekly gross from the last 7 active days of stats
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
          // Normalize to 6-day week if we have fewer days
          observed_weekly_gross = Math.round((totalGross / recentStats.length) * 6)
        }
      } catch { /* fallback below */ }

      // Fallback: hourly × 8hrs × 6 days
      const fallback_weekly_gross = Math.round((wData.avg_hourly_income_inr || 0) * 8 * 6)
      const weekly_gross = observed_weekly_gross ?? fallback_weekly_gross

      // Covered weekly income = 70% of observed/estimated weekly gross
      const B = Math.round(weekly_gross * 0.70)
      // Payout cap = 75% of covered weekly income
      const raw_cap = Math.round(B * 0.75)
      // Sanity guard: cap at ₹10,000 for demo/synthetic flows
      const payout_cap = Math.min(raw_cap, 10000)

      const cityFactor: Record<string, number> = { Mumbai: 1.3, Delhi: 1.2, Bangalore: 1.25 }
      const C = cityFactor[wData.city] ?? 1.0
      const E = wData.trust_score ?? 0.8
      setPolicyQuote({
        weekly_premium_inr: Math.round(B * 0.035 * E * C),
        max_payout_cap_inr: payout_cap,
        observed_weekly_gross: weekly_gross,
        B,
        E: Math.round(E * 100) / 100,
        C,
      })
    } catch(e) { console.error("Could not compute policy quote", e) }
  }, [supabase, profile])

  useEffect(() => {
    if (!profile) return
    loadDashboardData()
  }, [profile, loadDashboardData])

  const activatePolicy = async () => {
    setActivating(true)
    try {
      const { data: session } = await supabase.auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/policies/activate`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
      })
      if (res.ok) {
        setActivationMsg("Coverage Active!")
      }
    } catch(e) { console.error("Activation failed", e) }
    setActivating(false)
  }

  /* ---- Derived stats ---- */
  const totalEarnings = stats.reduce((sum, s) => sum + (s.gross_earnings_inr || 0), 0)
  const avgDailyOrders = stats.length
    ? Math.round(stats.reduce((sum, s) => sum + (s.completed_orders || 0), 0) / stats.length)
    : 0
  const avgGpsScore = stats.length
    ? Math.round(stats.reduce((sum, s) => sum + (s.gps_consistency_score || 0), 0) / stats.length * 100)
    : '--'

  if (!workerDetails) {
    if (dashboardError) {
      return (
        <div className="min-h-screen gradient-mesh flex items-center justify-center p-4">
          <div className="glass-card p-8 max-w-md w-full text-center space-y-4">
            <AlertTriangle size={32} className="text-amber-400 mx-auto" />
            <p className="text-white font-semibold">Dashboard unavailable</p>
            <p className="text-neutral-400 text-sm leading-relaxed">{dashboardError}</p>
          </div>
        </div>
      )
    }
    return (
      <div className="min-h-screen gradient-mesh">
        <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-8">
          {/* Skeleton header */}
          <section className="animate-fade-in-up">
            <Skeleton width="280px" height="2.5rem" className="mb-3" />
            <Skeleton width="200px" height="0.875rem" />
          </section>
          {/* Skeleton KPI cards */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="glass-card p-5 space-y-3">
                <Skeleton width="40px" height="40px" />
                <Skeleton width="100px" height="1.75rem" />
                <Skeleton width="80px" height="0.625rem" />
              </div>
            ))}
          </section>
          {/* Skeleton chart + triggers */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 glass-card p-6">
              <Skeleton width="160px" height="1.25rem" className="mb-4" />
              <Skeleton width="100%" height="200px" />
            </div>
            <div className="glass-card p-6">
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

  return (
    <div className="min-h-screen gradient-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-8">

        {/* ===== HEADER SECTION ===== */}
        <section className="animate-fade-in-up">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            {/* Welcome text */}
            <div>
              <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
                Welcome back, <span className="text-emerald-400">{profile?.full_name}</span>
              </h1>
              <p className="text-neutral-400 text-sm">
                Here is your performance snapshot and coverage status.
              </p>
            </div>

            {/* Profile pill */}
            <div className="glass-card px-5 py-3 flex flex-wrap items-center gap-4 text-sm">
              <span className="flex items-center gap-1.5 text-neutral-300">
                <MapPin size={15} className="text-emerald-400" />
                {workerDetails.city} &middot; {workerDetails.zones?.zone_name}
              </span>
              <span className="flex items-center gap-1.5 text-neutral-300">
                <Truck size={15} className="text-blue-400" />
                {workerDetails.platform_name} &middot; {workerDetails.vehicle_type}
              </span>
              <span className="flex items-center gap-1.5 text-neutral-300">
                <Activity size={15} className="text-purple-400" />
                Trust&nbsp;<strong className="text-white">{workerDetails.trust_score}</strong>
              </span>
            </div>
          </div>
        </section>

        {/* ===== QUICK STATS ROW ===== */}
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              icon: <IndianRupee size={22} className="text-emerald-400" />,
              value: totalEarnings,
              prefix: '₹',
              label: 'Total Earnings (14d)',
              delay: 'delay-100',
            },
            {
              icon: <ClipboardList size={22} className="text-blue-400" />,
              value: avgDailyOrders,
              prefix: '',
              label: 'Avg Daily Orders',
              delay: 'delay-200',
            },
            {
              icon: <Navigation2 size={22} className="text-purple-400" />,
              value: typeof avgGpsScore === 'number' ? avgGpsScore : 0,
              prefix: '',
              suffix: '%',
              label: 'GPS Score',
              delay: 'delay-300',
            },
            {
              icon: <Sparkles size={22} className="text-amber-400" />,
              value: workerDetails.trust_score ? Math.round(workerDetails.trust_score * 100) : 0,
              prefix: '',
              suffix: '%',
              label: 'Trust Score',
              delay: 'delay-400',
            },
          ].map((card, i) => (
            <div
              key={i}
              className={`glass-card p-5 flex flex-col gap-3 animate-fade-in-up ${card.delay}`}
            >
              <div className="glass p-2 w-fit rounded-lg">{card.icon}</div>
              <span className="text-2xl font-bold text-white">
                <AnimatedCounter
                  value={card.value}
                  prefix={card.prefix}
                  suffix={card.suffix || ''}
                />
              </span>
              <span className="text-xs text-neutral-400 uppercase tracking-wider">{card.label}</span>
            </div>
          ))}
        </section>

        {/* ===== CLAIM STATUS SUMMARY ===== */}
        {claimCounts.total > 0 && (
          <section className="section-enter">
            <div className="glass-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider flex items-center gap-2">
                  <ClipboardList size={16} /> My Claims Summary
                </h2>
                <span className="text-xs text-neutral-500">{claimCounts.total} total</span>
              </div>
              <div className="flex items-center gap-3">
                {/* Status segments */}
                <div className="flex-1 flex rounded-lg overflow-hidden h-3">
                  {claimCounts.approved > 0 && (
                    <div
                      className="h-full transition-all"
                      style={{
                        width: `${(claimCounts.approved / claimCounts.total) * 100}%`,
                        background: 'linear-gradient(90deg, #10b981, #34d399)',
                      }}
                    />
                  )}
                  {claimCounts.pending > 0 && (
                    <div
                      className="h-full transition-all"
                      style={{
                        width: `${(claimCounts.pending / claimCounts.total) * 100}%`,
                        background: 'linear-gradient(90deg, #f59e0b, #fbbf24)',
                      }}
                    />
                  )}
                  {claimCounts.rejected > 0 && (
                    <div
                      className="h-full transition-all"
                      style={{
                        width: `${(claimCounts.rejected / claimCounts.total) * 100}%`,
                        background: 'linear-gradient(90deg, #ef4444, #f87171)',
                      }}
                    />
                  )}
                </div>
              </div>
              <div className="flex items-center gap-4 mt-3 text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  <span className="text-neutral-400">Approved</span>
                  <span className="font-semibold text-white">{claimCounts.approved}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  <span className="text-neutral-400">Pending</span>
                  <span className="font-semibold text-white">{claimCounts.pending}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-400" />
                  <span className="text-neutral-400">Rejected</span>
                  <span className="font-semibold text-white">{claimCounts.rejected}</span>
                </span>
              </div>
            </div>
          </section>
        )}

        {/* ===== COVERAGE QUOTE CARD ===== */}
        {policyQuote && (
          <section className="section-enter">
            <div className="glass-card glow-emerald p-6 md:p-8">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                {/* Left -- title + numbers */}
                <div className="space-y-3 flex-1">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={22} className="text-emerald-400" />
                    <h2 className="text-xl font-semibold text-white">Streetwise Cover</h2>
                  </div>

                  <div className="flex flex-wrap items-baseline gap-6">
                    <div>
                      <span className="text-3xl font-bold text-emerald-400">
                        ₹{policyQuote.weekly_premium_inr}
                      </span>
                      <span className="text-neutral-400 text-sm ml-1">/ week</span>
                    </div>
                    <div>
                      <span className="text-2xl font-bold text-white">
                        ₹{policyQuote.max_payout_cap_inr?.toLocaleString('en-IN')}
                      </span>
                      <span className="text-neutral-400 text-sm ml-1">max payout</span>
                    </div>
                  </div>

                  {/* Formula breakdown */}
                  <div className="flex flex-wrap gap-3 text-xs">
                    {policyQuote.B != null && (
                      <span className="badge badge-emerald">B (Base) = {policyQuote.B}</span>
                    )}
                    {policyQuote.E != null && (
                      <span className="badge badge-blue">E (Earnings) = {policyQuote.E}</span>
                    )}
                    {policyQuote.C != null && (
                      <span className="badge badge-purple">C (City) = {policyQuote.C}</span>
                    )}
                  </div>
                </div>

                {/* Right -- CTA */}
                <div className="md:w-56 flex-shrink-0">
                  {activationMsg ? (
                    <div className="w-full py-3 glass text-emerald-400 text-center font-semibold rounded-xl flex items-center justify-center gap-2 border border-emerald-500/30">
                      <ShieldCheck size={18} /> {activationMsg}
                    </div>
                  ) : (
                    <button
                      onClick={activatePolicy}
                      disabled={activating}
                      className="btn-primary w-full py-3 text-base flex items-center justify-center gap-2"
                    >
                      <Zap size={18} />
                      {activating ? 'Activating...' : 'Activate Coverage'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ===== CHART + TRIGGERS ROW ===== */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Earnings Chart -- 2/3 */}
          <div className="lg:col-span-2 glass-card p-6">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                  <TrendingUp size={20} className="text-emerald-400" />
                  14-Day Earnings
                </h2>
                <p className="text-xs text-neutral-500 mt-1">
                  Gross earnings trajectory from platform stats
                </p>
              </div>
            </div>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats}>
                  <defs>
                    <linearGradient id="earningsGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="50%" stopColor="#10b981" stopOpacity={0.1} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis
                    dataKey="stat_date"
                    stroke="#525252"
                    tick={{ fontSize: 11, fill: '#737373' }}
                    tickFormatter={(v) => v.split('-')[2]}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#525252"
                    tick={{ fontSize: 11, fill: '#737373' }}
                    tickFormatter={(v) => `₹${v}`}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(10,10,10,0.92)',
                      backdropFilter: 'blur(16px)',
                      borderColor: 'rgba(16,185,129,0.2)',
                      borderRadius: '12px',
                      color: '#fff',
                      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                    }}
                    itemStyle={{ color: '#10b981' }}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="gross_earnings_inr"
                    name="Gross (INR)"
                    stroke="#10b981"
                    strokeWidth={2.5}
                    fill="url(#earningsGradient)"
                    dot={{ r: 3.5, fill: '#10b981', strokeWidth: 0 }}
                    activeDot={{ r: 6, stroke: '#10b981', strokeWidth: 2, fill: '#0a0a0a' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Zone Trigger Alerts -- 1/3 */}
          <div className="glass-card p-6 flex flex-col animate-fade-in-up delay-400">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <CloudRain size={20} className="text-blue-400" />
                Zone Trigger Alerts
              </h2>
              <p className="text-xs text-neutral-500 mt-1">
                Recent risks in your zone
              </p>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto max-h-[340px] pr-1">
              {activeTriggers.length === 0 ? (
                <div className="glass p-6 text-center rounded-xl">
                  <CloudRain size={32} className="text-neutral-600 mx-auto mb-3" />
                  <p className="text-sm text-neutral-500">No active triggers right now.</p>
                  <p className="text-xs text-neutral-600 mt-1">Your zone is clear.</p>
                </div>
              ) : (
                activeTriggers.map((t) => (
                  <div
                    key={t.id}
                    className="glass p-4 rounded-xl hover:bg-white/[0.04] transition-colors"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="pulse-live w-3 h-3 inline-block" />
                        <span
                          className={
                            t.severity_band === 'claim'
                              ? 'badge badge-amber'
                              : t.severity_band === 'escalation'
                              ? 'badge badge-red'
                              : 'badge badge-blue'
                          }
                        >
                          {t.severity_band}
                        </span>
                      </div>
                      <span className="text-[11px] text-neutral-500">
                        {new Date(t.started_at).toLocaleDateString()}
                      </span>
                    </div>
                    <h3 className="font-medium text-sm text-neutral-200 leading-snug">
                      {t.trigger_code.replaceAll('_', ' ')}
                    </h3>
                    <p className="text-xs text-neutral-500 mt-1.5 flex items-center gap-1">
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
