import React from 'react'
import EarningsNerdLogoIcon, { type LogoMode } from './EarningsNerdLogoIcon'

/* Brand lockup — the ONE wordmark source (codified v3, Q1 decision).
   Sage monogram + two-tone wordmark: "Earnings" in the primary ink, italic
   "Nerd" in the brand accent — mirrors public/assets/earningsnerd-logo-*.svg.
   NEVER hand-compose `Earnings<em>Nerd</em>` at a call site (Header and
   AuthShell did pre-v3 and drifted in size/tracking) — render this component.

   variant="full"      monogram + wordmark (auth shell, marketing chrome)
   variant="icon-only" just the monogram (Footer; Header below `sm`)
   variant="wordmark"  just the wordmark — pair with a separate icon-only
                       render when the two halves show/hide independently
                       (the Header hides the wordmark below `sm`).

   Size the wordmark via wordmarkClassName with SCALE sizes only (text-lg /
   text-xl…) — the fontSize ramp already carries the right letter-spacing;
   never add tracking-* here. Server-renderable: no hooks, no client directive. */

interface EarningsNerdLogoProps {
  className?: string
  iconClassName?: string
  /** Scale-size + visibility utilities for the wordmark, e.g. "hidden text-xl sm:inline". */
  wordmarkClassName?: string
  variant?: 'full' | 'icon-only' | 'wordmark'
  mode?: LogoMode
}

const WORDMARK_INK: Record<LogoMode, { name: string; accent: string }> = {
  auto: {
    name: 'text-text-primary-light dark:text-text-primary-dark',
    accent: 'text-brand-strong dark:text-brand-strong-dark',
  },
  light: { name: 'text-text-primary-light', accent: 'text-brand-strong' },
  dark: { name: 'text-text-primary-dark', accent: 'text-brand-strong-dark' },
}

function Wordmark({ mode, className }: { mode: LogoMode; className: string }) {
  const ink = WORDMARK_INK[mode]
  return (
    <span className={`font-semibold leading-none ${ink.name} ${className}`}>
      Earnings
      <em className={`italic ${ink.accent}`}>Nerd</em>
    </span>
  )
}

export default function EarningsNerdLogo({
  className = '',
  iconClassName = 'h-8 w-8',
  wordmarkClassName = 'text-lg',
  variant = 'full',
  mode = 'auto',
}: EarningsNerdLogoProps) {
  if (variant === 'icon-only') {
    return <EarningsNerdLogoIcon className={iconClassName} mode={mode} />
  }
  if (variant === 'wordmark') {
    return <Wordmark mode={mode} className={`${wordmarkClassName} ${className}`} />
  }
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <EarningsNerdLogoIcon className={iconClassName} mode={mode} />
      <Wordmark mode={mode} className={wordmarkClassName} />
    </span>
  )
}
