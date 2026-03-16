"use client"

import { useEffect, useState } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
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

export default function WorkerDashboard() {
  const { user, profile } = useUserStore()
  const supabase = createClient()

  const [workerDetails, setWorkerDetails] = useState<any>(null)
  const [stats, setStats] = useState<any[]>([])
  const [activeTriggers, setActiveTriggers] = useState<any[]>([])
  const [policyQuote, setPolicyQuote] = useState<any>(null)
  const [activating, setActivating] = useState(false)
  const [activationMsg, setActivationMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!profile) return
    loadDashboardData()
  }, [profile])

  const loadDashboardData = async () => {
    // Fetch Worker specifics
    const { data: wData } = await supabase
      .from('worker_profiles')
      .select('*, zones(zone_name)')
      .eq('profile_id', profile.id)
      .single()
    setWorkerDetails(wData)

    // Fetch Daily Stats (synthetic history via backend API)
    try {
      const { data: session } = await supabase.auth.getSession()
      const token = session.session?.access_token

      const statsRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/workers/me/stats`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setStats(statsData.stats || [])
      }
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

    // Call backend API for quote
    try {
      const { data: session } = await supabase.auth.getSession()
      const token = session.session?.access_token

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/policies/quote`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        setPolicyQuote(await res.json())
      }
    } catch(e) { console.error("Could not fetch policy quote", e) }
  }

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
    ? Math.round(stats.reduce((sum, s) => sum + (s.orders_completed || 0), 0) / stats.length)
    : 0

  if (!workerDetails) {
    return (
      <div className="min-h-screen gradient-mesh flex items-center justify-center">
        <div className="glass-card p-8 flex items-center gap-3">
          <div className="h-5 w-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-neutral-300">Loading dashboard...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen gradient-mesh">
      <div className="p-6 md:p-10 pb-24 max-w-7xl mx-auto space-y-8">

        {/* ===== HEADER SECTION ===== */}
        <section className="animate-fade-in-up">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            {/* Welcome text */}
            <div>
              <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
                Welcome back, <span className="text-emerald-400">{profile.full_name}</span>
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
              value: `₹${totalEarnings.toLocaleString('en-IN')}`,
              label: 'Total Earnings (14d)',
              delay: 'delay-100',
            },
            {
              icon: <ClipboardList size={22} className="text-blue-400" />,
              value: avgDailyOrders,
              label: 'Avg Daily Orders',
              delay: 'delay-200',
            },
            {
              icon: <Navigation2 size={22} className="text-purple-400" />,
              value: workerDetails.gps_score ?? '--',
              label: 'GPS Score',
              delay: 'delay-300',
            },
            {
              icon: <Sparkles size={22} className="text-amber-400" />,
              value: workerDetails.trust_score ?? '--',
              label: 'Trust Score',
              delay: 'delay-400',
            },
          ].map((card, i) => (
            <div
              key={i}
              className={`glass-card p-5 flex flex-col gap-3 animate-fade-in-up ${card.delay}`}
            >
              <div className="glass p-2 w-fit rounded-lg">{card.icon}</div>
              <span className="text-2xl font-bold text-white">{card.value}</span>
              <span className="text-xs text-neutral-400 uppercase tracking-wider">{card.label}</span>
            </div>
          ))}
        </section>

        {/* ===== COVERAGE QUOTE CARD ===== */}
        {policyQuote && (
          <section className="animate-fade-in-up delay-200">
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
          <div className="lg:col-span-2 glass-card p-6 animate-fade-in-up delay-300">
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
                <LineChart data={stats}>
                  <defs>
                    <linearGradient id="earningsGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
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
                      backgroundColor: 'rgba(10,10,10,0.85)',
                      backdropFilter: 'blur(12px)',
                      borderColor: 'rgba(255,255,255,0.1)',
                      borderRadius: '12px',
                      color: '#fff',
                    }}
                    itemStyle={{ color: '#10b981' }}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="gross_earnings_inr"
                    name="Gross (INR)"
                    stroke="#10b981"
                    strokeWidth={2.5}
                    dot={{ r: 3.5, fill: '#10b981', strokeWidth: 0 }}
                    activeDot={{ r: 6, stroke: '#10b981', strokeWidth: 2, fill: '#0a0a0a' }}
                  />
                </LineChart>
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
