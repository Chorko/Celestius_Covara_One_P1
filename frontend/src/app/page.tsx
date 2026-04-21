"use client"

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { useUserStore } from '@/store'
import ThemeToggle from '@/components/ThemeToggle'
import BrandMark from '@/components/BrandMark'
import { ArrowRight, AlertCircle, Download, Smartphone } from 'lucide-react'
import Image from 'next/image'

const DEMO9_EMAIL_PATTERN = /^demo\.(auto|review|fraud)\d{2}@synthetic\.covara\.dev$/i

export default function Home() {
  const router = useRouter()
  const supabase = createClient()
  const { setUser, setProfile } = useUserStore()

  const [email, setEmail] = useState('worker@demo.com')
  const [password, setPassword] = useState('demo1234')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const routeToRole = useCallback(async (userId: string) => {
    const controller = new AbortController()
    const tid = setTimeout(() => controller.abort(), 10000)

    let profileError: { code?: string; message?: string; details?: string } | null = null
    let profileData: Record<string, unknown> | null = null
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .abortSignal(controller.signal)
        .single()
      clearTimeout(tid)
      profileError = error
      profileData = data
    } catch (e: unknown) {
      clearTimeout(tid)
      await supabase.auth.signOut()
      if (controller.signal.aborted || (e instanceof Error && e.name === 'AbortError')) {
        setError('Cannot reach Supabase — request timed out. Check your network or try refreshing.')
      } else {
        setError(e instanceof Error ? e.message : 'Network error')
      }
      setLoading(false)
      return
    }

    if (profileError) {
      console.error('routeToRole error:', JSON.stringify(profileError))
      await supabase.auth.signOut()
      const code = profileError.code ?? ''
      const msg = profileError.message ?? ''
      const detail = profileError.details ?? ''
      if (code === 'PGRST205' || msg.toLowerCase().includes('schema') || detail.toLowerCase().includes('schema')) {
        setError(`Database not set up — run SQL migration files 01–07 in the Supabase SQL Editor, then try again. [${code || 'no-code'}: ${msg}]`)
      } else if (code === 'PGRST116') {
        setError(`Profile row missing — demo seed (06_synthetic_seed.sql) may not have run successfully. [${code}: ${msg}]`)
      } else {
        setError(`[${code || 'error'}] ${msg}${detail ? ` — ${detail}` : ''}`)
      }
      setLoading(false)
      return
    }
    if (profileData) {
      setProfile(profileData as Parameters<typeof setProfile>[0])
      if ((profileData as Record<string, unknown>).role === 'worker') router.push('/worker/dashboard')
      else if ((profileData as Record<string, unknown>).role === 'insurer_admin') router.push('/admin/dashboard')
    }
  }, [supabase, setProfile, router])

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setUser(session.user)
        routeToRole(session.user.id)
      }
    }).catch(() => {})
  }, [supabase.auth, setUser, routeToRole])

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    // Clear any stale local session before a fresh password sign-in.
    try {
      await supabase.auth.signOut({ scope: 'local' })
    } catch {
      // Ignore local sign-out errors and continue.
    }

    const { data, error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      console.error('signInWithPassword error:', JSON.stringify(error))
      const msg = error.message ?? ''
      const name = (error as unknown as Record<string, unknown>).name ?? ''
      const isDemo9Email = DEMO9_EMAIL_PATTERN.test(email)
      if (error.status === 0 || name === 'AuthRetryableFetchError' || msg.toLowerCase().includes('failed to fetch') || msg.toLowerCase().includes('network')) {
        setError('Cannot reach Supabase — your free-tier project may be paused. Visit the Supabase dashboard and click "Restore project", then try again.')
      } else if (isDemo9Email && (msg.toLowerCase().includes('schema') || error.status === 500)) {
        setError('DEMO9 auth is corrupted for this Supabase project. Run backend/sql/helpers/08c_fix_demo9_auth_users.sql (cleanup pass), recreate the 9 DEMO9 users (scripts/create_demo9_auth_users.py --apply), then run 08c again (sync pass).')
      } else if (msg.toLowerCase().includes('schema') || error.status === 500) {
        setError('Auth service error (500). For default demo users run scripts/recover_demo_auth_without_sql.py --mode full --apply. If auth errors persist, run supabase db query --file backend/sql/helpers/08_fix_demo_auth_users.sql --linked, then rerun the recovery script.')
      } else {
        setError(msg || 'Sign in failed')
      }
      setLoading(false)
    } else if (data.user) {
      setUser(data.user)
      await routeToRole(data.user.id)
    }
  }

  const handleGoogleLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: `${window.location.origin}/auth/callback` }
      })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed')
      setLoading(false)
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-6 md:px-8 md:py-8">
      <div className="absolute inset-0 pointer-events-none opacity-35">
        <Image
          src="/images/hero-bg.png"
          alt=""
          fill
          className="object-cover"
          priority
        />
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(160deg, color-mix(in srgb, var(--bg-primary) 72%, transparent) 4%, var(--bg-primary) 46%, var(--bg-primary) 100%)',
          }}
        />
      </div>

      <div className="absolute top-4 right-4 z-20">
        <ThemeToggle />
      </div>

      <div className="relative z-10 mx-auto grid w-full max-w-6xl gap-5 lg:grid-cols-[1.08fr_0.92fr]">
        <section className="card-elevated hidden p-8 md:p-10 lg:flex lg:flex-col lg:justify-between animate-fade-in-up">
          <div>
            <span
              className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
              style={{
                background: 'var(--accent-muted)',
                border: '1px solid color-mix(in srgb, var(--accent) 40%, transparent)',
                color: 'var(--accent)',
              }}
            >
              AI Claims Integrity Platform
            </span>

            <div className="mt-6 flex items-center gap-4">
              <BrandMark size={62} />
              <div>
                <h1 className="brand-wordmark text-4xl font-semibold leading-none" style={{ color: 'var(--text-primary)' }}>
                  Covara One
                </h1>
                <p className="mt-2 text-sm" style={{ color: 'var(--text-tertiary)' }}>
                  Parametric income protection for frontline workers.
                </p>
              </div>
            </div>

            <p className="mt-8 max-w-lg text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Risk sensing, payout routing, and fraud-aware review workflows from one operational surface,
              tuned for high-volume field operations.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              <div className="card p-4">
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Response Layer</p>
                <p className="mt-1 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Adaptive fraud routing</p>
              </div>
              <div className="card p-4">
                <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Worker Experience</p>
                <p className="mt-1 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Fast-lane claim submissions</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              Install Mobile Build
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Link href="/download" className="btn-primary w-full flex items-center justify-center gap-2 py-3">
                <Download size={16} /> Android APK
              </Link>
              <Link href="/download" className="btn-secondary w-full flex items-center justify-center gap-2 py-3">
                <Smartphone size={16} /> All Download Options
              </Link>
            </div>
          </div>
        </section>

        <section className="card-elevated p-7 md:p-9 animate-fade-in-up delay-100">
          <div className="mb-7 flex items-center gap-3">
            <BrandMark size={48} />
            <div>
              <h2 className="brand-wordmark text-2xl font-semibold leading-tight" style={{ color: 'var(--text-primary)' }}>
                Sign In
              </h2>
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                Access worker and insurer control consoles.
              </p>
            </div>
          </div>

          {error && (
            <div
              className="mb-6 rounded-xl p-3 text-sm flex items-start gap-2"
              style={{
                background: 'var(--danger-muted)',
                border: '1px solid var(--danger)',
                color: 'var(--danger)',
              }}
            >
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="mb-5 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => { setEmail('worker@demo.com'); setPassword('demo1234') }}
              className="py-2.5 px-3 rounded-xl text-xs font-semibold transition-all cursor-pointer"
              style={email === 'worker@demo.com'
                ? { background: 'var(--accent-muted)', border: '1px solid var(--accent)', color: 'var(--accent)' }
                : { background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', color: 'var(--text-tertiary)' }
              }
            >
              Worker Access
            </button>
            <button
              type="button"
              onClick={() => { setEmail('admin@demo.com'); setPassword('demo1234') }}
              className="py-2.5 px-3 rounded-xl text-xs font-semibold transition-all cursor-pointer"
              style={email === 'admin@demo.com'
                ? { background: 'var(--info-muted)', border: '1px solid var(--info)', color: 'var(--info)' }
                : { background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', color: 'var(--text-tertiary)' }
              }
            >
              Admin Access
            </button>
          </div>

          <form onSubmit={handleEmailLogin} className="space-y-4 mb-6">
            <div>
              <label
                className="text-xs font-medium uppercase tracking-wider mb-1.5 block"
                style={{ color: 'var(--text-tertiary)' }}
              >
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="Email address"
              />
            </div>
            <div>
              <label
                className="text-xs font-medium uppercase tracking-wider mb-1.5 block"
                style={{ color: 'var(--text-tertiary)' }}
              >
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="Password"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-3"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  Authenticating...
                </span>
              ) : (
                <>Continue <ArrowRight size={16} /></>
              )}
            </button>
          </form>

          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full" style={{ borderTop: '1px solid var(--border-primary)' }} />
            </div>
            <div className="relative flex justify-center text-xs">
              <span
                className="px-3"
                style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}
              >
                or continue with
              </span>
            </div>
          </div>

          <button
            onClick={handleGoogleLogin}
            type="button"
            className="btn-secondary w-full flex items-center justify-center gap-3"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Sign in with Google
          </button>

          <div className="mt-5 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
            New worker?{' '}
            <Link href="/signup" style={{ color: 'var(--accent)' }} className="font-medium">
              Create an account
            </Link>
          </div>

          <div className="mt-4 space-y-2 lg:hidden">
            <p className="text-xs text-center" style={{ color: 'var(--text-tertiary)' }}>
              Want the mobile app instead?
            </p>
            <Link href="/download" className="btn-primary w-full flex items-center justify-center gap-2 py-3">
              <Download size={16} /> Download Mobile App (Android APK)
            </Link>
            <Link href="/download" className="btn-secondary w-full flex items-center justify-center gap-2 py-3">
              <Smartphone size={16} /> View All Mobile Download Options
            </Link>
          </div>
        </section>
      </div>

      <p className="relative z-10 text-center text-xs mt-6" style={{ color: 'var(--text-tertiary)' }}>
        Secured by Supabase Auth and fraud-aware review controls.
      </p>
    </main>
  )
}
