"use client"

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { PieChart, ListChecks, Activity, LogOut, ShieldAlert } from 'lucide-react'

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, profile, logout } = useUserStore()
  const supabase = createClient()

  useEffect(() => {
    if (!user) {
      router.push('/')
    } else if (profile && profile.role !== 'insurer_admin') {
      router.push('/worker/dashboard')
    }
  }, [user, profile, router])

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    logout()
    router.push('/')
  }

  if (!user || !profile) return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">Loading...</div>

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col md:flex-row font-sans">
      {/* Sidebar */}
      <aside className="w-full md:w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="p-6 flex items-center gap-3 border-b border-slate-800">
          <ShieldAlert className="text-blue-500" size={24} />
          <span className="font-semibold text-lg tracking-tight text-white">DEVTrails Insurer</span>
        </div>
        
        <div className="p-6 pb-2">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Administrator</p>
          <p className="font-medium text-sm text-slate-300">{profile.full_name}</p>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          <Link href="/admin/dashboard" className="flex items-center gap-3 px-4 py-3 text-slate-400 hover:bg-slate-800 hover:text-white rounded-lg transition-colors">
            <PieChart size={20} />
            <span className="font-medium">Overview</span>
          </Link>
          <Link href="/admin/reviews" className="flex items-center gap-3 px-4 py-3 text-slate-400 hover:bg-slate-800 hover:text-white rounded-lg transition-colors">
            <ListChecks size={20} />
            <span className="font-medium">Claim Queue</span>
          </Link>
          <Link href="/admin/triggers" className="flex items-center gap-3 px-4 py-3 text-slate-400 hover:bg-slate-800 hover:text-white rounded-lg transition-colors">
            <Activity size={20} />
            <span className="font-medium">Triggers Engine</span>
          </Link>
        </nav>

        <div className="p-4 border-t border-slate-800">
          <button 
            onClick={handleSignOut}
            className="flex w-full items-center gap-3 px-4 py-3 text-slate-400 hover:bg-red-500/10 hover:text-red-400 rounded-lg transition-colors"
          >
            <LogOut size={20} />
            <span className="font-medium">Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto h-screen relative bg-slate-950">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-500/5 rounded-full blur-3xl pointer-events-none" />
        {children}
      </main>
    </div>
  )
}
