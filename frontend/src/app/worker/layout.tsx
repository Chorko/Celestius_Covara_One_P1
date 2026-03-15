"use client"

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { LayoutDashboard, FileText, LogOut, ShieldAlert } from 'lucide-react'

export default function WorkerLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, profile, logout } = useUserStore()
  const supabase = createClient()

  useEffect(() => {
    if (!user) {
      router.push('/')
    } else if (profile && profile.role !== 'worker') {
      router.push('/admin/dashboard')
    }
  }, [user, profile, router])

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    logout()
    router.push('/')
  }

  if (!user || !profile) return <div className="min-h-screen bg-neutral-950 flex items-center justify-center text-white">Loading...</div>

  return (
    <div className="min-h-screen bg-neutral-950 text-white flex flex-col md:flex-row">
      {/* Sidebar */}
      <aside className="w-full md:w-64 bg-neutral-900 border-r border-neutral-800 flex flex-col">
        <div className="p-6 flex items-center gap-3 border-b border-neutral-800">
          <ShieldAlert className="text-emerald-500" size={24} />
          <span className="font-semibold text-lg tracking-tight">DEV Trails</span>
        </div>
        
        <div className="p-6 pb-2">
          <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1">Worker</p>
          <p className="font-medium text-sm text-neutral-300">{profile.full_name}</p>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          <Link href="/worker/dashboard" className="flex items-center gap-3 px-4 py-3 bg-emerald-500/10 text-emerald-400 rounded-lg">
            <LayoutDashboard size={20} />
            <span className="font-medium">Dashboard</span>
          </Link>
          <Link href="/worker/claims" className="flex items-center gap-3 px-4 py-3 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 rounded-lg transition-colors">
            <FileText size={20} />
            <span className="font-medium">My Claims</span>
          </Link>
        </nav>

        <div className="p-4 border-t border-neutral-800">
          <button 
            onClick={handleSignOut}
            className="flex w-full items-center gap-3 px-4 py-3 text-neutral-400 hover:bg-red-500/10 hover:text-red-400 rounded-lg transition-colors"
          >
            <LogOut size={20} />
            <span className="font-medium">Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto h-screen relative">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />
        {children}
      </main>
    </div>
  )
}
