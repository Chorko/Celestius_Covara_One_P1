"use client"

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { useUserStore } from '@/store'
import { createClient } from '@/lib/supabase'
import { LayoutDashboard, FileText, CreditCard, LogOut, Shield, Menu, X, User } from 'lucide-react'

const navItems = [
  { href: '/worker/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/worker/claims', label: 'My Claims', icon: FileText },
  { href: '/worker/pricing', label: 'Coverage', icon: CreditCard },
]

export default function WorkerLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, profile, logout } = useUserStore()
  const supabase = createClient()
  const [drawerOpen, setDrawerOpen] = useState(false)

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

  if (!user || !profile) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#050510' }}>
        <div className="flex flex-col items-center gap-4">
          <div className="preload-logo">
            <Shield className="text-emerald-400" size={28} />
          </div>
          <span className="text-sm text-white/40">Loading...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="layout-root min-h-screen flex overflow-x-hidden" style={{ background: '#050510' }}>
      {/* ─── Desktop Sidebar ─── */}
      <aside className="desktop-sidebar w-[280px] min-h-screen glass-strong flex flex-col relative" style={{ borderRight: '1px solid rgba(255, 255, 255, 0.06)' }}>
        <div className="absolute top-0 left-0 w-full h-32 pointer-events-none" style={{ background: 'linear-gradient(180deg, rgba(16, 185, 129, 0.06) 0%, transparent 100%)' }} />

        {/* Branding */}
        <div className="relative p-6 flex items-center gap-3" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.05))', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
            <Shield className="text-emerald-400" size={20} />
          </div>
          <span className="font-bold text-lg text-white tracking-tight">Covara One</span>
        </div>

        {/* User info */}
        <div className="px-6 py-4" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
          <p className="text-sm font-medium text-white/80 mb-1">{profile.full_name}</p>
          <span className="badge badge-emerald">Worker</span>
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
                    ? 'text-emerald-300'
                    : 'text-white/40 hover:text-white/70 hover:bg-white/[0.03]'
                }`}
                style={isActive ? {
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.15)',
                  boxShadow: '0 0 20px rgba(16, 185, 129, 0.05)',
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
            className="btn-signout"
          >
            <LogOut size={18} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* ─── Mobile Header ─── */}
      <header className="mobile-header fixed top-0 left-0 right-0 z-30 glass-strong px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.05))', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
            <Shield className="text-emerald-400" size={16} />
          </div>
          <span className="font-bold text-sm text-white">Covara One</span>
        </div>
        <button onClick={() => setDrawerOpen(true)} className="w-8 h-8 flex items-center justify-center rounded-lg glass text-white/60 cursor-pointer">
          <Menu size={18} />
        </button>
      </header>

      {/* ─── Mobile Drawer ─── */}
      <div className={`drawer-overlay ${drawerOpen ? 'open' : ''}`} onClick={() => setDrawerOpen(false)} />
      <div className={`drawer-panel ${drawerOpen ? 'open' : ''}`}>
        <div className="flex items-center justify-between mb-6">
          <span className="text-white font-semibold text-sm">Menu</span>
          <button onClick={() => setDrawerOpen(false)} className="text-white/40 cursor-pointer"><X size={20} /></button>
        </div>
        <div className="flex items-center gap-3 p-3 glass rounded-xl mb-4">
          <div className="w-8 h-8 rounded-full bg-emerald-500/15 flex items-center justify-center">
            <User size={16} className="text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-white">{profile.full_name}</p>
            <p className="text-xs text-white/40">{user.email}</p>
          </div>
        </div>
        <button
          onClick={handleSignOut}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-red-400/80 glass mt-2 cursor-pointer"
        >
          <LogOut size={16} />
          Sign Out
        </button>
      </div>

      {/* ─── Main Content ─── */}
      <main className="flex-1 overflow-auto h-screen relative gradient-mesh">
        <div className="md:hidden h-14" /> {/* Mobile header spacer */}
        <div className="animate-page-enter">
          {children}
        </div>
      </main>

      {/* ─── Mobile Bottom Nav ─── */}
      <nav className="mobile-bottom-nav bottom-nav">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`bottom-nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={20} />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
