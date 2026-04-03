"use client"

import { useTheme } from './ThemeProvider'
import { Sun, Moon } from 'lucide-react'

export default function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggleTheme } = useTheme()

  return (
    <button
      onClick={toggleTheme}
      className={`p-2 rounded-lg transition-all ${className}`}
      style={{
        background: 'var(--bg-tertiary)',
        border: '1px solid var(--border-primary)',
        color: 'var(--text-secondary)',
      }}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  )
}
