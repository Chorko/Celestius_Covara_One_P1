"use client"

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import { useUserStore } from '@/store'
import { ShieldAlert, LogIn, ArrowRight } from 'lucide-react'

export default function Home() {
  const router = useRouter()
  const supabase = createClient()
  const { setUser, setProfile } = useUserStore()
  
  const [email, setEmail] = useState('worker@demo.com')
  const [password, setPassword] = useState('DevTrails@123')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Check existing session
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setUser(session.user)
        routeToRole(session.user.id)
      }
    })
  }, [supabase.auth, setUser])

  const routeToRole = async (userId: string) => {
    const { data: profile } = await supabase.from('profiles').select('*').eq('id', userId).single()
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
    <main className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4">
      <div className="max-w-md w-full bg-neutral-900 border border-neutral-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex items-center gap-3 mb-8">
          <div className="bg-emerald-500/20 p-2 rounded-lg text-emerald-400">
            <ShieldAlert size={28} />
          </div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">DEV Trails</h1>
        </div>

        <p className="text-neutral-400 mb-8">Parametric Income Protection for Gig Workers.</p>

        {error && (
          <div className="bg-red-500/10 text-red-400 p-3 rounded-lg mb-6 text-sm border border-red-500/20">
            {error}
          </div>
        )}

        {/* Demo Accounts Wrapper */}
        <form onSubmit={handleEmailLogin} className="space-y-4 mb-8">
          <div>
            <label className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-2 block">Demo Login</label>
            <input 
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-emerald-500/50 transition-colors mb-4"
              placeholder="Email address"
            />
            <input 
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-emerald-500/50 transition-colors"
              placeholder="Password"
            />
          </div>
          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-white text-black font-medium py-3 rounded-lg hover:bg-neutral-200 transition-colors flex items-center justify-center gap-2"
          >
            {loading ? 'Authenticating...' : 'Sign In Demo'} <ArrowRight size={18} />
          </button>
        </form>

        <div className="relative mb-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-neutral-800"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-neutral-900 text-neutral-500">Or continue with</span>
          </div>
        </div>

        <button 
          onClick={handleGoogleLogin}
          type="button"
          className="w-full bg-neutral-800 hover:bg-neutral-700 text-white font-medium py-3 rounded-lg transition-colors flex items-center justify-center gap-3 border border-neutral-700 hover:border-neutral-600"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Sign in with Google
        </button>

      </div>
    </main>
  )
}
