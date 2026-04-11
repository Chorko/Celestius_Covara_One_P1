"use client"

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import { Activity, PlayCircle, AlertTriangle, Zap, Radio, MapPin, Clock, Globe, Cpu } from 'lucide-react'

interface Zone {
  id: string; city: string; zone_name: string; pincode?: string
}

interface TriggerEvent {
  id: string; city: string; zone_id?: string; trigger_family: string; trigger_code: string
  observed_value: number; severity_band: string; source_type?: string; started_at: string
  ended_at?: string; official_threshold_label?: string; product_threshold_value?: number
  zones?: { zone_name?: string }
}

export default function AdminTriggers() {
  const supabase = createClient()
  const [triggers, setTriggers] = useState<TriggerEvent[]>([])
  const [historyTriggers, setHistoryTriggers] = useState<TriggerEvent[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [showHistory, setShowHistory] = useState(true)
  const [simResult, setSimResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [isSimulating, setIsSimulating] = useState(false)
  const [simForm, setSimForm] = useState({ city: 'Mumbai', zone_id: '', trigger_family: 'rain', trigger_code: 'RAIN_EXTREME', observed_value: 120, severity_band: 'escalation' })

  const loadTriggers = useCallback(async () => {
    try {
      const { data } = await supabase.from('trigger_events').select('*, zones(zone_name)').is('ended_at', null).order('started_at', { ascending: false })
      setTriggers(data || [])
      if (data && data.length > 0) setSimForm(s => s.zone_id ? s : { ...s, zone_id: data[0].zone_id || '' })
    } catch (e) { console.error('Could not load triggers', e) }
  }, [supabase])

  const loadHistoryTriggers = useCallback(async () => {
    try {
      const { data } = await supabase.from('trigger_events').select('*, zones(zone_name)').not('ended_at', 'is', null).order('started_at', { ascending: false }).limit(20)
      setHistoryTriggers(data || [])
    } catch (e) { console.error('Could not load history', e) }
  }, [supabase])

  const loadZones = useCallback(async () => {
    try {
      const { data } = await supabase.from('zones').select('id, city, zone_name, pincode').order('city')
      const zoneList = data || []
      setZones(zoneList)
      // Auto-set the first zone as default
      if (zoneList.length > 0 && !simForm.zone_id) {
        setSimForm(s => ({ ...s, zone_id: zoneList[0].id, city: zoneList[0].city }))
      }
    } catch (e) { console.error('Could not load zones', e) }
  }, [supabase, simForm.zone_id])

  useEffect(() => {
    queueMicrotask(() => {
      void loadTriggers()
      void loadHistoryTriggers()
      void loadZones()
    })
  }, [loadTriggers, loadHistoryTriggers, loadZones])

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault(); setIsSimulating(true); setSimResult(null)
    try {
      const { error } = await supabase.from('trigger_events').insert({ city: simForm.city, zone_id: simForm.zone_id || null, trigger_family: simForm.trigger_family, trigger_code: simForm.trigger_code, observed_value: Number(simForm.observed_value), severity_band: simForm.severity_band, source_type: 'mock', started_at: new Date().toISOString() })
      setSimResult(error ? { ok: false, msg: error.message } : { ok: true, msg: 'Trigger injected successfully.' })
    } catch (e: unknown) { setSimResult({ ok: false, msg: e instanceof Error ? e.message : 'Inject failed' }) }
    setIsSimulating(false); await loadTriggers()
  }

  const severityBadge = (b: string) => b === 'claim' ? 'badge-warning' : b === 'escalation' ? 'badge-danger' : 'badge-info'
  const severityIcon = (b: string) => b === 'escalation' ? <AlertTriangle size={12} /> : b === 'claim' ? <Zap size={12} /> : <Radio size={12} />
  const familyUnit = (f: string) => ({ rain: 'mm/24h', aqi: 'AQI', heat: 'deg C', traffic: '% delay', outage: 'min', demand: '% drop' }[f] || '')

  const TriggerCard = ({ t, faded = false }: { t: TriggerEvent; faded?: boolean }) => (
    <div className="card p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4" style={{ opacity: faded ? 0.7 : 1 }}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className={`badge ${severityBadge(t.severity_band)}`}>{severityIcon(t.severity_band)} {t.severity_band}</span>
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{t.trigger_code.replaceAll('_', ' ')}</span>
          {t.source_type && (
            <span className={`badge ${t.source_type === 'public_source' ? 'badge-success' : 'badge-purple'}`}>
              {t.source_type === 'public_source' ? <><Globe size={10} /> Public</> : <><Cpu size={10} /> Internal</>}
            </span>
          )}
          {t.ended_at && <span className="badge-neutral">Ended</span>}
        </div>
        <div className="flex items-center gap-4 text-xs flex-wrap" style={{ color: 'var(--text-tertiary)' }}>
          <span className="flex items-center gap-1"><MapPin size={12} /> {t.city}{t.zones?.zone_name && ` / ${t.zones.zone_name}`}</span>
          <span className="flex items-center gap-1"><AlertTriangle size={12} /> {t.official_threshold_label || `Threshold: ${t.product_threshold_value}`}</span>
        </div>
        <div className="flex items-center gap-4 text-[10px] mt-2 flex-wrap" style={{ color: 'var(--text-tertiary)' }}>
          <span className="flex items-center gap-1"><Clock size={10} /> Start: {new Date(t.started_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}</span>
          {t.ended_at && <span>End: {new Date(t.ended_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}</span>}
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{t.observed_value}</div>
        <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{familyUnit(t.trigger_family)}</div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen page-mesh">
      <div className="p-6 md:p-8 pb-28 max-w-7xl mx-auto space-y-8">
        <section className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 rounded-lg" style={{ background: 'var(--warning-muted)' }}>
              <Activity size={24} style={{ color: 'var(--warning)' }} />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>Trigger Engine</h1>
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Live parametric event feed and manual event injection sandbox.</p>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Simulator — sticky so it stays visible while scrolling history */}
          <section className="card p-6 h-fit animate-fade-in-up delay-100 lg:sticky lg:top-4">
            <h2 className="text-base font-semibold mb-5 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <PlayCircle size={18} style={{ color: 'var(--warning)' }} /> Inject Mock Trigger
            </h2>
            <form onSubmit={handleSimulate} className="space-y-4">
              {[
                { label: 'Trigger Family', type: 'select', value: simForm.trigger_family, key: 'trigger_family', options: [['rain','Rain'],['aqi','AQI'],['heat','Heat'],['traffic','Traffic'],['outage','Outage'],['demand','Demand']] },
                { label: 'Trigger Code', type: 'text', value: simForm.trigger_code, key: 'trigger_code', placeholder: 'e.g. RAIN_EXTREME' },
                { label: 'Observed Value', type: 'number', value: simForm.observed_value, key: 'observed_value' },
                { label: 'Severity Band', type: 'select', value: simForm.severity_band, key: 'severity_band', options: [['watch','Watch'],['claim','Claim'],['escalation','Escalation']] },
              ].map(field => (
                <div key={field.key}>
                  <label className="text-xs uppercase tracking-wider block mb-1.5 font-medium" style={{ color: 'var(--text-tertiary)' }}>{field.label}</label>
                  {field.type === 'select' ? (
                    <select value={field.value as string} onChange={e => setSimForm({ ...simForm, [field.key]: e.target.value })} className="input-field-select">
                      {field.options!.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  ) : (
                    <input type={field.type} value={field.value} onChange={e => setSimForm({ ...simForm, [field.key]: field.type === 'number' ? Number(e.target.value) : e.target.value })} className="input-field" placeholder={field.placeholder} />
                  )}
                </div>
              ))}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider block mb-1.5 font-medium" style={{ color: 'var(--text-tertiary)' }}>City</label>
                  <input type="text" value={simForm.city} onChange={e => setSimForm({ ...simForm, city: e.target.value })} className="input-field" />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider block mb-1.5 font-medium" style={{ color: 'var(--text-tertiary)' }}>Zone</label>
                  <select
                    value={simForm.zone_id}
                    onChange={e => {
                      const selected = zones.find(z => z.id === e.target.value)
                      setSimForm({ ...simForm, zone_id: e.target.value, city: selected?.city || simForm.city })
                    }}
                    className="input-field-select"
                    required
                  >
                    <option value="">Select zone…</option>
                    {zones.map(z => (
                      <option key={z.id} value={z.id}>
                        {z.city} / {z.zone_name}{z.pincode ? ` (${z.pincode})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <button type="submit" disabled={isSimulating} className="btn-primary w-full py-3 text-sm font-semibold flex items-center justify-center gap-2"
                style={{ background: 'var(--warning)', color: 'var(--text-inverse)' }}>
                {isSimulating ? (<><div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'transparent', borderTopColor: 'var(--text-inverse)' }} />Injecting...</>) : (<><Zap size={16} />Fire Mock Trigger</>)}
              </button>
              {simResult && (
                <div className="p-3 rounded-lg text-sm mt-1" style={{ background: simResult.ok ? 'var(--success-muted)' : 'var(--danger-muted)', border: `1px solid ${simResult.ok ? 'var(--success)' : 'var(--danger)'}`, color: simResult.ok ? 'var(--success)' : 'var(--danger)' }}>
                  {simResult.msg}
                </div>
              )}
            </form>
          </section>

          {/* Live Feed */}
          <section className="lg:col-span-2 animate-fade-in-up delay-200 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Activity size={18} style={{ color: 'var(--success)' }} /> Live Evaluator Feed
              </h2>
              <div className="flex items-center gap-3">
                <button onClick={() => setShowHistory(!showHistory)} className="text-xs px-3 py-1.5 rounded-lg font-medium transition-all"
                  style={{ background: showHistory ? 'var(--warning-muted)' : 'var(--bg-tertiary)', border: `1px solid ${showHistory ? 'var(--warning)' : 'var(--border-primary)'}`, color: showHistory ? 'var(--warning)' : 'var(--text-tertiary)' }}>
                  <Clock size={10} className="inline mr-1" /> {showHistory ? 'Hide History' : 'Show History'}
                </button>
                <span className="badge-success"><Radio size={10} /> {triggers.length} active</span>
              </div>
            </div>
            <div className="space-y-3">
              {triggers.length === 0 ? (
                <div className="card p-12 text-center">
                  <Radio size={28} className="mx-auto mb-4" style={{ color: 'var(--text-tertiary)' }} />
                  <p className="font-medium" style={{ color: 'var(--text-secondary)' }}>No active triggers</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Use the simulator to inject a mock trigger event</p>
                </div>
              ) : triggers.map(t => <TriggerCard key={t.id} t={t} />)}
            </div>
            {showHistory && historyTriggers.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}>
                    <Clock size={14} /> Recent History
                    <span className="badge-neutral ml-1">{historyTriggers.length} ended</span>
                  </h3>
                  <button
                    onClick={() => setShowHistory(false)}
                    className="text-xs px-2 py-1 rounded-lg"
                    style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)', border: '1px solid var(--border-primary)' }}
                  >
                    Collapse
                  </button>
                </div>
                <div className="space-y-3 overflow-y-auto max-h-[400px] pr-1">
                  {historyTriggers.map(t => <TriggerCard key={t.id} t={t} faded />)}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
