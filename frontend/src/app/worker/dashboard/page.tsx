"use client"

import { useEffect, useState } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { ShieldCheck, CloudRain, AlertTriangle, IndianRupee, Activity, Navigation2 } from 'lucide-react'

export default function WorkerDashboard() {
  const { user, profile } = useUserStore()
  const supabase = createClient()
  
  const [workerDetails, setWorkerDetails] = useState<any>(null)
  const [stats, setStats] = useState<any[]>([])
  const [activeTriggers, setActiveTriggers] = useState<any[]>([])
  const [policyQuote, setPolicyQuote] = useState<any>(null)
  const [activating, setActivating] = useState(false)
  const [activationMsg, setActivationMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!profile) return
    loadDashboardData()
  }, [profile])

  const loadDashboardData = async () => {
    // Fetch Worker specifics
    const { data: wData } = await supabase
      .from('worker_profiles')
      .select('*, zones(zone_name)')
      .eq('profile_id', profile.id)
      .single()
    setWorkerDetails(wData)

    // Fetch Daily Stats (synthetic history via backend API)
    try {
      const { data: session } = await supabase.auth.getSession()
      const token = session.session?.access_token
      
      const statsRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/workers/me/stats`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setStats(statsData.stats || [])
      }
    } catch(e) { console.error("Could not fetch dashboard stats", e) }

    // Fetch live triggers using our backend route pattern if we want, or supabase direct for prep
    // Direct supabase fetch of recently active triggers in their zone
    if (wData?.preferred_zone_id) {
       const { data: tData } = await supabase
         .from('trigger_events')
         .select('*')
         .eq('zone_id', wData.preferred_zone_id)
         .order('started_at', { ascending: false })
         .limit(3)
       setActiveTriggers(tData || [])
    }

    // Call backend API for quote
    try {
      const { data: session } = await supabase.auth.getSession()
      const token = session.session?.access_token
      
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/policies/quote`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        setPolicyQuote(await res.json())
      }
    } catch(e) { console.error("Could not fetch policy quote", e) }
  }

  const activatePolicy = async () => {
    setActivating(true)
    try {
      const { data: session } = await supabase.auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/policies/activate`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
      })
      if (res.ok) {
        setActivationMsg("Coverage Active!")
      }
    } catch(e) { console.error("Activation failed", e) }
    setActivating(false)
  }

  if (!workerDetails) return <div className="p-8">Loading dashboard...</div>

  return (
    <div className="p-8 pb-20 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* Header Profile Summary */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-3xl font-semibold mb-2">Welcome, {profile.full_name}</h1>
          <div className="flex flex-wrap items-center gap-4 text-sm text-neutral-400">
            <span className="flex items-center gap-1"><Navigation2 size={16}/> {workerDetails.city} • {workerDetails.zones?.zone_name}</span>
            <span className="bg-neutral-800 px-2 py-1 rounded text-neutral-300 border border-neutral-700">{workerDetails.platform_name} • {workerDetails.vehicle_type}</span>
            <span className="flex items-center gap-1"><Activity size={16}/> Trust Score: {workerDetails.trust_score}</span>
          </div>
        </div>
        
        {policyQuote && (
          <div className="bg-gradient-to-r from-emerald-500/20 to-emerald-900/20 border border-emerald-500/30 rounded-xl p-5 md:w-80 shadow-lg">
            <div className="flex justify-between items-start mb-2">
              <span className="text-emerald-400 font-medium flex items-center gap-2">
                <ShieldCheck size={18} /> Coverage Quote
              </span>
            </div>
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-2xl font-bold text-white">₹{policyQuote.max_payout_cap_inr}</span>
              <span className="text-sm text-emerald-500/80">max payout</span>
            </div>
            <p className="text-sm text-neutral-400 mb-4">Premium: ₹{policyQuote.weekly_premium_inr} / week</p>
            {activationMsg ? (
              <div className="w-full py-2 bg-emerald-500/20 text-emerald-400 text-center font-semibold rounded-lg flex items-center justify-center gap-2">
                <ShieldCheck size={18}/> {activationMsg}
              </div>
            ) : (
              <button 
                onClick={activatePolicy}
                disabled={activating}
                className="w-full py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold rounded-lg transition-colors disabled:opacity-50"
              >
                {activating ? "Activating..." : "Activate Coverage"}
              </button>
            )}
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Main Chart */}
        <section className="lg:col-span-2 bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-md">
          <div className="mb-6">
            <h2 className="text-lg font-medium flex items-center gap-2"><IndianRupee size={20} className="text-neutral-400"/> 14-Day Earnings History</h2>
            <p className="text-sm text-neutral-500">Synthetic trajectory from platform stats</p>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={stats}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                <XAxis dataKey="stat_date" stroke="#525252" tick={{fontSize: 12}} tickFormatter={(v) => v.split('-')[2]} />
                <YAxis stroke="#525252" tick={{fontSize: 12}} tickFormatter={(v) => `₹${v}`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#171717', borderColor: '#262626', color: '#fff' }}
                  itemStyle={{ color: '#10b981' }}
                />
                <Line type="monotone" dataKey="gross_earnings_inr" name="Gross (INR)" stroke="#10b981" strokeWidth={3} dot={{ r: 4, fill: "#10b981", strokeWidth: 0 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Live Triggers Feed */}
        <section className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-md flex flex-col">
          <div className="mb-6">
            <h2 className="text-lg font-medium flex items-center gap-2"><CloudRain size={20} className="text-blue-400"/> Zone Trigger Alerts</h2>
            <p className="text-sm text-neutral-500">Recent risks affecting your zone</p>
          </div>
          
          <div className="flex-1 space-y-4 overflow-auto">
            {activeTriggers.length === 0 ? (
              <div className="text-sm text-neutral-500 p-4 border border-dashed border-neutral-800 rounded-xl text-center">
                No active triggers right now.
              </div>
            ) : (
              activeTriggers.map((t) => (
                <div key={t.id} className="p-4 rounded-xl border border-neutral-800 bg-neutral-950/50">
                  <div className="flex justify-between items-start mb-2">
                    <span className={`text-xs font-semibold px-2 py-1 rounded ${
                      t.severity_band === 'claim' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/20' :
                      t.severity_band === 'escalation' ? 'bg-red-500/20 text-red-400 border border-red-500/20' :
                      'bg-blue-500/20 text-blue-400 border border-blue-500/20'
                    } uppercase tracking-wider`}>
                      {t.severity_band}
                    </span>
                    <span className="text-xs text-neutral-500">
                      {new Date(t.started_at).toLocaleDateString()}
                    </span>
                  </div>
                  <h3 className="font-medium text-sm text-neutral-200">{t.trigger_code.replace('_', ' ')}</h3>
                  <p className="text-xs text-neutral-400 mt-1 flex items-center gap-1">
                    <AlertTriangle size={12}/> {t.official_threshold_label || t.product_threshold_value}
                  </p>
                </div>
              ))
            )}
          </div>
        </section>

      </div>
    </div>
  )
}
