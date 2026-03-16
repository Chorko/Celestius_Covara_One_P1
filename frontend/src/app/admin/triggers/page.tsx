"use client"

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import {
  Activity, PlayCircle, AlertTriangle, Zap, Radio,
  MapPin, Clock, Globe, Cpu
} from 'lucide-react'

export default function AdminTriggers() {
  const supabase = createClient()
  const [triggers, setTriggers] = useState<any[]>([])

  // Simulator State
  const [isSimulating, setIsSimulating] = useState(false)
  const [simForm, setSimForm] = useState({
    city: 'Mumbai',
    zone_id: '',
    trigger_family: 'rain',
    trigger_code: 'RAIN_EXTREME',
    observed_value: 120,
    severity_band: 'escalation',
  })

  useEffect(() => {
    loadTriggers()
  }, [])

  const loadTriggers = async () => {
    const { data: session } = await supabase.auth.getSession()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/triggers/live`, {
      headers: { Authorization: `Bearer ${session.session?.access_token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setTriggers(data.active_triggers || [])
      // Auto-set the first zone ID for simulator if available
      if (data.active_triggers && data.active_triggers.length > 0 && !simForm.zone_id) {
        setSimForm((s) => ({ ...s, zone_id: data.active_triggers[0].zone_id }))
      }
    }
  }

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSimulating(true)
    const { data: session } = await supabase.auth.getSession()

    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/triggers/simulate`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.session?.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(simForm),
    })

    setIsSimulating(false)
    await loadTriggers()
  }

  const severityBadge = (band: string) => {
    switch (band) {
      case 'claim':
        return 'badge-amber'
      case 'escalation':
        return 'badge-red'
      default:
        return 'badge-blue'
    }
  }

  const severityIcon = (band: string) => {
    switch (band) {
      case 'escalation':
        return <AlertTriangle size={12} />
      case 'claim':
        return <Zap size={12} />
      default:
        return <Radio size={12} />
    }
  }

  const familyUnit = (family: string) => {
    switch (family) {
      case 'rain':
        return 'mm/24h'
      case 'aqi':
        return 'AQI'
      case 'heat':
        return 'deg C'
      case 'traffic':
        return '% delay'
      case 'outage':
        return 'min'
      case 'demand':
        return '% drop'
      default:
        return ''
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto gradient-mesh-admin min-h-screen">
      {/* Header */}
      <div className="mb-8 animate-fade-in-up">
        <div className="flex items-center gap-3 mb-2">
          <Activity size={28} className="text-amber-400" />
          <h1 className="text-3xl font-bold">Trigger Engine</h1>
        </div>
        <p className="text-neutral-400">
          Live parametric event feed and manual event injection sandbox.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Simulator */}
        <section className="glass-card p-6 h-fit animate-fade-in-up delay-100">
          <h2 className="text-lg font-semibold mb-5 flex items-center gap-2">
            <PlayCircle size={20} className="text-amber-400" /> Inject Mock Trigger
          </h2>

          <form onSubmit={handleSimulate} className="space-y-4">
            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                Trigger Family
              </label>
              <select
                value={simForm.trigger_family}
                onChange={(e) =>
                  setSimForm({ ...simForm, trigger_family: e.target.value })
                }
                className="glass-select"
              >
                <option value="rain">Rain</option>
                <option value="aqi">AQI</option>
                <option value="heat">Heat</option>
                <option value="traffic">Traffic</option>
                <option value="outage">Outage</option>
                <option value="demand">Demand</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                Trigger Code
              </label>
              <input
                type="text"
                value={simForm.trigger_code}
                onChange={(e) =>
                  setSimForm({ ...simForm, trigger_code: e.target.value })
                }
                className="glass-input"
                placeholder="e.g. RAIN_EXTREME"
              />
            </div>

            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                Observed Value
              </label>
              <input
                type="number"
                value={simForm.observed_value}
                onChange={(e) =>
                  setSimForm({ ...simForm, observed_value: Number(e.target.value) })
                }
                className="glass-input"
              />
            </div>

            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                Severity Band
              </label>
              <select
                value={simForm.severity_band}
                onChange={(e) =>
                  setSimForm({ ...simForm, severity_band: e.target.value })
                }
                className="glass-select"
              >
                <option value="watch">Watch</option>
                <option value="claim">Claim</option>
                <option value="escalation">Escalation</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                  City
                </label>
                <input
                  type="text"
                  value={simForm.city}
                  onChange={(e) =>
                    setSimForm({ ...simForm, city: e.target.value })
                  }
                  className="glass-input"
                />
              </div>
              <div>
                <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1.5">
                  Zone ID
                </label>
                <input
                  type="text"
                  value={simForm.zone_id}
                  onChange={(e) =>
                    setSimForm({ ...simForm, zone_id: e.target.value })
                  }
                  className="glass-input"
                  placeholder="UUID"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSimulating}
              className="w-full mt-2 py-3 rounded-xl font-semibold text-sm transition-all bg-gradient-to-r from-amber-500 to-orange-500 text-black hover:from-amber-400 hover:to-orange-400 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isSimulating ? (
                <>
                  <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  Injecting...
                </>
              ) : (
                <>
                  <Zap size={16} /> Fire Mock Trigger
                </>
              )}
            </button>
          </form>
        </section>

        {/* Live Feed */}
        <section className="lg:col-span-2 animate-fade-in-up delay-200">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Activity size={20} className="text-emerald-400" /> Live Evaluator Feed
            </h2>
            <span className="badge badge-emerald">
              <Radio size={10} className="animate-pulse-glow" />
              {triggers.length} active
            </span>
          </div>

          <div className="space-y-3">
            {triggers.length === 0 ? (
              <div className="glass-card p-12 text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
                  <Radio size={28} className="text-neutral-600" />
                </div>
                <p className="text-neutral-500 font-medium">No active triggers</p>
                <p className="text-xs text-neutral-600 mt-1">
                  Use the simulator to inject a mock trigger event
                </p>
              </div>
            ) : (
              triggers.map((t) => (
                <div
                  key={t.id}
                  className="glass-card p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="flex-1 min-w-0">
                    {/* Top row: severity + code */}
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={`badge ${severityBadge(t.severity_band)}`}>
                        {severityIcon(t.severity_band)}
                        {t.severity_band}
                      </span>
                      <span className="text-sm font-semibold text-white">
                        {t.trigger_code.replaceAll('_', ' ')}
                      </span>
                      {t.source_type && (
                        <span
                          className={`badge ${
                            t.source_type === 'public_source'
                              ? 'badge-emerald'
                              : 'badge-purple'
                          }`}
                        >
                          {t.source_type === 'public_source' ? (
                            <Globe size={10} />
                          ) : (
                            <Cpu size={10} />
                          )}
                          {t.source_type === 'public_source'
                            ? 'Public Source'
                            : 'Internal'}
                        </span>
                      )}
                    </div>

                    {/* Location and threshold */}
                    <div className="flex items-center gap-4 text-xs text-neutral-500 flex-wrap">
                      <span className="flex items-center gap-1">
                        <MapPin size={12} />
                        {t.city}
                        {t.zones?.zone_name && ` / ${t.zones.zone_name}`}
                      </span>
                      <span className="flex items-center gap-1">
                        <AlertTriangle size={12} />
                        {t.official_threshold_label || `Threshold: ${t.product_threshold_value}`}
                      </span>
                    </div>

                    {/* Timestamps */}
                    <div className="flex items-center gap-4 text-[10px] text-neutral-600 mt-2 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Clock size={10} />
                        Start: {new Date(t.started_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                      </span>
                      {t.ended_at && (
                        <span>
                          End: {new Date(t.ended_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Observed value */}
                  <div className="text-right shrink-0">
                    <div className="text-2xl font-bold text-white">{t.observed_value}</div>
                    <div className="text-xs text-neutral-500">
                      {familyUnit(t.trigger_family)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
