"use client"

import { useEffect, useState, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import {
  ShieldCheck, Shield, ShieldAlert, Clock,
  CheckCircle, CreditCard, X, Sparkles, IndianRupee, Lock, Brain,
  RefreshCw, TrendingUp, AlertTriangle, Activity
} from 'lucide-react'

interface PlanTier {
  name: string
  multiplier: number
  icon: React.ReactNode
  popular: boolean
  features: string[]
  processing: string
  color: string
  accentBorder: string
  accentBg: string
  accentText: string
}

const TIERS: PlanTier[] = [
  {
    name: 'Basic Shield',
    multiplier: 1,
    icon: <Shield size={28} />,
    popular: false,
    features: [
      'Core disruption coverage (rain, AQI, heat)',
      'Standard payout cap',
      'Basic fraud protection',
      'Weekly auto-renewal option',
    ],
    processing: '48h claim processing',
    color: 'blue',
    accentBorder: 'border-blue-500/30',
    accentBg: 'from-blue-500/10 to-blue-900/10',
    accentText: 'text-blue-400',
  },
  {
    name: 'Pro Guard',
    multiplier: 1.5,
    icon: <ShieldCheck size={28} />,
    popular: true,
    features: [
      'All disruption types + operational triggers',
      '1.5x payout cap',
      'Advanced AI fraud detection',
      'Gemini AI narrative reports',
      'Priority support queue',
    ],
    processing: '24h priority processing',
    color: 'emerald',
    accentBorder: 'border-emerald-500/30',
    accentBg: 'from-emerald-500/10 to-emerald-900/10',
    accentText: 'text-emerald-400',
  },
  {
    name: 'Elite Cover',
    multiplier: 2.5,
    icon: <ShieldAlert size={28} />,
    popular: false,
    features: [
      'All triggers + composite events',
      '2.5x payout cap',
      'Dedicated claim adjuster',
      'Full Income Twin analytics',
      'Zero-Touch instant payouts',
      'Multi-zone coverage',
    ],
    processing: 'Instant processing',
    color: 'purple',
    accentBorder: 'border-purple-500/30',
    accentBg: 'from-purple-500/10 to-purple-900/10',
    accentText: 'text-purple-400',
  },
]

// Simulated weekly zone risk factor — in production this comes from
// the trigger-event frequency / weather-forecast pipeline each Monday.
function getWeeklyRiskFactor(city: string): { factor: number; label: string; trend: 'up' | 'down' | 'stable' } {
  const factors: Record<string, { factor: number; label: string; trend: 'up' | 'down' | 'stable' }> = {
    Mumbai:    { factor: 1.15, label: 'Elevated — pre-monsoon rainfall risk', trend: 'up' },
    Delhi:     { factor: 1.08, label: 'Moderate — AQI forecast improving',    trend: 'down' },
    Bangalore: { factor: 1.02, label: 'Low — stable conditions expected',     trend: 'stable' },
    Hyderabad: { factor: 1.05, label: 'Moderate — spot AQI fluctuations',     trend: 'stable' },
  }
  return factors[city] ?? { factor: 1.0, label: 'Normal', trend: 'stable' as const }
}

interface QuoteData {
  weekly_premium_inr: number
  max_payout_cap_inr: number
  covered_income_b: number
  observed_weekly_gross: number
  exposure_e: number
  confidence_base: number
  risk_factor: number
  B: number
  E: number
  C: number
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
        // Try observed weekly gross from last 7 days of daily stats
        let observed_weekly_gross: number | null = null
        try {
          const { data: recentStats } = await supabase
            .from('platform_worker_daily_stats')
            .select('gross_earnings_inr')
            .eq('worker_profile_id', wp.profile_id)
            .order('stat_date', { ascending: false })
            .limit(7)
          if (recentStats && recentStats.length >= 3) {
            const totalGross = recentStats.reduce((s, r) => s + (r.gross_earnings_inr || 0), 0)
            observed_weekly_gross = Math.round((totalGross / recentStats.length) * 6)
          }
        } catch { /* fallback below */ }

        // Fallback: hourly × 8h × 6 days
        const fallback_weekly_gross = Math.round((wp.avg_hourly_income_inr || 0) * 8 * 6)
        const weekly_gross = observed_weekly_gross ?? fallback_weekly_gross

        // Covered weekly income B = 70% of gross
        const B = Math.round(weekly_gross * 0.70)
        // Payout cap = 75% of covered weekly income
        const raw_cap = Math.round(B * 0.75)
        // Sanity guard: cap at ₹10,000 for demo/synthetic flows
        const payout_cap = Math.min(raw_cap, 10000)

        // Weekly zone risk factor
        const risk = getWeeklyRiskFactor(wp.city)
        setRiskInfo(risk)

        const cityFactor: Record<string, number> = { Mumbai: 1.3, Delhi: 1.2, Bangalore: 1.25 }
        const C = cityFactor[wp.city] ?? 1.0
        const E = wp.trust_score ?? 0.8

        // Premium includes weekly risk factor
        const basePremium = B * 0.035 * E * C
        const weeklyPremium = Math.round(basePremium * risk.factor)

        setQuote({
          weekly_premium_inr: weeklyPremium,
          max_payout_cap_inr: payout_cap,
          covered_income_b: B,
          observed_weekly_gross: weekly_gross,
          exposure_e: Math.round(E * 100) / 100,
          confidence_base: C,
          risk_factor: risk.factor,
          B,
          E: Math.round(E * 100) / 100,
          C,
        })
      }
    } catch (e) {
      console.error('Could not fetch policy quote', e)
    }
    setLoading(false)
  }, [supabase, profile])

  useEffect(() => {
    if (!profile) return
    // Wrap in IIFE to avoid eslint set-state-in-effect
    void fetchQuote()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id])

  const handleChoosePlan = (tier: PlanTier) => {
    setSelectedPlan(tier)
    setPaymentSuccess(false)
    setPaying(false)
    setShowModal(true)
  }

  const handlePay = () => {
    setPaying(true)
    setTimeout(() => {
      setPaying(false)
      setPaymentSuccess(true)
    }, 2000)
  }

  const closeModal = () => {
    setShowModal(false)
    setSelectedPlan(null)
    setPaymentSuccess(false)
  }

  const getPremium = (multiplier: number) => {
    if (!quote) return 0
    return Math.round(quote.weekly_premium_inr * multiplier)
  }

  const getCap = (multiplier: number) => {
    if (!quote) return 0
    return Math.round(quote.max_payout_cap_inr * multiplier)
  }

  if (loading) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <div className="animate-pulse space-y-6">
          <div className="h-10 w-72 rounded-lg bg-white/5" />
          <div className="h-5 w-96 rounded bg-white/5" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
            {[1, 2, 3].map((i) => (
              <div key={i} className="glass-card p-8 h-96 rounded-2xl" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 md:p-8 pb-28 max-w-6xl mx-auto gradient-mesh min-h-screen">
      {/* Header */}
      <div className="text-center mb-8 animate-fade-in-up">
        <h1 className="text-4xl font-bold mb-3">Choose Your Coverage</h1>
        <p className="text-neutral-400 max-w-xl mx-auto">
          Parametric income protection tailored to your delivery schedule.
          All plans include automated claim triggers and AI-powered verification.
        </p>
        {quote && (
          <div className="mt-4 inline-flex items-center gap-2 badge badge-emerald text-xs">
            <Sparkles size={12} />
            Personalized weekly quote based on your profile
          </div>
        )}
      </div>

      {/* Weekly Risk Factor + Auto-Renew Bar */}
      {quote && (
        <div className="glass-card p-5 mb-8 animate-fade-in-up delay-100">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            {/* Risk factor */}
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                riskInfo.trend === 'up' ? 'bg-amber-500/10' :
                riskInfo.trend === 'down' ? 'bg-emerald-500/10' : 'bg-blue-500/10'
              }`}>
                {riskInfo.trend === 'up' && <TrendingUp size={20} className="text-amber-400" />}
                {riskInfo.trend === 'down' && <TrendingUp size={20} className="text-emerald-400 rotate-180" />}
                {riskInfo.trend === 'stable' && <Activity size={20} className="text-blue-400" />}
              </div>
              <div>
                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                  This Week&apos;s Risk Factor
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-sm font-bold ${
                    riskInfo.factor > 1.1 ? 'text-amber-400' :
                    riskInfo.factor < 1.0 ? 'text-emerald-400' : 'text-blue-400'
                  }`}>
                    {riskInfo.factor.toFixed(2)}×
                  </span>
                  <span className="text-xs text-neutral-500">{riskInfo.label}</span>
                </div>
                <p className="text-[10px] text-neutral-600 mt-0.5">
                  Premium adjusts weekly based on zone weather and disruption forecasts
                </p>
              </div>
            </div>

            {/* Auto-renew toggle */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <RefreshCw size={16} className={autoRenew ? 'text-emerald-400' : 'text-neutral-600'} />
                <span className="text-sm text-neutral-300">Auto-Renew</span>
              </div>
              <button
                onClick={() => setAutoRenew(!autoRenew)}
                className={`relative w-12 h-6 rounded-full transition-all duration-200 ${
                  autoRenew
                    ? 'bg-emerald-500/30 border border-emerald-500/40'
                    : 'bg-white/[0.06] border border-white/[0.08]'
                }`}
                aria-label="Toggle auto-renew"
              >
                <div className={`absolute top-0.5 w-5 h-5 rounded-full transition-all duration-200 ${
                  autoRenew
                    ? 'left-6 bg-emerald-400'
                    : 'left-0.5 bg-neutral-500'
                }`} />
              </button>
              <div className="text-xs text-neutral-500">
                {autoRenew ? (
                  <span className="text-emerald-400 font-medium">ON — renews weekly</span>
                ) : (
                  <span>OFF — manual renewal</span>
                )}
              </div>
            </div>
          </div>

          {autoRenew && (
            <div className="mt-3 flex items-center gap-2 text-[10px] text-neutral-500 border-t border-white/[0.04] pt-3">
              <AlertTriangle size={10} className="text-amber-400/60" />
              Weekly premium may change each Monday based on updated zone risk factors.
              You can disable auto-renew at any time.
            </div>
          )}
        </div>
      )}

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        {TIERS.map((tier, idx) => {
          const premium = getPremium(tier.multiplier)
          const cap = getCap(tier.multiplier)

          return (
            <div
              key={tier.name}
              className={`glass-card p-8 relative flex flex-col animate-fade-in-up ${
                tier.popular ? `${tier.accentBorder} glow-emerald` : ''
              }`}
              style={{ animationDelay: `${(idx + 1) * 100}ms` }}
            >
              {/* Popular badge */}
              {tier.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="badge badge-emerald px-4 py-1 text-xs font-bold">
                    MOST POPULAR
                  </span>
                </div>
              )}

              {/* Plan Header */}
              <div className="mb-6">
                <div className={`${tier.accentText} mb-3`}>{tier.icon}</div>
                <h2 className="text-xl font-bold mb-1">{tier.name}</h2>
                <p className="text-xs text-neutral-500 uppercase tracking-wider">
                  {tier.multiplier}x coverage multiplier
                </p>
              </div>

              {/* Price */}
              <div className="mb-6">
                <div className="flex items-baseline gap-1">
                  <span className="text-sm text-neutral-400">₹</span>
                  <span className="text-4xl font-bold">{premium || '—'}</span>
                  <span className="text-sm text-neutral-500">/week</span>
                </div>
                <p className="text-xs text-neutral-500 mt-2">
                  Weekly payout cap up to{' '}
                  <span className={`${tier.accentText} font-semibold`}>₹{cap?.toLocaleString('en-IN') || '—'}</span>
                </p>
              </div>

              {/* Processing */}
              <div className="flex items-center gap-2 mb-5 text-sm text-neutral-400">
                <Clock size={14} />
                <span>{tier.processing}</span>
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-8 flex-1">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm text-neutral-300">
                    <CheckCircle size={16} className={`${tier.accentText} mt-0.5 shrink-0`} />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA Button */}
              <button
                onClick={() => handleChoosePlan(tier)}
                disabled={!quote}
                className={`w-full py-3 rounded-xl font-semibold text-sm transition-all ${
                  tier.popular
                    ? 'btn-primary'
                    : 'btn-secondary hover:border-white/20'
                }`}
              >
                Choose {tier.name}
              </button>
            </div>
          )
        })}
      </div>

      {/* Formula Breakdown */}
      {quote && (
        <div className="glass-card p-6 animate-fade-in-up delay-400">
          <h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Brain size={16} /> Your Weekly Premium Breakdown
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div>
              <p className="text-neutral-500 text-xs mb-1">Observed Weekly Gross</p>
              <p className="font-semibold text-white">₹{quote.observed_weekly_gross?.toLocaleString('en-IN') || '—'}</p>
              <p className="text-[10px] text-neutral-600 mt-1">from last 7 active days</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Covered Income (B)</p>
              <p className="font-semibold text-white">₹{quote.covered_income_b?.toLocaleString('en-IN') || '—'}</p>
              <p className="text-[10px] text-neutral-600 mt-1">0.70 × weekly gross</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Exposure Score (E)</p>
              <p className="font-semibold text-white">{quote.exposure_e || '—'}</p>
              <p className="text-[10px] text-neutral-600 mt-1">Trust + accessibility</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">City Factor (C)</p>
              <p className="font-semibold text-white">{quote.confidence_base || '—'}</p>
              <p className="text-[10px] text-neutral-600 mt-1">Zone risk multiplier</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Weekly Premium</p>
              <p className="font-semibold text-emerald-400">₹{quote.weekly_premium_inr}</p>
              <p className="text-[10px] text-neutral-600 mt-1">B × 0.035 × E × C × {quote.risk_factor?.toFixed(2)}</p>
            </div>
          </div>
          <div className="mt-4 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] text-xs text-neutral-500 font-mono">
            Payout Cap = 0.75 × B = 0.75 × ₹{quote.covered_income_b?.toLocaleString('en-IN')} = ₹{quote.max_payout_cap_inr?.toLocaleString('en-IN')} (weekly max)
          </div>
        </div>
      )}

      {/* Payment Modal */}
      {showModal && selectedPlan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={closeModal}
          />

          {/* Modal Content */}
          <div className="glass-strong rounded-2xl p-8 w-full max-w-md relative z-10 animate-fade-in-up">
            {/* Close */}
            <button
              onClick={closeModal}
              className="absolute top-4 right-4 text-neutral-500 hover:text-white transition-colors"
            >
              <X size={20} />
            </button>

            {paymentSuccess ? (
              /* Success State */
              <div className="text-center py-6">
                <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-emerald-500/20 flex items-center justify-center glow-emerald">
                  <CheckCircle size={40} className="text-emerald-400" />
                </div>
                <h3 className="text-2xl font-bold mb-2">Coverage Activated!</h3>
                <p className="text-neutral-400 mb-2">
                  {selectedPlan.name} plan is now active.
                </p>
                <p className="text-sm text-neutral-500 mb-4">
                  Your weekly premium of ₹{getPremium(selectedPlan.multiplier)} is set.
                  Parametric triggers are now monitoring your zone.
                </p>
                <div className="flex items-center justify-center gap-3 mb-6">
                  <div className="badge badge-emerald text-xs">
                    <ShieldCheck size={12} /> Protected
                  </div>
                  {autoRenew && (
                    <div className="badge badge-blue text-xs">
                      <RefreshCw size={10} /> Auto-Renew ON
                    </div>
                  )}
                </div>
                {autoRenew && (
                  <p className="text-[10px] text-neutral-600 mb-4">
                    Premium auto-renews weekly. Price may adjust based on zone risk factors.
                  </p>
                )}
                <button onClick={closeModal} className="btn-primary w-full">
                  Back to Plans
                </button>
              </div>
            ) : (
              /* Payment Form */
              <>
                <div className="mb-6">
                  <h3 className="text-xl font-bold mb-1">Confirm Weekly Payment</h3>
                  <p className="text-sm text-neutral-400">
                    Activate your {selectedPlan.name} coverage
                  </p>
                </div>

                {/* Plan Summary */}
                <div className={`rounded-xl p-4 mb-4 bg-gradient-to-r ${selectedPlan.accentBg} border ${selectedPlan.accentBorder}`}>
                  <div className="flex justify-between items-center">
                    <div>
                      <p className={`font-semibold ${selectedPlan.accentText}`}>
                        {selectedPlan.name}
                      </p>
                      <p className="text-xs text-neutral-400">Weekly coverage plan</p>
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-bold">₹{getPremium(selectedPlan.multiplier)}</p>
                      <p className="text-xs text-neutral-500">/week</p>
                    </div>
                  </div>
                </div>

                {/* Auto-Renew in modal */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] mb-4">
                  <div className="flex items-center gap-2 text-sm">
                    <RefreshCw size={14} className={autoRenew ? 'text-emerald-400' : 'text-neutral-600'} />
                    <span className="text-neutral-300">Weekly Auto-Renew</span>
                  </div>
                  <button
                    onClick={() => setAutoRenew(!autoRenew)}
                    className={`relative w-10 h-5 rounded-full transition-all duration-200 ${
                      autoRenew
                        ? 'bg-emerald-500/30 border border-emerald-500/40'
                        : 'bg-white/[0.06] border border-white/[0.08]'
                    }`}
                  >
                    <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all duration-200 ${
                      autoRenew
                        ? 'left-5 bg-emerald-400'
                        : 'left-0.5 bg-neutral-500'
                    }`} />
                  </button>
                </div>

                {/* Mock Card Inputs */}
                <div className="space-y-4 mb-6">
                  <div>
                    <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                      Card Number
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        defaultValue="4242 4242 4242 4242"
                        className="glass-input pl-10"
                        readOnly
                      />
                      <CreditCard size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                        Expiry
                      </label>
                      <input
                        type="text"
                        defaultValue="12/28"
                        className="glass-input"
                        readOnly
                      />
                    </div>
                    <div>
                      <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                        CVV
                      </label>
                      <div className="relative">
                        <input
                          type="text"
                          defaultValue="***"
                          className="glass-input pl-10"
                          readOnly
                        />
                        <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
                      </div>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                      Cardholder Name
                    </label>
                    <input
                      type="text"
                      defaultValue={profile?.full_name || 'Demo User'}
                      className="glass-input"
                      readOnly
                    />
                  </div>
                </div>

                <p className="text-[10px] text-neutral-600 text-center mb-4">
                  This is a simulated payment for demonstration purposes. No real charges will be made.
                </p>

                {/* Pay Button */}
                <button
                  onClick={handlePay}
                  disabled={paying}
                  className="btn-primary w-full flex items-center justify-center gap-2"
                >
                  {paying ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <IndianRupee size={16} />
                      Pay ₹{getPremium(selectedPlan.multiplier)} / week
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
