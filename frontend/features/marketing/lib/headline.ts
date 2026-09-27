/**
 * Hero headline variants (the design's `headline` tweak). Wired through the repo's existing
 * PostHog feature-flag experiments (the same `useFeatureFlagVariantKey` pattern as the pricing
 * page's `pricing-experiment`): A is the default served in HTML (and the `<title>` / `og:title`),
 * C is the shipped control the experiment compares against. An unset flag (or PostHog down)
 * renders A, so nothing regresses when the experiment is not configured.
 */
export type HeadlineVariant = 'A' | 'B' | 'C'

export interface Headline {
  pre: string
  accent: string
  post: string
  /** Plain-text form for `<title>` / `og:title`. */
  title: string
}

export const HEADLINES: Record<HeadlineVariant, Headline> = {
  A: {
    pre: 'Read the filing faster. ',
    accent: 'Keep the source in view',
    post: '.',
    title: 'Read the filing faster. Keep the source in view',
  },
  B: {
    pre: 'The 10-K, summarized for you. ',
    accent: 'Source context included',
    post: '.',
    title: 'The 10-K, summarized for you. Source context included',
  },
  C: {
    pre: 'From ',
    accent: 'SEC filing',
    post: ' to structured summary',
    title: 'From SEC filing to structured summary',
  },
}

export const DEFAULT_HEADLINE: HeadlineVariant = 'A'
export const CONTROL_HEADLINE: HeadlineVariant = 'C'

/** PostHog multivariate flag. Variant keys: `A`, `B`, `C` (or `control`, an alias of C). */
export const HEADLINE_FLAG = 'landing-headline-experiment'

export const resolveHeadlineVariant = (flag: unknown): HeadlineVariant => {
  if (flag === 'A' || flag === 'B' || flag === 'C') return flag
  if (flag === 'control') return CONTROL_HEADLINE
  return DEFAULT_HEADLINE
}

export const pageTitleFor = (variant: HeadlineVariant): string =>
  `EarningsNerd | ${HEADLINES[variant].title}`
