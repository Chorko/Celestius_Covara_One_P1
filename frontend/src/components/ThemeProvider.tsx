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

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('dark')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    // Read saved preference or system preference
    const saved = localStorage.getItem('covara-theme') as Theme | null
    if (saved === 'dark' || saved === 'light') {
      setThemeState(saved)
      document.documentElement.setAttribute('data-theme', saved)
    } else {
      const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      const initial = systemDark ? 'dark' : 'light'
      setThemeState(initial)
      document.documentElement.setAttribute('data-theme', initial)
    }
    setMounted(true)
  }, [])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
    document.documentElement.setAttribute('data-theme', t)
    localStorage.setItem('covara-theme', t)
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }, [theme, setTheme])

  // Prevent flash: set data-theme before hydration
  if (!mounted) {
    return (
      <>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('covara-theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t)}else{document.documentElement.setAttribute('data-theme',window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light')}}catch(e){document.documentElement.setAttribute('data-theme','dark')}})()`,
          }}
        />
        {children}
      </>
    )
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
