'use client'

import { useEffect, useRef, useState } from 'react'

interface AnimatedCounterProps {
  value: number
  prefix?: string
  suffix?: string
  duration?: number
  decimals?: number
  className?: string
}

/**
 * Animated number counter — smoothly counts from 0 to target value.
 * Uses requestAnimationFrame for 60fps smooth animation.
 * Formats numbers with Indian locale (₹1,23,456).
 */
export default function AnimatedCounter({
  value,
  prefix = '',
  suffix = '',
  duration = 1200,
  decimals = 0,
  className = '',
}: AnimatedCounterProps) {
  const [display, setDisplay] = useState('0')
  const frameRef = useRef<number>(0)
  const startRef = useRef<number>(0)

  useEffect(() => {
    if (value === 0) {
      return
    }

    const startTime = performance.now()
    startRef.current = startTime

    const animate = (now: number) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease-out cubic for smooth deceleration
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = eased * value

      if (decimals > 0) {
        setDisplay(current.toFixed(decimals))
      } else {
        setDisplay(Math.round(current).toLocaleString('en-IN'))
      }

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate)
      }
    }

    frameRef.current = requestAnimationFrame(animate)

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
  }, [value, duration, decimals])

  const shown = value === 0 ? '0' : display

  return (
    <span className={`stat-number ${className}`}>
      {prefix}{shown}{suffix}
    </span>
  )
}
