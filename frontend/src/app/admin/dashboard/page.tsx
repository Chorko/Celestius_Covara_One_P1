"use client"

import { useEffect, useState, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import dynamic from 'next/dynamic'
import 'leaflet/dist/leaflet.css'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import AnimatedCounter from '@/components/AnimatedCounter'
import Skeleton from '@/components/Skeleton'
import Link from 'next/link'
import {
  Shield, Users, AlertTriangle, CheckCircle, IndianRupee,
  Clock, ArrowRight, Activity, FileSearch,
} from 'lucide-react'
const ZoneRiskMap = dynamic(() => import('@/components/admin/ZoneRiskMap'), {
  ssr: false,
  loading: () => (
    <div className="card p-6">
      <Skeleton width="180px" height="1.25rem" className="mb-4" />
      <Skeleton width="100%" height="120px" className="mb-3" />
      <Skeleton width="100%" height="420px" />
    </div>
  ),
})

/* eslint-disable @typescript-eslint/no-explicit-any */
interface ClaimItem { id: string; claim_status: string; claim_reason: string; claimed_at: string; worker_profiles?: { platform_name?: string; city?: string }; [key: string]: any }
/* eslint-enable @typescript-eslint/no-explicit-any */

export default function AdminDashboard() {
  const { profile } = useUserStore()
  const supabase = createClient()
  const [workerCount, setWorkerCount] = useState(0)
  const [claims, setClaims] = useState<ClaimItem[]>([])
  const [fraudCount, setFraudCount] = useState(0)
  const [totalPayouts, setTotalPayouts] = useState(0)
  const [lossRatio, setLossRatio] = useState(0)
  const [bcr, setBcr] = useState(0)
  const [approvedCount, setApprovedCount] = useState(0)
  const [reviewCount, setReviewCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [chartsLoading, setChartsLoading] = useState(true)

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [triggerDistribution, setTriggerDistribution] = useState<any[]>([])
  /* eslint-enable @typescript-eslint/no-explicit-any */

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setChartsLoading(true)
    try {
      const { count: wc } = await supabase.from('worker_profiles').select('*', { count: 'exact', head: true })
      setWorkerCount(wc || 0)
      const { data: claimData } = await supabase.from('manual_claims').select('*, worker_profiles(platform_name, city)').order('claimed_at', { ascending: false })
      const allClaims = claimData || []
      setClaims(allClaims)
      const approved = allClaims.filter(c => ['approved', 'auto_approved', 'paid'].includes(c.claim_status))
      setApprovedCount(approved.length)
      const review = allClaims.filter(c => ['submitted', 'soft_hold_verification', 'fraud_escalated_review'].includes(c.claim_status))
      setReviewCount(review.length)
    } catch (e) { console.error('Dashboard KPI error', e) }
    setLoading(false)

    // Load charts data in parallel
    try {
      const [prResult, trResult] = await Promise.allSettled([
        supabase.from('payout_recommendations').select('fraud_holdback_fh, recommended_payout, expected_payout, gross_premium'),
        supabase.from('trigger_events').select('trigger_family').order('started_at', { ascending: false }),
      ])
      if (prResult.status === 'fulfilled' && prResult.value.data) {
        const prData = prResult.value.data
        setFraudCount(prData.filter(p => (p.fraud_holdback_fh ?? 0) > 0.3).length)
        const payout = prData.reduce((s, p) => s + (p.recommended_payout || 0), 0)
        setTotalPayouts(payout)
        
        const expected = prData.reduce((s, p) => s + (p.expected_payout || 0), 0)
        const premium = prData.reduce((s, p) => s + (p.gross_premium || 0), 0)
        if (premium > 0) {
          setLossRatio(payout / premium)
          setBcr(expected / premium)
        }
      }
      if (trResult.status === 'fulfilled' && trResult.value.data) {
        const trData = trResult.value.data
        const fam: Record<string, number> = {}
        trData.forEach(t => { fam[t.trigger_family] = (fam[t.trigger_family] || 0) + 1 })
        setTriggerDistribution(Object.entries(fam).map(([name, value]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), value })))
      }
    } catch (e) { console.error('Dashboard charts error', e) }
    setChartsLoading(false)
  }, [supabase])

  useEffect(() => { loadDashboard() }, [loadDashboard])

  const CHART_COLORS = ['#2563eb', '#22c55e', '#eab308', '#ef4444', '#6366f1', '#f97316']
  const PIE_TOOLTIP = ({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) => {
    if (active && payload?.length) {
      return (
        <div className="card p-3 text-xs" style={{ boxShadow: 'var(--shadow-lg)' }}>
          <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>{payload[0].name}</p>
          <p style={{ color: 'var(--text-secondary)' }}>{payload[0].value} events</p>
        </div>
      )
    }
    return null
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case 'approved': case 'auto_approved': case 'paid': return 'badge-success'
      case 'submitted': case 'soft_hold_verification': return 'badge-warning'
      case 'fraud_escalated_review': return 'badge-purple'
      case 'rejected': case 'post_approval_flagged': return 'badge-danger'
      default: return 'badge-info'
    }
  }
  const statusLabel = (s: string) => ({ auto_approved: 'Auto', approved: 'Approved', paid: 'Paid', submitted: 'Submitted', soft_hold_verification: 'Verify', fraud_escalated_review: 'Fraud', rejected: 'Rejected', post_approval_flagged: 'Flagged' } as Record<string, string>)[s] || s

  if (loading) {
    return (
      <div className="min-h-screen p-6 md:p-10 max-w-7xl mx-auto space-y-8">
        <Skeleton width="280px" height="2.5rem" className="mb-3" />
        <Skeleton width="400px" height="1rem" />
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[1,2,3,4,5].map(i => <div key={i} className="card p-5"><Skeleton width="100%" height="80px" /></div>)}
        </div>
        {/* Pipeline + charts skeleton */}
        <div className="card p-5"><Skeleton width="100%" height="48px" /></div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card p-6"><Skeleton width="160px" height="1.25rem" className="mb-4" /><Skeleton width="100%" height="256px" /></div>
          <div className="card p-6">
            <Skeleton width="180px" height="1.25rem" className="mb-4" />
            <div className="space-y-2">
              {[1,2,3,4,5,6].map(i => <Skeleton key={i} width="100%" height="60px" />)}
            </div>
          </div>
        </div>
      </div>
    )
  }

  const kpiCards = [
    { icon: <Users size={20} style={{ color: 'var(--success)' }} />, value: workerCount, label: 'Active Workers', sub: 'Covered on platform', accent: 'var(--success)' },
    { icon: <Clock size={20} style={{ color: 'var(--warning)' }} />, value: reviewCount, label: 'Needs Review', sub: 'Manual / escalated / AI-uncertain', accent: 'var(--warning)' },
    { icon: <AlertTriangle size={20} style={{ color: 'var(--danger)' }} />, value: fraudCount, label: 'Fraud Detected', sub: 'High fraud score — rejected', accent: 'var(--danger)' },
    { icon: <CheckCircle size={20} style={{ color: 'var(--accent)' }} />, value: approvedCount, label: 'Approved Claims', sub: `Out of ${claims.length} total claims`, accent: 'var(--accent)' },
    { icon: <IndianRupee size={20} style={{ color: 'var(--info)' }} />, value: totalPayouts, prefix: '₹', label: 'Total Payouts', sub: `Expected: ₹${totalPayouts.toLocaleString('en-IN')}`, accent: 'var(--info)' },
  ]

  const actuarialCards = [
    { icon: <Activity size={20} style={{ color: 'var(--purple, #a855f7)' }} />, value: bcr, prefix: '', suffix: 'x', label: 'Burning Cost Rate', sub: 'Target: 0.55 - 0.70', accent: 'var(--purple, #a855f7)', isFloat: true },
    { icon: <Shield size={20} style={{ color: 'var(--blue, #3b82f6)' }} />, value: lossRatio, prefix: '', suffix: 'x', label: 'Loss Ratio', sub: 'Payout vs Premium', accent: 'var(--blue, #3b82f6)', isFloat: true },
  ]

  const pipelineData = [
    { label: 'Approved', count: approvedCount, color: 'var(--success)' },
    { label: 'Review', count: reviewCount, color: 'var(--warning)' },
    { label: 'Fraud', count: fraudCount, color: 'var(--danger)' },
  ]
  const pipelineTotal = pipelineData.reduce((s, p) => s + p.count, 0) || 1

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <section className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 rounded-lg" style={{ background: 'var(--accent-muted)' }}>
              <Shield size={24} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>Insurance Operations Center</h1>
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                Welcome back, <strong>{profile?.full_name}</strong>. Real-time parametric insurance metrics across all operational zones.
              </p>
            </div>
          </div>
        </section>

        {/* KPI Cards */}
        <section className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {kpiCards.map((c, i) => (
            <div key={i} className={`card p-5 animate-fade-in-up delay-${(i + 1) * 100}`} style={{ borderLeft: `3px solid ${c.accent}` }}>
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-md" style={{ background: 'var(--bg-tertiary)' }}>{c.icon}</div>
                <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>{c.label}</span>
              </div>
              <span className="text-2xl font-bold block" style={{ color: 'var(--text-primary)' }}>
                <AnimatedCounter value={c.value} prefix={c.prefix || ''} />
              </span>
              <span className="text-xs mt-1 block" style={{ color: 'var(--text-tertiary)' }}>{c.sub}</span>
            </div>
          ))}

          {/* Actuarial Metrics */}
          {actuarialCards.map((c, i) => (
            <div key={`act-${i}`} className={`card p-5 animate-fade-in-up delay-${(i + kpiCards.length + 1) * 100}`} style={{ borderLeft: `3px solid ${c.accent}` }}>
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-md" style={{ background: 'var(--bg-tertiary)' }}>{c.icon}</div>
                <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>{c.label}</span>
              </div>
              <span className="text-2xl font-bold block" style={{ color: 'var(--text-primary)' }}>
                {c.value > 0 ? (
                  <span>{c.prefix}{c.value.toFixed(2)}{c.suffix}</span>
                ) : (
                  <AnimatedCounter value={0} prefix={c.prefix || ''} />
                )}
              </span>
              <span className="text-xs mt-1 block" style={{ color: 'var(--text-tertiary)' }}>{c.sub}</span>
            </div>
          ))}
        </section>

        {/* Pipeline Bar */}
        <section className="card p-5 section-enter">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}>
              <Activity size={16} /> Claim Pipeline Status
            </h2>
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{claims.length} total claims</span>
          </div>
          <div className="flex rounded-lg overflow-hidden h-3" style={{ background: 'var(--bg-tertiary)' }}>
            {pipelineData.map((p, i) => p.count > 0 && (
              <div key={i} className="h-full transition-all" style={{ width: `${(p.count / pipelineTotal) * 100}%`, background: p.color }} />
            ))}
          </div>
          <div className="flex items-center gap-5 mt-3 text-xs">
            {pipelineData.map((p, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
                <span style={{ color: 'var(--text-tertiary)' }}>{p.label}</span>
                <strong style={{ color: 'var(--text-primary)' }}>{p.count}</strong>
                <span style={{ color: 'var(--text-tertiary)' }}>({Math.round((p.count / pipelineTotal) * 100)}%)</span>
              </span>
            ))}
          </div>
        </section>

        {/* Zone Risk Map */}
        <ZoneRiskMap />

        {/* Charts + Recent Claims */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Pie Chart */}
          <div className="card p-6">
            <div className="mb-4">
              <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Activity size={18} style={{ color: 'var(--info)' }} /> Trigger Distribution
              </h2>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Disruption events by family across all zones</p>
            </div>
            {chartsLoading ? (
              <div className="h-64"><Skeleton width="100%" height="256px" /></div>
            ) : triggerDistribution.length > 0 ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={triggerDistribution} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3} strokeWidth={0}>
                      {triggerDistribution.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip content={<PIE_TOOLTIP />} />
                    <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--text-tertiary)' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center" style={{ color: 'var(--text-tertiary)' }}>
                <p className="text-sm">No trigger events recorded</p>
              </div>
            )}
          </div>

          {/* Recent Claims */}
          <div className="card p-6 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                  <FileSearch size={18} style={{ color: 'var(--accent)' }} /> Recent Activity
                </h2>
                <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Latest claim submissions and decisions</p>
              </div>
              <Link href="/admin/reviews" className="text-xs font-medium flex items-center gap-1" style={{ color: 'var(--accent)' }}>
                View all <ArrowRight size={12} />
              </Link>
            </div>
            {chartsLoading ? (
              <div className="space-y-2">
                {[1,2,3,4,5,6].map(i => <Skeleton key={i} width="100%" height="60px" />)}
              </div>
            ) : (
              <div className="flex-1 space-y-2 overflow-y-auto max-h-[300px]">
                {claims.slice(0, 6).map(c => (
                  <div key={c.id} className="flex items-center justify-between p-3 rounded-lg transition-colors" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`badge ${statusBadge(c.claim_status)}`}>{statusLabel(c.claim_status)}</span>
                        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          {new Date(c.claimed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </span>
                      </div>
                      <p className="text-sm truncate" style={{ color: 'var(--text-secondary)' }}>{c.claim_reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}


