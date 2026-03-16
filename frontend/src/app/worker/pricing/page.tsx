"use client"

import { useEffect, useState } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import {
  ShieldCheck, Shield, ShieldAlert, Zap, Clock, Bot, Brain, Eye,
  CheckCircle, CreditCard, X, Sparkles, IndianRupee, Lock
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
      'Weekly auto-renewal',
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

export default function WorkerPricing() {
  const { user, profile } = useUserStore()
  const supabase = createClient()

  const [quote, setQuote] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPlan, setSelectedPlan] = useState<PlanTier | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [paying, setPaying] = useState(false)
  const [paymentSuccess, setPaymentSuccess] = useState(false)

  useEffect(() => {
    if (!profile) return
    fetchQuote()
  }, [profile])

  const fetchQuote = async () => {
    setLoading(true)
    try {
      const { data: session } = await supabase.auth.getSession()
      const token = session.session?.access_token
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/policies/quote`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        setQuote(await res.json())
      }
    } catch (e) {
      console.error('Could not fetch policy quote', e)
    }
    setLoading(false)
  }

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
    <div className="p-8 max-w-6xl mx-auto gradient-mesh min-h-screen">
      {/* Header */}
      <div className="text-center mb-12 animate-fade-in-up">
        <h1 className="text-4xl font-bold mb-3">Choose Your Coverage</h1>
        <p className="text-neutral-400 max-w-xl mx-auto">
          Parametric income protection tailored to your delivery schedule.
          All plans include automated claim triggers and AI-powered verification.
        </p>
        {quote && (
          <div className="mt-4 inline-flex items-center gap-2 badge badge-emerald text-xs">
            <Sparkles size={12} />
            Personalized quote based on your profile
          </div>
        )}
      </div>

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
                  Payout cap up to{' '}
                  <span className={`${tier.accentText} font-semibold`}>₹{cap || '—'}</span>
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
            <Brain size={16} /> Your Premium Breakdown
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-neutral-500 text-xs mb-1">Covered Income (B)</p>
              <p className="font-semibold text-white">₹{quote.covered_income_b || '—'}</p>
              <p className="text-[10px] text-neutral-600 mt-1">0.70 x hourly x shift x days</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Exposure Score (E)</p>
              <p className="font-semibold text-white">{quote.exposure_e || '—'}</p>
              <p className="text-[10px] text-neutral-600 mt-1">Shift and accessibility weighted</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Confidence Score (C)</p>
              <p className="font-semibold text-white">{quote.confidence_base || '—'}</p>
              <p className="text-[10px] text-neutral-600 mt-1">Trust, GPS, bank verified</p>
            </div>
            <div>
              <p className="text-neutral-500 text-xs mb-1">Weekly Premium</p>
              <p className="font-semibold text-emerald-400">₹{quote.weekly_premium_inr}</p>
              <p className="text-[10px] text-neutral-600 mt-1">Gross / (1 - 0.12 - 0.10) x U</p>
            </div>
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
                <p className="text-sm text-neutral-500 mb-6">
                  Your weekly premium of ₹{getPremium(selectedPlan.multiplier)} will be auto-debited.
                  Parametric triggers are now monitoring your zone.
                </p>
                <div className="badge badge-emerald text-xs mb-6">
                  <ShieldCheck size={12} /> Protected
                </div>
                <button onClick={closeModal} className="btn-primary w-full">
                  Back to Plans
                </button>
              </div>
            ) : (
              /* Payment Form */
              <>
                <div className="mb-6">
                  <h3 className="text-xl font-bold mb-1">Confirm Payment</h3>
                  <p className="text-sm text-neutral-400">
                    Activate your {selectedPlan.name} coverage
                  </p>
                </div>

                {/* Plan Summary */}
                <div className={`rounded-xl p-4 mb-6 bg-gradient-to-r ${selectedPlan.accentBg} border ${selectedPlan.accentBorder}`}>
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
                      Pay ₹{getPremium(selectedPlan.multiplier)}
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
