"use client"

import { useEffect, useState } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { Camera, MapPin, Send, AlertCircle, Clock, CheckCircle, XCircle } from 'lucide-react'

export default function WorkerClaims() {
  const { user, profile } = useUserStore()
  const supabase = createClient()
  
  const [claims, setClaims] = useState<any[]>([])
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

  useEffect(() => {
    if (profile) loadClaims()
  }, [profile])

  const loadClaims = async () => {
    try {
      const { data: session } = await supabase.auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims`, {
        headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setClaims(data.claims)
      }
    } catch (e) { console.error("Could not load claims", e) }
  }

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
      let evidenceUrl = null;
      
      // Handle file upload first if present
      if (file && user) {
        setUploadingFile(true)
        const fileExt = file.name.split('.').pop()
        const fileName = `${user.id}-${Date.now()}.${fileExt}`
        const filePath = `${fileName}`
        
        const { error: uploadError } = await supabase.storage.from('claim-evidence').upload(filePath, file)
        if (uploadError) {
          throw new Error(`Evidence upload failed: ${uploadError.message}`)
        }
        
        const { data } = supabase.storage.from('claim-evidence').getPublicUrl(filePath)
        evidenceUrl = data.publicUrl
        setUploadingFile(false)
      }

      const { data: session } = await supabase.auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${session.session?.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          claim_reason: reason,
          stated_lat: lat,
          stated_lng: lng,
          evidence_url: evidenceUrl
        })
      })

      if (!res.ok) throw new Error("Failed to submit claim")
      
      setReason('')
      setLat(null)
      setLng(null)
      setFile(null)
      await loadClaims()
    } catch (e: any) {
      setSubmitError(e.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold mb-2">My Claims</h1>
        <p className="text-neutral-400">File a new manual claim or track the status of existing ones.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Submit Form */}
        <div className="md:col-span-1 bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl h-fit">
          <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
            <Send size={20} className="text-emerald-500" /> File a Claim
          </h2>
          {submitError && <div className="text-red-400 text-sm mb-4">{submitError}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider mb-2 block">Reason for disruption</label>
              <textarea 
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-emerald-500/50 min-h-[100px]"
                placeholder="e.g. Severe waterlogging blocked access to the pickup restaurant..."
              />
            </div>

            <div className="p-4 bg-neutral-950/50 border border-neutral-800 border-dashed rounded-xl">
              <label className="text-xs text-neutral-500 uppercase tracking-wider mb-3 block">Evidence & Location</label>
              <div className="space-y-2">
                <div className="relative">
                  <input 
                    type="file" 
                    accept="image/*"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <button type="button" className={`w-full py-2 ${file ? 'bg-emerald-500/20 text-emerald-400' : 'bg-neutral-800 hover:bg-neutral-700'} rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors`}>
                    <Camera size={16} /> {file ? "Photo Selected" : "Attach Photo"}
                  </button>
                  {file && <span className="text-xs text-neutral-400 mt-2 block text-center truncate">{file.name}</span>}
                </div>
                <button 
                  type="button" 
                  onClick={handleGetLocation}
                  disabled={locating}
                  className="w-full py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors"
                >
                  <MapPin size={16} className={lat ? "text-emerald-500" : ""} />
                  {lat ? `Location: ${lat.toFixed(4)}, ${lng?.toFixed(4)}` : locating ? 'Locating...' : 'Pin Current Location'}
                </button>
              </div>
            </div>

            <button 
              type="submit" 
              disabled={isSubmitting || !reason}
              className="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold py-3 rounded-xl transition-colors"
            >
              {isSubmitting ? (uploadingFile ? 'Uploading Photo...' : 'Submitting...') : 'Submit Claim'}
            </button>
          </form>
        </div>

        {/* Claim History List */}
        <div className="md:col-span-2 space-y-4">
          <h2 className="text-lg font-medium mb-4">Claim History</h2>
          
          {claims.length === 0 ? (
            <div className="text-center p-12 bg-neutral-900 border border-neutral-800 border-dashed rounded-2xl text-neutral-500">
              You have no past claims on record.
            </div>
          ) : (
            claims.map(claim => (
              <div key={claim.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 hover:border-neutral-700 transition-colors">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    {claim.claim_status === 'approved' && <CheckCircle size={18} className="text-emerald-500" />}
                    {claim.claim_status === 'held' && <Clock size={18} className="text-yellow-500" />}
                    {claim.claim_status === 'submitted' && <AlertCircle size={18} className="text-blue-500" />}
                    {claim.claim_status === 'rejected' && <XCircle size={18} className="text-red-500" />}
                    <span className="font-semibold capitalize text-neutral-200">{claim.claim_status}</span>
                  </div>
                  <span className="text-sm text-neutral-500">{new Date(claim.claimed_at).toLocaleDateString()}</span>
                </div>
                
                <p className="text-sm text-neutral-400 mb-3">{claim.claim_reason}</p>
                
                <div className="flex gap-3 text-xs text-neutral-500 font-medium">
                  <span className="bg-neutral-950 px-2 py-1 rounded">ID: {claim.id.split('-')[0]}</span>
                  {claim.trigger_events && (
                    <span className="bg-blue-500/10 text-blue-400 px-2 py-1 rounded">
                      Matched: {claim.trigger_events.trigger_family}
                    </span>
                  )}
                  {claim.stated_lat && (
                    <span className="flex items-center gap-1"><MapPin size={12}/> {claim.stated_lat.toFixed(2)}, {claim.stated_lng?.toFixed(2)}</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

      </div>
    </div>
  )
}
