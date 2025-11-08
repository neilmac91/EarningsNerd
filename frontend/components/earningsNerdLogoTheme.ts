'use client'
// Shared palette and color-mode hook for EarningsNerd logo components
import { useEffect, useState } from 'react'

export type LogoMode = 'light' | 'dark' | 'auto'
export type ResolvedLogoMode = Exclude<LogoMode, 'auto'>

export const earningsNerdColorSchemes: Record<ResolvedLogoMode, {
  background: string
  surface: string
  ringOuter: string
  ringInner: string
  accent: string
  accentBright: string
  primary: string
  primaryBright: string
  textPrimary: string
  textMuted: string
  textSubtle: string
  glow: string
  halo: string
  outline: string
}> = {
  light: {
    background: '#f8fafc',
    surface: '#ffffff',
    ringOuter: '#1e293b',
    ringInner: '#0f172a',
    accent: '#f59e0b',
    accentBright: '#f97316',
    primary: '#0f766e',
    primaryBright: '#14b8a6',
    textPrimary: '#0f172a',
    textMuted: '#1f2937',
    textSubtle: '#475569',
    glow: 'rgba(20, 184, 166, 0.22)',
    halo: 'rgba(14, 116, 144, 0.18)',
    outline: 'rgba(15, 23, 42, 0.12)',
  },
  dark: {
    background: '#0b1120',
    surface: '#11182a',
    ringOuter: '#38bdf8',
    ringInner: '#1d4ed8',
    accent: '#fbbf24',
    accentBright: '#f59e0b',
    primary: '#2dd4bf',
    primaryBright: '#5eead4',
    textPrimary: '#f8fafc',
    textMuted: '#cbd5f5',
    textSubtle: '#94a3b8',
    glow: 'rgba(45, 212, 191, 0.28)',
    halo: 'rgba(37, 99, 235, 0.32)',
    outline: 'rgba(148, 163, 184, 0.16)',
  },
}

export function useResolvedLogoMode(mode: LogoMode): ResolvedLogoMode {
  const [resolved, setResolved] = useState<ResolvedLogoMode>(mode === 'dark' ? 'dark' : 'light')

  useEffect(() => {
    if (mode === 'auto') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      const update = (event: MediaQueryListEvent | MediaQueryList) => {
        setResolved(event.matches ? 'dark' : 'light')
      }

      update(mediaQuery)
      mediaQuery.addEventListener('change', update)

      return () => mediaQuery.removeEventListener('change', update)
    }

    setResolved(mode)
  }, [mode])

  return resolved
}
