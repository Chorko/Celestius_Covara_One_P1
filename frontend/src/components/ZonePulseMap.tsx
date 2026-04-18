"use client"

import { useEffect, useMemo, useRef } from 'react'

interface ZoneTriggerPoint {
  id: string
  trigger_code?: string
  severity_band?: string
  started_at?: string
  lat?: number | null
  lng?: number | null
  official_threshold_label?: string | null
}

interface ZonePulseMapProps {
  centerLat: number
  centerLng: number
  zoneName: string
  polygonGeoJson?: unknown
  triggers: ZoneTriggerPoint[]
}

function markerColor(severityBand?: string): string {
  if (severityBand === 'escalation') return '#ef4444'
  if (severityBand === 'claim') return '#f59e0b'
  return '#38bdf8'
}

function triggerCoordinates(
  trigger: ZoneTriggerPoint,
  index: number,
  centerLat: number,
  centerLng: number,
): [number, number] {
  if (typeof trigger.lat === 'number' && typeof trigger.lng === 'number') {
    return [trigger.lat, trigger.lng]
  }

  // Spread unknown trigger coordinates around the zone center for readability.
  const offsetLat = Math.sin((index + 1) * 1.7) * 0.0075
  const offsetLng = Math.cos((index + 1) * 1.7) * 0.0075
  return [centerLat + offsetLat, centerLng + offsetLng]
}

export default function ZonePulseMap({
  centerLat,
  centerLng,
  zoneName,
  polygonGeoJson,
  triggers,
}: ZonePulseMapProps) {
  const mapRef = useRef<HTMLDivElement | null>(null)

  const triggerKey = useMemo(
    () =>
      triggers
        .map((t) => `${t.id}:${t.severity_band || ''}:${t.started_at || ''}:${t.lat || ''}:${t.lng || ''}`)
        .join('|'),
    [triggers],
  )

  const polygonKey = useMemo(() => JSON.stringify(polygonGeoJson || null), [polygonGeoJson])

  useEffect(() => {
    let mounted = true
    let map: import('leaflet').Map | null = null

    const init = async () => {
      const L = await import('leaflet')
      if (!mounted || !mapRef.current) {
        return
      }

      map = L.map(mapRef.current, {
        zoomControl: true,
        attributionControl: true,
      }).setView([centerLat, centerLng], 12)
      const readyMap = map

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(readyMap)

      const zoneMarker = L.circleMarker([centerLat, centerLng], {
        radius: 9,
        color: '#22d3ee',
        weight: 2,
        fillColor: '#0e7490',
        fillOpacity: 0.9,
      }).addTo(readyMap)
      zoneMarker.bindPopup(`<strong>${zoneName}</strong><br/>Zone center`)

      let polygonLayer: import('leaflet').GeoJSON | null = null
      if (polygonGeoJson && typeof polygonGeoJson === 'object') {
        try {
          polygonLayer = L.geoJSON(polygonGeoJson as any, {
            style: {
              color: '#38bdf8',
              weight: 2,
              fillColor: '#38bdf8',
              fillOpacity: 0.12,
            },
          }).addTo(readyMap)
        } catch {
          polygonLayer = null
        }
      }

      triggers.forEach((trigger, index) => {
        const [lat, lng] = triggerCoordinates(trigger, index, centerLat, centerLng)
        const color = markerColor(trigger.severity_band)
        const label = (trigger.trigger_code || 'trigger').replaceAll('_', ' ')
        const started = trigger.started_at
          ? new Date(trigger.started_at).toLocaleString('en-IN', {
              day: 'numeric',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit',
            })
          : 'now'

        L.circleMarker([lat, lng], {
          radius: 7,
          color,
          weight: 2,
          fillColor: color,
          fillOpacity: 0.78,
        })
          .addTo(readyMap)
          .bindPopup(
            `<strong>${label}</strong><br/>Severity: ${(trigger.severity_band || 'watch').toUpperCase()}<br/>Started: ${started}`,
          )
      })

      if (polygonLayer) {
        readyMap.fitBounds(polygonLayer.getBounds().pad(0.14))
      }
    }

    void init()

    return () => {
      mounted = false
      if (map) {
        map.remove()
      }
    }
  }, [centerLat, centerLng, zoneName, polygonKey, triggerKey, triggers, polygonGeoJson])

  return (
    <div
      ref={mapRef}
      className="w-full rounded-xl"
      style={{ height: '320px', border: '1px solid var(--border-primary)' }}
    />
  )
}
