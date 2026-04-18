"use client"

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { useUserStore } from '@/store'
import { backendGet } from '@/lib/backendApi'
import ZonePulseMap from '@/components/ZonePulseMap'
import Skeleton from '@/components/Skeleton'
import {
  AlertTriangle,
  CloudRain,
  MapPin,
  Navigation,
  Shield,
  Sparkles,
  TrendingUp,
  Zap,
} from 'lucide-react'

interface ZoneDetail {
  id: string
  city: string
  zone_name: string
  center_lat: number | null
  center_lng: number | null
  polygon_geojson?: unknown
}

interface WorkerZoneProfile {
  profile_id: string
  city?: string
  platform_name?: string
  preferred_zone_id?: string
  trust_score?: number
  gps_consistency_score?: number
  zones?: {
    zone_name?: string
  }
}

interface TriggerRow {
  id: string
  trigger_code?: string
  trigger_family?: string
  severity_band?: string
  source_type?: string
  started_at?: string
  ended_at?: string | null
  official_threshold_label?: string | null
  product_threshold_value?: string | null
  observed_value?: number | null
}

function severityBadge(severity: string | undefined): string {
  if (severity === 'escalation') return 'badge-danger'
  if (severity === 'claim') return 'badge-warning'
  return 'badge-info'
}

function severityWeight(severity: string | undefined): number {
  if (severity === 'escalation') return 3
  if (severity === 'claim') return 2
  return 1
}

