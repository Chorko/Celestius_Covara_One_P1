"use client"

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import { backendGet, BackendApiError } from '@/lib/backendApi'
import { Users, Search, MapPin, ChevronDown, ChevronUp, Mail, Shield, Navigation2, Bike, CheckCircle, XCircle, Fingerprint, BarChart3, FileText, Clock } from 'lucide-react'

/* eslint-disable @typescript-eslint/no-explicit-any */
interface WorkerProfile {
  profile_id: string; city?: string; platform_name?: string; vehicle_type?: string; avg_hourly_income_inr?: number; trust_score?: number; gps_consistency_score?: number; gps_consent?: boolean; bank_verified?: boolean; preferred_zone_id?: string
  profiles?: { id?: string; full_name?: string; email?: string; phone?: string }; zones?: { zone_name?: string }; [key: string]: any
}
interface WorkerClaim { id: string; claim_status: string; claim_reason: string; claimed_at: string; trigger_events?: { trigger_code?: string; trigger_family?: string }; [key: string]: any }
interface WorkersListResponse { workers: WorkerProfile[]; count: number }
interface WorkerClaimsResponse { claims: WorkerClaim[]; count: number }
/* eslint-enable @typescript-eslint/no-explicit-any */

function formatLoadError(error: unknown): string {
  if (error instanceof BackendApiError) {
    if (error.status === 401) {
      return 'Session expired. Please sign in again.'
    }
    if (error.status === 403) {
      return 'Admin role required for worker directory access.'
    }
    return error.detail
  }

  return error instanceof Error ? error.message : 'Failed to load worker directory'
}

