"use client"

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AlertCircle, ArrowLeft, CheckCircle2, Shield, Smartphone } from 'lucide-react'

import { createClient } from '@/lib/supabase'
import { backendGet, backendPost, BackendApiError } from '@/lib/backendApi'
import { useUserStore } from '@/store'

interface ZoneOption {
  id: string
  city: string
  zone_name: string
}

interface OtpSendResponse {
  message?: string
  otp?: string
  mock?: boolean
}

interface OtpVerifyResponse {
  verified: boolean
  message?: string
}

function formatApiError(error: unknown): string {
  if (error instanceof BackendApiError) {
    return error.detail
  }
  return error instanceof Error ? error.message : 'Request failed'
}

export default function SignupPage() {
  const router = useRouter()
  const supabase = createClient()
  const { setUser, setProfile } = useUserStore()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [otpCode, setOtpCode] = useState('')

  const [platformName, setPlatformName] = useState('Swiggy')
  const [city, setCity] = useState('Mumbai')
  const [zoneId, setZoneId] = useState('')
  const [vehicleType, setVehicleType] = useState('bike')
  const [hourlyIncome, setHourlyIncome] = useState('90')

  const [panNumber, setPanNumber] = useState('')
  const [bankAccount, setBankAccount] = useState('')
  const [ifsc, setIfsc] = useState('')

  const [zones, setZones] = useState<ZoneOption[]>([])
  const [otpSending, setOtpSending] = useState(false)
  const [otpVerifying, setOtpVerifying] = useState(false)
  const [otpSent, setOtpSent] = useState(false)
  const [otpVerified, setOtpVerified] = useState(false)
  const [otpHint, setOtpHint] = useState<string | null>(null)

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const loadZones = async () => {
      try {
        const { data } = await supabase
          .from('zones')
          .select('id, city, zone_name')
          .order('city', { ascending: true })
          .order('zone_name', { ascending: true })

        const rows = (data || []) as ZoneOption[]
        setZones(rows)
        if (rows.length > 0) {
          setZoneId(rows[0].id)
          setCity(rows[0].city)
        }
      } catch {
        setZones([])
      }
    }

    void loadZones()
  }, [supabase])

  const sendOtp = async () => {
    setError(null)
    setOtpHint(null)
    setOtpSending(true)
    try {
      const res = await fetch('/api/kyc/otp/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phone.trim() }),
      })
      const payload = (await res.json()) as OtpSendResponse | { detail?: string }
      if (!res.ok) {
        throw new Error((payload as { detail?: string }).detail || 'OTP send failed')
      }

      setOtpSent(true)
      const hint = (payload as OtpSendResponse).mock
        ? `OTP sent in mock mode. Use ${(payload as OtpSendResponse).otp || '123456'} for demo.`
        : ((payload as OtpSendResponse).message || 'OTP sent successfully.')
      setOtpHint(hint)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'OTP send failed')
    } finally {
      setOtpSending(false)
    }
  }

  const verifyOtp = async () => {
    setError(null)
    setOtpVerifying(true)
    try {
      const res = await fetch('/api/kyc/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phone.trim(), code: otpCode.trim() }),
      })
      const payload = (await res.json()) as OtpVerifyResponse | { detail?: string }
      if (!res.ok) {
        throw new Error((payload as { detail?: string }).detail || 'OTP verification failed')
      }

      if (!(payload as OtpVerifyResponse).verified) {
        throw new Error('OTP is invalid or expired')
      }

      setOtpVerified(true)
      setOtpHint((payload as OtpVerifyResponse).message || 'Phone verified.')
    } catch (e: unknown) {
      setOtpVerified(false)
      setError(e instanceof Error ? e.message : 'OTP verification failed')
    } finally {
      setOtpVerifying(false)
    }
  }

  const handleSignUp = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)

    if (!otpVerified) {
      setError('Verify your phone OTP before creating an account.')
      return
    }

    const selectedZone = zones.find((z) => z.id === zoneId)
    const resolvedCity = selectedZone?.city || city

    setSaving(true)
    try {
      const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            full_name: fullName.trim(),
            phone: phone.trim(),
          },
        },
      })

      if (signUpError) {
        throw new Error(signUpError.message)
      }

      let session = signUpData.session
      if (!session) {
        const signIn = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        })
        if (signIn.error) {
          throw new Error('Account created, but session was not established. Confirm email (if enabled) and sign in.')
        }
        session = signIn.data.session
      }

      if (!session) {
        throw new Error('Unable to establish session after signup.')
      }

      setUser(session.user)

      let bankVerified = false
      if (bankAccount.trim() && ifsc.trim()) {
        const bankResult = await backendPost<{ verified: boolean }>(
          supabase,
          '/kyc/bank/verify',
          {
            account_number: bankAccount.trim(),
            ifsc: ifsc.trim().toUpperCase(),
          },
        )
        bankVerified = Boolean(bankResult.verified)
      }

      if (panNumber.trim()) {
        await backendPost(
          supabase,
          '/kyc/pan/verify',
          { pan_number: panNumber.trim().toUpperCase() },
        )
      }

      await backendPost(
        supabase,
        '/auth/onboarding/worker',
        {
          full_name: fullName.trim(),
          phone: phone.trim(),
          platform_name: platformName.trim(),
          city: resolvedCity,
          preferred_zone_id: zoneId || null,
          vehicle_type: vehicleType.trim() || null,
          avg_hourly_income_inr: Number(hourlyIncome || 0),
          gps_consent: true,
          bank_verified: bankVerified,
        },
      )

      const me = await backendGet<{ profile?: Record<string, unknown> }>(supabase, '/auth/me')
      if (me?.profile) {
        setProfile(me.profile as never)
      }

      setMessage('Account created successfully. Redirecting to your dashboard...')
      router.replace('/worker/dashboard')
    } catch (e: unknown) {
      setError(formatApiError(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="min-h-screen page-mesh p-4 md:p-6">
      <div className="max-w-3xl mx-auto">
        <div className="mb-4">
          <Link href="/" className="inline-flex items-center gap-2 text-sm" style={{ color: 'var(--text-tertiary)' }}>
            <ArrowLeft size={14} /> Back to login
          </Link>
        </div>

        <div className="card-elevated p-6 md:p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: 'var(--accent-muted)' }}>
              <Shield size={20} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Create Worker Account</h1>
              <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                OTP onboarding + KYC-ready profile + parametric coverage access.
              </p>
            </div>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-lg flex items-start gap-2 text-sm" style={{ background: 'var(--danger-muted)', border: '1px solid var(--danger)', color: 'var(--danger)' }}>
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {message && (
            <div className="mb-4 p-3 rounded-lg flex items-start gap-2 text-sm" style={{ background: 'var(--success-muted)', border: '1px solid var(--success)', color: 'var(--success)' }}>
              <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
              <span>{message}</span>
            </div>
          )}

          <form onSubmit={handleSignUp} className="space-y-5">
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Full Name</label>
                <input required value={fullName} onChange={(e) => setFullName(e.target.value)} className="input-field" placeholder="Arjun Sharma" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Email</label>
                <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="input-field" placeholder="worker@example.com" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Password</label>
                <input required type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className="input-field" placeholder="Min 8 characters" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Phone (E.164)</label>
                <input required value={phone} onChange={(e) => setPhone(e.target.value)} className="input-field" placeholder="+919876543210" />
              </div>
            </section>

            <section className="card p-4" style={{ background: 'var(--bg-tertiary)' }}>
              <div className="flex items-center gap-2 mb-3">
                <Smartphone size={15} style={{ color: 'var(--accent)' }} />
                <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Twilio OTP Verification</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <button
                  type="button"
                  onClick={sendOtp}
                  disabled={otpSending || !phone.trim()}
                  className="btn-secondary py-2.5"
                >
                  {otpSending ? 'Sending OTP...' : otpSent ? 'Resend OTP' : 'Send OTP'}
                </button>
                <input
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  className="input-field"
                  placeholder="Enter OTP"
                />
                <button
                  type="button"
                  onClick={verifyOtp}
                  disabled={otpVerifying || !otpCode.trim() || !otpSent}
                  className="btn-primary py-2.5"
                >
                  {otpVerifying ? 'Verifying...' : otpVerified ? 'Verified' : 'Verify OTP'}
                </button>
              </div>
              {otpHint && (
                <p className="text-xs mt-2" style={{ color: otpVerified ? 'var(--success)' : 'var(--text-tertiary)' }}>
                  {otpHint}
                </p>
              )}
            </section>

            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Platform</label>
                <input required value={platformName} onChange={(e) => setPlatformName(e.target.value)} className="input-field" placeholder="Swiggy / Zomato" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Vehicle Type</label>
                <input value={vehicleType} onChange={(e) => setVehicleType(e.target.value)} className="input-field" placeholder="Bike" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>City</label>
                <input required value={city} onChange={(e) => setCity(e.target.value)} className="input-field" placeholder="Mumbai" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Preferred Zone</label>
                <select
                  value={zoneId}
                  onChange={(e) => {
                    setZoneId(e.target.value)
                    const zone = zones.find((z) => z.id === e.target.value)
                    if (zone) {
                      setCity(zone.city)
                    }
                  }}
                  className="input-field"
                >
                  <option value="">Select zone</option>
                  {zones.map((zone) => (
                    <option key={zone.id} value={zone.id}>{zone.zone_name} ({zone.city})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Avg Hourly Income (INR)</label>
                <input required type="number" min={20} step="1" value={hourlyIncome} onChange={(e) => setHourlyIncome(e.target.value)} className="input-field" placeholder="90" />
              </div>
            </section>

            <section className="card p-4" style={{ background: 'var(--bg-tertiary)' }}>
              <p className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Optional KYC at Signup</p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>PAN Number</label>
                  <input value={panNumber} onChange={(e) => setPanNumber(e.target.value.toUpperCase())} className="input-field" placeholder="ABCDE1234F" maxLength={10} />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Bank Account</label>
                  <input value={bankAccount} onChange={(e) => setBankAccount(e.target.value)} className="input-field" placeholder="XXXXXXXXXXXX" />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-tertiary)' }}>IFSC</label>
                  <input value={ifsc} onChange={(e) => setIfsc(e.target.value.toUpperCase())} className="input-field" placeholder="SBIN0001234" />
                </div>
              </div>
              <p className="text-[11px] mt-2" style={{ color: 'var(--text-tertiary)' }}>
                PAN and bank verification call the configured KYC provider (Sandbox/Postman mock) during signup.
              </p>
            </section>

            <button type="submit" disabled={saving || !otpVerified} className="btn-primary w-full py-3">
              {saving ? 'Creating account...' : 'Create account and continue'}
            </button>
          </form>
        </div>
      </div>
    </main>
  )
}
