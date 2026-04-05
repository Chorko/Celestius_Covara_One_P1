"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createClient } from '@/lib/supabase'
import type { LayerGroup, Map as LeafletMap } from 'leaflet'
import { AlertTriangle, Layers3, MapPin, Radar, RefreshCw } from 'lucide-react'

type LeafletModule = typeof import('leaflet')

type SeverityBand = 'watch' | 'claim' | 'escalation'

type ClusterStats = {
  clusters: number
  clusteredClaims: number
  noiseClaims: number
}

type ZoneRow = {
  id: string
  city: string
  zone_name: string
  center_lat: number | string | null
  center_lng: number | string | null
}

type TriggerRow = {
  id: string
  zone_id: string | null
  city: string
  trigger_family: string
  trigger_code: string
  observed_value: number | string | null
  severity_band: SeverityBand
  started_at: string
}

type ClaimRow = {
  id: string
  claim_status: string
  stated_lat: number | string | null
  stated_lng: number | string | null
  claimed_at: string
}

type GeoPoint = {
  lat: number
  lng: number
}

const INDIA_CENTER: [number, number] = [20.5937, 78.9629]
const DBSCAN_EPSILON_KM = 1.2
const DBSCAN_MIN_POINTS = 3

const SUSPICIOUS_STATES = new Set([
  'fraud_escalated_review',
  'rejected',
  'post_approval_flagged',
])

function toNumber(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null
  }

  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function toRadians(deg: number): number {
  return (deg * Math.PI) / 180
}

function haversineKm(a: GeoPoint, b: GeoPoint): number {
  const R = 6371
  const dLat = toRadians(b.lat - a.lat)
  const dLng = toRadians(b.lng - a.lng)
  const lat1 = toRadians(a.lat)
  const lat2 = toRadians(b.lat)

  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.sin(dLng / 2) ** 2 * Math.cos(lat1) * Math.cos(lat2)

  return 2 * R * Math.asin(Math.sqrt(h))
}

function getNeighbors(points: GeoPoint[], index: number, epsKm: number): number[] {
  const neighbors: number[] = []

  for (let i = 0; i < points.length; i += 1) {
    if (haversineKm(points[index], points[i]) <= epsKm) {
      neighbors.push(i)
    }
  }

  return neighbors
}

// Returns cluster labels by index. -1 means noise.
function runDbscan(points: GeoPoint[], epsKm: number, minPts: number): number[] {
  const UNVISITED = -99
  const NOISE = -1
  const labels = new Array(points.length).fill(UNVISITED)
  let clusterId = 0

  for (let i = 0; i < points.length; i += 1) {
    if (labels[i] !== UNVISITED) {
      continue
    }

    const neighbors = getNeighbors(points, i, epsKm)

    if (neighbors.length < minPts) {
      labels[i] = NOISE
      continue
    }

    labels[i] = clusterId
    const seeds = neighbors.filter((neighborIdx) => neighborIdx !== i)

    while (seeds.length > 0) {
      const current = seeds.shift()
      if (current === undefined) {
        continue
      }

      if (labels[current] === NOISE) {
        labels[current] = clusterId
      }

      if (labels[current] !== UNVISITED) {
        continue
      }

      labels[current] = clusterId
      const currentNeighbors = getNeighbors(points, current, epsKm)

      if (currentNeighbors.length >= minPts) {
        currentNeighbors.forEach((neighborIdx) => {
          if (!seeds.includes(neighborIdx)) {
            seeds.push(neighborIdx)
          }
        })
      }
    }

    clusterId += 1
  }

  return labels
}

function severityStyle(band: SeverityBand): {
  stroke: string
  fill: string
  radius: number
} {
  if (band === 'escalation') {
    return { stroke: '#ef4444', fill: '#ef4444', radius: 11 }
  }

  if (band === 'claim') {
    return { stroke: '#f59e0b', fill: '#f59e0b', radius: 9 }
  }

  return { stroke: '#22c55e', fill: '#22c55e', radius: 8 }
}

