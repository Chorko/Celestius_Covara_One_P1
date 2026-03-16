"use client"

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import { useUserStore } from '@/store'
import { Shield, ArrowRight, Zap, Dna, Ghost } from 'lucide-react'

export default function Home() {
  const router = useRouter()
  const supabase = createClient()
  const { setUser, setProfile } = useUserStore()

  const [email, setEmail] = useState('worker@demo.com')
  const [password, setPassword] = useState('demo1234')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Check existing session
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setUser(session.user)
        routeToRole(session.user.id)
      }
    }).catch(() => {
      // Session expired or invalid — stay on login page
    })
  }, [supabase.auth, setUser])

  const routeToRole = async (userId: string) => {
    const { data: profile, error: profileError } = await supabase.from('profiles').select('*').eq('id', userId).single()
    if (profileError) {
      // Schema or RLS error — sign out stale session so user can re-login cleanly
      await supabase.auth.signOut()
      setError(profileError.message)
      return
    }
    if (profile) {
      setProfile(profile)
      if (profile.role === 'worker') router.push('/worker/dashboard')
      else if (profile.role === 'insurer_admin') router.push('/admin/dashboard')
    }
  }

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError(error.message)
      setLoading(false)
    } else if (data.user) {
      setUser(data.user)
      await routeToRole(data.user.id)
    }
  }

  const handleGoogleLogin = async () => {
    setLoading(true)
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` }
    })
  }

  return (
    <main className="min-h-screen relative overflow-hidden flex items-center justify-center p-4" style={{ background: '#050510' }}>
      {/* Animated floating orbs */}
      <div className="absolute top-[-10%] left-[-5%] w-[500px] h-[500px] rounded-full animate-float" style={{ background: 'radial-gradient(circle, rgba(16, 185, 129, 0.12) 0%, transparent 70%)', animationDuration: '8s' }} />
      <div className="absolute bottom-[-15%] right-[-10%] w-[600px] h-[600px] rounded-full animate-float" style={{ background: 'radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%)', animationDuration: '10s', animationDelay: '2s' }} />
      <div className="absolute top-[40%] right-[15%] w-[350px] h-[350px] rounded-full animate-float" style={{ background: 'radial-gradient(circle, rgba(139, 92, 246, 0.08) 0%, transparent 70%)', animationDuration: '12s', animationDelay: '4s' }} />
      <div className="absolute bottom-[30%] left-[10%] w-[250px] h-[250px] rounded-full animate-float" style={{ background: 'radial-gradient(circle, rgba(16, 185, 129, 0.06) 0%, transparent 70%)', animationDuration: '9s', animationDelay: '1s' }} />
      <div className="absolute top-[15%] left-[50%] w-[200px] h-[200px] rounded-full animate-float" style={{ background: 'radial-gradient(circle, rgba(59, 130, 246, 0.07) 0%, transparent 70%)', animationDuration: '11s', animationDelay: '3s' }} />

      {/* Main card */}
      <div className="relative z-10 w-full max-w-md animate-fade-in-up">
        <div className="glass-strong rounded-2xl p-8 glow-emerald">
          {/* Branding */}
          <div className="flex flex-col items-center text-center mb-8 animate-fade-in-up">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style={{ background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.05))', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
              <Shield className="text-emerald-400" size={32} />
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight mb-2">DEVTrails</h1>
            <p className="text-sm text-white/50 leading-relaxed max-w-xs">
              AI-Powered Parametric Income Protection for Gig Workers
            </p>
          </div>

          {/* Feature pills */}
          <div className="flex flex-wrap justify-center gap-2 mb-8 animate-fade-in-up delay-100">
            <span className="badge badge-emerald">
              <Zap size={10} /> Zero-Touch Claims
            </span>
            <span className="badge badge-purple">
              <Dna size={10} /> Disruption DNA
            </span>
            <span className="badge badge-amber">
              <Ghost size={10} /> Ghost Shift Detector
            </span>
          </div>

          {/* Error display */}
          {error && (
            <div className="mb-6 p-3 rounded-xl text-sm animate-fade-in-up" style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#fca5a5' }}>
              {error}
            </div>
          )}

          {/* Quick-switch buttons */}
          <div className="flex gap-2 mb-5 animate-fade-in-up delay-200">
            <button
              type="button"
              onClick={() => { setEmail('worker@demo.com'); setPassword('demo1234') }}
              className={`flex-1 py-2 px-3 rounded-xl text-xs font-semibold transition-all cursor-pointer ${email === 'worker@demo.com' ? 'text-emerald-300' : 'text-white/40 hover:text-white/60'}`}
              style={email === 'worker@demo.com'
                ? { background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)' }
                : { background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.08)' }
              }
            >
              Login as Worker
            </button>
            <button
              type="button"
              onClick={() => { setEmail('admin@demo.com'); setPassword('demo1234') }}
              className={`flex-1 py-2 px-3 rounded-xl text-xs font-semibold transition-all cursor-pointer ${email === 'admin@demo.com' ? 'text-blue-300' : 'text-white/40 hover:text-white/60'}`}
              style={email === 'admin@demo.com'
                ? { background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.3)' }
                : { background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.08)' }
              }
            >
              Login as Admin
            </button>
          </div>

          {/* Login form */}
          <form onSubmit={handleEmailLogin} className="space-y-4 mb-6 animate-fade-in-up delay-300">
            <div>
              <label className="text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-1.5 block">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="glass-input"
                placeholder="Email address"
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-1.5 block">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="glass-input"
                placeholder="Password"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  Authenticating...
                </span>
              ) : (
                <>Sign In <ArrowRight size={16} /></>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative mb-6 animate-fade-in-up delay-400">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)' }} />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 text-white/30" style={{ background: 'rgba(255, 255, 255, 0.06)' }}>or continue with</span>
            </div>
          </div>

          {/* Google OAuth */}
          <button
            onClick={handleGoogleLogin}
            type="button"
            className="btn-secondary w-full flex items-center justify-center gap-3 animate-fade-in-up delay-500"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Sign in with Google
          </button>
        </div>

        {/* Footer */}
        <p className="text-center text-[11px] text-white/20 mt-6 animate-fade-in-up delay-500">
          Secured by Supabase Auth &middot; Powered by AI
        </p>
      </div>
    </main>
  )
}
