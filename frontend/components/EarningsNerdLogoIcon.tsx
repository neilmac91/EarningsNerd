'use client'

import React, { useId } from 'react'
import { earningsNerdColorSchemes, LogoMode, useResolvedLogoMode } from './earningsNerdLogoTheme'

interface EarningsNerdLogoIconProps {
  className?: string
  mode?: LogoMode
}

export default function EarningsNerdLogoIcon({
  className = 'h-10 w-10',
  mode = 'auto',
}: EarningsNerdLogoIconProps) {
  const resolvedMode = useResolvedLogoMode(mode)
  const palette = earningsNerdColorSchemes[resolvedMode]
  const baseId = useId()
  const accentGradientId = `${baseId}-accent`

  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
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
}

