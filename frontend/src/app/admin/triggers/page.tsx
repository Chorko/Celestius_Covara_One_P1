"use client"

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { Activity, PlayCircle, AlertCircle } from 'lucide-react'

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
    severity_band: 'escalation'
  })

  useEffect(() => { loadTriggers() }, [])

  const loadTriggers = async () => {
    const { data: session } = await supabase.auth.getSession()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/triggers/live`, {
      headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
    })
    if (res.ok) {
      const data = await res.json()
      setTriggers(data.active_triggers || [])
      // Auto-set the first zone ID for simulator if available
      if (data.active_triggers && data.active_triggers.length > 0 && !simForm.zone_id) {
        setSimForm(s => ({ ...s, zone_id: data.active_triggers[0].zone_id }))
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
        'Authorization': `Bearer ${session.session?.access_token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(simForm)
    })
    
    setIsSimulating(false)
    await loadTriggers()
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      <div className="mb-8">
        <h1 className="text-3xl font-semibold mb-2 text-white">Trigger Engine</h1>
        <p className="text-slate-400">Live parametric event feed and manual event injection sandbox.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Simulator */}
        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-6 h-fit">
          <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
            <PlayCircle size={20} className="text-amber-500"/> Inject Mock Trigger
          </h2>
          <form onSubmit={handleSimulate} className="space-y-4">
            <div>
              <label className="text-xs text-slate-500 uppercase block mb-1">City</label>
              <input 
                type="text" value={simForm.city} onChange={e => setSimForm({...simForm, city: e.target.value})}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-sm text-white" 
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 uppercase block mb-1">Zone ID</label>
              <input 
                type="text" value={simForm.zone_id} onChange={e => setSimForm({...simForm, zone_id: e.target.value})}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-sm text-white" 
                placeholder="UUID" required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-500 uppercase block mb-1">Family</label>
                <select 
                  value={simForm.trigger_family} onChange={e => setSimForm({...simForm, trigger_family: e.target.value})}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-sm text-white"
                >
                  <option value="rain">Rain</option>
                  <option value="aqi">AQI</option>
                  <option value="heat">Heat</option>
                  <option value="traffic">Traffic</option>
                  <option value="outage">Outage</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-500 uppercase block mb-1">Code</label>
                <input 
                  type="text" value={simForm.trigger_code} onChange={e => setSimForm({...simForm, trigger_code: e.target.value})}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-sm text-white" 
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-500 uppercase block mb-1">Observed Val</label>
                <input 
                  type="number" value={simForm.observed_value} onChange={e => setSimForm({...simForm, observed_value: Number(e.target.value)})}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-sm text-white" 
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 uppercase block mb-1">Severity</label>
                <select 
                  value={simForm.severity_band} onChange={e => setSimForm({...simForm, severity_band: e.target.value})}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-sm text-white"
                >
                  <option value="watch">Watch</option>
                  <option value="claim">Claim</option>
                  <option value="escalation">Escalation</option>
                </select>
              </div>
            </div>
            <button 
              type="submit" disabled={isSimulating}
              className="w-full mt-4 bg-amber-500 hover:bg-amber-400 text-black font-semibold py-2 rounded-lg transition-colors"
            >
              {isSimulating ? 'Injecting...' : 'Fire Mock Trigger'}
            </button>
          </form>
        </section>

        {/* Live Feed */}
        <section className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
            <Activity size={20} className="text-emerald-500"/> Live Evaluator Feed
          </h2>
          
          <div className="space-y-3">
            {triggers.map(t => (
              <div key={t.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                      t.severity_band === 'claim' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/20' :
                      t.severity_band === 'escalation' ? 'bg-red-500/20 text-red-400 border border-red-500/20' :
                      'bg-blue-500/20 text-blue-400 border border-blue-500/20'
                    }`}>
                      {t.severity_band}
                    </span>
                    <span className="text-sm font-medium text-slate-200">{t.trigger_code.replace('_', ' ')}</span>
                  </div>
                  <p className="text-xs text-slate-400 flex items-center gap-1 mt-2">
                    <AlertTriangle size={12}/> {t.city} • {t.zones?.zone_name} • {t.official_threshold_label || t.product_threshold_value}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold text-white">{t.observed_value}</div>
                  <div className="text-xs text-slate-500">Value</div>
                </div>
              </div>
            ))}
          </div>
        </section>

      </div>
    </div>
  )
}
