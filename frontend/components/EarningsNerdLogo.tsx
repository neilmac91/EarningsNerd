'use client'

import React, { useId } from 'react'
import { earningsNerdColorSchemes, LogoMode, useResolvedLogoMode } from './earningsNerdLogoTheme'

interface EarningsNerdLogoProps {
  className?: string
  iconClassName?: string
  variant?: 'full' | 'icon-only'
  mode?: LogoMode
  hideTagline?: boolean
}

export default function EarningsNerdLogo({
  className = '',
  iconClassName = 'h-12 w-12',
  variant = 'full',
  mode = 'auto',
  hideTagline = false,
}: EarningsNerdLogoProps) {
  const resolvedMode = useResolvedLogoMode(mode)
  const palette = earningsNerdColorSchemes[resolvedMode]
  const baseId = useId()
  const accentGradientId = `${baseId}-accent`

  const Icon = () => (
    <svg
      viewBox="0 0 64 64"
      className={iconClassName}
      role="img"
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id={accentGradientId} x1="0%" y1="80%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={palette.primary} />
          <stop offset="60%" stopColor={palette.primaryBright} />
          <stop offset="100%" stopColor={palette.accent} />
        </linearGradient>
      </defs>

      <circle cx="32" cy="32" r="26" fill={palette.surface} stroke={palette.ringOuter} strokeWidth="2" />
      <path
        d="M18 40 L28 30 L36 35 L46 22"
        stroke={`url(#${accentGradientId})`}
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="46" cy="22" r="3.2" fill={palette.accentBright} />
    </svg>
  )

  if (variant === 'icon-only') {
    return <Icon />
  }

  return (
    <div className={`inline-flex items-center gap-6 ${className}`}>
      <div className="relative flex flex-shrink-0 items-center justify-center">
        <Icon />
        <span
          className="absolute -bottom-1.5 -right-1.5 inline-flex h-3 w-3 animate-[pulse_2s_ease-in-out_infinite] rounded-full"
          style={{ background: palette.accentBright, boxShadow: `0 0 12px ${palette.accent}` }}
          aria-hidden="true"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline gap-2">
          <span
            className="text-[1.45rem] font-semibold leading-none tracking-tight"
            style={{ color: palette.textPrimary }}
          >
            Earnings
          </span>
          <span
            className="text-[1.45rem] font-semibold leading-none tracking-tight"
            style={{
              color: palette.primaryBright,
              backgroundImage: `linear-gradient(118deg, ${palette.primaryBright} 0%, ${palette.accent} 90%)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Nerd
          </span>
        </div>
        {!hideTagline && (
          <div className="flex items-center gap-2 text-[0.7rem] font-medium uppercase tracking-[0.32em]">
            <span style={{ color: palette.textSubtle }}>AI Earnings Intelligence</span>
            <span
              className="inline-flex h-[2px] w-6 rounded-full"
              style={{ background: `linear-gradient(90deg, ${palette.primaryBright}, ${palette.accent})` }}
              aria-hidden="true"
            />
            <span style={{ color: palette.textMuted }}>SEC Filings Decoded</span>
          </div>
        )}
      </div>
    </div>
  )
}

