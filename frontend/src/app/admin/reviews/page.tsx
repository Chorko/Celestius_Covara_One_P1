"use client"

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import { backendGet, backendPost, BackendApiError } from '@/lib/backendApi'
import {
  FileSearch, CheckCircle, XCircle, Shield,
  ChevronDown, ChevronUp, Eye, Image, Bot, Scale,
  Pause, ArrowUpCircle, IndianRupee, Fingerprint, Brain, AlertTriangle
} from 'lucide-react'

interface ClaimRecord {
  id: string; claim_status: string; claim_reason: string; claim_mode?: string; claimed_at: string
  worker_profiles?: { platform_name?: string; city?: string; trust_score?: number; profiles?: { full_name?: string; email?: string } }
  trigger_events?: { trigger_family?: string; trigger_code?: string; zone_id?: string }
}
interface PayoutRecommendation {
  recommended_payout?: number; expected_payout?: number; payout_cap?: number; fraud_holdback_fh?: number
  confidence_score_c?: number; covered_weekly_income_b?: number; claim_probability_p?: number
  severity_score_s?: number; exposure_score_e?: number; outlier_uplift_u?: number; gross_premium?: number
  explanation_json?: { ai_summary?: string }
}
interface EvidenceItem { storage_path?: string; evidence_type?: string; exif_lat?: number; exif_lng?: number; exif_timestamp?: string }
interface DetailData { claim: ClaimRecord; payout_recommendation: PayoutRecommendation | null; evidence: EvidenceItem[] }

interface ClaimsListResponse {
  claims: ClaimRecord[]
}

interface ClaimDetailResponse {
  claim: ClaimRecord
  payout_recommendation: PayoutRecommendation | null
  evidence: EvidenceItem[]
}

function formatApiError(error: unknown): string {
  if (error instanceof BackendApiError) {
    if (error.status === 401) {
      return 'Session expired. Please sign in again.'
    }
    if (error.status === 403) {
      return 'Admin role required for this action.'
    }
    return error.detail
  }

  return error instanceof Error ? error.message : 'Request failed'
}

