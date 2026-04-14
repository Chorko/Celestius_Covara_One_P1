"use client"

import { useEffect, useState, useCallback } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { useUserStore } from '@/store'
import ThemeToggle from '@/components/ThemeToggle'
import {
  LayoutDashboard,
  FileText,
  CreditCard,
  Coins,
  Shield,
  LogOut,
  Menu,
  X,
} from 'lucide-react'

const NAV_ITEMS = [
  { href: '/worker/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/worker/claims', label: 'My Claims', icon: FileText },
  { href: '/worker/rewards', label: 'Rewards', icon: Coins },
  { href: '/worker/pricing', label: 'Coverage', icon: CreditCard },
]

export default function WorkerLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()
  const { profile, logout, setUser, setProfile } = useUserStore()
  const [drawerOpen, setDrawerOpen] = useState(false)

  const handleSignOut = useCallback(async () => {
    await supabase.auth.signOut()
    logout()
    router.push('/')
  }, [supabase, logout, router])

  // Hydrate store state and enforce worker role.
  useEffect(() => {
    let active = true

    const hydrate = async () => {
      const { data: { session } } = await supabase.auth.getSession()
      if (!active) {
        return
      }

      if (!session) {
        router.push('/')
        return
      }

      setUser(session.user)

      try {
        const { data: profileRow } = await supabase
          .from('profiles')
          .select('*')
          .eq('id', session.user.id)
          .maybeSingle()

        if (!active || !profileRow) {
          return
        }

        setProfile(profileRow)

        if (profileRow.role && profileRow.role !== 'worker') {
          router.push(profileRow.role === 'insurer_admin' ? '/admin/dashboard' : '/')
        }
      } catch {
        // Keep layout usable even if profile fetch is temporarily unavailable.
      }
    }

    void hydrate()

    return () => {
      active = false
    }
  }, [supabase, router, setProfile, setUser])

  return (
    <div className="flex min-h-screen layout-root" style={{ background: 'var(--bg-primary)' }}>
      {/* ═══ DESKTOP SIDEBAR ═══ */}
      <aside
        className="desktop-sidebar fixed top-0 left-0 h-screen w-[240px] flex flex-col z-40 sidebar"
      >
        {/* Branding */}
        <div className="px-5 py-5 flex items-center gap-3" style={{ borderBottom: '1px solid var(--border-primary)' }}>
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center"
            style={{ background: 'var(--accent-muted)', border: '1px solid var(--border-secondary)' }}
          >
            <Shield style={{ color: 'var(--accent)' }} size={18} />
          </div>
          <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>Covara One</span>
        </div>

        {/* User info */}
        <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--border-primary)' }}>
          <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
            {profile?.full_name || 'Worker'}
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            {profile?.email || ''}
          </p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
              >
                <item.icon size={18} />
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Bottom actions */}
        <div className="px-3 pb-4 space-y-2" style={{ borderTop: '1px solid var(--border-primary)', paddingTop: '12px' }}>
          <div className="flex items-center justify-between px-3">
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Theme</span>
            <ThemeToggle />
          </div>
          <button onClick={handleSignOut} className="btn-signout">
            <LogOut size={16} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* ═══ MOBILE HEADER ═══ */}
      <header
        className="mobile-header hidden fixed top-0 left-0 right-0 z-40 items-center justify-between px-4 py-3"
        style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-primary)' }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'var(--accent-muted)' }}
          >
            <Shield style={{ color: 'var(--accent)' }} size={16} />
          </div>
          <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>Covara One</span>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => setDrawerOpen(true)}
            className="p-2 rounded-lg"
            style={{ color: 'var(--text-secondary)' }}
          >
            <Menu size={20} />
          </button>
        </div>
      </header>

      {/* ═══ MOBILE DRAWER ═══ */}
      <div className={`drawer-overlay ${drawerOpen ? 'open' : ''}`} onClick={() => setDrawerOpen(false)} />
      <div className={`drawer-panel ${drawerOpen ? 'open' : ''}`}>
        <div className="flex items-center justify-between mb-6">
          <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>Menu</span>
          <button onClick={() => setDrawerOpen(false)} style={{ color: 'var(--text-tertiary)' }}>
            <X size={20} />
          </button>
        </div>
        {profile && (
          <div className="mb-6 pb-4" style={{ borderBottom: '1px solid var(--border-primary)' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{profile.full_name}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{profile.email}</p>
          </div>
        )}
        <nav className="space-y-1 mb-6">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setDrawerOpen(false)}
                className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
              >
                <item.icon size={18} />
                {item.label}
              </Link>
            )
          })}
        </nav>
        <button onClick={handleSignOut} className="btn-signout">
          <LogOut size={16} />
          Sign Out
        </button>
      </div>

      {/* ═══ MOBILE BOTTOM NAV ═══ */}
      <nav className="bottom-nav mobile-bottom-nav hidden">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`bottom-nav-item ${isActive ? 'active' : ''}`}
            >
              <item.icon size={20} />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>

      {/* ═══ MAIN CONTENT ═══ */}
      <main className="flex-1 ml-0 md:ml-[240px] min-h-screen pt-14 md:pt-0">
        {children}
      </main>
    </div>
  )
}
