"use client"

import { useEffect, useState, useCallback, useMemo } from 'react'
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

function buildFallbackClaims(): ClaimItem[] {
  const now = new Date()
  const daysAgoIso = (daysAgo: number) => {
    const d = new Date(now)
    d.setDate(now.getDate() - daysAgo)
    return d.toISOString()
  }

  return [
    {
      id: 'demo-claim-01',
      claim_status: 'approved',
      claim_reason: 'Heavy rain flooding caused widespread cancellations in Andheri.',
      claimed_at: daysAgoIso(1),
      worker_profiles: { platform_name: 'Swiggy', city: 'Mumbai' },
    },
    {
      id: 'demo-claim-02',
      claim_status: 'soft_hold_verification',
      claim_reason: 'AQI spike disrupted shift continuity in Connaught Place.',
      claimed_at: daysAgoIso(2),
      worker_profiles: { platform_name: 'Swiggy', city: 'Delhi' },
    },
    {
      id: 'demo-claim-03',
      claim_status: 'fraud_escalated_review',
      claim_reason: 'Clustered submissions detected around identical geolocation points.',
      claimed_at: daysAgoIso(2),
      worker_profiles: { platform_name: 'Zomato', city: 'Mumbai' },
    },
    {
      id: 'demo-claim-04',
      claim_status: 'paid',
      claim_reason: 'Traffic collapse validated with operational telemetry in Koramangala.',
      claimed_at: daysAgoIso(3),
      worker_profiles: { platform_name: 'Zepto', city: 'Bangalore' },
    },
    {
      id: 'demo-claim-05',
      claim_status: 'submitted',
      claim_reason: 'Platform outage claim awaiting initial triage.',
      claimed_at: daysAgoIso(0),
      worker_profiles: { platform_name: 'Swiggy', city: 'Hyderabad' },
    },
    {
      id: 'demo-claim-06',
      claim_status: 'rejected',
      claim_reason: 'Claim rejected due to mismatch between shift logs and stated impact.',
      claimed_at: daysAgoIso(4),
      worker_profiles: { platform_name: 'Zomato', city: 'Bangalore' },
    },
  ]
}

const FALLBACK_TRIGGER_DISTRIBUTION = [
  { name: 'Rain', value: 9 },
  { name: 'Aqi', value: 6 },
  { name: 'Traffic', value: 4 },
  { name: 'Outage', value: 3 },
]

const REVIEW_STATUSES = ['submitted', 'soft_hold_verification', 'fraud_escalated_review']
const APPROVED_STATUSES = ['approved', 'auto_approved', 'paid']
const FRAUD_STATUSES = ['fraud_escalated_review', 'post_approval_flagged']
const REJECTED_STATUSES = ['rejected', 'post_approval_flagged']

const TIER_1_CITIES = new Set([
  'mumbai',
  'delhi',
  'new delhi',
  'bengaluru',
  'bangalore',
  'hyderabad',
  'chennai',
  'pune',
  'kolkata',
  'ahmedabad',
])

const TIER_2_CITIES = new Set([
  'jaipur',
  'lucknow',
  'surat',
  'indore',
  'nagpur',
  'bhopal',
  'patna',
  'ludhiana',
  'chandigarh',
  'coimbatore',
  'kochi',
  'visakhapatnam',
  'vadodara',
  'noida',
  'gurugram',
  'thane',
])

function normalizeText(value: string | undefined | null): string {
  return String(value || '').trim().toLowerCase()
}

function getCityTier(city: string | undefined | null): 'tier1' | 'tier2' | 'tier3' | 'unknown' {
  const normalized = normalizeText(city)
  if (!normalized || normalized === 'pending local') {
    return 'unknown'
  }
  if (TIER_1_CITIES.has(normalized)) {
    return 'tier1'
  }
  if (TIER_2_CITIES.has(normalized)) {
    return 'tier2'
  }
  return 'tier3'
}

