"use client"

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { FileSearch, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'

export default function AdminReviews() {
  const supabase = createClient()
  const [claims, setClaims] = useState<any[]>([])
  const [selectedClaim, setSelectedClaim] = useState<any | null>(null)
  const [detailData, setDetailData] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  
  useEffect(() => { loadClaims() }, [])

  const loadClaims = async () => {
    const { data: session } = await supabase.auth.getSession()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims`, {
      headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
    })
    if (res.ok) {
      const data = await res.json()
      setClaims(data.claims)
    }
  }

  const loadDetail = async (id: string) => {
    setLoading(true)
    const { data: session } = await supabase.auth.getSession()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims/${id}`, {
      headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
    })
    if (res.ok) {
      setDetailData(await res.json())
      setSelectedClaim(id)
    }
    setLoading(false)
  }

  const handleReviewAction = async (decision: string) => {
    if (!selectedClaim) return
    const { data: session } = await supabase.auth.getSession()
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims/${selectedClaim}/review`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${session.session?.access_token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ decision, decision_reason: `Admin review - ${decision}` })
    })
    setSelectedClaim(null)
    setDetailData(null)
    await loadClaims()
  }

  return (
    <div className="p-8 h-full flex flex-col md:flex-row gap-6 animate-in fade-in duration-500">
      
      {/* Queue List */}
      <div className="w-full md:w-1/3 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col overflow-hidden">
        <div className="p-4 border-b border-slate-800 bg-slate-900 z-10">
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <FileSearch size={20} className="text-blue-500"/> Review Queue
          </h2>
        </div>
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {claims.map(c => (
            <div 
              key={c.id} 
              onClick={() => loadDetail(c.id)}
              className={`p-4 rounded-xl border cursor-pointer transition-colors ${
                selectedClaim === c.id ? 'bg-blue-500/10 border-blue-500/50' : 'bg-slate-950 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-slate-200">{c.worker_profiles?.platform_name} Worker</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  c.claim_status === 'approved' ? 'bg-emerald-500/20 text-emerald-400' :
                  c.claim_status === 'held' || c.claim_status === 'submitted' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-red-500/20 text-red-400'
                }`}>{c.claim_status}</span>
              </div>
              <p className="text-xs text-slate-400 truncate mt-1">{c.claim_reason}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Detail Pane */}
      <div className="w-full md:w-2/3 bg-slate-900 border border-slate-800 rounded-2xl p-6 overflow-auto">
        {!selectedClaim ? (
          <div className="h-full flex items-center justify-center text-slate-500">
            Select a claim from the queue to review
          </div>
        ) : loading ? (
          <div className="h-full flex items-center justify-center text-slate-500">Loading details...</div>
        ) : detailData ? (
          <div className="space-y-6">
            <div className="flex justify-between items-start border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-xl font-semibold text-white">Claim Review: {detailData.claim.id.split('-')[0]}</h2>
                <p className="text-sm text-slate-400 mt-1">Zone: {detailData.claim.trigger_events?.zone_id || 'Unknown'} | Submitted: {new Date(detailData.claim.claimed_at).toLocaleString()}</p>
              </div>
              <span className="bg-slate-800 px-3 py-1 rounded text-sm text-slate-300">
                Mode: {detailData.claim.claim_mode}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Payout Recommendation</h3>
                <div className="text-3xl font-bold text-emerald-400 mb-1">
                  ₹{detailData.payout_recommendation?.recommended_payout}
                </div>
                <div className="text-xs text-slate-400">
                  Expected: ₹{detailData.payout_recommendation?.expected_payout} • Cap: ₹{detailData.payout_recommendation?.payout_cap}
                </div>
              </div>
              
              <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Ghost Shift Fraud Check</h3>
                <div className="text-3xl font-bold text-yellow-400 mb-1">
                  {detailData.payout_recommendation?.fraud_holdback_fh.toFixed(2)} Holdback
                </div>
                <div className="text-xs text-slate-400">
                  Confidence Score (C): {detailData.payout_recommendation?.confidence_score_c}
                </div>
              </div>
            </div>

            <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl">
              <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Worker Stated Reason</h3>
              <p className="text-sm text-slate-300">{detailData.claim.claim_reason}</p>
            </div>

            {detailData.payout_recommendation?.explanation_json?.ai_summary && (
              <div className="bg-purple-900/10 border border-purple-500/20 p-4 rounded-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-2xl pointer-events-none" />
                <h3 className="text-xs font-medium text-purple-400 flex items-center gap-2 uppercase tracking-wider mb-2">
                  <span className="text-lg">✨</span> Gemini AI Review Assist
                </h3>
                <p className="text-sm text-purple-100/90 leading-relaxed italic border-l-2 border-purple-500/50 pl-3">
                  "{detailData.payout_recommendation.explanation_json.ai_summary}"
                </p>
              </div>
            )}

            {detailData.claim.claim_status === 'held' || detailData.claim.claim_status === 'submitted' ? (
              <div className="border-t border-slate-800 pt-6 flex gap-3">
                <button 
                  onClick={() => handleReviewAction('approve')}
                  className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 rounded-xl transition-colors flex justify-center items-center gap-2"
                >
                  <CheckCircle size={18} /> Approve Payout
                </button>
                <button 
                  onClick={() => handleReviewAction('reject')}
                  className="flex-1 bg-red-900/50 hover:bg-red-900 text-red-200 border border-red-800 font-medium py-3 rounded-xl transition-colors flex justify-center items-center gap-2"
                >
                  <XCircle size={18} /> Reject Claim
                </button>
              </div>
            ) : (
              <div className="border-t border-slate-800 pt-6 text-center text-slate-500">
                This claim has already been {detailData.claim.claim_status}.
              </div>
            )}
            
          </div>
        ) : null}
      </div>

    </div>
  )
}
