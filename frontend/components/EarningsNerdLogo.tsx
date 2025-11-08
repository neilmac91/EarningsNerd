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
  const haloGradientId = `${baseId}-halo`
  const ringGradientId = `${baseId}-ring`
  const accentGradientId = `${baseId}-accent`
  const innerGlowId = `${baseId}-inner`

  const Icon = () => (
    <svg
      viewBox="0 0 64 64"
      className={iconClassName}
      role="img"
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <radialGradient id={haloGradientId} cx="50%" cy="45%" r="55%">
          <stop offset="10%" stopColor={palette.glow} stopOpacity="0.7" />
          <stop offset="70%" stopColor={palette.halo} stopOpacity="0.4" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <linearGradient id={ringGradientId} x1="28%" y1="0%" x2="78%" y2="98%">
          <stop offset="0%" stopColor={palette.ringOuter} />
          <stop offset="100%" stopColor={palette.ringInner} />
        </linearGradient>
        <linearGradient id={accentGradientId} x1="0%" y1="80%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={palette.primary} />
          <stop offset="60%" stopColor={palette.primaryBright} />
          <stop offset="100%" stopColor={palette.accent} />
        </linearGradient>
        <radialGradient id={innerGlowId} cx="50%" cy="35%" r="65%">
          <stop offset="0%" stopColor={palette.surface} stopOpacity="0.92" />
          <stop offset="60%" stopColor={palette.surface} stopOpacity="0.78" />
          <stop offset="100%" stopColor={palette.background} stopOpacity="0.85" />
        </radialGradient>
      </defs>

      <circle cx="32" cy="32" r="30" fill={`url(#${haloGradientId})`} />
      <circle
        cx="32"
        cy="32"
        r="26.5"
        fill={palette.background}
        stroke={`url(#${ringGradientId})`}
        strokeWidth="1.6"
      />
      <circle cx="32" cy="32" r="22" fill={`url(#${innerGlowId})`} stroke={palette.outline} strokeWidth="0.6" />

      {/* Neural arc */}
      <path
        d="M17 25c3-8 10-13 15-13s11.5 5.2 15 13"
        stroke={palette.textSubtle}
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.55"
      />

      {/* Insight path */}
      <path
        d="M18 40 L26.5 28.5 L33.5 34 L46 22"
        stroke={`url(#${accentGradientId})`}
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {[{ x: 18, y: 40 }, { x: 26.5, y: 28.5 }, { x: 33.5, y: 34 }, { x: 46, y: 22 }].map((point) => (
        <circle key={`${point.x}-${point.y}`} cx={point.x} cy={point.y} r="2.3" fill={palette.accentBright} opacity="0.9" />
      ))}

      {/* Analyst glasses motif */}
      <circle cx="24" cy="34" r="6" fill={palette.surface} stroke={palette.primary} strokeWidth="2.2" />
      <circle cx="40" cy="34" r="6" fill={palette.surface} stroke={palette.primary} strokeWidth="2.2" />
      <path
        d="M30 33.7h4"
        stroke={palette.primaryBright}
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M18.5 34c-1.2 0-2.2 0.8-2.2 2"
        stroke={palette.textSubtle}
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
        opacity="0.4"
      />
      <path
        d="M45.5 34c1.2 0 2.2 0.8 2.2 2"
        stroke={palette.textSubtle}
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
        opacity="0.4"
      />

      {/* Spark highlight */}
      <path
        d="M42 17l1.1 2.3 2.3 1.1-2.3 1.1-1.1 2.3-1.1-2.3-2.3-1.1 2.3-1.1z"
        fill={palette.accent}
        opacity="0.85"
      />
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

