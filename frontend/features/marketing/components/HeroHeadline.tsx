'use client'

import { useEffect } from 'react'
import localFont from 'next/font/local'
import { useFeatureFlagVariantKey } from 'posthog-js/react'
import {
  DEFAULT_HEADLINE,
  HEADLINES,
  HEADLINE_FLAG,
  pageTitleFor,
  resolveHeadlineVariant,
} from '@/features/marketing/lib/headline'

// A separate face keeps the approved hero italic out of the wordmark and shared Inter loaders.
const heroItalic = localFont({
  src: '../../../scripts/brand/fonts/Inter-Variable-Italic-latin.woff2',
  weight: '100 900',
  style: 'italic',
  display: 'swap',
  variable: '--font-hero-italic',
  adjustFontFallback: false,
})

/**
 * The H1 (the page's LCP element). Server HTML always carries the default variant (A), which is
 * also what `<title>` / `og:title` state; once PostHog resolves the `landing-headline-experiment`
 * flag on the client, B or C swap in and the document title follows (a display-only flag, with
 * the control arm C).
 */
export default function HeroHeadline() {
  const variant = resolveHeadlineVariant(useFeatureFlagVariantKey(HEADLINE_FLAG))
  const headline = HEADLINES[variant]

  useEffect(() => {
    if (variant !== DEFAULT_HEADLINE) document.title = pageTitleFor(variant)
  }, [variant])

  return (
    <h1
      id="hero-h"
      data-headline-variant={variant}
      className="text-4xl font-semibold leading-[1.1] text-text-primary-light dark:text-text-primary-dark sm:text-5xl lg:text-6xl"
    >
      {headline.pre}
      {/* C5 is specific to “the source”; the other experiment arms keep the shared mark. */}
      <span className={`en-mark ${variant === DEFAULT_HEADLINE ? `${heroItalic.variable} en-hero-emphasis` : ''}`}>
        {headline.accent}
      </span>
      {headline.post}
    </h1>
  )
}
