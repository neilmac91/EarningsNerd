/**
 * The site social card: public/og-image.png, rendered from scripts/brand/og-template.html by
 * `npm run brand:assets`. This is the one place its URL is typed (routeMetadata.spec.ts holds it).
 * Bump `?v=` whenever the committed card changes so social scrapers fetch the new pixels.
 *
 * Next replaces a nested `openGraph` or `twitter` object wholesale rather than merging it with the
 * root layout's, so every page that sets its own openGraph carries `images: [SOCIAL_CARD]` too. The
 * company and filing pages carry it as well: the founder declined page-specific cards (D8, decisions
 * log D-040).
 */
export const SOCIAL_CARD = {
  url: '/og-image.png?v=7',
  width: 1200,
  height: 630,
  alt: 'EarningsNerd: the summary that shows its work',
} as const
