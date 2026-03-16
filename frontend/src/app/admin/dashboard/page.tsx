"use client"

import { useEffect, useState } from 'react'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import {
  Users, Clock, CheckCircle, IndianRupee, Activity, ArrowRight,
  FileSearch, Zap, Shield, TrendingUp, AlertTriangle
} from 'lucide-react'
import Link from 'next/link'

const COLORS = ['#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#6366f1', '#a855f7']

export default function AdminDashboard() {
  const { profile } = useUserStore()
  const supabase = createClient()
  const [data, setData] = useState<any>(null)
  const [recentClaims, setRecentClaims] = useState<any[]>([])

  useEffect(() => {
    loadAnalytics()
    loadRecentClaims()
  }, [])

  const loadAnalytics = async () => {
    try {
      const { data: session } = await supabase.auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/analytics/summary`, {
        headers: { Authorization: `Bearer ${session.session?.access_token}` },
      })
      if (res.ok) {
        setData(await res.json())
      }
    } catch (e) {
      console.error('Could not load analytics', e)
    }
  }

  const loadRecentClaims = async () => {
    try {
      const { data: session } = await supabase.auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/claims`, {
        headers: { Authorization: `Bearer ${session.session?.access_token}` },
      })
      if (res.ok) {
        const d = await res.json()
        setRecentClaims((d.claims || []).slice(0, 6))
      }
    } catch (e) {
      console.error('Could not load recent claims', e)
    }
  }

  if (!data) {
    return (
      <div className="p-8 max-w-7xl mx-auto gradient-mesh-admin min-h-screen">
        <div className="animate-pulse space-y-6">
          <div className="h-10 w-80 rounded-lg bg-white/5" />
          <div className="grid grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="glass-card p-6 h-32 rounded-2xl" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  const { metrics, charts } = data
  const triggerMixData = Object.entries(charts.trigger_mix || {}).map(
    ([name, value]) => ({ name: name.toUpperCase(), value })
  )

  const statusColor = (status: string) => {
    switch (status) {
      case 'approved': return 'badge-emerald'
      case 'held':
      case 'submitted': return 'badge-amber'
      case 'rejected': return 'badge-red'
      default: return 'badge-blue'
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'approved': return <CheckCircle size={12} />
      case 'held':
      case 'submitted': return <Clock size={12} />
      default: return <AlertTriangle size={12} />
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto gradient-mesh-admin min-h-screen">
      {/* Header */}
      <div className="mb-8 animate-fade-in-up">
        <div className="flex items-center gap-3 mb-2">
          <Shield size={28} className="text-blue-400" />
          <h1 className="text-3xl font-bold">Insurance Operations Center</h1>
        </div>
        <p className="text-neutral-400">
          Welcome back, <span className="text-white font-medium">{profile?.full_name}</span>.
          Real-time parametric insurance metrics across all operational zones.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="glass-card p-6 animate-fade-in-up delay-100">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-medium text-neutral-400">Active Workers</span>
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <Users size={20} className="text-emerald-400" />
            </div>
          </div>
          <div className="text-3xl font-bold mb-1">{metrics.active_workers}</div>
          <p className="text-xs text-emerald-400 flex items-center gap-1">
            <TrendingUp size={12} /> Covered on platform
          </p>
        </div>

        <div className="glass-card p-6 animate-fade-in-up delay-200">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-medium text-neutral-400">Pending Claims</span>
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <Clock size={20} className="text-amber-400" />
            </div>
          </div>
          <div className="text-3xl font-bold mb-1">{metrics.pending_claims}</div>
          <p className="text-xs text-amber-400">Awaiting manual review</p>
        </div>

        <div className="glass-card p-6 animate-fade-in-up delay-300">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-medium text-neutral-400">Approved Claims</span>
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <CheckCircle size={20} className="text-emerald-400" />
            </div>
          </div>
          <div className="text-3xl font-bold mb-1">{metrics.approved_claims}</div>
          <p className="text-xs text-neutral-500">
            Out of {metrics.total_claims} total claims
          </p>
        </div>

        <div className="glass-card p-6 animate-fade-in-up delay-400">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-medium text-neutral-400">Total Payouts</span>
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <IndianRupee size={20} className="text-blue-400" />
            </div>
          </div>
          <div className="text-3xl font-bold mb-1">
            ₹{metrics.total_recommended_payout_inr?.toLocaleString('en-IN') || 0}
          </div>
          <p className="text-xs text-neutral-500">
            Expected: ₹{metrics.total_expected_payout_inr?.toLocaleString('en-IN') || 0}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 mb-8">
        {/* Trigger Distribution Chart */}
        <div className="lg:col-span-2 glass-card p-6 animate-fade-in-up delay-300">
          <div className="mb-6">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Activity size={20} className="text-blue-400" /> Trigger Distribution
            </h2>
            <p className="text-xs text-neutral-500 mt-1">
              Disruption events by family across all zones
            </p>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={triggerMixData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={95}
                  paddingAngle={4}
                  dataKey="value"
                  stroke="none"
                >
                  {triggerMixData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(10, 10, 20, 0.9)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    color: '#fff',
                    borderRadius: '0.75rem',
                    backdropFilter: 'blur(12px)',
                  }}
                  itemStyle={{ color: '#fff' }}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value: string) => (
                    <span style={{ color: '#a1a1aa', fontSize: '0.75rem' }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Activity Feed */}
        <div className="lg:col-span-3 glass-card p-6 animate-fade-in-up delay-400">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <FileSearch size={20} className="text-purple-400" /> Recent Activity
              </h2>
              <p className="text-xs text-neutral-500 mt-1">Latest claim submissions and decisions</p>
            </div>
            <Link
              href="/admin/reviews"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
            >
              View all <ArrowRight size={12} />
            </Link>
          </div>

          <div className="space-y-3 max-h-72 overflow-auto">
            {recentClaims.length === 0 ? (
              <div className="text-center py-12 text-neutral-500 text-sm">
                No recent claim activity
              </div>
            ) : (
              recentClaims.map((claim) => (
                <div
                  key={claim.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
                      {statusIcon(claim.claim_status)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {claim.worker_profiles?.platform_name || 'Worker'} - {claim.worker_profiles?.city || 'Unknown'}
                      </p>
                      <p className="text-xs text-neutral-500 truncate">{claim.claim_reason}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-3">
                    <span className={`badge ${statusColor(claim.claim_status)}`}>
                      {claim.claim_status}
                    </span>
                    <span className="text-xs text-neutral-600">
                      {new Date(claim.claimed_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-in-up delay-500">
        <Link href="/admin/reviews" className="glass-card p-5 flex items-center gap-4 group cursor-pointer">
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
            <FileSearch size={22} className="text-blue-400" />
          </div>
          <div>
            <p className="font-semibold text-sm">Review Claims</p>
            <p className="text-xs text-neutral-500">Adjudicate pending submissions</p>
          </div>
          <ArrowRight size={16} className="text-neutral-600 ml-auto group-hover:text-white transition-colors" />
        </Link>

        <Link href="/admin/triggers" className="glass-card p-5 flex items-center gap-4 group cursor-pointer">
          <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center group-hover:bg-amber-500/20 transition-colors">
            <Zap size={22} className="text-amber-400" />
          </div>
          <div>
            <p className="font-semibold text-sm">Trigger Engine</p>
            <p className="text-xs text-neutral-500">Monitor and inject triggers</p>
          </div>
          <ArrowRight size={16} className="text-neutral-600 ml-auto group-hover:text-white transition-colors" />
        </Link>

        <Link href="/admin/users" className="glass-card p-5 flex items-center gap-4 group cursor-pointer">
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center group-hover:bg-purple-500/20 transition-colors">
            <Users size={22} className="text-purple-400" />
          </div>
          <div>
            <p className="font-semibold text-sm">Manage Users</p>
            <p className="text-xs text-neutral-500">Search and inspect worker profiles</p>
          </div>
          <ArrowRight size={16} className="text-neutral-600 ml-auto group-hover:text-white transition-colors" />
        </Link>
      </div>
    </div>
  )
}
