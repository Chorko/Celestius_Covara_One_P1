"use client"

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import { backendGet, backendPost, BackendApiError } from '@/lib/backendApi'
import {
  FileSearch, CheckCircle, XCircle, Shield,
  ChevronDown, ChevronUp, Eye, Image as ImageIcon, Bot, Scale,
  Pause, ArrowUpCircle, IndianRupee, Fingerprint, Brain, AlertTriangle
} from 'lucide-react'

type QueueFilter = 'all' | 'mine' | 'unassigned' | 'overdue'

interface ReviewMeta {
  assignment_state?: 'unassigned' | 'assigned' | 'in_review' | 'escalated' | 'resolved'
  assigned_reviewer_profile_id?: string
  assigned_reviewer_name?: string
  assigned_at?: string
  review_due_at?: string
  sla_status?: 'on_track' | 'due_soon' | 'overdue' | 'not_set' | 'escalated' | 'resolved'
  claim_age_hours?: number | null
  hours_to_due?: number | null
  is_overdue?: boolean
  can_current_user_review?: boolean
}

interface ClaimRecord {
  id: string; claim_status: string; claim_reason: string; claim_mode?: string; claimed_at: string
  worker_profiles?: { platform_name?: string; city?: string; trust_score?: number; profiles?: { full_name?: string; email?: string } }
  trigger_events?: { trigger_family?: string; trigger_code?: string; zone_id?: string }
  assigned_reviewer?: { id?: string; full_name?: string }
  assigned_reviewer_profile_id?: string
  assignment_state?: string
  review_due_at?: string
  review_meta?: ReviewMeta
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
  queue?: string
}

interface ClaimDetailResponse {
  claim: ClaimRecord
  payout_recommendation: PayoutRecommendation | null
  evidence: EvidenceItem[]
}