export default function WorkerZonePage() {
  const { profile } = useUserStore()
  const supabase = createClient()

  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [workerZone, setWorkerZone] = useState<WorkerZoneProfile | null>(null)
  const [zoneDetail, setZoneDetail] = useState<ZoneDetail | null>(null)
  const [activeTriggers, setActiveTriggers] = useState<TriggerRow[]>([])
  const [triggerHistory, setTriggerHistory] = useState<TriggerRow[]>([])

  const loadZoneData = useCallback(async () => {
    if (!profile?.id) {
      setLoading(false)
      return
    }

    setLoading(true)
    setLoadError(null)

    try {
      let workerData: WorkerZoneProfile | null = null

      // Prefer backend profile read because it is service-role backed and avoids
      // client-side RLS drift causing false "not configured" states.
      try {
        const workerFromApi = await backendGet<WorkerZoneProfile>(supabase, '/workers/me')
        workerData = workerFromApi || null
      } catch {
        const { data: workerFallback } = await supabase
          .from('worker_profiles')
          .select('profile_id, city, platform_name, preferred_zone_id, trust_score, gps_consistency_score, zones(zone_name)')
          .eq('profile_id', profile.id)
          .maybeSingle()
        workerData = (workerFallback as WorkerZoneProfile | null) || null
      }

      if (!workerData) {
        setWorkerZone(null)
        setZoneDetail(null)
        setActiveTriggers([])
        setTriggerHistory([])
        setLoadError('Worker profile is not configured yet.')
        setLoading(false)
        return
      }

      setWorkerZone(workerData)

      if (!workerData.preferred_zone_id) {
        setZoneDetail(null)
        setActiveTriggers([])
        setTriggerHistory([])
        setLoadError('Preferred zone is not assigned yet. Contact admin ops.')
        setLoading(false)
        return
      }

      const [activeResult, historyResult] = await Promise.all([
        supabase
          .from('trigger_events')
          .select('id, trigger_code, trigger_family, severity_band, source_type, started_at, ended_at, official_threshold_label, product_threshold_value, observed_value')
          .eq('zone_id', workerData.preferred_zone_id)
          .is('ended_at', null)
          .order('started_at', { ascending: false })
          .limit(8),
        supabase
          .from('trigger_events')
          .select('id, trigger_code, trigger_family, severity_band, source_type, started_at, ended_at, official_threshold_label, product_threshold_value, observed_value')
          .eq('zone_id', workerData.preferred_zone_id)
          .order('started_at', { ascending: false })
          .limit(40),
      ])

      setActiveTriggers((activeResult.data || []) as TriggerRow[])
      setTriggerHistory((historyResult.data || []) as TriggerRow[])

      try {
        const zone = await backendGet<ZoneDetail>(supabase, `/zones/${workerData.preferred_zone_id}`)
        setZoneDetail(zone)
      } catch {
        const { data: zoneFallback } = await supabase
          .from('zones')
          .select('id, city, zone_name, center_lat, center_lng, polygon_geojson')
          .eq('id', workerData.preferred_zone_id)
          .maybeSingle()
        setZoneDetail((zoneFallback as ZoneDetail | null) || null)
      }
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : 'Could not load zone intelligence')
    } finally {
      setLoading(false)
    }
  }, [profile?.id, supabase])

  useEffect(() => {
    void loadZoneData()
  }, [loadZoneData])

  const historicalDisruptions = useMemo(
    () => triggerHistory.filter((trigger) => Boolean(trigger.ended_at)).length,
    [triggerHistory],
  )

  const riskScore = useMemo(() => {
    if (triggerHistory.length === 0) {
      return 0
    }

    const weighted = triggerHistory.reduce((sum, trigger) => {
      const recencyBoost = trigger.ended_at ? 1 : 1.6
      return sum + (severityWeight(trigger.severity_band) * recencyBoost)
    }, 0)

    const normalized = Math.min(100, Math.round((weighted / (triggerHistory.length * 3)) * 100))
    return normalized
  }, [triggerHistory])

  if (loading) {
    return (
      <div className="min-h-screen page-mesh">
        <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-6">
          <section>
            <Skeleton width="220px" height="2rem" className="mb-3" />
            <Skeleton width="340px" height="0.875rem" />
          </section>
          <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((id) => (
              <div key={id} className="card p-5">
                <Skeleton width="100%" height="70px" />
              </div>
            ))}
          </section>
          <section className="card p-6">
            <Skeleton width="100%" height="320px" />
          </section>
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="card p-5"><Skeleton width="100%" height="280px" /></div>
            <div className="card p-5"><Skeleton width="100%" height="280px" /></div>
          </section>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-10 pb-28 max-w-7xl mx-auto space-y-6">
        <section className="animate-fade-in-up">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <MapPin size={24} style={{ color: 'var(--accent)' }} />
                My Zone Intelligence
              </h1>
              <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>
                Live disruptions, historical trigger timeline, and map-level coverage insight for your assigned operating zone.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={activeTriggers.length > 0 ? 'badge-warning' : 'badge-success'}>
                {activeTriggers.length > 0 ? `${activeTriggers.length} active` : 'No active trigger'}
              </span>
              <Link href="/worker/dashboard" className="badge-info">
                Back To Dashboard
              </Link>
            </div>
          </div>
        </section>

        {loadError && (
          <section className="card p-4 flex items-start gap-2" style={{ background: 'var(--warning-muted)', border: '1px solid var(--warning)' }}>
            <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--warning)' }} />
            <p className="text-sm" style={{ color: 'var(--warning)' }}>{loadError}</p>
          </section>
        )}

        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card p-5" style={{ borderLeft: '3px solid var(--accent)' }}>
            <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Zone</p>
            <p className="text-lg font-semibold mt-1" style={{ color: 'var(--text-primary)' }}>
              {zoneDetail?.zone_name || workerZone?.zones?.zone_name || 'Unassigned'}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{zoneDetail?.city || workerZone?.city || 'Unknown city'}</p>
          </div>

          <div className="card p-5" style={{ borderLeft: '3px solid var(--warning)' }}>
            <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Active Alerts</p>
            <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{activeTriggers.length}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Currently impacting this zone</p>
          </div>

          <div className="card p-5" style={{ borderLeft: '3px solid var(--info)' }}>
            <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Historical Events</p>
            <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{historicalDisruptions}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Resolved disruptions in history window</p>
          </div>

          <div className="card p-5" style={{ borderLeft: '3px solid var(--danger)' }}>
            <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Zone Risk Score</p>
            <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{riskScore}%</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Severity + recency weighted</p>
          </div>
        </section>

        <section className="card p-6 section-enter">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Navigation size={18} style={{ color: 'var(--accent)' }} />
                Zone Map
              </h2>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                Trigger markers are plotted around the active zone. Live events pulse; resolved events remain in the timeline below.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="badge-info">Trust {Number(workerZone?.trust_score || 0).toFixed(2)}</span>
              <span className="badge-info">GPS {Number(workerZone?.gps_consistency_score || 0).toFixed(2)}</span>
              <span className="badge-success">{workerZone?.platform_name || 'Platform'}</span>
            </div>
          </div>

          {zoneDetail && typeof zoneDetail.center_lat === 'number' && typeof zoneDetail.center_lng === 'number' ? (
            <ZonePulseMap
              centerLat={zoneDetail.center_lat}
              centerLng={zoneDetail.center_lng}
              zoneName={zoneDetail.zone_name}
              polygonGeoJson={zoneDetail.polygon_geojson}
              triggers={activeTriggers.map((trigger) => ({
                id: trigger.id,
                trigger_code: trigger.trigger_code,
                severity_band: trigger.severity_band,
                started_at: trigger.started_at,
                official_threshold_label: trigger.official_threshold_label,
              }))}
            />
          ) : (
            <div className="p-6 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>
              Zone coordinates are not available for this worker yet.
            </div>
          )}
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="card p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2 mb-4" style={{ color: 'var(--text-tertiary)' }}>
              <Zap size={14} /> Active Triggers
            </h3>

            {activeTriggers.length === 0 ? (
              <div className="p-5 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>
                No active disruptions currently. Your zone is stable.
              </div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {activeTriggers.map((trigger) => (
                  <div key={trigger.id} className="p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className={severityBadge(trigger.severity_band)}>
                        {String(trigger.severity_band || 'watch').toUpperCase()}
                      </span>
                      <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                        {trigger.started_at ? new Date(trigger.started_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'Now'}
                      </span>
                    </div>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {String(trigger.trigger_code || 'trigger').replaceAll('_', ' ')}
                    </p>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                      {trigger.official_threshold_label || trigger.product_threshold_value || 'Threshold matched'}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider flex items-center gap-2 mb-4" style={{ color: 'var(--text-tertiary)' }}>
              <TrendingUp size={14} /> Trigger History
            </h3>

            {triggerHistory.length === 0 ? (
              <div className="p-5 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}>
                No historical events logged for this zone yet.
              </div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {triggerHistory.map((trigger) => {
                  const isActive = !trigger.ended_at
                  return (
                    <div key={`history-${trigger.id}`} className="p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="flex items-center gap-2">
                          <span className={severityBadge(trigger.severity_band)}>
                            {String(trigger.severity_band || 'watch').toUpperCase()}
                          </span>
                          <span className={isActive ? 'badge-warning' : 'badge-success'}>{isActive ? 'ACTIVE' : 'RESOLVED'}</span>
                        </div>
                        <span className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                          {trigger.started_at ? new Date(trigger.started_at).toLocaleDateString('en-IN') : 'Unknown'}
                        </span>
                      </div>

                      <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {String(trigger.trigger_code || 'trigger').replaceAll('_', ' ')}
                      </p>

                      <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                        {trigger.official_threshold_label || trigger.product_threshold_value || 'Threshold matched'}
                      </p>

                      <p className="text-[11px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                        Source: {trigger.source_type || 'unknown'}
                      </p>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </section>

        <section className="card p-5" style={{ borderLeft: '3px solid var(--accent)' }}>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Shield size={16} style={{ color: 'var(--accent)' }} /> Coverage Action
              </h3>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                Live zone spikes can impact claim windows. Keep coverage active and check rewards for bonus reductions.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/worker/pricing" className="btn-primary px-4 py-2 text-sm">Update Coverage</Link>
              <Link href="/worker/rewards" className="btn-secondary px-4 py-2 text-sm">
                <Sparkles size={14} /> Rewards
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
