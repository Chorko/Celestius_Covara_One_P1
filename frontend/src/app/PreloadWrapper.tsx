"use client"

import { useState, useEffect } from 'react'
import BrandMark from '@/components/BrandMark'

export function PreloadWrapper({ children }: { children: React.ReactNode }) {
  const [loaded, setLoaded] = useState(false)
  const [hide, setHide] = useState(false)

  useEffect(() => {
    const t1 = setTimeout(() => setLoaded(true), 1000)
    const t2 = setTimeout(() => setHide(true), 1400)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [])

  return (
    <>
      {!hide && (
        <div className={`preload-screen ${loaded ? 'hide' : ''}`}>
          <div className="preload-logo">
            <BrandMark size={46} />
          </div>
          <span className="preload-title brand-wordmark">Covara One</span>
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