interface ReviewActionResponse {
  status: string
  claim_id: string
  decision: string
  assignment_state?: string
  payout?: {
    status?: string
    payout?: {
      provider_key?: string
      provider_reference_id?: string
    }
    reason?: string
  }
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
  const [queueFilter, setQueueFilter] = useState<QueueFilter>('all')
  const [activeQueue, setActiveQueue] = useState<string>('all')
  const [selectedClaim, setSelectedClaim] = useState<string | null>(null)
  const [detailData, setDetailData] = useState<DetailData | null>(null)
  const [loading, setLoading] = useState(false)
  const [pipelineExpanded, setPipelineExpanded] = useState(false)
  const [decisionReason, setDecisionReason] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [assignLoading, setAssignLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadClaims = useCallback(async () => {
    try {
      setLoadError(null)
      const response = await backendGet<ClaimsListResponse>(supabase, `/claims/?queue=${queueFilter}`)
      setClaims(response.claims || [])
      setActiveQueue(response.queue || queueFilter)
    } catch (e: unknown) {
      console.error('Could not load claims', e)
      setClaims([])
      setActiveQueue(queueFilter)
      setLoadError(formatApiError(e))
    }
  }, [supabase, queueFilter])

  useEffect(() => { loadClaims() }, [loadClaims])

  const loadDetail = async (claimId: string) => {
    setSelectedClaim(claimId)
    setLoading(true)
    setActionError(null)
    setActionSuccess(null)
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
    setActionSuccess(null)

    let response: ReviewActionResponse | null = null

    try {
      if (decision === 'flag_post_approval') {
        await backendPost(supabase, `/claims/${claimId}/flag`, {
          fraud_severity: 'moderate',
          reason: decisionReason || undefined,
        })
        response = {
          status: 'flagged',
          claim_id: claimId,
          decision,
        }
      } else {
        response = await backendPost<ReviewActionResponse>(supabase, `/claims/${claimId}/review`, {
          decision,
          decision_reason: decisionReason || undefined,
        })
      }
    } catch (e: unknown) {
      setActionError(formatApiError(e))
      setActionLoading(null)
      return
    }

    if (decision === 'approve') {
      const payoutStatus = response?.payout?.status || 'unknown'
      const provider = response?.payout?.payout?.provider_key
      const providerRef = response?.payout?.payout?.provider_reference_id
      const providerLabel = provider ? ` via ${provider}` : ''
      const referenceLabel = providerRef ? ` (${providerRef})` : ''
      setActionSuccess(`Claim approved. Payout initiation status: ${payoutStatus}${providerLabel}${referenceLabel}`)
    } else if (decision === 'flag_post_approval') {
      setActionSuccess('Claim flagged for post-approval fraud review.')
    } else {
      setActionSuccess(`Claim decision applied: ${decision}.`)
    }

    setActionLoading(null)
    setSelectedClaim(null)
    setDetailData(null)
    setDecisionReason('')
    await loadClaims()
  }

  const handleAssignToMe = async () => {
    if (!detailData) return
    setAssignLoading(true)
    setActionError(null)

    try {
      await backendPost(supabase, `/claims/${detailData.claim.id}/assign`, {
        due_in_hours: 24,
      })
      await loadDetail(detailData.claim.id)
      await loadClaims()
    } catch (e: unknown) {
      setActionError(formatApiError(e))
    } finally {
      setAssignLoading(false)
    }
  }

  const slaBadgeClass = (sla?: string) => {
    switch (sla) {
      case 'overdue': return 'badge-danger'
      case 'due_soon': return 'badge-warning'
      case 'on_track': return 'badge-success'
      case 'escalated': return 'badge-purple'
      case 'resolved': return 'badge-info'
      default: return 'badge-info'
    }
  }

  const slaLabel = (sla?: string) => ({
    overdue: 'Overdue',
    due_soon: 'Due Soon',
    on_track: 'On Track',
    escalated: 'Escalated',
    resolved: 'Resolved',
    not_set: 'No SLA',
  } as Record<string, string>)[sla || 'not_set'] || 'No SLA'

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
  const reviewMeta = claim?.review_meta
  const canReviewDecision = ['submitted', 'soft_hold_verification', 'fraud_escalated_review', 'held'].includes(claim?.claim_status || '')
  const canReview = canReviewDecision && (reviewMeta?.can_current_user_review ?? true)
  const reviewBlockedByOwnership = canReviewDecision && reviewMeta?.can_current_user_review === false
  const canPostApprovalFlag = ['approved', 'auto_approved', 'paid'].includes(claim?.claim_status || '')

  return (
    <div className="p-4 md:p-6 pb-28 h-full flex flex-col md:flex-row gap-6 min-h-screen page-mesh animate-fade-in-up">
      {/* Left Panel */}
      <div className="w-full md:w-[340px] shrink-0 card flex flex-col overflow-hidden">
        <div className="p-5" style={{ borderBottom: '1px solid var(--border-primary)' }}>
          <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><FileSearch size={18} style={{ color: 'var(--accent)' }} /> Review Queue</h2>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{claims.length} claims in queue ({activeQueue})</p>
          {actionSuccess && (
            <div
              className="mt-3 p-2.5 rounded-md text-xs"
              style={{ background: 'var(--success-muted)', color: 'var(--success)', border: '1px solid var(--success)' }}
            >
              {actionSuccess}
            </div>
          )}
          {loadError && (
            <div
              className="mt-3 p-2.5 rounded-md text-xs"
              style={{ background: 'var(--warning-muted)', color: 'var(--warning)', border: '1px solid var(--warning)' }}
            >
              Queue temporarily unavailable: {loadError}
            </div>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2">
            {([
              { key: 'all', label: 'All' },
              { key: 'mine', label: 'Mine' },
              { key: 'unassigned', label: 'Unassigned' },
              { key: 'overdue', label: 'Overdue' },
            ] as Array<{ key: QueueFilter; label: string }>).map((q) => (
              <button
                key={q.key}
                onClick={() => setQueueFilter(q.key)}
                className="text-xs py-1.5 px-2 rounded-md border transition-colors"
                style={{
                  borderColor: queueFilter === q.key ? 'var(--accent)' : 'var(--border-primary)',
                  background: queueFilter === q.key ? 'var(--accent-muted)' : 'var(--bg-tertiary)',
                  color: queueFilter === q.key ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-auto p-3 space-y-2">
          {claims.length === 0 ? (
            <div className="text-center py-16 space-y-3" style={{ color: 'var(--text-tertiary)' }}>
              <p className="text-sm">{loadError ? 'Unable to load claims right now' : 'No claims in queue'}</p>
              {loadError && (
                <button
                  onClick={() => void loadClaims()}
                  className="text-xs py-1.5 px-3 rounded-md border"
                  style={{ borderColor: 'var(--border-secondary)', color: 'var(--text-secondary)', background: 'var(--bg-tertiary)' }}
                >
                  Retry
                </button>
              )}
            </div>
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
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span className={`badge ${slaBadgeClass(c.review_meta?.sla_status)}`}>{slaLabel(c.review_meta?.sla_status)}</span>
                {c.review_meta?.assignment_state && <span className="badge-info">{c.review_meta.assignment_state}</span>}
              </div>
              <p className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                Owner: {c.review_meta?.assigned_reviewer_name || c.assigned_reviewer?.full_name || 'Unassigned'}
              </p>
              {c.review_meta?.review_due_at && (
                <p className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                  Due: {new Date(c.review_meta.review_due_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                </p>
              )}
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
                <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
                  Owner: {reviewMeta?.assigned_reviewer_name || claim?.assigned_reviewer?.full_name || 'Unassigned'}
                  {reviewMeta?.review_due_at && (
                    <span> | Due {new Date(reviewMeta.review_due_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                  )}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 justify-end">
                {isFraud && <span className="badge-danger flex items-center gap-1"><AlertTriangle size={12} /> Fraud Detected</span>}
                <span className={claim?.claim_mode === 'trigger_auto' ? 'badge-success' : 'badge-info'}>
                  {claim?.claim_mode === 'trigger_auto' ? 'Auto-Triggered' : 'Manual Claim'}
                </span>
                <span className={`badge ${slaBadgeClass(reviewMeta?.sla_status)}`}>{slaLabel(reviewMeta?.sla_status)}</span>
                {reviewMeta?.assignment_state && <span className="badge-info">{reviewMeta.assignment_state}</span>}
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
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}><ImageIcon size={14} /> Evidence Gallery</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {evidence.map((ev, idx) => (
                    <div key={idx} className="aspect-video rounded-lg overflow-hidden flex items-center justify-center relative group" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                      {ev.storage_path ? (
                        /* eslint-disable-next-line @next/next/no-img-element */
                        <img src={ev.storage_path} alt={`Evidence ${idx + 1}`} className="object-cover w-full h-full" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden') }} />
                      ) : null}
                      <div className={`flex flex-col items-center ${ev.storage_path ? 'hidden' : ''}`} style={{ color: 'var(--text-tertiary)' }}>
                        <ImageIcon size={24} aria-label="Evidence placeholder" /><span className="text-xs mt-1">{ev.evidence_type || 'photo'}</span>
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
                {reviewMeta?.assignment_state === 'unassigned' && (
                  <button
                    onClick={handleAssignToMe}
                    disabled={assignLoading || actionLoading !== null}
                    className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-medium text-sm transition-all disabled:opacity-50"
                    style={{ background: 'var(--accent-muted)', color: 'var(--accent)', border: '1px solid var(--accent)' }}
                  >
                    {assignLoading ? <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'transparent', borderTopColor: 'var(--accent)' }} /> : <Shield size={16} />}
                    Assign To Me
                  </button>
                )}
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
            ) : reviewBlockedByOwnership ? (
              <div className="pt-6" style={{ borderTop: '1px solid var(--border-primary)' }}>
                <div className="p-3 rounded-lg text-sm" style={{ background: 'var(--warning-muted)', border: '1px solid var(--warning)', color: 'var(--warning)' }}>
                  This claim is assigned to another reviewer. Reassign ownership before taking review actions.
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
