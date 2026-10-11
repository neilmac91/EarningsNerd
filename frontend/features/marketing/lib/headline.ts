/**
 * Hero headline variants (the design's `headline` tweak). Wired through the repo's existing
 * PostHog feature-flag experiments: A is the default served in HTML (and the `<title>` / `og:title`),
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
    pre: 'Read the filing faster. Keep ',
    accent: 'the source',
    post: ' in view.',
    title: 'Read the filing faster. Keep the source in view',
  },
  // B and C are two of the five brand headlines (docs/voice-and-style.md › Headlines); A survives
  // from the July copy pass as the served default. The accent phrase carries the mark (.en-mark),
  // so it stays short enough never to break across lines at phone width (docs/brand/06-system.md
  // §6, Misuse): on A the mark sits under "the source", the words the device stands for.
  B: {
    pre: 'Read it faster. ',
    accent: 'Check it anyway',
    post: '.',
    title: 'Read it faster. Check it anyway',
  },
  C: {
    pre: 'The summary that ',
    accent: 'shows its work',
    post: '.',
    title: 'The summary that shows its work',
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
