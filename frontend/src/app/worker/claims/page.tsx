"use client"

import { useEffect, useState, useRef, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import {
  FileText, MapPin, Send, AlertCircle, Clock, CheckCircle, XCircle,
  Upload, LocateFixed, Zap, ImageIcon, FileWarning,
} from 'lucide-react'

/* eslint-disable @typescript-eslint/no-explicit-any */
interface ClaimItem {
  id: string; claim_status: string; claim_reason: string; claim_mode?: string; claimed_at: string
  stated_lat?: number; stated_lng?: number
  trigger_events?: { trigger_code?: string; trigger_family?: string; severity_band?: string }
  claim_evidence?: { storage_path?: string; evidence_type?: string }[]
  [key: string]: any
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export default function WorkerClaims() {
  const { user, profile } = useUserStore()
  const supabase = createClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [claims, setClaims] = useState<ClaimItem[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [reason, setReason] = useState('')
  const [lat, setLat] = useState<number | null>(null)
  const [lng, setLng] = useState<number | null>(null)
  const [locating, setLocating] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  const loadClaims = useCallback(async () => {
    try {
      const { data } = await supabase
        .from('manual_claims')
        .select('*, trigger_events(trigger_code, trigger_family, severity_band), claim_evidence(*)')
        .eq('worker_profile_id', profile!.id)
        .order('claimed_at', { ascending: false })
      setClaims(data || [])
    } catch (e) { console.error("Could not load claims", e) }
  }, [supabase, profile])

  useEffect(() => { if (profile) loadClaims() }, [profile, loadClaims])

  const handleGetLocation = () => {
    setLocating(true)
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => { setLat(pos.coords.latitude); setLng(pos.coords.longitude); setLocating(false) },
        () => setLocating(false)
      )
    } else { setLocating(false) }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setIsSubmitting(true); setSubmitError(null)
    try {
      let storagePath: string | null = null
      if (file && user) {
        setUploadingFile(true)
        const fileExt = file.name.split('.').pop()
        const fileName = `${user.id}-${Date.now()}.${fileExt}`
        const { error: uploadError, data: uploadData } = await supabase.storage.from('claim-evidence').upload(fileName, file)
        if (uploadError) throw new Error(`Evidence upload failed: ${uploadError.message}`)
        storagePath = uploadData?.path || fileName
        setUploadingFile(false)
      }
      const { data: newClaim, error: insertError } = await supabase.from('manual_claims').insert({
        worker_profile_id: profile!.id, claim_mode: 'manual', claim_reason: reason,
        stated_lat: lat || null, stated_lng: lng || null, claim_status: 'submitted', claimed_at: new Date().toISOString(),
      }).select().single()
      if (insertError) throw new Error(insertError.message || 'Failed to submit claim')
      if (newClaim && storagePath) {
        await supabase.from('claim_evidence').insert({ claim_id: newClaim.id, evidence_type: 'photo', storage_path: storagePath })
      }
      setReason(''); setLat(null); setLng(null); setFile(null); await loadClaims()
    } catch (e: unknown) { setSubmitError(e instanceof Error ? e.message : 'Failed to submit claim') }
    finally { setIsSubmitting(false) }
  }

  const statusConfig: Record<string, { icon: React.ReactNode; badge: string; label: string }> = {
    auto_approved: { icon: <CheckCircle size={14} style={{ color: 'var(--success)' }} />, badge: 'badge-success', label: 'Auto-Approved' },
    approved: { icon: <CheckCircle size={14} style={{ color: 'var(--success)' }} />, badge: 'badge-success', label: 'Approved' },
    paid: { icon: <CheckCircle size={14} style={{ color: 'var(--success)' }} />, badge: 'badge-success', label: 'Paid' },
    soft_hold_verification: { icon: <Clock size={14} style={{ color: 'var(--accent)' }} />, badge: 'badge-info', label: 'Verification' },
    fraud_escalated_review: { icon: <AlertCircle size={14} style={{ color: 'var(--warning)' }} />, badge: 'badge-warning', label: 'Under Review' },
    held: { icon: <Clock size={14} style={{ color: 'var(--warning)' }} />, badge: 'badge-warning', label: 'Held' },
    submitted: { icon: <AlertCircle size={14} style={{ color: 'var(--warning)' }} />, badge: 'badge-warning', label: 'Submitted' },
    rejected: { icon: <XCircle size={14} style={{ color: 'var(--danger)' }} />, badge: 'badge-danger', label: 'Rejected' },
    post_approval_flagged: { icon: <XCircle size={14} style={{ color: 'var(--danger)' }} />, badge: 'badge-danger', label: 'Flagged' },
  }

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-6xl mx-auto space-y-6">
        <section className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-1">
            <div className="p-2.5 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
              <FileText size={22} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>My Claims</h1>
              <p className="text-sm mt-0.5" style={{ color: 'var(--text-tertiary)' }}>File a new manual claim or track the status of existing ones.</p>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Claim Form */}
          <section className="lg:col-span-2 animate-fade-in-up delay-100">
            <div className="card p-6 h-fit sticky top-8">
              <h2 className="text-base font-semibold mb-5 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Send size={16} style={{ color: 'var(--accent)' }} /> File a Claim
              </h2>
              {submitError && (
                <div className="p-3 rounded-lg mb-4 flex items-start gap-2" style={{ background: 'var(--danger-muted)', border: '1px solid var(--danger)', color: 'var(--danger)' }}>
                  <AlertCircle size={16} className="mt-0.5 shrink-0" /><p className="text-sm">{submitError}</p>
                </div>
              )}
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="text-xs uppercase tracking-wider mb-2 block font-medium" style={{ color: 'var(--text-tertiary)' }}>Disruption Reason</label>
                  <textarea required value={reason} onChange={(e) => setReason(e.target.value)} className="input-field w-full min-h-[120px] resize-y" placeholder="e.g. Severe waterlogging blocked access to the pickup restaurant..." />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider mb-2 block font-medium" style={{ color: 'var(--text-tertiary)' }}>Evidence Photo</label>
                  <div
                    onDrop={(e) => { e.preventDefault(); setIsDragging(false); const f = e.dataTransfer.files?.[0]; if (f?.type.startsWith('image/')) setFile(f) }}
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                    onDragLeave={() => setIsDragging(false)}
                    onClick={() => fileInputRef.current?.click()}
                    className="rounded-lg p-6 border-2 border-dashed cursor-pointer transition-all text-center"
                    style={{
                      borderColor: isDragging ? 'var(--accent)' : file ? 'var(--success)' : 'var(--border-secondary)',
                      background: isDragging ? 'var(--accent-muted)' : file ? 'var(--success-muted)' : 'var(--bg-tertiary)',
                    }}
                  >
                    <input ref={fileInputRef} type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} className="hidden" />
                    {file ? (
                      <div className="space-y-2">
                        <ImageIcon size={24} style={{ color: 'var(--success)' }} className="mx-auto" />
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--success)' }}>{file.name}</p>
                        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{(file.size / 1024).toFixed(0)} KB — Click to change</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <Upload size={24} className="mx-auto" style={{ color: 'var(--text-tertiary)' }} />
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Drag & drop or click to upload</p>
                        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>JPG, PNG or HEIC up to 10 MB</p>
                      </div>
                    )}
                  </div>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider mb-2 block font-medium" style={{ color: 'var(--text-tertiary)' }}>Location</label>
                  <button type="button" onClick={handleGetLocation} disabled={locating}
                    className="w-full py-3 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-all"
                    style={{ background: lat ? 'var(--success-muted)' : 'var(--bg-tertiary)', border: `1px solid ${lat ? 'var(--success)' : 'var(--border-primary)'}`, color: lat ? 'var(--success)' : 'var(--text-secondary)' }}>
                    <LocateFixed size={16} />
                    {lat ? `${lat.toFixed(4)}, ${lng?.toFixed(4)}` : locating ? 'Acquiring GPS...' : 'Pin Current Location'}
                  </button>
                </div>
                <button type="submit" disabled={isSubmitting || !reason} className="btn-primary w-full py-3 text-sm font-semibold flex items-center justify-center gap-2">
                  {isSubmitting ? (<><div className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />{uploadingFile ? 'Uploading Photo...' : 'Submitting...'}</>) : (<><Zap size={16} />Submit Claim</>)}
                </button>
              </form>
            </div>
          </section>

          {/* Claims History */}
          <section className="lg:col-span-3 space-y-3 animate-fade-in-up delay-200">
            <h2 className="text-base font-semibold flex items-center gap-2 mb-1" style={{ color: 'var(--text-primary)' }}>
              <Clock size={16} style={{ color: 'var(--text-tertiary)' }} /> Claim History
              {claims.length > 0 && <span className="badge-info ml-1">{claims.length}</span>}
            </h2>
            {claims.length === 0 ? (
              <div className="card p-12 text-center">
                <FileWarning size={40} className="mx-auto mb-4" style={{ color: 'var(--text-tertiary)' }} />
                <h3 className="font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>No claims yet</h3>
                <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>When you file a claim, it will appear here with live status updates.</p>
              </div>
            ) : (
              claims.map((claim, index) => {
                const cfg = statusConfig[claim.claim_status] || statusConfig.submitted
                return (
                  <div key={claim.id} className={`card p-5 animate-fade-in-up ${index <= 4 ? `delay-${(index + 1) * 100}` : ''}`}>
                    <div className="flex justify-between items-start mb-3">
                      <span className={`badge ${cfg.badge} flex items-center gap-1.5`}>{cfg.icon}{cfg.label}</span>
                      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                        {new Date(claim.claimed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </span>
                    </div>
                    <p className="text-sm mb-3 line-clamp-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{claim.claim_reason}</p>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="badge-neutral font-mono">#{claim.id.split('-')[0]}</span>
                      {claim.claim_mode && <span className={claim.claim_mode === 'trigger_auto' ? 'badge-purple' : 'badge-info'}>{claim.claim_mode === 'trigger_auto' ? 'Auto-trigger' : 'Manual'}</span>}
                      {claim.trigger_events && <span className="badge-info flex items-center gap-1"><Zap size={10} />{claim.trigger_events.trigger_family}</span>}
                      {claim.stated_lat && <span className="badge-neutral flex items-center gap-1"><MapPin size={11} />{claim.stated_lat.toFixed(2)}, {claim.stated_lng?.toFixed(2)}</span>}
                    </div>
                  </div>
                )
              })
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
