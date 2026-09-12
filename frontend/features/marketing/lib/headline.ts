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
    pre: 'Every number in the filing, ',
    accent: 'traced to the filing',
    post: '.',
    title: 'Every number in the filing, traced to the filing',
  },
  B: {
    pre: 'The 10-K, read for you. ',
    accent: 'Sources included',
    post: '.',
    title: 'The 10-K, read for you. Sources included',
  },
  C: {
    pre: 'Understand any ',
    accent: 'SEC filing',
    post: ' in minutes',
    title: 'Understand any SEC filing in minutes',
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
