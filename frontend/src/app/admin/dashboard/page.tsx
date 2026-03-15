"use client"

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { Users, AlertTriangle, CheckCircle, IndianRupee } from 'lucide-react'

export default function AdminDashboard() {
  const supabase = createClient()
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    loadAnalytics()
  }, [])

  const loadAnalytics = async () => {
    try {
      const { data: session } = await supabase.auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/analytics/summary`, {
        headers: { 'Authorization': `Bearer ${session.session?.access_token}` }
      })
      if (res.ok) {
        setData(await res.json())
      }
    } catch (e) { console.error("Could not load analytics", e) }
  }

  if (!data) return <div className="p-8">Loading analytics...</div>

  const { metrics, charts } = data
  const triggerMixData = Object.entries(charts.trigger_mix || {}).map(([name, value]) => ({ name: name.toUpperCase(), value }))
  const COLORS = ['#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#6366f1', '#a855f7']

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      <div className="mb-8">
        <h1 className="text-3xl font-semibold mb-2 text-white">Platform Overview</h1>
        <p className="text-slate-400">Real-time parametric insurance metrics across all operational zones.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-3 text-slate-400 mb-4">
            <Users size={20} /> <span className="font-medium">Covered Workers</span>
          </div>
          <div className="text-3xl font-bold text-white">{metrics.active_workers}</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-3 text-slate-400 mb-4">
            <AlertTriangle size={20} className="text-yellow-500" /> <span className="font-medium">Pending Claims</span>
          </div>
          <div className="text-3xl font-bold text-white">{metrics.pending_claims}</div>
          <p className="text-xs text-slate-500 mt-2">Requires manual review</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-3 text-slate-400 mb-4">
            <CheckCircle size={20} className="text-emerald-500" /> <span className="font-medium">Approved Claims</span>
          </div>
          <div className="text-3xl font-bold text-white">{metrics.approved_claims}</div>
          <p className="text-xs text-slate-500 mt-2">Out of {metrics.total_claims} total</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-3 text-slate-400 mb-4">
            <IndianRupee size={20} className="text-blue-500" /> <span className="font-medium">Platform Payouts</span>
          </div>
          <div className="text-3xl font-bold text-white">₹{metrics.total_recommended_payout_inr}</div>
          <p className="text-xs text-slate-500 mt-2">Expected baseline: ₹{metrics.total_expected_payout_inr}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Trigger Distribution Chart */}
        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="mb-6">
            <h2 className="text-lg font-medium text-white">Trigger Event Mix</h2>
            <p className="text-sm text-slate-500">Distribution of historical disruptions by category</p>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={triggerMixData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {triggerMixData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Legend verticalAlign="bottom" height={36}/>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>

      </div>
    </div>
  )
}