export default function AdminUsers() {
  const supabase = createClient()
  const [workers, setWorkers] = useState<WorkerProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [cityFilter, setCityFilter] = useState('')
  const [expandedWorker, setExpandedWorker] = useState<string | null>(null)
  const [workerClaims, setWorkerClaims] = useState<Record<string, WorkerClaim[]>>({})
  const [claimLoading, setClaimLoading] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadWorkers = useCallback(async (city?: string) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '200' })
      if (city) {
        params.set('city', city)
      }
      const response = await backendGet<WorkersListResponse>(supabase, `/workers?${params.toString()}`)
      setWorkers(response.workers || [])
      setLoadError(null)
    } catch (e) {
      console.error('Could not load workers', e)
      setWorkers([])
      setLoadError(formatLoadError(e))
    }
    setLoading(false)
  }, [supabase])

  useEffect(() => {
    queueMicrotask(() => {
      void loadWorkers()
    })
  }, [loadWorkers])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (cityFilter.trim()) {
      void loadWorkers(cityFilter.trim())
      return
    }
    void loadWorkers()
  }

  const toggleExpand = async (workerId: string) => {
    if (expandedWorker === workerId) { setExpandedWorker(null); return }
    setExpandedWorker(workerId)
    if (!workerClaims[workerId]) {
      setClaimLoading(workerId)
      try {
        const response = await backendGet<WorkerClaimsResponse>(supabase, `/workers/${workerId}/claims?limit=5`)
        setWorkerClaims(prev => ({ ...prev, [workerId]: response.claims || [] }))
      } catch (e) {
        console.error('Could not load claims', e)
        setWorkerClaims(prev => ({ ...prev, [workerId]: [] }))
      }
      setClaimLoading(null)
    }
  }

  const filteredWorkers = workers.filter(w => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return [w.profiles?.full_name, w.profiles?.email, w.city, w.platform_name].some(s => (s || '').toLowerCase().includes(q))
  })

  const trustColor = (score: number) => score >= 0.8 ? 'var(--success)' : score >= 0.6 ? 'var(--warning)' : 'var(--danger)'

  const statusBadge = (s: string) => {
    switch (s) {
      case 'approved': case 'auto_approved': case 'paid': return 'badge-success'
      case 'submitted': case 'soft_hold_verification': return 'badge-warning'
      case 'fraud_escalated_review': return 'badge-purple'
      case 'rejected': case 'post_approval_flagged': return 'badge-danger'
      default: return 'badge-info'
    }
  }
  const statusLabel = (s: string) => ({ auto_approved: 'Auto', approved: 'Approved', paid: 'Paid', submitted: 'Submitted', soft_hold_verification: 'Verify', fraud_escalated_review: 'Fraud', rejected: 'Rejected', post_approval_flagged: 'Flagged' } as Record<string, string>)[s] || s

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-8 pb-28 max-w-6xl mx-auto space-y-6">
        <section className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 rounded-lg" style={{ background: 'var(--info-muted)' }}><Users size={24} style={{ color: 'var(--info)' }} /></div>
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>Worker Directory</h1>
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Search and inspect worker profiles, trust scores, and claim history.</p>
            </div>
          </div>
        </section>

        {/* Search */}
        <section className="card p-5 animate-fade-in-up delay-100">
          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
              <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search by name, email, city, or platform..." className="input-field pl-10" />
            </div>
            <div className="relative sm:w-48">
              <MapPin size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
              <input type="text" value={cityFilter} onChange={e => setCityFilter(e.target.value)} placeholder="Filter by city..." className="input-field pl-10" />
            </div>
            <button type="submit" className="btn-primary flex items-center justify-center gap-2 sm:w-32"><Search size={16} /> Search</button>
          </form>
        </section>

        {loadError && (
          <section className="card p-4 text-sm" style={{ background: 'var(--warning-muted)', border: '1px solid var(--warning)', color: 'var(--warning)' }}>
            {loadError}
          </section>
        )}

        {/* Results */}
        <section className="space-y-3 animate-fade-in-up delay-200">
          {loading ? (
            <div className="card p-16 text-center">
              <div className="w-8 h-8 border-2 rounded-full animate-spin mx-auto mb-4" style={{ borderColor: 'var(--border-secondary)', borderTopColor: 'var(--info)' }} />
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading workers...</p>
            </div>
          ) : filteredWorkers.length === 0 ? (
            <div className="card p-16 text-center">
              <Users size={28} className="mx-auto mb-4" style={{ color: 'var(--text-tertiary)' }} />
              <p className="font-medium" style={{ color: 'var(--text-secondary)' }}>No workers found</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{searchQuery ? 'Try adjusting your search query' : 'No workers registered yet'}</p>
            </div>
          ) : (
            <>
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Showing {filteredWorkers.length} worker{filteredWorkers.length !== 1 ? 's' : ''}</p>
              {filteredWorkers.map(worker => {
                const isExpanded = expandedWorker === worker.profile_id
                const claims = workerClaims[worker.profile_id] || []
                const ts = worker.trust_score || 0

                return (
                  <div key={worker.profile_id} className="card overflow-hidden">
                    <div className="p-5 flex items-center justify-between cursor-pointer transition-colors" onClick={() => toggleExpand(worker.profile_id)} style={{ borderBottom: isExpanded ? '1px solid var(--border-primary)' : undefined }}>
                      <div className="flex items-center gap-4 min-w-0 flex-1">
                        <div className="w-11 h-11 rounded-lg flex items-center justify-center shrink-0" style={{ background: 'var(--info-muted)', border: '1px solid var(--border-secondary)' }}>
                          <span className="font-bold text-sm" style={{ color: 'var(--info)' }}>
                            {(worker.profiles?.full_name || 'W').split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)}
                          </span>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{worker.profiles?.full_name || 'Unknown'}</span>
                            <span className="text-xs flex items-center gap-1" style={{ color: 'var(--text-tertiary)' }}><Mail size={10} /> {worker.profiles?.email || '—'}</span>
                          </div>
                          <div className="flex items-center gap-3 text-xs mt-1 flex-wrap" style={{ color: 'var(--text-tertiary)' }}>
                            <span className="flex items-center gap-1"><MapPin size={10} /> {worker.city || '—'}</span>
                            <span className="flex items-center gap-1"><Bike size={10} /> {worker.platform_name || '—'} / {worker.vehicle_type || '—'}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 shrink-0 ml-3">
                        <div className="hidden sm:flex items-center gap-2">
                          <div className="w-20 progress-bar"><div className="progress-bar-fill" style={{ width: `${ts * 100}%`, background: trustColor(ts) }} /></div>
                          <span className="text-xs font-semibold" style={{ color: trustColor(ts) }}>{(ts * 100).toFixed(0)}</span>
                        </div>
                        <div className="hidden sm:flex items-center gap-1.5">
                          <span className={worker.gps_consent ? 'badge-success' : 'badge-danger'} title="GPS"><Navigation2 size={10} /> GPS</span>
                          <span className={worker.bank_verified ? 'badge-success' : 'badge-warning'} title="Bank">{worker.bank_verified ? <CheckCircle size={10} /> : <Clock size={10} />} Bank</span>
                        </div>
                        {isExpanded ? <ChevronUp size={16} style={{ color: 'var(--text-tertiary)' }} /> : <ChevronDown size={16} style={{ color: 'var(--text-tertiary)' }} />}
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="p-5 space-y-5" style={{ background: 'var(--bg-primary)' }}>
                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}><Fingerprint size={14} /> Full Profile</h4>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                            {[
                              { l: 'City', v: worker.city || '—' }, { l: 'Platform', v: worker.platform_name || '—' },
                              { l: 'Vehicle Type', v: worker.vehicle_type || '—' }, { l: 'Hourly Income', v: `₹${worker.avg_hourly_income_inr || '—'}` },
                            ].map((item, i) => (
                              <div key={i}><p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{item.l}</p><p className="text-sm font-medium mt-0.5" style={{ color: 'var(--text-primary)' }}>{item.v}</p></div>
                            ))}
                            <div>
                              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Trust Score</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                <div className="w-16 progress-bar"><div className="progress-bar-fill" style={{ width: `${ts * 100}%`, background: trustColor(ts) }} /></div>
                                <span className="text-sm font-bold" style={{ color: trustColor(ts) }}>{ts.toFixed(2)}</span>
                              </div>
                            </div>
                            <div><p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>GPS Consistency</p><p className="text-sm font-medium mt-0.5" style={{ color: 'var(--text-primary)' }}>{worker.gps_consistency_score?.toFixed(2) || '—'}</p></div>
                            <div><p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>GPS Consent</p><p className="text-sm font-medium mt-0.5">{worker.gps_consent ? <span className="flex items-center gap-1" style={{ color: 'var(--success)' }}><CheckCircle size={12} /> Yes</span> : <span className="flex items-center gap-1" style={{ color: 'var(--danger)' }}><XCircle size={12} /> No</span>}</p></div>
                            <div><p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Bank Verified</p><p className="text-sm font-medium mt-0.5">{worker.bank_verified ? <span className="flex items-center gap-1" style={{ color: 'var(--success)' }}><CheckCircle size={12} /> Verified</span> : <span className="flex items-center gap-1" style={{ color: 'var(--warning)' }}><Clock size={12} /> Pending</span>}</p></div>
                          </div>
                        </div>

                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}><FileText size={14} /> Recent Claims</h4>
                          {claimLoading === worker.profile_id ? (
                            <div className="text-center py-6 text-sm" style={{ color: 'var(--text-tertiary)' }}>
                              <div className="w-4 h-4 border-2 rounded-full animate-spin mx-auto mb-2" style={{ borderColor: 'var(--border-secondary)', borderTopColor: 'var(--accent)' }} />Loading claims...
                            </div>
                          ) : claims.length === 0 ? (
                            <div className="text-center py-6 text-sm rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px dashed var(--border-secondary)', color: 'var(--text-tertiary)' }}>No claims filed by this worker</div>
                          ) : (
                            <div className="space-y-2">
                              {claims.slice(0, 5).map(claim => (
                                <div key={claim.id} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                                  <div className="min-w-0 flex-1">
                                    <p className="text-sm truncate" style={{ color: 'var(--text-secondary)' }}>{claim.claim_reason}</p>
                                    <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                                      {new Date(claim.claimed_at).toLocaleDateString('en-IN', { dateStyle: 'medium' })}
                                      {claim.trigger_events?.trigger_family && <span className="ml-2" style={{ color: 'var(--accent)' }}>{claim.trigger_events.trigger_family}</span>}
                                    </p>
                                  </div>
                                  <span className={`badge ${statusBadge(claim.claim_status)} shrink-0 ml-3`}>{statusLabel(claim.claim_status)}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="grid grid-cols-3 gap-3">
                          {[
                            { icon: <BarChart3 size={16} style={{ color: 'var(--accent)' }} />, val: claims.length, label: 'Total Claims' },
                            { icon: <CheckCircle size={16} style={{ color: 'var(--success)' }} />, val: claims.filter(c => ['approved', 'auto_approved', 'paid'].includes(c.claim_status)).length, label: 'Approved' },
                            { icon: <Shield size={16} style={{ color: 'var(--warning)' }} />, val: claims.filter(c => ['submitted', 'soft_hold_verification', 'fraud_escalated_review'].includes(c.claim_status)).length, label: 'Pending' },
                          ].map((s, i) => (
                            <div key={i} className="card p-4 text-center">
                              <div className="mx-auto mb-2 w-fit">{s.icon}</div>
                              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{s.val}</p>
                              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{s.label}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </>
          )}
        </section>
      </div>
    </div>
  )
}
