"use client"

import { useEffect, useState, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import {
  Shield, ShieldCheck, Clock,
  CheckCircle, CreditCard, X, Sparkles, IndianRupee, Lock, Brain,
  RefreshCw, TrendingUp, AlertTriangle, Activity
} from 'lucide-react'
import Skeleton from '@/components/Skeleton'

interface PlanTier {
  id: 'essential' | 'plus'
  name: string
  weeklyBenefit: number
  icon: React.ReactNode
  popular: boolean
  features: string[]
  target: string
}

const PLANS: PlanTier[] = [
  {
    id: 'essential', name: 'Essential', weeklyBenefit: 3000,
    icon: <Shield size={28} />, popular: false,
    features: [
      'Weekly income protection (₹3,000 basis)',
      '15-trigger coverage (rain, AQI, heat, closures)',
      'Pre-agreed parametric payout bands',
      'AI-powered fraud verification',
      'Weekly auto-renewal option',
    ],
    target: 'Lower premium · wider adoption · cost-sensitive workers',
  },
  {
    id: 'plus', name: 'Plus', weeklyBenefit: 4500,
    icon: <ShieldCheck size={28} />, popular: true,
    features: [
      'Weekly income protection (₹4,500 basis)',
      '15-trigger coverage + composite disruption events',
      'Pre-agreed parametric payout bands',
      'Advanced Ghost Shift Detector protection',
      'Gemini AI claim narrative reports',
      'Priority review queue',
    ],
    target: 'Higher protection · experienced workers · tougher zones',
  },
]

const PAYOUT_BANDS = [
  { band: 1, label: 'Band 1 — Watch', multiplier: 0.25, description: 'Moderate disruption with partial exposure' },
  { band: 2, label: 'Band 2 — Claim', multiplier: 0.50, description: 'Major disruption with strong exposure' },
  { band: 3, label: 'Band 3 — Escalation', multiplier: 1.00, description: 'Severe disruption with full exposure match' },
]

function getWeeklyRiskFactor(city: string): { factor: number; label: string; trend: 'up' | 'down' | 'stable' } {
  const factors: Record<string, { factor: number; label: string; trend: 'up' | 'down' | 'stable' }> = {
    Mumbai:    { factor: 1.15, label: 'Elevated — pre-monsoon rainfall risk', trend: 'up' },
    Delhi:     { factor: 1.08, label: 'Moderate — AQI forecast improving', trend: 'down' },
    Bangalore: { factor: 1.02, label: 'Low — stable conditions expected', trend: 'stable' },
    Hyderabad: { factor: 1.05, label: 'Moderate — spot AQI fluctuations', trend: 'stable' },
  }
  return factors[city] ?? { factor: 1.0, label: 'Normal', trend: 'stable' as const }
}

interface QuoteData {
  weekly_premium_inr: number; max_payout_cap_inr: number; covered_income_b: number
  observed_weekly_gross: number; exposure_e: number; confidence_base: number; risk_factor: number
  B: number; E: number; C: number
}

export default function WorkerPricing() {
  const { profile } = useUserStore()
  const supabase = createClient()
  const [quote, setQuote] = useState<QuoteData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPlan, setSelectedPlan] = useState<PlanTier | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [paying, setPaying] = useState(false)
  const [paymentSuccess, setPaymentSuccess] = useState(false)
  const [autoRenew, setAutoRenew] = useState(true)
  const [riskInfo, setRiskInfo] = useState<{ factor: number; label: string; trend: 'up' | 'down' | 'stable' }>({ factor: 1.0, label: 'Normal', trend: 'stable' })

  const fetchQuote = useCallback(async () => {
    setLoading(true)
    try {
      const { data: wp } = await supabase
        .from('worker_profiles')
        .select('profile_id, avg_hourly_income_inr, city, trust_score')
        .eq('profile_id', profile!.id)
        .single()
      if (wp) {
        let observed_weekly_gross: number | null = null
        try {
          const { data: recentStats } = await supabase.from('platform_worker_daily_stats').select('gross_earnings_inr').eq('worker_profile_id', wp.profile_id).order('stat_date', { ascending: false }).limit(7)
          if (recentStats && recentStats.length >= 3) {
            const totalGross = recentStats.reduce((s, r) => s + (r.gross_earnings_inr || 0), 0)
            observed_weekly_gross = Math.round((totalGross / recentStats.length) * 6)
          }
        } catch { /* fallback below */ }
        const fallback = Math.round((wp.avg_hourly_income_inr || 0) * 8 * 6)
        const weekly_gross = observed_weekly_gross ?? fallback
        const B = Math.round(weekly_gross * 0.70)
        const raw_cap = Math.round(B * 0.75)
        const payout_cap = Math.min(raw_cap, 10000)
        const risk = getWeeklyRiskFactor(wp.city)
        setRiskInfo(risk)
        const cityFactor: Record<string, number> = { Mumbai: 1.3, Delhi: 1.2, Bangalore: 1.25 }
        const C = cityFactor[wp.city] ?? 1.0
        const E = wp.trust_score ?? 0.8
        const weeklyPremium = Math.round(B * 0.035 * E * C * risk.factor)
        setQuote({ weekly_premium_inr: weeklyPremium, max_payout_cap_inr: payout_cap, covered_income_b: B, observed_weekly_gross: weekly_gross, exposure_e: Math.round(E * 100) / 100, confidence_base: C, risk_factor: risk.factor, B, E: Math.round(E * 100) / 100, C })
      }
    } catch (e) { console.error('Could not fetch policy quote', e) }
    setLoading(false)
  }, [supabase, profile])

  useEffect(() => {
    if (!profile) {
      setLoading(false)
      return
    }
    void fetchQuote()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id])

  const handleChoosePlan = (plan: PlanTier) => { setSelectedPlan(plan); setPaymentSuccess(false); setPaying(false); setShowModal(true) }
  const handlePay = () => { setPaying(true); setTimeout(() => { setPaying(false); setPaymentSuccess(true) }, 2000) }
  const closeModal = () => { setShowModal(false); setSelectedPlan(null); setPaymentSuccess(false) }
  // Fixed IRDAI plan prices — always shown even if quote fetch fails
  const FIXED_PRICES: Record<string, number> = { essential: 28, plus: 42 }
  const getPremium = (plan: PlanTier) => {
    if (!quote) return FIXED_PRICES[plan.id]
    const essentialBenefit = PLANS.find(p => p.id === 'essential')?.weeklyBenefit ?? 3000
    const actuarial = Math.round(quote.weekly_premium_inr * (plan.weeklyBenefit / essentialBenefit))
    return actuarial > 0 ? actuarial : FIXED_PRICES[plan.id]
  }

  if (loading) {
    return (
      <div className="p-8 max-w-5xl mx-auto space-y-6">
        <div className="text-center space-y-3">
          <Skeleton width="200px" height="2rem" className="mx-auto" />
          <Skeleton width="360px" height="1rem" className="mx-auto" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
          {[1, 2].map(i => <div key={i} className="card p-8"><Skeleton width="100%" height="300px" /></div>)}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-8 pb-28 max-w-5xl mx-auto space-y-8">
        {/* Header */}
        <section className="text-center animate-fade-in-up">
          <h1 className="text-3xl md:text-4xl font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Choose Your Coverage</h1>
          <p className="max-w-xl mx-auto text-sm leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
            Parametric income protection with pre-agreed payout bands.
            Two plans maximize conversion clarity — choose affordability or stronger cover.
          </p>
          {quote && (
            <div className="mt-4 inline-flex items-center gap-2 badge-success text-xs">
              <Sparkles size={12} /> Personalized weekly quote based on your profile
            </div>
          )}
        </section>

        {/* Weekly Risk Factor Bar */}
        {quote && (
          <section className="card p-5 animate-fade-in-up delay-100">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg" style={{
                  background: riskInfo.trend === 'up' ? 'var(--warning-muted)' : riskInfo.trend === 'down' ? 'var(--success-muted)' : 'var(--accent-muted)'
                }}>
                  {riskInfo.trend === 'up' && <TrendingUp size={18} style={{ color: 'var(--warning)' }} />}
                  {riskInfo.trend === 'down' && <TrendingUp size={18} className="rotate-180" style={{ color: 'var(--success)' }} />}
                  {riskInfo.trend === 'stable' && <Activity size={18} style={{ color: 'var(--accent)' }} />}
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>This Week&apos;s Risk Factor</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-sm font-bold" style={{
                      color: riskInfo.factor > 1.1 ? 'var(--warning)' : riskInfo.factor < 1.0 ? 'var(--success)' : 'var(--accent)'
                    }}>{riskInfo.factor.toFixed(2)}×</span>
                    <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{riskInfo.label}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <RefreshCw size={14} style={{ color: autoRenew ? 'var(--success)' : 'var(--text-tertiary)' }} />
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Auto-Renew</span>
                </div>
                <button onClick={() => setAutoRenew(!autoRenew)}
                  className="relative w-11 h-6 rounded-full transition-all"
                  style={{ background: autoRenew ? 'var(--success-muted)' : 'var(--bg-tertiary)', border: `1px solid ${autoRenew ? 'var(--success)' : 'var(--border-secondary)'}` }}>
                  <div className="absolute top-0.5 w-5 h-5 rounded-full transition-all"
                    style={{ background: autoRenew ? 'var(--success)' : 'var(--text-tertiary)', left: autoRenew ? '20px' : '2px' }} />
                </button>
                <span className="text-xs font-medium" style={{ color: autoRenew ? 'var(--success)' : 'var(--text-tertiary)' }}>
                  {autoRenew ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>
          </section>
        )}

        {/* Plan Cards */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {PLANS.map((plan, idx) => {
            const premium = getPremium(plan)
            return (
              <div key={plan.id}
                className={`card p-8 relative flex flex-col animate-fade-in-up`}
                style={{
                  animationDelay: `${(idx + 1) * 80}ms`,
                  borderColor: plan.popular ? 'var(--accent)' : undefined,
                  borderWidth: plan.popular ? '2px' : undefined,
                }}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="badge-info px-4 py-1 text-xs font-bold">RECOMMENDED</span>
                  </div>
                )}
                <div className="mb-6">
                  <div className="mb-3" style={{ color: plan.popular ? 'var(--accent)' : 'var(--text-tertiary)' }}>{plan.icon}</div>
                  <h2 className="text-xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>{plan.name}</h2>
                  <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{plan.target}</p>
                </div>
                <div className="mb-5">
                  <div className="flex items-baseline gap-1">
                    <span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>₹</span>
                    <span className="text-4xl font-bold" style={{ color: 'var(--text-primary)' }}>{premium || '—'}</span>
                    <span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>/week</span>
                  </div>
                  <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
                    Weekly benefit basis: <span className="font-semibold" style={{ color: plan.popular ? 'var(--accent)' : 'var(--text-secondary)' }}>₹{plan.weeklyBenefit.toLocaleString('en-IN')}</span>
                  </p>
                </div>
                <div className="mb-5 p-4 rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>Pre-Agreed Payout Bands</p>
                  <div className="space-y-2">
                    {PAYOUT_BANDS.map(b => (
                      <div key={b.band} className="flex justify-between items-center text-sm">
                        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{b.label}</span>
                        <span className="font-semibold" style={{ color: plan.popular ? 'var(--accent)' : 'var(--text-primary)' }}>
                          ₹{Math.round(plan.weeklyBenefit * b.multiplier).toLocaleString('en-IN')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <CheckCircle size={16} className="mt-0.5 shrink-0" style={{ color: plan.popular ? 'var(--accent)' : 'var(--success)' }} />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <button onClick={() => handleChoosePlan(plan)}
                  className={plan.popular ? 'btn-primary w-full py-3 text-sm font-semibold' : 'btn-secondary w-full py-3 text-sm font-semibold'}>
                  Choose {plan.name}
                </button>
              </div>
            )
          })}
        </section>

        {/* Basis Risk Note */}
        <section className="card p-4 animate-fade-in-up delay-300">
          <div className="flex items-start gap-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--warning)' }} />
            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
              <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>Basis risk note:</span>{' '}
              Because this is a parametric product, payouts are based on pre-agreed trigger bands,
              not actual individual loss. A trigger may occur without equal impact for every worker,
              and some workers may suffer loss without a clean trigger match.
            </p>
          </div>
        </section>

        {/* IRDAI Standard Exclusions */}
        <section className="card p-4 animate-fade-in-up delay-300">
          <div className="flex items-start gap-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--danger)' }} />
            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
              <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>Standard Exclusions (Per IRDAI Guidelines):</span>{' '}
              Please note that Covara One's parametric insurance does not cover disruptions or losses arising directly or indirectly from acts of War, Invasion, Act of foreign enemy, Hostilities (whether war be declared or not), Civil War, Rebellion, Revolution, or global Pandemics.
            </p>
          </div>
        </section>

        {/* Formula Breakdown */}
        {quote && (
          <section className="card p-6 animate-fade-in-up delay-400">
            <h3 className="text-sm font-semibold uppercase tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}>
              <Brain size={16} /> Your Weekly Premium Breakdown
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
              {[
                { label: 'Observed Weekly Gross', value: `₹${quote.observed_weekly_gross?.toLocaleString('en-IN') || '—'}`, sub: 'from last 7 active days' },
                { label: 'Covered Income (B)', value: `₹${quote.covered_income_b?.toLocaleString('en-IN') || '—'}`, sub: '0.70 × weekly gross' },
                { label: 'Exposure Score (E)', value: `${quote.exposure_e || '—'}`, sub: 'Trust + accessibility' },
                { label: 'City Factor (C)', value: `${quote.confidence_base || '—'}`, sub: 'Zone risk multiplier' },
                { label: 'Weekly Premium', value: `₹${quote.weekly_premium_inr}`, sub: `B × 0.035 × E × C × ${quote.risk_factor?.toFixed(2)}`, highlight: true },
              ].map((item, i) => (
                <div key={i}>
                  <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{item.label}</p>
                  <p className="font-semibold" style={{ color: item.highlight ? 'var(--accent)' : 'var(--text-primary)' }}>{item.value}</p>
                  <p className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>{item.sub}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 p-3 rounded-lg text-xs font-mono" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}>
              Payout Cap = 0.75 × B = 0.75 × ₹{quote.covered_income_b?.toLocaleString('en-IN')} = ₹{quote.max_payout_cap_inr?.toLocaleString('en-IN')} (weekly max)
            </div>
          </section>
        )}

        {/* Payment Modal */}
        {showModal && selectedPlan && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)' }} onClick={closeModal} />
            <div className="card-elevated rounded-xl p-8 w-full max-w-md relative z-10 animate-fade-in-up">
              <button onClick={closeModal} className="absolute top-4 right-4 transition-colors" style={{ color: 'var(--text-tertiary)' }}>
                <X size={20} />
              </button>
              {paymentSuccess ? (
                <div className="text-center py-6">
                  <div className="w-20 h-20 mx-auto mb-6 rounded-full flex items-center justify-center" style={{ background: 'var(--success-muted)' }}>
                    <CheckCircle size={40} style={{ color: 'var(--success)' }} />
                  </div>
                  <h3 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>{selectedPlan.name} Activated!</h3>
                  <p className="mb-2" style={{ color: 'var(--text-secondary)' }}>Your weekly income protection is now active.</p>
                  <p className="text-sm mb-4" style={{ color: 'var(--text-tertiary)' }}>
                    Weekly benefit: ₹{selectedPlan.weeklyBenefit.toLocaleString('en-IN')} · Triggers are monitoring your zone.
                  </p>
                  <div className="flex items-center justify-center gap-3 mb-6">
                    <span className="badge-success"><ShieldCheck size={12} /> Protected</span>
                    {autoRenew && <span className="badge-info"><RefreshCw size={10} /> Auto-Renew ON</span>}
                  </div>
                  <button onClick={closeModal} className="btn-primary w-full">Back to Plans</button>
                </div>
              ) : (
                <>
                  <div className="mb-6">
                    <h3 className="text-xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>Confirm Weekly Payment</h3>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Activate your {selectedPlan.name} coverage</p>
                  </div>
                  <div className="rounded-lg p-4 mb-4 flex justify-between items-center" style={{ background: 'var(--accent-muted)', border: '1px solid var(--accent)' }}>
                    <div>
                      <p className="font-semibold" style={{ color: 'var(--accent)' }}>{selectedPlan.name}</p>
                      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>₹{selectedPlan.weeklyBenefit.toLocaleString('en-IN')}/week benefit</p>
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>₹{getPremium(selectedPlan)}</p>
                      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>/week</p>
                    </div>
                  </div>
                  <div className="space-y-4 mb-6">
                    <div>
                      <label className="text-xs uppercase tracking-wider block mb-1.5 font-medium" style={{ color: 'var(--text-tertiary)' }}>Card Number</label>
                      <div className="relative">
                        <input type="text" defaultValue="4242 4242 4242 4242" className="input-field pl-10" readOnly />
                        <CreditCard size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs uppercase tracking-wider block mb-1.5 font-medium" style={{ color: 'var(--text-tertiary)' }}>Expiry</label>
                        <input type="text" defaultValue="12/28" className="input-field" readOnly />
                      </div>
                      <div>
                        <label className="text-xs uppercase tracking-wider block mb-1.5 font-medium" style={{ color: 'var(--text-tertiary)' }}>CVV</label>
                        <div className="relative">
                          <input type="text" defaultValue="***" className="input-field pl-10" readOnly />
                          <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
                        </div>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs uppercase tracking-wider block mb-1.5 font-medium" style={{ color: 'var(--text-tertiary)' }}>Cardholder Name</label>
                      <input type="text" defaultValue={profile?.full_name || 'Demo User'} className="input-field" readOnly />
                    </div>
                  </div>
                  <p className="text-[10px] text-center mb-4" style={{ color: 'var(--text-tertiary)' }}>
                    This is a simulated payment for demonstration purposes. No real charges will be made.
                  </p>
                  <button onClick={handlePay} disabled={paying} className="btn-primary w-full flex items-center justify-center gap-2">
                    {paying ? (<><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Processing...</>) : (<><IndianRupee size={16} />Pay ₹{getPremium(selectedPlan)} / week</>)}
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
