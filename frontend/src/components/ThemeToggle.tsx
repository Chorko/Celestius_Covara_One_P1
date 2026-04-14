"use client"

import { useEffect, useState } from 'react'
import { useTheme } from './ThemeProvider'
import { Sun, Moon } from 'lucide-react'

export default function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggleTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const nextTheme = theme === 'dark' ? 'light' : 'dark'

  return (
    <button
      onClick={mounted ? toggleTheme : undefined}
      className={`p-2 rounded-lg transition-all ${className}`}
      style={{
        background: 'var(--bg-tertiary)',
        border: '1px solid var(--border-primary)',
        color: 'var(--text-secondary)',
      }}
      aria-label={mounted ? `Switch to ${nextTheme} mode` : 'Toggle theme'}
      title={mounted ? `Switch to ${nextTheme} mode` : 'Toggle theme'}
    >
      {mounted ? (theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />) : <Moon size={16} />}
    </button>
  )
}
