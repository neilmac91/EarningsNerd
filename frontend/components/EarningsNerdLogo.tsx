import React from 'react'
import EarningsNerdLogoIcon, { type LogoMode } from './EarningsNerdLogoIcon'

/* Brand lockup: the sage monogram + the two-tone wordmark ("Earnings" ink,
   italic "Nerd" in the brand accent — mirrors public/assets/earningsnerd-logo-*.svg).
   variant="icon-only" renders just the monogram (Header/Footer usage).
   The v1 tagline strip, pulse dot, and gradient text are retired with the
   sage rebrand. Server-renderable: no hooks, no client directive. */

interface EarningsNerdLogoProps {
  className?: string
  iconClassName?: string
  variant?: 'full' | 'icon-only'
  mode?: LogoMode
}

const WORDMARK_INK: Record<LogoMode, { name: string; accent: string }> = {
  auto: {
    name: 'text-text-primary-light dark:text-text-primary-dark',
    accent: 'text-brand-strong dark:text-brand-dark',
  },
  light: { name: 'text-text-primary-light', accent: 'text-brand-strong' },
  dark: { name: 'text-text-primary-dark', accent: 'text-brand-dark' },
}

export default function EarningsNerdLogo({
  className = '',
  iconClassName = 'h-8 w-8',
  variant = 'full',
  mode = 'auto',
}: EarningsNerdLogoProps) {
  if (variant === 'icon-only') {
    return <EarningsNerdLogoIcon className={iconClassName} mode={mode} />
  }

  const ink = WORDMARK_INK[mode]
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <EarningsNerdLogoIcon className={iconClassName} mode={mode} />
      <span className={`text-lg font-bold leading-none ${ink.name}`}>
        Earnings
        <em className={`italic ${ink.accent}`}>Nerd</em>
      </span>
    </span>
  )
}
