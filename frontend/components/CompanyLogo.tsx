'use client'

import { useState } from 'react'
import Image from 'next/image'

const LOGO_DEV_TOKEN = process.env.NEXT_PUBLIC_LOGO_DEV_TOKEN

function initialsFor(ticker: string | null | undefined): string {
  if (!ticker) return '?'
  const letters = ticker.replace(/[^A-Za-z]/g, '')
  return (letters.slice(0, 2) || ticker.slice(0, 2) || '?').toUpperCase()
}

interface CompanyLogoProps {
  /** Stock ticker — the only required identity we key logos off everywhere. */
  ticker: string | null | undefined
  /** Full company name, used for the accessible label when available. */
  name?: string | null
  /** Diameter in px. Both the monogram and the real logo render at this fixed size. */
  size?: number
  /** Mark as high-priority for the single above-the-fold logo on a page (e.g. company header). */
  priority?: boolean
  className?: string
}

/**
 * Company mark reused across every surface that shows a ticker. Renders the
 * initials monogram first and only swaps in the real logo once it has loaded,
 * so a missing/slow/failed logo is never a broken image or a layout shift —
 * it just stays on the monogram. The slot is a fixed-size box regardless of
 * outcome, so nothing ever shifts around it.
 */
export default function CompanyLogo({
  ticker,
  name,
  size = 32,
  priority = false,
  className = '',
}: CompanyLogoProps) {
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)

  const showImage = Boolean(LOGO_DEV_TOKEN) && Boolean(ticker) && !failed
  const label = name ? `${name} logo` : `${ticker || 'Company'} logo`

  return (
    <span
      role="img"
      aria-label={label}
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-strong/15 ring-1 ring-brand-light/30 dark:bg-brand-dark/15 dark:ring-brand-dark/30 ${className}`}
      style={{ width: size, height: size }}
    >
      <span
        aria-hidden="true"
        className={`font-semibold text-brand-strong transition-opacity duration-base dark:text-brand-strong-dark ${
          loaded ? 'opacity-0' : 'opacity-100'
        }`}
        style={{ fontSize: Math.max(9, Math.round(size * 0.38)) }}
      >
        {initialsFor(ticker)}
      </span>
      {showImage && ticker && (
        <Image
          // format=png (broad support) at 2x the render size for retina; Logo.dev is ticker-keyed
          // so no ticker→domain resolution step is needed. Uppercased for consistent CDN cache keys.
          src={`https://img.logo.dev/ticker/${encodeURIComponent(ticker.toUpperCase())}?token=${LOGO_DEV_TOKEN}&size=${size * 2}&format=png&retina=true`}
          alt=""
          aria-hidden="true"
          width={size}
          height={size}
          unoptimized
          priority={priority}
          className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-base ${
            loaded ? 'opacity-100' : 'opacity-0'
          }`}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      )}
    </span>
  )
}
