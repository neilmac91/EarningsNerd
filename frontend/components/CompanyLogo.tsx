'use client'

import { useCallback, useState } from 'react'

const LOGO_DEV_TOKEN = process.env.NEXT_PUBLIC_LOGO_DEV_TOKEN

function initialsFor(ticker: string | null | undefined): string {
  if (!ticker) return '?'
  const letters = ticker.replace(/[^A-Za-z]/g, '')
  return (letters.slice(0, 2) || ticker.slice(0, 2) || '?').toUpperCase()
}

/**
 * The key Logo.dev reads for a US listing. A dotted class share (`BRK.B`, `BF.B`, the calendar's
 * form) must go dashed: Logo.dev reads `.X` as an exchange suffix, so `BRK.B` answered another
 * company's mark and `BF.B` nothing. Uppercased for one CDN cache key per company.
 */
export function logoDevKey(ticker: string): string {
  return ticker.trim().toUpperCase().replace(/\./g, '-')
}

/**
 * One mark URL at `px` device pixels. `fallback=404` keeps the CDN from answering a missing logo
 * with a generated placeholder of its own (illegible at 20px), so a miss reaches `onError` and the
 * monogram below stays, as designed. `format=png` keeps transparency.
 */
function logoDevUrl(key: string, px: number): string {
  return `https://img.logo.dev/ticker/${encodeURIComponent(key)}?token=${LOGO_DEV_TOKEN}&size=${px}&format=png&fallback=404`
}

interface CompanyLogoProps {
  /** Stock ticker — the only required identity we key logos off everywhere. */
  ticker: string | null | undefined
  /** Full company name, used for the accessible label when available. */
  name?: string | null
  /**
   * Required on purpose, so every call site decides. `true` when the company's name is rendered
   * as text beside the logo (in the same link, option or row): the mark is then hidden from
   * assistive tech, so screen readers don't announce the name twice. `false` when the logo stands
   * alone and its "<name> logo" label is the only way to identify the company.
   */
  decorative: boolean
  /** Side in px. Both the monogram and the real logo render at this fixed size. */
  size?: number
  /** Mark as high-priority for the single above-the-fold logo on a page (e.g. company header). */
  priority?: boolean
  className?: string
}

/**
 * Company mark reused across every surface that shows a ticker. Renders the initials monogram first
 * and only swaps in the real logo once it has loaded, so a missing/slow/failed logo is never a
 * broken image or a layout shift — it just stays on the monogram. The slot is a fixed-size box
 * regardless of outcome, so nothing ever shifts around it.
 *
 * The slot is a white tile with a hairline and a small radius (4px under 28px, else 8px), in both
 * themes: Logo.dev serves two kinds of asset, full-bleed square tiles in the brand's own ground and
 * transparent marks, and a tile keeps both whole (a circle cut the tiles' corners) on the ground the
 * marks were drawn for (a dark mark on the dark theme's tint was invisible; DESIGN_SYSTEM.md §9).
 * The image is offered at exactly 1x, 2x and 3x the slot, so a whole-number pixel ratio draws it
 * 1:1 and a fractional one resamples from the nearest candidate rather than from a 4x oversample.
 */
export default function CompanyLogo({
  ticker,
  name,
  decorative,
  size = 32,
  priority = false,
  className = '',
}: CompanyLogoProps) {
  const key = ticker ? logoDevKey(ticker) : ''
  // Load state is per key: a mounted instance can change ticker in place (the analysis page's
  // picker), and a stale `loaded` would hide the next monogram or a stale `failed` the next mark.
  const [loadedFor, setLoadedFor] = useState('')
  const [failedFor, setFailedFor] = useState('')
  const loaded = loadedFor === key
  const failed = failedFor === key
  // A mark that settled before React hydrated fired `load` or `error` with nobody listening (the
  // landing's chips are server-rendered above the fold): read its state on mount, as next/image does.
  const onMount = useCallback(
    (img: HTMLImageElement | null) => {
      if (!img?.complete) return
      if (img.naturalWidth > 0) setLoadedFor(key)
      else setFailedFor(key)
    },
    [key],
  )

  const showImage = Boolean(LOGO_DEV_TOKEN) && Boolean(key) && !failed
  const label = name ? `${name} logo` : `${ticker || 'Company'} logo`
  const radius = size < 28 ? 'rounded-sm' : 'rounded'

  return (
    <span
      {...(decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': label })}
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden bg-white ring-1 ring-border-light dark:ring-white/10 ${radius} ${className}`}
      style={{ width: size, height: size }}
    >
      {/* The tile is white in both themes (the §9 exemption), so the monogram keeps the light ink in
          both; listed in themePairs.spec.ts's residue, as the Google button's hairline is. */}
      <span
        aria-hidden="true"
        className={`font-semibold text-brand-strong transition-opacity duration-base ${
          loaded ? 'opacity-0' : 'opacity-100'
        }`}
        style={{ fontSize: Math.max(9, Math.round(size * 0.38)) }}
      >
        {initialsFor(ticker)}
      </span>
      {/* A plain img on purpose: a CDN raster at a fixed px size with its own 1x/2x/3x candidates.
          next/image added nothing here (it ran `unoptimized`) and snaps candidates to its size list,
          which hands a 24px slot a 32px asset to resample. */}
      {showImage && (
        // eslint-disable-next-line @next/next/no-img-element -- see the note above
        <img
          key={key}
          ref={onMount}
          src={logoDevUrl(key, size * 2)}
          srcSet={`${logoDevUrl(key, size)} 1x, ${logoDevUrl(key, size * 2)} 2x, ${logoDevUrl(key, size * 3)} 3x`}
          alt=""
          aria-hidden="true"
          width={size}
          height={size}
          decoding="async"
          loading={priority ? 'eager' : 'lazy'}
          fetchPriority={priority ? 'high' : undefined}
          className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-base ${
            loaded ? 'opacity-100' : 'opacity-0'
          }`}
          onLoad={() => setLoadedFor(key)}
          onError={() => setFailedFor(key)}
        />
      )}
    </span>
  )
}
