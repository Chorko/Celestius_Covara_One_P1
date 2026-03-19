"use client"

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import {
  Users, Search, MapPin, ChevronDown, ChevronUp, Mail,
  Shield, Navigation2, Bike, CheckCircle, XCircle,
  Fingerprint, BarChart3, FileText, Clock
} from 'lucide-react'

/* eslint-disable @typescript-eslint/no-explicit-any */
interface WorkerProfile {
  profile_id: string
  city?: string
  platform_name?: string
  vehicle_type?: string
  avg_hourly_income_inr?: number
  trust_score?: number
  gps_consistency_score?: number
  gps_consent?: boolean
  bank_verified?: boolean
  preferred_zone_id?: string
  profiles?: { id?: string; full_name?: string; email?: string; phone?: string }
  zones?: { zone_name?: string }
  [key: string]: any
}

interface WorkerClaim {
  id: string
  claim_status: string
  claim_reason: string
  claimed_at: string
  trigger_events?: { trigger_code?: string; trigger_family?: string }
  [key: string]: any
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export default function AdminUsers() {
  const supabase = createClient()
  const [workers, setWorkers] = useState<WorkerProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [cityFilter, setCityFilter] = useState('')
  const [expandedWorker, setExpandedWorker] = useState<string | null>(null)
  const [workerClaims, setWorkerClaims] = useState<Record<string, WorkerClaim[]>>({})
  const [claimLoading, setClaimLoading] = useState<string | null>(null)

  const loadWorkers = useCallback(async (city?: string) => {
    setLoading(true)
    try {
      let query = supabase
        .from('worker_profiles')
        .select('*, profiles(id, full_name, email, phone), zones(zone_name)')
        .order('trust_score', { ascending: false })
      if (city) query = query.eq('city', city)
      const { data } = await query
      setWorkers(data || [])
    } catch (e) {
      console.error('Could not load workers', e)
    }
    setLoading(false)
  }, [supabase])

  useEffect(() => {
    loadWorkers()
  }, [loadWorkers])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (cityFilter.trim()) {
      loadWorkers(cityFilter.trim())
    } else {
      loadWorkers()
    }
  }

  const toggleExpand = async (workerId: string) => {
    if (expandedWorker === workerId) {
      setExpandedWorker(null)
      return
    }
    setExpandedWorker(workerId)

    // Load claims for this worker if not already loaded
    if (!workerClaims[workerId]) {
      setClaimLoading(workerId)
      try {
        const { data } = await supabase
          .from('manual_claims')
          .select('id, claim_status, claim_reason, claimed_at, trigger_events(trigger_code, trigger_family)')
          .eq('worker_profile_id', workerId)
          .order('claimed_at', { ascending: false })
          .limit(5)
        setWorkerClaims((prev) => ({ ...prev, [workerId]: (data || []) as WorkerClaim[] }))
      } catch (e) {
        console.error('Could not load claims for worker', e)
      }
      setClaimLoading(null)
    }
  }