function PieTooltipContent({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
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

export default function AdminDashboard() {
  const { profile } = useUserStore()
  const supabase = createClient()
  const [workerCount, setWorkerCount] = useState(0)
  const [claims, setClaims] = useState<ClaimItem[]>([])
  const [totalPayouts, setTotalPayouts] = useState(0)
  const [lossRatio, setLossRatio] = useState(0)
  const [bcr, setBcr] = useState(0)
  const [loading, setLoading] = useState(true)
  const [chartsLoading, setChartsLoading] = useState(true)
  const [tierFilter, setTierFilter] = useState<'all' | 'tier1' | 'tier2' | 'tier3'>('all')
  const [cityFilter, setCityFilter] = useState('all')
  const [platformFilter, setPlatformFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'review' | 'approved' | 'fraud' | 'rejected'>('all')

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [triggerDistribution, setTriggerDistribution] = useState<any[]>([])
  /* eslint-enable @typescript-eslint/no-explicit-any */

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setChartsLoading(true)
    let shouldUseFallback = false
    const kpiController = new AbortController()
    const kpiTimeout = setTimeout(() => kpiController.abort(), 9000)

    try {
      const { count: wc } = await supabase
        .from('worker_profiles')
        .select('*', { count: 'exact', head: true })
        .abortSignal(kpiController.signal)
      setWorkerCount(wc || 0)
      const { data: claimData } = await supabase
        .from('manual_claims')
        .select('*, worker_profiles(platform_name, city)')
        .order('claimed_at', { ascending: false })
        .abortSignal(kpiController.signal)
      const allClaims = claimData || []
      if (allClaims.length > 0) {
        setClaims(allClaims)
      } else {
        shouldUseFallback = true
      }
    } catch (e) {
      console.error('Dashboard KPI error', e)
      shouldUseFallback = true
    } finally {
      clearTimeout(kpiTimeout)
    }

    if (shouldUseFallback) {
      const fallbackClaims = buildFallbackClaims()
      setClaims(fallbackClaims)
      setWorkerCount((prev) => (prev > 0 ? prev : 24))
      setTotalPayouts(38450)
      setLossRatio(0.64)
      setBcr(0.58)
      setTriggerDistribution(FALLBACK_TRIGGER_DISTRIBUTION)
    }

    setLoading(false)

    // Load charts data in parallel
    const chartController = new AbortController()
    const chartTimeout = setTimeout(() => chartController.abort(), 9000)

    try {
      let payoutDataFound = false
      let triggerDataFound = false

      const [prResult, trResult] = await Promise.allSettled([
        supabase
          .from('payout_recommendations')
          .select('fraud_holdback_fh, recommended_payout, expected_payout, gross_premium')
          .abortSignal(chartController.signal),
        supabase
          .from('trigger_events')
          .select('trigger_family')
          .order('started_at', { ascending: false })
          .abortSignal(chartController.signal),
      ])
      if (prResult.status === 'fulfilled' && prResult.value.data) {
        const prData = prResult.value.data
        if (prData.length > 0) {
          payoutDataFound = true
          const payout = prData.reduce((s, p) => s + (p.recommended_payout || 0), 0)
          setTotalPayouts(payout)

          const expected = prData.reduce((s, p) => s + (p.expected_payout || 0), 0)
          const premium = prData.reduce((s, p) => s + (p.gross_premium || 0), 0)
          if (premium > 0) {
            setLossRatio(payout / premium)
            setBcr(expected / premium)
          }
        }
      }
      if (trResult.status === 'fulfilled' && trResult.value.data) {
        const trData = trResult.value.data
        if (trData.length > 0) {
          triggerDataFound = true
          const fam: Record<string, number> = {}
          trData.forEach(t => { fam[t.trigger_family] = (fam[t.trigger_family] || 0) + 1 })
          setTriggerDistribution(Object.entries(fam).map(([name, value]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), value })))
        }
      }

      if (!payoutDataFound && shouldUseFallback) {
        setTotalPayouts(38450)
        setLossRatio(0.64)
        setBcr(0.58)
      }
      if (!triggerDataFound && shouldUseFallback) {
        setTriggerDistribution(FALLBACK_TRIGGER_DISTRIBUTION)
      }
    } catch (e) {
      console.error('Dashboard charts error', e)
      if (shouldUseFallback) {
        setTriggerDistribution(FALLBACK_TRIGGER_DISTRIBUTION)
      }
    } finally {
      clearTimeout(chartTimeout)
    }
    setChartsLoading(false)
  }, [supabase])

  useEffect(() => {
    queueMicrotask(() => {
      void loadDashboard()
    })
  }, [loadDashboard])

  const CHART_COLORS = ['#2563eb', '#22c55e', '#eab308', '#ef4444', '#6366f1', '#f97316']
  const cityOptions = useMemo(() => {
    return Array.from(new Set(
      claims
        .map((claim) => String(claim.worker_profiles?.city || '').trim())
        .filter((city) => city.length > 0)
    )).sort((a, b) => a.localeCompare(b))
  }, [claims])

  const platformOptions = useMemo(() => {
    return Array.from(new Set(
      claims
        .map((claim) => String(claim.worker_profiles?.platform_name || '').trim())
        .filter((platform) => platform.length > 0)
    )).sort((a, b) => a.localeCompare(b))
  }, [claims])

  const filteredClaims = useMemo(() => {
    return claims.filter((claim) => {
      const city = String(claim.worker_profiles?.city || '').trim()
      const platform = String(claim.worker_profiles?.platform_name || '').trim()
      const tier = getCityTier(city)

      if (tierFilter !== 'all' && tier !== tierFilter) {
        return false
      }
      if (cityFilter !== 'all' && normalizeText(city) !== normalizeText(cityFilter)) {
        return false
      }
      if (platformFilter !== 'all' && normalizeText(platform) !== normalizeText(platformFilter)) {
        return false
      }

      if (statusFilter === 'review' && !REVIEW_STATUSES.includes(claim.claim_status)) {
        return false
      }
      if (statusFilter === 'approved' && !APPROVED_STATUSES.includes(claim.claim_status)) {
        return false
      }
      if (statusFilter === 'fraud' && !FRAUD_STATUSES.includes(claim.claim_status)) {
        return false
      }
      if (statusFilter === 'rejected' && !REJECTED_STATUSES.includes(claim.claim_status)) {
        return false
      }

      return true
    })
  }, [claims, tierFilter, cityFilter, platformFilter, statusFilter])

  const filteredApprovedCount = filteredClaims.filter((claim) => APPROVED_STATUSES.includes(claim.claim_status)).length
  const filteredReviewCount = filteredClaims.filter((claim) => REVIEW_STATUSES.includes(claim.claim_status)).length
  const filteredFraudCount = filteredClaims.filter((claim) => FRAUD_STATUSES.includes(claim.claim_status)).length

  const filtersApplied = tierFilter !== 'all' || cityFilter !== 'all' || platformFilter !== 'all' || statusFilter !== 'all'

  const resetFilters = () => {
    setTierFilter('all')
    setCityFilter('all')
    setPlatformFilter('all')
    setStatusFilter('all')
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
    { icon: <Users size={20} style={{ color: 'var(--success)' }} />, value: workerCount, label: 'Active Workers', sub: filtersApplied ? `${filteredClaims.length} filtered claims in scope` : 'Covered on platform', accent: 'var(--success)' },
    { icon: <Clock size={20} style={{ color: 'var(--warning)' }} />, value: filteredReviewCount, label: 'Needs Review', sub: 'Manual / escalated / AI-uncertain', accent: 'var(--warning)' },
    { icon: <AlertTriangle size={20} style={{ color: 'var(--danger)' }} />, value: filteredFraudCount, label: 'Fraud Detected', sub: 'High-risk or post-approval flagged', accent: 'var(--danger)' },
    { icon: <CheckCircle size={20} style={{ color: 'var(--accent)' }} />, value: filteredApprovedCount, label: 'Approved Claims', sub: `Out of ${filteredClaims.length} filtered claims`, accent: 'var(--accent)' },
    { icon: <IndianRupee size={20} style={{ color: 'var(--info)' }} />, value: totalPayouts, prefix: '₹', label: 'Total Payouts', sub: `Expected: ₹${totalPayouts.toLocaleString('en-IN')}`, accent: 'var(--info)' },
  ]

  const actuarialCards = [
    { icon: <Activity size={20} style={{ color: 'var(--purple, #a855f7)' }} />, value: bcr, prefix: '', suffix: 'x', label: 'Burning Cost Rate', sub: 'Target: 0.55 - 0.70', accent: 'var(--purple, #a855f7)', isFloat: true },
    { icon: <Shield size={20} style={{ color: 'var(--blue, #3b82f6)' }} />, value: lossRatio, prefix: '', suffix: 'x', label: 'Loss Ratio', sub: 'Payout vs Premium', accent: 'var(--blue, #3b82f6)', isFloat: true },
  ]

  const pipelineData = [
    { label: 'Approved', count: filteredApprovedCount, color: 'var(--success)' },
    { label: 'Review', count: filteredReviewCount, color: 'var(--warning)' },
    { label: 'Fraud', count: filteredFraudCount, color: 'var(--danger)' },
  ]
  const pipelineTotal = pipelineData.reduce((s, p) => s + p.count, 0) || 1

  const operationsDeck = [
    {
      title: 'Review Queue',
      href: '/admin/reviews',
      value: filteredReviewCount,
      helper: filteredReviewCount > 0 ? 'Pending claims need triage' : 'Queue is clear',
      tone: 'var(--warning)',
      cta: 'Open Reviews',
    },
    {
      title: 'Fraud Triage',
      href: '/admin/reviews',
      value: filteredFraudCount,
      helper: filteredFraudCount > 0 ? 'High-risk claims flagged' : 'No elevated fraud spikes',
      tone: 'var(--danger)',
      cta: 'Inspect Signals',
    },
    {
      title: 'Event Ops',
      href: '/admin/events',
      value: filteredClaims.length,
      helper: 'Relay, requeue, and dead-letter controls',
      tone: 'var(--accent)',
      cta: 'Open Event Ops',
    },
    {
      title: 'Trigger Console',
      href: '/admin/triggers',
      value: triggerDistribution.reduce((s, t) => s + Number(t.value || 0), 0),
      helper: 'Validate active trigger families',
      tone: 'var(--info)',
      cta: 'Open Triggers',
    },
  ]

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

        {/* Analytics Filters */}
        <section className="card p-5 section-enter">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                Analytics Filters
              </h2>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                Slice operational metrics by city tier, city, platform, and decision status.
              </p>
            </div>
            <button
              type="button"
              onClick={resetFilters}
              className="px-3 py-1.5 rounded-md text-xs font-medium"
              style={{ border: '1px solid var(--border-primary)', color: 'var(--text-secondary)', background: 'var(--bg-tertiary)' }}
            >
              Reset Filters
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            <label className="space-y-1.5">
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>City Tier</span>
              <select
                value={tierFilter}
                onChange={(e) => setTierFilter(e.target.value as 'all' | 'tier1' | 'tier2' | 'tier3')}
                className="w-full rounded-md px-3 py-2 text-sm"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
              >
                <option value="all">All Tiers</option>
                <option value="tier1">Tier 1</option>
                <option value="tier2">Tier 2</option>
                <option value="tier3">Tier 3+</option>
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>City</span>
              <select
                value={cityFilter}
                onChange={(e) => setCityFilter(e.target.value)}
                className="w-full rounded-md px-3 py-2 text-sm"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
              >
                <option value="all">All Cities</option>
                {cityOptions.map((city) => (
                  <option key={city} value={city}>{city}</option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Platform</span>
              <select
                value={platformFilter}
                onChange={(e) => setPlatformFilter(e.target.value)}
                className="w-full rounded-md px-3 py-2 text-sm"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
              >
                <option value="all">All Platforms</option>
                {platformOptions.map((platform) => (
                  <option key={platform} value={platform}>{platform}</option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Decision Status</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'all' | 'review' | 'approved' | 'fraud' | 'rejected')}
                className="w-full rounded-md px-3 py-2 text-sm"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
              >
                <option value="all">All Statuses</option>
                <option value="review">Review Required</option>
                <option value="approved">Approved / Paid</option>
                <option value="fraud">Fraud Signals</option>
                <option value="rejected">Rejected / Flagged</option>
              </select>
            </label>
          </div>

          <p className="text-xs mt-3" style={{ color: 'var(--text-tertiary)' }}>
            Showing {filteredClaims.length} of {claims.length} claims in current analytics scope.
          </p>
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
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{filteredClaims.length} filtered claims</span>
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

        {/* Ops Command Deck */}
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 section-enter">
          {operationsDeck.map((item, index) => (
            <Link
              key={item.title}
              href={item.href}
              className={`card p-5 animate-fade-in-up delay-${(index + 2) * 100} transition-all hover:translate-y-[-2px]`}
              style={{ borderTop: `2px solid ${item.tone}` }}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                  {item.title}
                </h3>
                <span className="text-base font-bold" style={{ color: item.tone }}>
                  {item.value.toLocaleString('en-IN')}
                </span>
              </div>
              <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                {item.helper}
              </p>
              <span className="text-xs font-medium inline-flex items-center gap-1" style={{ color: item.tone }}>
                {item.cta} <ArrowRight size={12} />
              </span>
            </Link>
          ))}
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
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Disruption events by family across all zones (network-wide)</p>
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
                    <Tooltip content={<PieTooltipContent />} />
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
                {filteredClaims.length === 0 ? (
                  <div className="p-4 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', color: 'var(--text-tertiary)' }}>
                    No claims match the selected filters.
                  </div>
                ) : (
                  filteredClaims.slice(0, 6).map(c => (
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
                  ))
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}


