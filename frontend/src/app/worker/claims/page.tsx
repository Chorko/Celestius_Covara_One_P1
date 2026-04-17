"use client"

import { useEffect, useState, useRef, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { backendGet, backendPost, BackendApiError } from '@/lib/backendApi'
import {
  FileText, MapPin, Send, AlertCircle, Clock, CheckCircle, XCircle,
  Upload, LocateFixed, Zap, ImageIcon, FileWarning,
} from 'lucide-react'

/* eslint-disable @typescript-eslint/no-explicit-any */
interface ClaimItem {
  id: string; claim_status: string; claim_reason: string; claim_mode?: string; claimed_at: string
  stated_lat?: number; stated_lng?: number
  trigger_events?: { trigger_code?: string; trigger_family?: string; severity_band?: string }
  [key: string]: any
}
/* eslint-enable @typescript-eslint/no-explicit-any */

interface ClaimsListResponse {
  claims: ClaimItem[]
}

interface ZoneOption {
  id: string
  city: string
  zone_name: string
  pincode?: string | null
}


function normalizePincode(value: string): string {
  return value.replace(/\D/g, '')
}

function formatSubmitError(error: unknown): string {
  if (error instanceof BackendApiError) {
    if (error.status === 401) {
      return 'Session expired. Please sign in again.'
    }

    if (error.status === 409) {
      return 'A similar claim already exists for this trigger event.'
    }

    if (error.status === 429) {
      return 'You are submitting too frequently. Please wait and retry.'
    }

    return error.detail
  }

  return error instanceof Error ? error.message : 'Failed to submit claim'
}

export default function WorkerClaims() {
  const { user, profile } = useUserStore()
  const supabase = createClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [claims, setClaims] = useState<ClaimItem[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [zones, setZones] = useState<ZoneOption[]>([])
  const [selectedZoneId, setSelectedZoneId] = useState('')
  const [pincode, setPincode] = useState('')
  const [reason, setReason] = useState('')
  const [lat, setLat] = useState<number | null>(null)
  const [lng, setLng] = useState<number | null>(null)
  const [locating, setLocating] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  const loadClaims = useCallback(async () => {
    if (!profile) {
      return
    }

    try {
      const response = await backendGet<ClaimsListResponse>(supabase, '/claims/')
      setClaims(response.claims || [])
    } catch (e) { console.error("Could not load claims", e) }
  }, [supabase, profile])

  const loadZones = useCallback(async () => {
    if (!profile) {
      return
    }

    try {
      let zoneRows: ZoneOption[] = []
      const withPincode = await supabase
        .from('zones')
        .select('id, city, zone_name, pincode')
        .order('city', { ascending: true })
        .order('zone_name', { ascending: true })

      if (withPincode.error) {
        const fallback = await supabase
          .from('zones')
          .select('id, city, zone_name')
          .order('city', { ascending: true })
          .order('zone_name', { ascending: true })

        if (fallback.error) {
          throw fallback.error
        }

        zoneRows = (fallback.data || []).map((row) => ({ ...row, pincode: null })) as ZoneOption[]
      } else {
        zoneRows = (withPincode.data || []) as ZoneOption[]
      }

      setZones(zoneRows)

      if (!selectedZoneId && zoneRows.length > 0) {
        const preferredZoneId = typeof (profile as Record<string, unknown>).preferred_zone_id === 'string'
          ? String((profile as Record<string, unknown>).preferred_zone_id)
          : ''
        const defaultZone = zoneRows.find((z) => z.id === preferredZoneId) || zoneRows[0]
        setSelectedZoneId(defaultZone.id)
        if (defaultZone.pincode) {
          setPincode(defaultZone.pincode)
        }
      }
    } catch (e) {
      console.error('Could not load zones for claim form', e)
    }
  }, [profile, selectedZoneId, supabase])

  useEffect(() => {
    if (profile) {
      loadClaims()
      loadZones()
    }
  }, [profile, loadClaims, loadZones])

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
      const selectedZone = zones.find((zone) => zone.id === selectedZoneId)
      const normalizedPincode = normalizePincode(pincode)

      if (!selectedZone) {
        throw new Error('Please select a place before submitting your claim.')
      }

      if (normalizedPincode.length !== 6) {
        throw new Error('Please enter a valid 6-digit pincode.')
      }

      let evidenceUrl: string | null = null

      if (file) {
        setUploadingFile(true)
        try {
          const fileExt = file.name.split('.').pop() || 'jpg'
          const uploaderId = user?.id || profile?.id || 'worker'
          const fileName = `${uploaderId}-${Date.now()}.${fileExt}`
          const { error: uploadError, data: uploadData } = await supabase.storage
            .from('claim-evidence')
            .upload(fileName, file)

          if (uploadError) {
            throw new Error(`Evidence upload failed: ${uploadError.message}`)
          }

          const storedPath = uploadData?.path || fileName
          const { data: publicUrlData } = supabase.storage
            .from('claim-evidence')
            .getPublicUrl(storedPath)
          evidenceUrl = publicUrlData?.publicUrl || storedPath
        } finally {
          setUploadingFile(false)
        }
      }

      await backendPost<{ status: string; claim: ClaimItem }>(supabase, '/claims/', {
        claim_reason: reason,
        place: selectedZone.zone_name,
        city: selectedZone.city,
        pincode: normalizedPincode,
        stated_lat: lat || undefined,
        stated_lng: lng || undefined,
        evidence_url: evidenceUrl || undefined,
        plan: 'essential',
      })

      setReason(''); setLat(null); setLng(null); setFile(null); await loadClaims()
    } catch (e: unknown) { setSubmitError(formatSubmitError(e)) }
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
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs uppercase tracking-wider mb-2 block font-medium" style={{ color: 'var(--text-tertiary)' }}>Place</label>
                    <select
                      required
                      value={selectedZoneId}
                      onChange={(e) => {
                        const zoneId = e.target.value
                        setSelectedZoneId(zoneId)
                        const picked = zones.find((z) => z.id === zoneId)
                        if (picked?.pincode) {
                          setPincode(picked.pincode)
                        }
                      }}
                      className="input-field w-full"
                    >
                      <option value="">Select place</option>
                      {zones.map((zone) => (
                        <option key={zone.id} value={zone.id}>
                          {zone.zone_name} ({zone.city})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs uppercase tracking-wider mb-2 block font-medium" style={{ color: 'var(--text-tertiary)' }}>Pincode</label>
                    <input
                      required
                      inputMode="numeric"
                      maxLength={6}
                      value={pincode}
                      onChange={(e) => setPincode(normalizePincode(e.target.value).slice(0, 6))}
                      className="input-field w-full"
                      placeholder="e.g. 400051"
                    />
                  </div>
                </div>
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
                    {lat ? `${lat.toFixed(4)}, ${lng?.toFixed(4)}` : locating ? 'Acquiring GPS...' : 'Pin Current Location (Optional)'}
                  </button>
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting || !reason || !selectedZoneId || normalizePincode(pincode).length !== 6}
                  className="btn-primary w-full py-3 text-sm font-semibold flex items-center justify-center gap-2"
                >
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