function renderTriggerLabel(trigger: TriggerRow): string {
  const observed = toNumber(trigger.observed_value)
  const observedText = observed === null ? 'n/a' : observed.toString()

  return `${trigger.trigger_code.replaceAll('_', ' ')} (${observedText})`
}

export default function ZoneRiskMap() {
  const supabase = createClient()
  const mapContainerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<LeafletMap | null>(null)
  const layerGroupRef = useRef<LayerGroup | null>(null)
  const leafletRef = useRef<LeafletModule | null>(null)

  const [zones, setZones] = useState<ZoneRow[]>([])
  const [activeTriggers, setActiveTriggers] = useState<TriggerRow[]>([])
  const [suspiciousClaims, setSuspiciousClaims] = useState<ClaimRow[]>([])
  const [clusterStats, setClusterStats] = useState<ClusterStats>({
    clusters: 0,
    clusteredClaims: 0,
    noiseClaims: 0,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const suspiciousPoints = useMemo(() => {
    return suspiciousClaims
      .map((claim) => {
        const lat = toNumber(claim.stated_lat)
        const lng = toNumber(claim.stated_lng)

        if (lat === null || lng === null) {
          return null
        }

        return {
          id: claim.id,
          status: claim.claim_status,
          lat,
          lng,
          claimedAt: claim.claimed_at,
        }
      })
      .filter((point): point is { id: string; status: string; lat: number; lng: number; claimedAt: string } => point !== null)
  }, [suspiciousClaims])

  const loadMapData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()

      const [zonesResult, triggersResult, claimsResult] = await Promise.all([
        supabase
          .from('zones')
          .select('id, city, zone_name, center_lat, center_lng')
          .order('city')
          .order('zone_name'),
        supabase
          .from('trigger_events')
          .select('id, zone_id, city, trigger_family, trigger_code, observed_value, severity_band, started_at')
          .is('ended_at', null)
          .order('started_at', { ascending: false })
          .limit(100),
        supabase
          .from('manual_claims')
          .select('id, claim_status, stated_lat, stated_lng, claimed_at')
          .in('claim_status', Array.from(SUSPICIOUS_STATES))
          .gte('claimed_at', since)
          .not('stated_lat', 'is', null)
          .not('stated_lng', 'is', null)
          .order('claimed_at', { ascending: false })
          .limit(400),
      ])

      if (zonesResult.error) {
        throw zonesResult.error
      }
      if (triggersResult.error) {
        throw triggersResult.error
      }
      if (claimsResult.error) {
        throw claimsResult.error
      }

      setZones(zonesResult.data || [])
      setActiveTriggers((triggersResult.data || []) as TriggerRow[])
      setSuspiciousClaims((claimsResult.data || []) as ClaimRow[])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load map data'
      setError(message)
    }

    setLoading(false)
  }, [supabase])

  useEffect(() => {
    loadMapData()
  }, [loadMapData])

  useEffect(() => {
    const intervalId = setInterval(() => {
      loadMapData()
    }, 60_000)

    return () => clearInterval(intervalId)
  }, [loadMapData])

  useEffect(() => {
    let isMounted = true

    const initializeMap = async () => {
      if (!mapContainerRef.current || mapRef.current) {
        return
      }

      const L = await import('leaflet')
      if (!isMounted || !mapContainerRef.current) {
        return
      }

      leafletRef.current = L
      const map = L.map(mapContainerRef.current, {
        zoomControl: true,
        preferCanvas: true,
      }).setView(INDIA_CENTER, 5)

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
      }).addTo(map)

      mapRef.current = map
      layerGroupRef.current = L.layerGroup().addTo(map)
    }

    initializeMap()

    return () => {
      isMounted = false
      mapRef.current?.remove()
      mapRef.current = null
      layerGroupRef.current = null
      leafletRef.current = null
    }
  }, [])

  useEffect(() => {
    const L = leafletRef.current
    const map = mapRef.current
    const layerGroup = layerGroupRef.current

    if (!L || !map || !layerGroup) {
      return
    }

    layerGroup.clearLayers()

    const plottedPoints: [number, number][] = []
    const zoneCenterById = new Map<string, { zoneName: string; city: string; lat: number; lng: number }>()

    zones.forEach((zone) => {
      const lat = toNumber(zone.center_lat)
      const lng = toNumber(zone.center_lng)

      if (lat === null || lng === null) {
        return
      }

      zoneCenterById.set(zone.id, {
        zoneName: zone.zone_name,
        city: zone.city,
        lat,
        lng,
      })

      const zoneCircle = L.circle([lat, lng], {
        radius: 700,
        color: '#60a5fa',
        fillColor: '#3b82f6',
        fillOpacity: 0.06,
        weight: 1.5,
      })

      zoneCircle.bindTooltip(`${zone.city} / ${zone.zone_name}`, {
        direction: 'top',
        opacity: 0.95,
      })

      zoneCircle.addTo(layerGroup)
      plottedPoints.push([lat, lng])
    })

    activeTriggers.forEach((trigger) => {
      const zoneCenter = trigger.zone_id ? zoneCenterById.get(trigger.zone_id) : undefined
      if (!zoneCenter) {
        return
      }

      const style = severityStyle(trigger.severity_band)
      const marker = L.circleMarker([zoneCenter.lat, zoneCenter.lng], {
        radius: style.radius,
        color: style.stroke,
        fillColor: style.fill,
        fillOpacity: 0.45,
        weight: 2,
      })

      marker.bindPopup(
        `<strong>${zoneCenter.city} / ${zoneCenter.zoneName}</strong><br/>` +
          `${renderTriggerLabel(trigger)}<br/>` +
          `Band: ${trigger.severity_band}<br/>` +
          `Started: ${new Date(trigger.started_at).toLocaleString('en-IN', {
            dateStyle: 'short',
            timeStyle: 'short',
          })}`
      )

      marker.addTo(layerGroup)
      plottedPoints.push([zoneCenter.lat, zoneCenter.lng])
    })

    const labels = runDbscan(suspiciousPoints, DBSCAN_EPSILON_KM, DBSCAN_MIN_POINTS)
    const clusters = new Map<number, typeof suspiciousPoints>()

    labels.forEach((label, idx) => {
      if (label < 0) {
        return
      }

      const list = clusters.get(label)
      if (list) {
        list.push(suspiciousPoints[idx])
      } else {
        clusters.set(label, [suspiciousPoints[idx]])
      }
    })

    clusters.forEach((claims, clusterId) => {
      const centroid = claims.reduce(
        (acc, claim) => {
          return { lat: acc.lat + claim.lat, lng: acc.lng + claim.lng }
        },
        { lat: 0, lng: 0 }
      )

      const center = {
        lat: centroid.lat / claims.length,
        lng: centroid.lng / claims.length,
      }

      const maxDistanceKm = claims.reduce((maxSoFar, claim) => {
        const dist = haversineKm(center, claim)
        return Math.max(maxSoFar, dist)
      }, 0)

      const radiusMeters = Math.max(700, Math.ceil(maxDistanceKm * 1000) + 180)

      const clusterCircle = L.circle([center.lat, center.lng], {
        radius: radiusMeters,
        color: '#ef4444',
        fillColor: '#ef4444',
        fillOpacity: 0.12,
        weight: 2,
        dashArray: '6 4',
      })

      clusterCircle.bindPopup(
        `<strong>DBSCAN Cluster #${clusterId + 1}</strong><br/>` +
          `Suspicious claims: ${claims.length}<br/>` +
          `Radius: ${Math.round(radiusMeters)} m`
      )

      clusterCircle.addTo(layerGroup)
      plottedPoints.push([center.lat, center.lng])

      claims.forEach((claim) => {
        const claimPoint = L.circleMarker([claim.lat, claim.lng], {
          radius: 5,
          color: '#b91c1c',
          fillColor: '#f87171',
          fillOpacity: 0.75,
          weight: 1,
        })

        claimPoint.bindTooltip(
          `Claim ${claim.id.slice(0, 8)} | ${claim.status}`,
          { direction: 'top' }
        )

        claimPoint.addTo(layerGroup)
        plottedPoints.push([claim.lat, claim.lng])
      })
    })

    const noiseClaims = labels.filter((label) => label < 0).length
    const clusteredClaims = labels.filter((label) => label >= 0).length
    setClusterStats({
      clusters: clusters.size,
      clusteredClaims,
      noiseClaims,
    })

    if (plottedPoints.length > 0) {
      map.fitBounds(L.latLngBounds(plottedPoints), {
        padding: [24, 24],
        maxZoom: 12,
      })
    } else {
      map.setView(INDIA_CENTER, 5)
    }
  }, [zones, activeTriggers, suspiciousPoints])

  return (
    <section className="card p-6 section-enter">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2
            className="text-base font-semibold flex items-center gap-2"
            style={{ color: 'var(--text-primary)' }}
          >
            <Layers3 size={18} style={{ color: 'var(--info)' }} /> Zone Risk Map
          </h2>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
            Live trigger heat, operational zone centers, and DBSCAN suspicious-claim clusters.
          </p>
        </div>

        <button
          type="button"
          onClick={loadMapData}
          className="btn-secondary text-xs px-3 py-2 flex items-center gap-2"
          disabled={loading}
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4 text-xs">
        <div className="card p-3">
          <span style={{ color: 'var(--text-tertiary)' }}>Zones</span>
          <p className="text-sm font-semibold mt-1" style={{ color: 'var(--text-primary)' }}>
            {zones.length}
          </p>
        </div>
        <div className="card p-3">
          <span style={{ color: 'var(--text-tertiary)' }}>Active Triggers</span>
          <p className="text-sm font-semibold mt-1" style={{ color: 'var(--warning)' }}>
            {activeTriggers.length}
          </p>
        </div>
        <div className="card p-3">
          <span style={{ color: 'var(--text-tertiary)' }}>Fraud Clusters</span>
          <p className="text-sm font-semibold mt-1" style={{ color: 'var(--danger)' }}>
            {clusterStats.clusters}
          </p>
        </div>
        <div className="card p-3">
          <span style={{ color: 'var(--text-tertiary)' }}>Clustered Claims</span>
          <p className="text-sm font-semibold mt-1" style={{ color: 'var(--danger)' }}>
            {clusterStats.clusteredClaims}
          </p>
        </div>
        <div className="card p-3">
          <span style={{ color: 'var(--text-tertiary)' }}>Noise Claims</span>
          <p className="text-sm font-semibold mt-1" style={{ color: 'var(--text-primary)' }}>
            {clusterStats.noiseClaims}
          </p>
        </div>
      </div>

      {error && (
        <div
          className="mb-3 p-3 rounded-lg text-sm"
          style={{
            background: 'var(--danger-muted)',
            border: '1px solid var(--danger)',
            color: 'var(--danger)',
          }}
        >
          {error}
        </div>
      )}

      <div className="zone-risk-map-frame" style={{ border: '1px solid var(--border-primary)', borderRadius: '12px', overflow: 'hidden', background: 'var(--bg-tertiary)' }}>
        <div ref={mapContainerRef} className="zone-risk-map" style={{ width: '100%', height: '430px' }} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        <span className="flex items-center gap-1">
          <MapPin size={12} style={{ color: '#3b82f6' }} /> Zone centers
        </span>
        <span className="flex items-center gap-1">
          <Radar size={12} style={{ color: '#f59e0b' }} /> Active trigger markers
        </span>
        <span className="flex items-center gap-1">
          <AlertTriangle size={12} style={{ color: '#ef4444' }} /> DBSCAN fraud clusters
        </span>
      </div>
    </section>
  )
}

