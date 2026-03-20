"use client"

import { useState, useEffect } from 'react'
import { Shield } from 'lucide-react'

export function PreloadWrapper({ children }: { children: React.ReactNode }) {
  const [loaded, setLoaded] = useState(false)
  const [hide, setHide] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setLoaded(true), 1600)
    const t2 = setTimeout(() => setHide(true), 2200)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [])

  return (
    <>
      {!hide && (
        <div className={`preload-screen ${loaded ? 'hide' : ''}`}>
          <div className="preload-logo">
            <Shield className="text-emerald-400" size={32} />
          </div>
          <span className="preload-title">Covara One</span>
          <span className="preload-subtitle">Parametric Income Protection</span>
          <div className="preload-bar-track">
            <div className="preload-bar-fill" />
          </div>
        </div>
      )}
      <div className={loaded ? 'animate-page-enter' : 'opacity-0'}>
        {children}
      </div>
    </>
  )
}
