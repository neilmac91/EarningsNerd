'use client'

import { useEffect } from 'react'
import { useFeatureFlagVariantKey } from 'posthog-js/react'
import BrandEmphasis from './BrandEmphasis'
import {
  DEFAULT_HEADLINE,
  HEADLINES,
  HEADLINE_FLAG,
  pageTitleFor,
  resolveHeadlineVariant,
} from '@/features/marketing/lib/headline'

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
      className="isolate [container-type:inline-size] text-4xl font-semibold leading-[1.1] text-text-primary-light dark:text-text-primary-dark sm:text-5xl lg:text-6xl"
    >
      {headline.pre}
      <BrandEmphasis trailingPeriod={headline.post === '.'}>{headline.accent}</BrandEmphasis>
      {headline.post === '.' ? null : headline.post}
    </h1>
  )
}
