"use client"

import { useEffect, useState, useRef, useCallback } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import {
  FileText,
  MapPin,
  Send,
  AlertCircle,
  Clock,
  CheckCircle,
  XCircle,
  Upload,
  LocateFixed,
  Zap,
  ImageIcon,
  FileWarning,
} from 'lucide-react'

/* eslint-disable @typescript-eslint/no-explicit-any */
interface ClaimItem {
  id: string
  claim_status: string
  claim_reason: string
  claim_mode?: string
  claimed_at: string
  stated_lat?: number
  stated_lng?: number
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

  // Form State
  const [reason, setReason] = useState('')
  const [lat, setLat] = useState<number | null>(null)
  const [lng, setLng] = useState<number | null>(null)
  const [locating, setLocating] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // File Upload State
  const [file, setFile] = useState<File | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)

  // Drag state
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

  useEffect(() => {
    if (profile) loadClaims()
  }, [profile, loadClaims])

  const handleGetLocation = () => {
    setLocating(true)
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLat(pos.coords.latitude)
          setLng(pos.coords.longitude)
          setLocating(false)
        },
        () => setLocating(false)
      )
    } else {
      setLocating(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setSubmitError(null)

    try {
      let storagePath: string | null = null

      // Handle file upload first if present
      if (file && user) {
        setUploadingFile(true)
        const fileExt = file.name.split('.').pop()
        const fileName = `${user.id}-${Date.now()}.${fileExt}`

        const { error: uploadError, data: uploadData } = await supabase.storage
          .from('claim-evidence')
          .upload(fileName, file)
        if (uploadError) {
          throw new Error(`Evidence upload failed: ${uploadError.message}`)
        }
        storagePath = uploadData?.path || fileName
        setUploadingFile(false)
      }

      const { data: newClaim, error: insertError } = await supabase
        .from('manual_claims')
        .insert({
          worker_profile_id: profile!.id,
          claim_mode: 'manual',
          claim_reason: reason,
          stated_lat: lat || null,
          stated_lng: lng || null,
          claim_status: 'submitted',
          claimed_at: new Date().toISOString(),
        })
        .select()
        .single()

      if (insertError) throw new Error(insertError.message || 'Failed to submit claim')

      if (newClaim && storagePath) {
        await supabase.from('claim_evidence').insert({
          claim_id: newClaim.id,
          evidence_type: 'photo',
          storage_path: storagePath,
        })
      }

      setReason('')
      setLat(null)
      setLng(null)
      setFile(null)
      await loadClaims()
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : 'Failed to submit claim')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files?.[0]
    if (droppedFile && droppedFile.type.startsWith('image/')) {
      setFile(droppedFile)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const statusConfig: Record<string, { icon: React.ReactNode; badge: string; label: string }> = {
    auto_approved: {
      icon: <CheckCircle size={16} className="text-emerald-400" />,
      badge: 'badge-emerald',
      label: 'Auto-Approved',
    },
    approved: {
      icon: <CheckCircle size={16} className="text-emerald-400" />,
      badge: 'badge-emerald',
      label: 'Approved',
    },
    paid: {
      icon: <CheckCircle size={16} className="text-emerald-400" />,
      badge: 'badge-emerald',
      label: 'Paid',
    },
    soft_hold_verification: {
      icon: <Clock size={16} className="text-blue-400" />,
      badge: 'badge-blue',
      label: 'Verification',
    },
    fraud_escalated_review: {
      icon: <AlertCircle size={16} className="text-amber-400" />,
      badge: 'badge-amber',
      label: 'Under Review',
    },
    held: {
      icon: <Clock size={16} className="text-amber-400" />,
      badge: 'badge-amber',
      label: 'Held',
    },
    submitted: {
      icon: <AlertCircle size={16} className="text-amber-400" />,
      badge: 'badge-amber',
      label: 'Submitted',
    },
    rejected: {
      icon: <XCircle size={16} className="text-red-400" />,
      badge: 'badge-red',
      label: 'Rejected',
    },
    post_approval_flagged: {
      icon: <XCircle size={16} className="text-red-400" />,
      badge: 'badge-red',
      label: 'Flagged',
    },
  }

  return (
    <div className="min-h-screen gradient-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-6xl mx-auto space-y-8">

        {/* ===== PAGE HEADER ===== */}
        <section className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-1">
            <div className="glass p-2.5 rounded-xl">
              <FileText size={24} className="text-emerald-400" />
            </div>
            <div>
              <h1 className="text-3xl md:text-4xl font-bold text-white">My Claims</h1>
              <p className="text-neutral-400 text-sm mt-0.5">
                File a new manual claim or track the status of existing ones.
              </p>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">

          {/* ===== NEW CLAIM FORM ===== */}
          <section className="lg:col-span-2 animate-fade-in-up delay-100">
            <div className="glass-card p-6 h-fit sticky top-8">
              <h2 className="text-lg font-semibold text-white mb-5 flex items-center gap-2">
                <Send size={18} className="text-emerald-400" />
                File a Claim
              </h2>

              {/* Error display */}
              {submitError && (
                <div className="glass p-3 rounded-xl border border-red-500/30 mb-4 flex items-start gap-2">
                  <AlertCircle size={16} className="text-red-400 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-red-300">{submitError}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Reason */}
                <div>
                  <label className="text-xs text-neutral-500 uppercase tracking-wider mb-2 block font-medium">
                    Disruption Reason
                  </label>
                  <textarea
                    required
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    className="glass-input w-full min-h-[120px] resize-y"
                    placeholder="e.g. Severe waterlogging blocked access to the pickup restaurant..."
                  />
                </div>

                {/* Evidence upload -- drag and drop */}
                <div>
                  <label className="text-xs text-neutral-500 uppercase tracking-wider mb-2 block font-medium">
                    Evidence Photo
                  </label>
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => fileInputRef.current?.click()}
                    className={`glass rounded-xl p-6 border-2 border-dashed cursor-pointer transition-all text-center
                      ${isDragging
                        ? 'border-emerald-400/60 bg-emerald-500/[0.06]'
                        : file
                        ? 'border-emerald-500/30 bg-emerald-500/[0.04]'
                        : 'border-white/10 hover:border-white/20'
                      }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                      className="hidden"
                    />

                    {file ? (
                      <div className="space-y-2">
                        <ImageIcon size={28} className="text-emerald-400 mx-auto" />
                        <p className="text-sm text-emerald-300 font-medium truncate">{file.name}</p>
                        <p className="text-xs text-neutral-500">
                          {(file.size / 1024).toFixed(0)} KB -- Click to change
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <Upload size={28} className="text-neutral-500 mx-auto" />
                        <p className="text-sm text-neutral-400">
                          Drag & drop or click to upload
                        </p>
                        <p className="text-xs text-neutral-600">
                          JPG, PNG or HEIC up to 10 MB
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* GPS pin */}
                <div>
                  <label className="text-xs text-neutral-500 uppercase tracking-wider mb-2 block font-medium">
                    Location
                  </label>
                  <button
                    type="button"
                    onClick={handleGetLocation}
                    disabled={locating}
                    className={`glass w-full py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-all
                      ${lat
                        ? 'border border-emerald-500/30 text-emerald-300'
                        : 'hover:bg-white/[0.06] text-neutral-300'
                      }`}
                  >
                    <LocateFixed size={16} className={lat ? 'text-emerald-400' : 'text-neutral-500'} />
                    {lat
                      ? `${lat.toFixed(4)}, ${lng?.toFixed(4)}`
                      : locating
                      ? 'Acquiring GPS...'
                      : 'Pin Current Location'}
                  </button>
                </div>

                {/* Submit */}
                <button
                  type="submit"
                  disabled={isSubmitting || !reason}
                  className="btn-primary w-full py-3.5 text-sm font-semibold flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <div className="h-4 w-4 border-2 border-black/40 border-t-black rounded-full animate-spin" />
                      {uploadingFile ? 'Uploading Photo...' : 'Submitting...'}
                    </>
                  ) : (
                    <>
                      <Zap size={16} />
                      Submit Claim
                    </>
                  )}
                </button>
              </form>
            </div>
          </section>

          {/* ===== CLAIMS HISTORY ===== */}
          <section className="lg:col-span-3 space-y-4 animate-fade-in-up delay-200">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-1">
              <Clock size={18} className="text-neutral-400" />
              Claim History
              {claims.length > 0 && (
                <span className="badge badge-blue ml-1">{claims.length}</span>
              )}
            </h2>

            {claims.length === 0 ? (
              <div className="glass-card p-12 text-center">
                <FileWarning size={48} className="text-neutral-700 mx-auto mb-4" />
                <h3 className="text-neutral-400 font-medium mb-1">No claims yet</h3>
                <p className="text-sm text-neutral-600">
                  When you file a claim, it will appear here with live status updates.
                </p>
              </div>
            ) : (
              claims.map((claim, index) => {
                const cfg = statusConfig[claim.claim_status] || statusConfig.submitted
                return (
                  <div
                    key={claim.id}
                    className={`glass-card p-5 hover:bg-white/[0.04] transition-colors animate-fade-in-up ${
                      index <= 4 ? `delay-${(index + 1) * 100}` : ''
                    }`}
                  >
                    {/* Top row -- status + date */}
                    <div className="flex justify-between items-start mb-3">
                      <span className={`badge ${cfg.badge} flex items-center gap-1.5`}>
                        {cfg.icon}
                        {cfg.label}
                      </span>
                      <span className="text-xs text-neutral-500">
                        {new Date(claim.claimed_at).toLocaleDateString('en-IN', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                        })}
                      </span>
                    </div>

                    {/* Claim reason */}
                    <p className="text-sm text-neutral-300 mb-3 line-clamp-2 leading-relaxed">
                      {claim.claim_reason}
                    </p>

                    {/* Meta row */}
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="glass px-2.5 py-1 rounded-lg text-neutral-400 font-mono">
                        #{claim.id.split('-')[0]}
                      </span>

                      {claim.claim_mode && (
                        <span className={`badge ${claim.claim_mode === 'trigger_auto' ? 'badge-purple' : 'badge-blue'}`}>
                          {claim.claim_mode === 'trigger_auto' ? 'Auto-trigger' : 'Manual'}
                        </span>
                      )}

                      {claim.trigger_events && (
                        <span className="badge badge-blue flex items-center gap-1">
                          <Zap size={10} />
                          {claim.trigger_events.trigger_family}
                        </span>
                      )}

                      {claim.stated_lat && (
                        <span className="glass px-2.5 py-1 rounded-lg text-neutral-400 flex items-center gap-1">
                          <MapPin size={11} />
                          {claim.stated_lat.toFixed(2)}, {claim.stated_lng?.toFixed(2)}
                        </span>
                      )}
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
