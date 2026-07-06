import { readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * F3 structural guard — makes the "components/ = ui + chrome ONLY" rule enforced, not just true today.
 *
 * After F3 moved every domain component into features/<domain>/components/, frontend/components/ holds
 * ONLY the reusable UI library (ui/) and app chrome (header/footer/theme/error-boundaries/brand-logos/
 * dev). An eslint rule can't catch file *creation*, so this spec fails the moment a new file lands in
 * components/ — telling the author where it belongs — turning the review-time rule into a structural
 * one (same move that worked for the query-key eslint rule). If you're intentionally adding genuine
 * shared chrome/ui, add it to ALLOWLIST here in the same PR.
 */
const ALLOWLIST = [
  'ui', // the shared UI component library (components/ui/*)
  'ChartErrorBoundary.tsx',
  'CompanyLogo.tsx',
  'CookieConsent.tsx',
  'EarningsNerdLogo.tsx',
  'EarningsNerdLogoIcon.tsx',
  'Footer.tsx',
  'GlobalErrorBoundary.tsx',
  'Header.tsx',
  'SecondaryHeader.tsx',
  'SentryTestButton.tsx',
  'SiteChrome.tsx',
  'ThemeProvider.tsx',
  'ThemeToggle.tsx',
]

const componentsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../components')

describe('components/ stays ui + chrome only (F3 structural guard)', () => {
  const entries = readdirSync(componentsDir)

  it('has no unexpected files — domain components belong in features/<domain>/components/', () => {
    const unexpected = entries.filter((e) => !ALLOWLIST.includes(e))
    expect(
      unexpected,
      `Unexpected entry in components/: ${unexpected.join(', ')}. components/ is the UI library (ui/) ` +
        `+ app chrome ONLY — put a domain component in features/<domain>/components/ instead. If this is ` +
        `genuinely new shared chrome/ui, add it to ALLOWLIST in this spec.`,
    ).toEqual([])
  })

  it('still has every allowlisted chrome file (catches a rename that skips this guard)', () => {
    const missing = ALLOWLIST.filter((e) => !entries.includes(e))
    expect(
      missing,
      `Allowlisted chrome entry missing from components/: ${missing.join(', ')} — update ALLOWLIST if it moved.`,
    ).toEqual([])
  })
})