export default function AdminReviews() {
  const supabase = createClient()
  const [claims, setClaims] = useState<ClaimRecord[]>([])
  const [selectedClaim, setSelectedClaim] = useState<string | null>(null)
  const [detailData, setDetailData] = useState<DetailData | null>(null)
  const [loading, setLoading] = useState(false)
  const [pipelineExpanded, setPipelineExpanded] = useState(false)
  const [decisionReason, setDecisionReason] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const loadClaims = useCallback(async () => {
    try {
      const response = await backendGet<ClaimsListResponse>(supabase, '/claims/')
      setClaims(response.claims || [])
    } catch (e) { console.error('Could not load claims', e) }
  }, [supabase])

  useEffect(() => { loadClaims() }, [loadClaims])

  const loadDetail = async (claimId: string) => {
    setSelectedClaim(claimId)
    setLoading(true)
    setActionError(null)
    setPipelineExpanded(false)

    try {
      const detail = await backendGet<ClaimDetailResponse>(supabase, `/claims/${claimId}`)
      setDetailData({
        claim: detail.claim,
        payout_recommendation: detail.payout_recommendation,
        evidence: detail.evidence || [],
      })
    } catch (e: unknown) {
      setActionError(formatApiError(e))
      setDetailData(null)
    } finally {
      setLoading(false)
    }
  }

  const handleReviewAction = async (decision: string) => {
    if (!detailData) return
    const claimId = detailData.claim.id
    setActionLoading(decision)
    setActionError(null)

    try {
      if (decision === 'flag_post_approval') {
        await backendPost(supabase, `/claims/${claimId}/flag`, {
          fraud_severity: 'moderate',
          reason: decisionReason || undefined,
        })
      } else {
        await backendPost(supabase, `/claims/${claimId}/review`, {
          decision,
          decision_reason: decisionReason || undefined,
        })
      }
    } catch (e: unknown) {
      setActionError(formatApiError(e))
      setActionLoading(null)
      return
    }

    setActionLoading(null)
    setSelectedClaim(null)
    setDetailData(null)
    setDecisionReason('')
    await loadClaims()
  }

  const statusBadge = (s: string) => {
    switch (s) {
      case 'approved': case 'auto_approved': case 'paid': return 'badge-success'
      case 'soft_hold_verification': return 'badge-info'
      case 'fraud_escalated_review': return 'badge-purple'
      case 'submitted': return 'badge-warning'
      case 'rejected': case 'post_approval_flagged': return 'badge-danger'
      default: return 'badge-info'
    }
  }
  const statusLabel = (s: string) => ({ auto_approved: 'Auto-Approved', approved: 'Approved', paid: 'Paid', submitted: 'Submitted', soft_hold_verification: 'Verification', fraud_escalated_review: 'Fraud Review', rejected: 'Rejected', post_approval_flagged: 'Flagged' } as Record<string, string>)[s] || s

  const pr = detailData?.payout_recommendation
  const claim = detailData?.claim
  const evidence = detailData?.evidence || []
  const explJson = pr?.explanation_json
  const isFraud = (pr?.fraud_holdback_fh ?? 0) > 0.30
  const canReview = ['submitted', 'soft_hold_verification', 'fraud_escalated_review', 'held'].includes(claim?.claim_status || '')
  const canPostApprovalFlag = ['approved', 'auto_approved', 'paid'].includes(claim?.claim_status || '')

  return (
    <div className="p-4 md:p-6 pb-28 h-full flex flex-col md:flex-row gap-6 min-h-screen page-mesh animate-fade-in-up">
      {/* Left Panel */}
      <div className="w-full md:w-[340px] shrink-0 card flex flex-col overflow-hidden">
        <div className="p-5" style={{ borderBottom: '1px solid var(--border-primary)' }}>
          <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><FileSearch size={18} style={{ color: 'var(--accent)' }} /> Review Queue</h2>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{claims.length} claims in pipeline</p>
        </div>
        <div className="flex-1 overflow-auto p-3 space-y-2">
          {claims.length === 0 ? (
            <div className="text-center py-16 text-sm" style={{ color: 'var(--text-tertiary)' }}>No claims in queue</div>
          ) : ( claims.map(c => (
            <div key={c.id} onClick={() => loadDetail(c.id)}
              className="p-4 rounded-lg cursor-pointer transition-all"
              style={{
                background: selectedClaim === c.id ? 'var(--accent-muted)' : 'var(--bg-tertiary)',
                border: `1px solid ${selectedClaim === c.id ? 'var(--accent)' : 'var(--border-primary)'}`,
              }}>
              <div className="flex justify-between items-start mb-2">
                <span className="text-sm font-medium truncate pr-2" style={{ color: 'var(--text-primary)' }}>{c.worker_profiles?.platform_name || 'Worker'} - {c.worker_profiles?.city || 'Unknown'}</span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={`badge ${statusBadge(c.claim_status)} shrink-0`}>{statusLabel(c.claim_status)}</span>
                </div>
              </div>
              <p className="text-xs truncate" style={{ color: 'var(--text-tertiary)' }}>{c.claim_reason}</p>
              <p className="text-[10px] mt-2" style={{ color: 'var(--text-tertiary)' }}>
                {new Date(c.claimed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                {c.trigger_events?.trigger_family && <span className="ml-2" style={{ color: 'var(--accent)' }}>{c.trigger_events.trigger_family}</span>}
              </p>
            </div>
          )))}
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 card overflow-auto">
        {!selectedClaim ? (
          <div className="h-full flex flex-col items-center justify-center p-8">
            <div className="w-20 h-20 rounded-xl flex items-center justify-center mb-4" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
              <Eye size={32} style={{ color: 'var(--text-tertiary)' }} />
            </div>
            <p className="font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>No Claim Selected</p>
            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Select a claim from the queue to begin review</p>
          </div>
        ) : loading ? (
          <div className="h-full flex items-center justify-center" style={{ color: 'var(--text-tertiary)' }}>
            <div className="w-6 h-6 border-2 rounded-full animate-spin mr-3" style={{ borderColor: 'var(--border-secondary)', borderTopColor: 'var(--accent)' }} />Loading claim details...
          </div>
        ) : detailData ? (
          <div className="p-6 space-y-6">
            {/* Claim Header */}
            <div className="flex justify-between items-start pb-5" style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                  <Scale size={22} style={{ color: 'var(--accent)' }} /> Claim {claim?.id?.split('-')[0] ?? '???'}
                </h2>
                <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>
                  Submitted {claim?.claimed_at ? new Date(claim.claimed_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'N/A'}
                  {claim?.trigger_events?.zone_id && <span> | Zone: {claim.trigger_events.zone_id.split('-')[0]}</span>}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {isFraud && <span className="badge-danger flex items-center gap-1"><AlertTriangle size={12} /> Fraud Detected</span>}
                <span className={claim?.claim_mode === 'trigger_auto' ? 'badge-success' : 'badge-info'}>
                  {claim?.claim_mode === 'trigger_auto' ? 'Auto-Triggered' : 'Manual Claim'}
                </span>
              </div>
            </div>

            {/* Score Cards */}
            {pr && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="card p-5" style={{ borderLeft: '3px solid var(--success)' }}>
                  <div className="flex items-center gap-2 mb-3"><IndianRupee size={16} style={{ color: 'var(--success)' }} /><h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Payout</h3></div>
                  <div className="text-3xl font-bold" style={{ color: 'var(--success)' }}>₹{pr.recommended_payout?.toLocaleString('en-IN')}</div>
                  <div className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}><p>Expected: ₹{pr.expected_payout}</p><p>Cap: ₹{pr.payout_cap}</p></div>
                </div>
                <div className="card p-5" style={{ borderLeft: `3px solid ${(pr.fraud_holdback_fh ?? 0) > 0.15 ? 'var(--danger)' : (pr.fraud_holdback_fh ?? 0) > 0.05 ? 'var(--warning)' : 'var(--success)'}` }}>
                  <div className="flex items-center gap-2 mb-3"><Fingerprint size={16} style={{ color: (pr.fraud_holdback_fh ?? 0) > 0.15 ? 'var(--danger)' : 'var(--warning)' }} /><h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Fraud Holdback</h3></div>
                  <div className="text-3xl font-bold" style={{ color: (pr.fraud_holdback_fh ?? 0) > 0.15 ? 'var(--danger)' : (pr.fraud_holdback_fh ?? 0) > 0.05 ? 'var(--warning)' : 'var(--success)' }}>{((pr.fraud_holdback_fh ?? 0) * 100).toFixed(1)}%</div>
                  <div className="progress-bar mt-2"><div className="progress-bar-fill" style={{ width: `${Math.min((pr.fraud_holdback_fh ?? 0) * 200, 100)}%`, background: (pr.fraud_holdback_fh ?? 0) > 0.15 ? 'var(--danger)' : (pr.fraud_holdback_fh ?? 0) > 0.05 ? 'var(--warning)' : 'var(--success)' }} /></div>
                </div>
                <div className="card p-5" style={{ borderLeft: '3px solid var(--accent)' }}>
                  <div className="flex items-center gap-2 mb-3"><Shield size={16} style={{ color: 'var(--accent)' }} /><h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Confidence</h3></div>
                  <div className="text-3xl font-bold" style={{ color: 'var(--accent)' }}>{((pr.confidence_score_c ?? 0) * 100).toFixed(0)}%</div>
                  <div className="progress-bar mt-2"><div className="progress-bar-fill" style={{ width: `${(pr.confidence_score_c ?? 0) * 100}%`, background: 'var(--accent)' }} /></div>
                </div>
              </div>
            )}

            {/* Worker Statement */}
            {claim?.claim_reason && (
              <div className="card p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}><FileSearch size={14} /> Worker&apos;s Statement</h3>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{claim.claim_reason}</p>
              </div>
            )}

            {/* Evidence Gallery */}
            {evidence.length > 0 && (
              <div className="card p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}><Image size={14} /> Evidence Gallery</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {evidence.map((ev, idx) => (
                    <div key={idx} className="aspect-video rounded-lg overflow-hidden flex items-center justify-center relative group" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                      {ev.storage_path ? (
                        /* eslint-disable-next-line @next/next/no-img-element */
                        <img src={ev.storage_path} alt={`Evidence ${idx + 1}`} className="object-cover w-full h-full" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden') }} />
                      ) : null}
                      <div className={`flex flex-col items-center ${ev.storage_path ? 'hidden' : ''}`} style={{ color: 'var(--text-tertiary)' }}>
                        <Image size={24} aria-label="Evidence placeholder" /><span className="text-xs mt-1">{ev.evidence_type || 'photo'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Analysis */}
            {explJson?.ai_summary && (
              <div className="card p-5 relative overflow-hidden" style={{ borderLeft: '3px solid var(--info)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--info)' }}><Bot size={16} /> Gemini AI Analysis</h3>
                <p className="text-sm leading-relaxed italic pl-4" style={{ color: 'var(--text-secondary)', borderLeft: '2px solid var(--info)' }}>&ldquo;{explJson.ai_summary}&rdquo;</p>
              </div>
            )}

            {/* Pipeline Breakdown */}
            {pr && (
              <div className="card overflow-hidden">
                <button onClick={() => setPipelineExpanded(!pipelineExpanded)} className="w-full p-5 flex items-center justify-between text-left transition-colors" style={{ color: 'var(--text-primary)' }}>
                  <h3 className="text-xs font-semibold uppercase tracking-wider flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}><Brain size={14} /> Pipeline Breakdown</h3>
                  {pipelineExpanded ? <ChevronUp size={16} style={{ color: 'var(--text-tertiary)' }} /> : <ChevronDown size={16} style={{ color: 'var(--text-tertiary)' }} />}
                </button>
                {pipelineExpanded && (
                  <div className="px-5 pb-5" style={{ borderTop: '1px solid var(--border-primary)' }}>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4">
                      {[
                        { label: 'Covered Income (B)', val: `₹${pr.covered_weekly_income_b}` },
                        { label: 'Claim Probability (p)', val: pr.claim_probability_p },
                        { label: 'Severity (S)', val: pr.severity_score_s },
                        { label: 'Exposure (E)', val: pr.exposure_score_e },
                        { label: 'Confidence (C)', val: pr.confidence_score_c },
                        { label: 'Fraud Holdback (FH)', val: pr.fraud_holdback_fh },
                        { label: 'Outlier Uplift (U)', val: pr.outlier_uplift_u },
                        { label: 'Gross Premium', val: `₹${pr.gross_premium}`, highlight: true },
                      ].map((item, i) => (
                        <div key={i}>
                          <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{item.label}</p>
                          <p className="text-lg font-bold mt-1" style={{ color: item.highlight ? 'var(--success)' : 'var(--text-primary)' }}>{item.val}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 p-3 rounded-lg text-xs font-mono" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}>
                      Final = min(Cap, B × S × E × C × (1 - FH)) = min(₹{pr.payout_cap}, ₹{pr.recommended_payout}) = ₹{pr.recommended_payout}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            {canReview ? (
              <div className="pt-6 space-y-4" style={{ borderTop: '1px solid var(--border-primary)' }}>
                {actionError && <div className="p-3 rounded-lg text-sm" style={{ background: 'var(--danger-muted)', border: '1px solid var(--danger)', color: 'var(--danger)' }}>{actionError}</div>}
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider block mb-2" style={{ color: 'var(--text-tertiary)' }}>Decision Reason (Optional)</label>
                  <textarea value={decisionReason} onChange={e => setDecisionReason(e.target.value)} placeholder="Provide reasoning..." className="input-field min-h-[80px] resize-none" />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { key: 'approve', label: 'Approve', icon: <CheckCircle size={16} />, bg: 'var(--success-muted)', color: 'var(--success)', border: 'var(--success)' },
                    { key: 'hold', label: 'Hold', icon: <Pause size={16} />, bg: 'var(--warning-muted)', color: 'var(--warning)', border: 'var(--warning)' },
                    { key: 'escalate', label: 'Escalate', icon: <ArrowUpCircle size={16} />, bg: 'var(--info-muted)', color: 'var(--info)', border: 'var(--info)' },
                    { key: 'reject', label: 'Reject', icon: <XCircle size={16} />, bg: 'var(--danger-muted)', color: 'var(--danger)', border: 'var(--danger)' },
                  ].map(a => (
                    <button key={a.key} onClick={() => handleReviewAction(a.key)} disabled={actionLoading !== null}
                      className="flex items-center justify-center gap-2 py-3 rounded-lg font-medium text-sm transition-all disabled:opacity-50"
                      style={{ background: a.bg, color: a.color, border: `1px solid ${a.border}` }}>
                      {actionLoading === a.key ? <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'transparent', borderTopColor: a.color }} /> : a.icon}
                      {a.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : canPostApprovalFlag ? (
              <div className="pt-6 space-y-4" style={{ borderTop: '1px solid var(--border-primary)' }}>
                {actionError && <div className="p-3 rounded-lg text-sm" style={{ background: 'var(--danger-muted)', border: '1px solid var(--danger)', color: 'var(--danger)' }}>{actionError}</div>}
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider block mb-2" style={{ color: 'var(--text-tertiary)' }}>Fraud Flag Reason (Optional)</label>
                  <textarea value={decisionReason} onChange={e => setDecisionReason(e.target.value)} placeholder="Explain why this approved claim should be post-flagged..." className="input-field min-h-[80px] resize-none" />
                </div>
                <button
                  onClick={() => handleReviewAction('flag_post_approval')}
                  disabled={actionLoading !== null}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-lg font-medium text-sm transition-all disabled:opacity-50"
                  style={{ background: 'var(--danger-muted)', color: 'var(--danger)', border: '1px solid var(--danger)' }}
                >
                  {actionLoading === 'flag_post_approval' ? <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'transparent', borderTopColor: 'var(--danger)' }} /> : <AlertTriangle size={16} />}
                  Flag Post-Approval Fraud
                </button>
              </div>
            ) : (
              <div className="pt-6 text-center" style={{ borderTop: '1px solid var(--border-primary)' }}>
                <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>This claim has already been <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>{claim?.claim_status}</span>.</p>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}