  // Client-side filter by name, email, or city
  const filteredWorkers = workers.filter((w) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    const name = (w.profiles?.full_name || '').toLowerCase()
    const email = (w.profiles?.email || '').toLowerCase()
    const city = (w.city || '').toLowerCase()
    const platform = (w.platform_name || '').toLowerCase()
    return (
      name.includes(q) ||
      email.includes(q) ||
      city.includes(q) ||
      platform.includes(q)
    )
  })

  const trustColor = (score: number) => {
    if (score >= 0.8) return '#10b981'
    if (score >= 0.6) return '#f59e0b'
    return '#ef4444'
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

  return (
    <div className="p-8 max-w-6xl mx-auto gradient-mesh-admin min-h-screen">
      {/* Header */}
      <div className="mb-8 animate-fade-in-up">
        <div className="flex items-center gap-3 mb-2">
          <Users size={28} className="text-purple-400" />
          <h1 className="text-3xl font-bold">Worker Directory</h1>
        </div>
        <p className="text-neutral-400">
          Search and inspect worker profiles, trust scores, and claim history.
        </p>
      </div>

      {/* Search Bar */}
      <div className="glass-card p-5 mb-8 animate-fade-in-up delay-100">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, email, city, or platform..."
              className="glass-input pl-10"
            />
          </div>
          <div className="relative sm:w-48">
            <MapPin
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500"
            />
            <input
              type="text"
              value={cityFilter}
              onChange={(e) => setCityFilter(e.target.value)}
              placeholder="Filter by city..."
              className="glass-input pl-10"
            />
          </div>
          <button type="submit" className="btn-primary flex items-center justify-center gap-2 sm:w-32">
            <Search size={16} /> Search
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="space-y-3 animate-fade-in-up delay-200">
        {loading ? (
          <div className="glass-card p-16 text-center">
            <div className="w-8 h-8 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-neutral-500 text-sm">Loading workers...</p>
          </div>
        ) : filteredWorkers.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
              <Users size={28} className="text-neutral-600" />
            </div>
            <p className="text-neutral-500 font-medium">No workers found</p>
            <p className="text-xs text-neutral-600 mt-1">
              {searchQuery
                ? 'Try adjusting your search query'
                : 'No workers registered on the platform yet'}
            </p>
          </div>
        ) : (
          <>
            <p className="text-xs text-neutral-500 mb-2">
              Showing {filteredWorkers.length} worker{filteredWorkers.length !== 1 ? 's' : ''}
            </p>

            {filteredWorkers.map((worker) => {
              const isExpanded = expandedWorker === worker.profile_id
              const claims = workerClaims[worker.profile_id] || []
              const trustScore = worker.trust_score || 0

              return (
                <div key={worker.profile_id} className="glass-card overflow-hidden">
                  {/* Main Row */}
                  <div
                    className="p-5 flex items-center justify-between cursor-pointer hover:bg-white/[0.02] transition-colors"
                    onClick={() => toggleExpand(worker.profile_id)}
                  >
                    <div className="flex items-center gap-4 min-w-0 flex-1">
                      {/* Avatar */}
                      <div className="w-11 h-11 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center shrink-0">
                        <span className="text-purple-400 font-bold text-sm">
                          {(worker.profiles?.full_name || 'W')
                            .split(' ')
                            .map((n: string) => n[0])
                            .join('')
                            .toUpperCase()
                            .slice(0, 2)}
                        </span>
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-sm">
                            {worker.profiles?.full_name || 'Unknown'}
                          </span>
                          <span className="text-xs text-neutral-500 flex items-center gap-1">
                            <Mail size={10} />
                            {worker.profiles?.email || '—'}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-neutral-500 mt-1 flex-wrap">
                          <span className="flex items-center gap-1">
                            <MapPin size={10} /> {worker.city || '—'}
                          </span>
                          <span className="flex items-center gap-1">
                            <Bike size={10} /> {worker.platform_name || '—'} / {worker.vehicle_type || '—'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 shrink-0 ml-3">
                      {/* Trust Score */}
                      <div className="hidden sm:flex items-center gap-2">
                        <div className="w-20">
                          <div className="progress-bar">
                            <div
                              className="progress-bar-fill"
                              style={{
                                width: `${trustScore * 100}%`,
                                background: trustColor(trustScore),
                              }}
                            />
                          </div>
                        </div>
                        <span
                          className="text-xs font-semibold"
                          style={{ color: trustColor(trustScore) }}
                        >
                          {(trustScore * 100).toFixed(0)}
                        </span>
                      </div>

                      {/* Quick badges */}
                      <div className="hidden sm:flex items-center gap-1.5">
                        {worker.gps_consent ? (
                          <span className="badge badge-emerald" title="GPS Consent">
                            <Navigation2 size={10} /> GPS
                          </span>
                        ) : (
                          <span className="badge badge-red" title="No GPS">
                            <XCircle size={10} /> GPS
                          </span>
                        )}
                        {worker.bank_verified ? (
                          <span className="badge badge-emerald" title="Bank Verified">
                            <CheckCircle size={10} /> Bank
                          </span>
                        ) : (
                          <span className="badge badge-amber" title="Bank Not Verified">
                            <Clock size={10} /> Bank
                          </span>
                        )}
                      </div>

                      {isExpanded ? (
                        <ChevronUp size={16} className="text-neutral-500" />
                      ) : (
                        <ChevronDown size={16} className="text-neutral-500" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Detail */}
                  {isExpanded && (
                    <div className="border-t border-white/[0.06] p-5 bg-white/[0.01] space-y-5">
                      {/* Profile Details Grid */}
                      <div>
                        <h4 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <Fingerprint size={14} /> Full Profile
                        </h4>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              City
                            </p>
                            <p className="text-sm font-medium mt-0.5">{worker.city || '—'}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              Platform
                            </p>
                            <p className="text-sm font-medium mt-0.5">
                              {worker.platform_name || '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              Vehicle Type
                            </p>
                            <p className="text-sm font-medium mt-0.5">
                              {worker.vehicle_type || '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              Hourly Income
                            </p>
                            <p className="text-sm font-medium mt-0.5">
                              ₹{worker.avg_hourly_income_inr || '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              Trust Score
                            </p>
                            <div className="flex items-center gap-2 mt-0.5">
                              <div className="w-16 progress-bar">
                                <div
                                  className="progress-bar-fill"
                                  style={{
                                    width: `${trustScore * 100}%`,
                                    background: trustColor(trustScore),
                                  }}
                                />
                              </div>
                              <span
                                className="text-sm font-bold"
                                style={{ color: trustColor(trustScore) }}
                              >
                                {trustScore.toFixed(2)}
                              </span>
                            </div>
                          </div>
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              GPS Consistency
                            </p>
                            <p className="text-sm font-medium mt-0.5">
                              {worker.gps_consistency_score?.toFixed(2) || '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              GPS Consent
                            </p>
                            <p className="text-sm font-medium mt-0.5">
                              {worker.gps_consent ? (
                                <span className="text-emerald-400 flex items-center gap-1">
                                  <CheckCircle size={12} /> Yes
                                </span>
                              ) : (
                                <span className="text-red-400 flex items-center gap-1">
                                  <XCircle size={12} /> No
                                </span>
                              )}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] text-neutral-600 uppercase tracking-wider">
                              Bank Verified
                            </p>
                            <p className="text-sm font-medium mt-0.5">
                              {worker.bank_verified ? (
                                <span className="text-emerald-400 flex items-center gap-1">
                                  <CheckCircle size={12} /> Verified
                                </span>
                              ) : (
                                <span className="text-amber-400 flex items-center gap-1">
                                  <Clock size={12} /> Pending
                                </span>
                              )}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Recent Claims */}
                      <div>
                        <h4 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <FileText size={14} /> Recent Claims
                        </h4>
                        {claimLoading === worker.profile_id ? (
                          <div className="text-center py-6 text-sm text-neutral-500">
                            <div className="w-4 h-4 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin mx-auto mb-2" />
                            Loading claims...
                          </div>
                        ) : claims.length === 0 ? (
                          <div className="text-center py-6 text-sm text-neutral-600 bg-white/[0.02] rounded-xl border border-white/[0.04] border-dashed">
                            No claims filed by this worker
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {claims.slice(0, 5).map((claim) => (
                              <div
                                key={claim.id}
                                className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]"
                              >
                                <div className="min-w-0 flex-1">
                                  <p className="text-sm truncate">{claim.claim_reason}</p>
                                  <p className="text-[10px] text-neutral-600 mt-0.5">
                                    {new Date(claim.claimed_at).toLocaleDateString('en-IN', {
                                      dateStyle: 'medium',
                                    })}
                                    {claim.trigger_events?.trigger_family && (
                                      <span className="ml-2 text-blue-400/70">
                                        {claim.trigger_events.trigger_family}
                                      </span>
                                    )}
                                  </p>
                                </div>
                                <span className={`badge ${statusBadge(claim.claim_status)} shrink-0 ml-3`}>
                                  {claim.claim_status}
                                </span>
                              </div>
                            ))}
                            {claims.length > 5 && (
                              <p className="text-xs text-neutral-600 text-center pt-1">
                                + {claims.length - 5} more claim{claims.length - 5 !== 1 ? 's' : ''}
                              </p>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Stats Summary */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="glass-card p-4 text-center">
                          <BarChart3 size={16} className="text-blue-400 mx-auto mb-2" />
                          <p className="text-lg font-bold">{claims.length}</p>
                          <p className="text-[10px] text-neutral-500 uppercase tracking-wider">
                            Total Claims
                          </p>
                        </div>
                        <div className="glass-card p-4 text-center">
                          <CheckCircle size={16} className="text-emerald-400 mx-auto mb-2" />
                          <p className="text-lg font-bold">
                            {claims.filter((c) => c.claim_status === 'approved').length}
                          </p>
                          <p className="text-[10px] text-neutral-500 uppercase tracking-wider">
                            Approved
                          </p>
                        </div>
                        <div className="glass-card p-4 text-center">
                          <Shield size={16} className="text-amber-400 mx-auto mb-2" />
                          <p className="text-lg font-bold">
                            {claims.filter(
                              (c) => c.claim_status === 'held' || c.claim_status === 'submitted'
                            ).length}
                          </p>
                          <p className="text-[10px] text-neutral-500 uppercase tracking-wider">
                            Pending
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </>
        )}
      </div>
    </div>
  )
}
