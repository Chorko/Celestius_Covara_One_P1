"use client"

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import {
  FileSearch, CheckCircle, XCircle, Clock, AlertTriangle, Shield,
  ChevronDown, ChevronUp, Eye, Image, Bot, Scale, ShieldAlert,
  Pause, ArrowUpCircle, IndianRupee, Fingerprint, Brain
} from 'lucide-react'

export default function AdminReviews() {
  const supabase = createClient()
  const [claims, setClaims] = useState<any[]>([])
  const [selectedClaim, setSelectedClaim] = useState<any | null>(null)
  const [detailData, setDetailData] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [pipelineExpanded, setPipelineExpanded] = useState(false)
  const [decisionReason, setDecisionReason] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    loadClaims()
  }, [])

  const loadClaims = async () => {
    const { data: session } = await supabase.auth.getSession()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims`, {
      headers: { Authorization: `Bearer ${session.session?.access_token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setClaims(data.claims)
    }
  }

  const loadDetail = async (id: string) => {
    setLoading(true)
    setDecisionReason('')
    setPipelineExpanded(false)
    const { data: session } = await supabase.auth.getSession()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims/${id}`, {
      headers: { Authorization: `Bearer ${session.session?.access_token}` },
    })
    if (res.ok) {
      setDetailData(await res.json())
      setSelectedClaim(id)
    }
    setLoading(false)
  }

  const handleReviewAction = async (decision: string) => {
    if (!selectedClaim) return
    setActionLoading(decision)
    const { data: session } = await supabase.auth.getSession()
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/claims/${selectedClaim}/review`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.session?.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          decision,
          decision_reason: decisionReason || `Admin review - ${decision}`,
        }),
      }
    )
    if (!res.ok) {
      console.error('Review action failed:', res.status)
      setActionLoading(null)
      return
    }
    setActionLoading(null)
    setSelectedClaim(null)
    setDetailData(null)
    setDecisionReason('')
    await loadClaims()
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return 'badge-emerald'
      case 'held':
      case 'submitted':
        return 'badge-amber'
      case 'rejected':
        return 'badge-red'
      default:
        return 'badge-blue'
    }
  }

  const pr = detailData?.payout_recommendation
  const claim = detailData?.claim
  const evidence = detailData?.evidence || []
  const explJson = pr?.explanation_json

  return (
    <div className="p-6 h-full flex flex-col md:flex-row gap-6 gradient-mesh-admin min-h-screen animate-fade-in-up">
      {/* Left Panel - Queue */}
      <div className="w-full md:w-[360px] shrink-0 glass-card flex flex-col overflow-hidden">
        <div className="p-5 border-b border-white/[0.06]">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FileSearch size={20} className="text-blue-400" /> Review Queue
          </h2>
          <p className="text-xs text-neutral-500 mt-1">
            {claims.length} claims in pipeline
          </p>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-2">
          {claims.length === 0 ? (
            <div className="text-center py-16 text-neutral-500 text-sm">
              No claims in queue
            </div>
          ) : (
            claims.map((c) => (
              <div
                key={c.id}
                onClick={() => loadDetail(c.id)}
                className={`p-4 rounded-xl cursor-pointer transition-all ${
                  selectedClaim === c.id
                    ? 'bg-blue-500/10 border border-blue-500/30 glow-blue'
                    : 'bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] hover:border-white/[0.08]'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-medium truncate pr-2">
                    {c.worker_profiles?.platform_name || 'Worker'} - {c.worker_profiles?.city || 'Unknown'}
                  </span>
                  <span className={`badge ${statusBadge(c.claim_status)} shrink-0`}>
                    {c.claim_status}
                  </span>
                </div>
                <p className="text-xs text-neutral-500 truncate">{c.claim_reason}</p>
                <p className="text-[10px] text-neutral-600 mt-2">
                  {new Date(c.claimed_at).toLocaleDateString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  })}
                  {c.trigger_events?.trigger_family && (
                    <span className="ml-2 text-blue-400/70">
                      {c.trigger_events.trigger_family}
                    </span>
                  )}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Panel - Detail */}
      <div className="flex-1 glass-card overflow-auto">
        {!selectedClaim ? (
          <div className="h-full flex flex-col items-center justify-center text-neutral-500 p-8">
            <div className="w-20 h-20 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-4">
              <Eye size={32} className="text-neutral-600" />
            </div>
            <p className="font-medium mb-1">No Claim Selected</p>
            <p className="text-sm text-neutral-600">
              Select a claim from the queue to begin review
            </p>
          </div>
        ) : loading ? (
          <div className="h-full flex items-center justify-center text-neutral-500">
            <div className="w-6 h-6 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin mr-3" />
            Loading claim details...
          </div>
        ) : detailData ? (
          <div className="p-6 space-y-6">
            {/* Claim Header */}
            <div className="flex justify-between items-start border-b border-white/[0.06] pb-5">
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <Scale size={22} className="text-blue-400" />
                  Claim {claim.id.split('-')[0]}
                </h2>
                <p className="text-sm text-neutral-500 mt-1">
                  Submitted{' '}
                  {new Date(claim.claimed_at).toLocaleString('en-IN', {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })}
                  {claim.trigger_events?.zone_id && (
                    <span> | Zone: {claim.trigger_events.zone_id.split('-')[0]}</span>
                  )}
                </p>
              </div>
              <span className={`badge ${claim.claim_mode === 'auto' ? 'badge-emerald' : 'badge-blue'}`}>
                {claim.claim_mode === 'auto' ? 'Auto-Triggered' : 'Manual Claim'}
              </span>
            </div>

            {/* Score Cards */}
            {pr && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="glass-card p-5 glow-emerald">
                  <div className="flex items-center gap-2 mb-3">
                    <IndianRupee size={16} className="text-emerald-400" />
                    <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                      Payout Recommendation
                    </h3>
                  </div>
                  <div className="text-3xl font-bold text-emerald-400 mb-1">
                    ₹{pr.recommended_payout?.toLocaleString('en-IN')}
                  </div>
                  <div className="text-xs text-neutral-500 space-y-0.5">
                    <p>Expected: ₹{pr.expected_payout}</p>
                    <p>Cap: ₹{pr.payout_cap}</p>
                  </div>
                </div>

                <div
                  className={`glass-card p-5 ${
                    pr.fraud_holdback_fh > 0.1 ? 'glow-purple' : ''
                  }`}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Fingerprint
                      size={16}
                      className={pr.fraud_holdback_fh > 0.15 ? 'text-red-400' : 'text-amber-400'}
                    />
                    <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                      Fraud Holdback
                    </h3>
                  </div>
                  <div
                    className={`text-3xl font-bold mb-1 ${
                      pr.fraud_holdback_fh > 0.15
                        ? 'text-red-400'
                        : pr.fraud_holdback_fh > 0.05
                        ? 'text-amber-400'
                        : 'text-emerald-400'
                    }`}
                  >
                    {(pr.fraud_holdback_fh * 100).toFixed(1)}%
                  </div>
                  <div className="progress-bar mt-2">
                    <div
                      className="progress-bar-fill"
                      style={{
                        width: `${Math.min(pr.fraud_holdback_fh * 100 * 2, 100)}%`,
                        background:
                          pr.fraud_holdback_fh > 0.15
                            ? '#ef4444'
                            : pr.fraud_holdback_fh > 0.05
                            ? '#f59e0b'
                            : '#10b981',
                      }}
                    />
                  </div>
                </div>

                <div className="glass-card p-5 glow-blue">
                  <div className="flex items-center gap-2 mb-3">
                    <Shield size={16} className="text-blue-400" />
                    <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                      Confidence Score
                    </h3>
                  </div>
                  <div className="text-3xl font-bold text-blue-400 mb-1">
                    {(pr.confidence_score_c * 100).toFixed(0)}%
                  </div>
                  <div className="progress-bar mt-2">
                    <div
                      className="progress-bar-fill"
                      style={{
                        width: `${pr.confidence_score_c * 100}%`,
                        background: '#3b82f6',
                      }}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Worker Statement */}
            <div className="glass-card p-5">
              <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <FileSearch size={14} /> Worker&apos;s Statement
              </h3>
              <p className="text-sm text-neutral-300 leading-relaxed">
                {claim.claim_reason}
              </p>
            </div>

            {/* Evidence Gallery */}
            {evidence.length > 0 && (
              <div className="glass-card p-5">
                <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                  <Image size={14} /> Evidence Gallery
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {evidence.map((ev: any, idx: number) => (
                    <div
                      key={idx}
                      className="aspect-video rounded-xl bg-white/[0.03] border border-white/[0.06] overflow-hidden flex items-center justify-center relative group"
                    >
                      {ev.storage_path ? (
                        <img
                          src={ev.storage_path}
                          alt={`Evidence ${idx + 1}`}
                          className="object-cover w-full h-full"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none'
                            ;(e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden')
                          }}
                        />
                      ) : null}
                      <div className={`flex flex-col items-center text-neutral-600 ${ev.storage_path ? 'hidden' : ''}`}>
                        <Image size={24} />
                        <span className="text-xs mt-1">{ev.evidence_type || 'photo'}</span>
                      </div>
                      {ev.exif_lat && (
                        <div className="absolute bottom-0 left-0 right-0 bg-black/60 backdrop-blur-sm text-[10px] text-neutral-300 p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                          GPS: {ev.exif_lat.toFixed(4)}, {ev.exif_lng?.toFixed(4)}
                          {ev.exif_timestamp && ` | ${ev.exif_timestamp}`}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Analysis */}
            {explJson?.ai_summary && (
              <div className="glass-card p-5 relative overflow-hidden border-purple-500/20 bg-purple-500/[0.03]">
                <div className="absolute top-0 right-0 w-40 h-40 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
                <h3 className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-3 flex items-center gap-2 relative">
                  <Bot size={16} /> Gemini AI Analysis
                </h3>
                <p className="text-sm text-purple-100/80 leading-relaxed italic border-l-2 border-purple-500/40 pl-4 relative">
                  &ldquo;{explJson.ai_summary}&rdquo;
                </p>
              </div>
            )}

            {/* Pipeline Breakdown (Expandable) */}
            {pr && (
              <div className="glass-card overflow-hidden">
                <button
                  onClick={() => setPipelineExpanded(!pipelineExpanded)}
                  className="w-full p-5 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
                >
                  <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider flex items-center gap-2">
                    <Brain size={14} /> Pipeline Breakdown
                  </h3>
                  {pipelineExpanded ? (
                    <ChevronUp size={16} className="text-neutral-500" />
                  ) : (
                    <ChevronDown size={16} className="text-neutral-500" />
                  )}
                </button>
                {pipelineExpanded && (
                  <div className="px-5 pb-5 border-t border-white/[0.04]">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4">
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Covered Income (B)
                        </p>
                        <p className="text-lg font-bold text-white mt-1">
                          ₹{pr.covered_weekly_income_b}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Claim Probability (p)
                        </p>
                        <p className="text-lg font-bold text-white mt-1">
                          {pr.claim_probability_p}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Severity (S)
                        </p>
                        <p className="text-lg font-bold text-white mt-1">
                          {pr.severity_score_s}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Exposure (E)
                        </p>
                        <p className="text-lg font-bold text-white mt-1">
                          {pr.exposure_score_e}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Confidence (C)
                        </p>
                        <p className="text-lg font-bold text-white mt-1">
                          {pr.confidence_score_c}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Fraud Holdback (FH)
                        </p>
                        <p className="text-lg font-bold text-white mt-1">
                          {pr.fraud_holdback_fh}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Outlier Uplift (U)
                        </p>
                        <p className="text-lg font-bold text-white mt-1">
                          {pr.outlier_uplift_u}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                          Gross Premium
                        </p>
                        <p className="text-lg font-bold text-emerald-400 mt-1">
                          ₹{pr.gross_premium}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] text-xs text-neutral-500 font-mono">
                      Final = min(Cap, B * S * E * C * (1 - FH)) = min(₹{pr.payout_cap}, ₹{pr.recommended_payout}) = ₹{pr.recommended_payout}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            {(claim.claim_status === 'held' || claim.claim_status === 'submitted') ? (
              <div className="border-t border-white/[0.06] pt-6 space-y-4">
                <div>
                  <label className="text-xs font-semibold text-neutral-400 uppercase tracking-wider block mb-2">
                    Decision Reason (Optional)
                  </label>
                  <textarea
                    value={decisionReason}
                    onChange={(e) => setDecisionReason(e.target.value)}
                    placeholder="Provide reasoning for the review decision..."
                    className="glass-input min-h-[80px] resize-none"
                  />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <button
                    onClick={() => handleReviewAction('approve')}
                    disabled={actionLoading !== null}
                    className="flex items-center justify-center gap-2 py-3 rounded-xl font-medium text-sm transition-all bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/25 hover:border-emerald-500/40 disabled:opacity-50"
                  >
                    {actionLoading === 'approve' ? (
                      <div className="w-4 h-4 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
                    ) : (
                      <CheckCircle size={16} />
                    )}
                    Approve
                  </button>
                  <button
                    onClick={() => handleReviewAction('hold')}
                    disabled={actionLoading !== null}
                    className="flex items-center justify-center gap-2 py-3 rounded-xl font-medium text-sm transition-all bg-amber-500/15 text-amber-400 border border-amber-500/20 hover:bg-amber-500/25 hover:border-amber-500/40 disabled:opacity-50"
                  >
                    {actionLoading === 'hold' ? (
                      <div className="w-4 h-4 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
                    ) : (
                      <Pause size={16} />
                    )}
                    Hold
                  </button>
                  <button
                    onClick={() => handleReviewAction('escalate')}
                    disabled={actionLoading !== null}
                    className="flex items-center justify-center gap-2 py-3 rounded-xl font-medium text-sm transition-all bg-purple-500/15 text-purple-400 border border-purple-500/20 hover:bg-purple-500/25 hover:border-purple-500/40 disabled:opacity-50"
                  >
                    {actionLoading === 'escalate' ? (
                      <div className="w-4 h-4 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin" />
                    ) : (
                      <ArrowUpCircle size={16} />
                    )}
                    Escalate
                  </button>
                  <button
                    onClick={() => handleReviewAction('reject')}
                    disabled={actionLoading !== null}
                    className="flex items-center justify-center gap-2 py-3 rounded-xl font-medium text-sm transition-all bg-red-500/15 text-red-400 border border-red-500/20 hover:bg-red-500/25 hover:border-red-500/40 disabled:opacity-50"
                  >
                    {actionLoading === 'reject' ? (
                      <div className="w-4 h-4 border-2 border-red-400/30 border-t-red-400 rounded-full animate-spin" />
                    ) : (
                      <XCircle size={16} />
                    )}
                    Reject
                  </button>
                </div>
              </div>
            ) : (
              <div className="border-t border-white/[0.06] pt-6 text-center">
                <p className="text-neutral-500 text-sm">
                  This claim has already been{' '}
                  <span className="font-semibold text-neutral-400">{claim.claim_status}</span>.
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}
