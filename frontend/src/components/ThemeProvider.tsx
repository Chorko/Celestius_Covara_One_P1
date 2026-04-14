"use client"

import { createContext, useContext, useEffect, useState, useCallback } from 'react'

type Theme = 'dark' | 'light'
interface ThemeContextType {
  theme: Theme
  toggleTheme: () => void
  setTheme: (t: Theme) => void
}

const ThemeContext = createContext<ThemeContextType>({
  theme: 'dark',
  toggleTheme: () => {},
  setTheme: () => {},
})

export function useTheme() {
  return useContext(ThemeContext)
}

function resolveInitialTheme(): Theme {
  if (typeof window === 'undefined') {
    return 'dark'
  }

  const saved = window.localStorage.getItem('covara-theme')
  if (saved === 'dark' || saved === 'light') {
    return saved
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => resolveInitialTheme())

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('covara-theme', theme)
  }, [theme])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((current) => (current === 'dark' ? 'light' : 'dark'))
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
