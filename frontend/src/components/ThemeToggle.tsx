"use client"

import { useSyncExternalStore } from 'react'
import { useTheme } from './ThemeProvider'
import { Sun, Moon } from 'lucide-react'

const subscribe = () => () => {}
const getClientSnapshot = () => true
const getServerSnapshot = () => false

export default function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggleTheme } = useTheme()
  const mounted = useSyncExternalStore(subscribe, getClientSnapshot, getServerSnapshot)

  const nextTheme = theme === 'dark' ? 'light' : 'dark'

  return (
    <button
      onClick={mounted ? toggleTheme : undefined}
      className={`px-2.5 py-2.5 rounded-xl transition-all ${className}`}
      style={{
        background: 'color-mix(in srgb, var(--bg-tertiary) 74%, transparent)',
        border: '1px solid var(--border-primary)',
        color: 'var(--text-secondary)',
        boxShadow: 'var(--shadow-sm)',
      }}
      aria-label={mounted ? `Switch to ${nextTheme} mode` : 'Toggle theme'}
      title={mounted ? `Switch to ${nextTheme} mode` : 'Toggle theme'}
    >
      {mounted ? (theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />) : <Moon size={16} />}
    </button>
  )
}
