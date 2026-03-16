"use client"

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { PieChart, ListChecks, Activity, Search, LogOut, Shield } from 'lucide-react'

const navItems = [
  { href: '/admin/dashboard', label: 'Overview', icon: PieChart },
  { href: '/admin/reviews', label: 'Review Queue', icon: ListChecks },
  { href: '/admin/triggers', label: 'Trigger Engine', icon: Activity },
  { href: '/admin/users', label: 'User Search', icon: Search },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
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

  if (!user || !profile) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#050510' }}>
        <div className="flex items-center gap-3 text-white/40">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex" style={{ background: '#050510' }}>
      {/* Glass Sidebar */}
      <aside className="w-[280px] min-h-screen glass-strong flex flex-col relative" style={{ borderRight: '1px solid rgba(255, 255, 255, 0.06)' }}>
        {/* Sidebar glow accent - blue for admin */}
        <div className="absolute top-0 left-0 w-full h-32 pointer-events-none" style={{ background: 'linear-gradient(180deg, rgba(59, 130, 246, 0.06) 0%, transparent 100%)' }} />

        {/* Branding */}
        <div className="relative p-6 flex items-center gap-3" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(59, 130, 246, 0.05))', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
            <Shield className="text-blue-400" size={20} />
          </div>
          <span className="font-bold text-lg text-white tracking-tight">DEVTrails Admin</span>
        </div>

        {/* User info */}
        <div className="px-6 py-4" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
          <p className="text-sm font-medium text-white/80 mb-1">{profile.full_name}</p>
          <span className="badge badge-blue">Admin</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 mt-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'text-blue-300'
                    : 'text-white/40 hover:text-white/70 hover:bg-white/[0.03]'
                }`}
                style={isActive ? {
                  background: 'rgba(59, 130, 246, 0.1)',
                  border: '1px solid rgba(59, 130, 246, 0.15)',
                  boxShadow: '0 0 20px rgba(59, 130, 246, 0.05)',
                } : {
                  border: '1px solid transparent',
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Sign out */}
        <div className="p-3" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
          <button
            onClick={handleSignOut}
            className="flex w-full items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-white/30 hover:text-red-400 transition-all cursor-pointer"
            style={{ border: '1px solid transparent' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(239, 68, 68, 0.08)'
              e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.15)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.borderColor = 'transparent'
            }}
          >
            <LogOut size={18} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto h-screen relative gradient-mesh-admin">
        {children}
      </main>
    </div>
  )
}
