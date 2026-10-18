import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import PrivacyPage from '@/app/privacy/page'
import SecurityPage from '@/app/security/page'
import TermsPage from '@/app/terms/page'
import { ANALYTICS_CONSENT_CLAUSE } from '@/lib/consentCopy'
import { LEGAL_DATES } from '@/lib/legalDates'

/**
 * The legal pages say what the code and the hosting do, and their dates move with their text (D-046; CLAUDE.md
 * rule 12; lessons/brand-a-promise-names-what-the-code-enforces.md).
 *
 * 1. /security's claims that nothing in the repository supported stay out (REMOVED_CLAIMS): a Redis cache
 *    (production runs none, ADR-0004), an uptime figure or guarantee (none is offered), firewalls or intrusion
 *    detection (nothing configures either), "all API endpoints" behind authentication (search, company pages and
 *    summaries are public), a Content Security Policy against XSS (the site sends frame-ancestors only), role-based
 *    access control (one administrator flag), and "enterprise-grade" or "industry-standard" in place of a fact. The
 *    waitlist page's Security tile is held to the same list, with its old "No personal financial data stored"
 *    (payment records are kept). Read: /security's rendered text, and every copy literal of app/waitlist/page.tsx.
 *    The planted forms score the reach: main's sentences fail, the page's new sentences pass.
 * 2. The consent dialog's analytics clause and /privacy's analytics cookies line are one constant,
 *    ANALYTICS_CONSENT_CLAUSE (lib/consentCopy.ts), in D-046's words: each of the two places it once, /privacy
 *    renders it, and no other copy literal types its account-id sentence. CookieConsent.spec.tsx reads it as the
 *    dialog's analytics checkbox description.
 * 3. A legal page's text moves only with its date. LEGAL_TEXT lists, per page, each LEGAL_DATES date with a hash of
 *    the text the page rendered under it (the "Last updated" date itself read as {date}), oldest first, and the last
 *    row is today's page: a text change with no new row and no new date fails, a date moved with no text change fails
 *    (a row's date is not the page's, or two rows share a hash), and dates only rise. Out of reach, review-checked: a
 *    new hash written over the last row under its old date instead of appended under a new one.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

type LegalPage = keyof typeof LEGAL_DATES

const PAGES: Record<LegalPage, () => ReactElement> = {
  terms: () => <TermsPage />,
  privacy: () => <PrivacyPage />,
  security: () => <SecurityPage />,
}

/**
 * Each legal page's dated texts, oldest first; append a row (never rewrite one) in the commit that changes a page's
 * text, with the page's LEGAL_DATES key moved to that row's date. The hash is the first 16 hex digits of the SHA-256
 * of pageText() with the page's date read as {date}.
 */
const LEGAL_TEXT: Record<LegalPage, Array<{ date: string; sha256: string }>> = {
  terms: [{ date: 'June 16, 2026', sha256: '82ecb15a746bee66' }],
  privacy: [{ date: 'October 18, 2026', sha256: '628571d3d40dd705' }],
  security: [{ date: 'October 18, 2026', sha256: '166d91ee20efb221' }],
}

/** A rendered page's text: its text nodes in order, joined by a space, whitespace collapsed. */
function pageText(container: HTMLElement): string {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  const parts: string[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.nodeValue ?? '')
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

const rendered = (page: LegalPage) => {
  const { container, unmount } = render(PAGES[page]())
  const text = pageText(container)
  unmount()
  return text
}

const textHash = (text: string, date: string) =>
  createHash('sha256').update(text.split(date).join('{date}')).digest('hex').slice(0, 16)

const REMOVED_CLAIMS: Array<[string, RegExp]> = [
  ['a Redis cache', /\bredis\b/i],
  ['an uptime figure or guarantee', /\b\d{2}(?:\.\d+)?\s?%|\buptime guarantees?\b|\bguaranteed uptime\b/i],
  ['firewalls or intrusion detection', /\bfirewalls?\b|\bintrusion (?:detection|prevention)\b/i],
  ['every API endpoint behind authentication', /\b(?:all|every)(?: of our| the)? API endpoints?\b/i],
  ['a Content Security Policy against XSS', /\b(?:CSP|Content[- ]Security[- ]Policy)\b[^.]*\bXSS\b|\bXSS\b[^.]*\b(?:CSP|Content[- ]Security[- ]Policy)\b/i],
  ['role-based access control', /\brole-based access\b|\bRBAC\b/i],
  ['an adjective in place of a fact', /\benterprise-grade\b|\bindustry-standard\b/i],
  ['no personal financial data', /\bno personal financial data\b/i],
]

const claimsIn = (where: string, text: string) =>
  REMOVED_CLAIMS.filter(([, re]) => re.test(text)).map(([label]) => `${where} (${label}): ${JSON.stringify(text)}`)

/** Every copy literal of a module: strings, templates (`{x}` for each substitution) and JSX text. */
function literals(rel: string): string[] {
  const sf = ts.createSourceFile(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'), ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const out: string[] = []
  const visit = (node: ts.Node) => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) out.push(node.text)
    else if (ts.isTemplateExpression(node)) out.push([node.head.text, ...node.templateSpans.map((s) => `{x}${s.literal.text}`)].join(''))
    else if (ts.isJsxText(node) && !node.containsOnlyTriviaWhiteSpaces) out.push(node.text)
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out.map((text) => text.replace(/\s+/g, ' ').trim())
}

describe("/security says what the code and the hosting do (D-046)", () => {
  it('names none of the claims D-046 removed, and neither does the waitlist page', () => {
    const text = rendered('security')
    expect(text.length).toBeGreaterThan(4000)
    const sentences = text.split(/(?<=[.:;])\s+/)
    const waitlist = literals('app/waitlist/page.tsx')
    expect(waitlist).toContain('Security') // the trust panel's tile title: the scan reads the tile's copy
    expect([...sentences.flatMap((s) => claimsIn('/security', s)), ...waitlist.flatMap((l) => claimsIn('app/waitlist/page.tsx', l))]).toEqual([])
  })

  it("reads main's claims and passes the page's new sentences (a self-check on planted forms)", () => {
    const planted: Array<[string, boolean]> = [
      ['Our Redis cache is configured with authentication and access controls to prevent unauthorized access.', true],
      ['Our application is hosted on secure, enterprise-grade cloud infrastructure with 99.9% uptime guarantees.', true],
      ['We implement firewalls, intrusion detection systems, and other network security measures.', true],
      ['All API endpoints are protected with authentication and authorization mechanisms.', true],
      ['We use Content Security Policy (CSP) headers to prevent XSS attacks.', true],
      ['User permissions are managed through role-based access control (RBAC).', true],
      ['We implement industry-standard security measures to protect your personal information.', true],
      ['Encrypted data in transit and at rest. No personal financial data stored.', true],
      ["The site sends X-Frame-Options DENY and a Content-Security-Policy of frame-ancestors 'none', so other sites cannot show its pages in a frame.", false],
      ["The API's responses under /api carry a Content-Security-Policy of default-src 'none'.", false],
      ['The API caps how often logins, new accounts and filing-text searches can be used. Each API server keeps its own count.', false],
      ['The database runs on Google Cloud SQL, which encrypts the data it stores by default.', false],
      ['Administrator tools need an administrator account, and the API checks Pro features against your plan.', false],
      ['Your data travels over HTTPS and is kept in Google Cloud SQL, which encrypts it at rest. Card details stay with Stripe.', false],
    ]
    expect(planted.map(([sentence]) => claimsIn('planted', sentence).length > 0)).toEqual(planted.map(([, flagged]) => flagged))
  })
})

describe('the consent clause and /privacy say the same thing, from one constant (D-046, F33)', () => {
  it("is D-046's sentence", () => {
    expect(ANALYTICS_CONSENT_CLAUSE).toBe(
      'Usage statistics through PostHog, so we can see which pages work. When you are logged in they are tied to an internal account id.',
    )
  })

  it('the consent dialog and /privacy each place it once, and /privacy renders it', () => {
    for (const rel of ['components/CookieConsent.tsx', 'app/privacy/page.tsx']) {
      const sf = ts.createSourceFile(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      let imported = false
      let placed = 0
      const visit = (node: ts.Node) => {
        if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier) && node.moduleSpecifier.text === '@/lib/consentCopy') {
          const named = node.importClause?.namedBindings
          imported = !!named && ts.isNamedImports(named) && named.elements.some((el) => el.name.text === 'ANALYTICS_CONSENT_CLAUSE' && !el.propertyName)
        }
        if (ts.isJsxExpression(node) && node.expression && ts.isIdentifier(node.expression) && node.expression.text === 'ANALYTICS_CONSENT_CLAUSE') placed++
        ts.forEachChild(node, visit)
      }
      visit(sf)
      expect({ rel, imported, placed }).toEqual({ rel, imported: true, placed: 1 })
    }
    expect(rendered('privacy')).toContain(`Analytics Cookies: ${ANALYTICS_CONSENT_CLAUSE}`)
  })

  it('no other copy types the clause', () => {
    const modules = execFileSync('git', ['ls-files', '--', ...SCAN_DIRS], { cwd: FRONTEND, encoding: 'utf8' })
      .split('\n')
      .filter((rel) => /\.tsx?$/.test(rel) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(rel) && rel !== 'lib/consentCopy.ts')
    expect(modules.length).toBeGreaterThan(300)
    const typed = modules.flatMap((rel) =>
      literals(rel).filter((l) => /\btied to an internal account id\b|\busage statistics through posthog\b/i.test(l)).map((l) => `${rel}: ${l}`),
    )
    expect(typed).toEqual([])
  })
})

describe('a legal page’s date moves with its text (D-046)', () => {
  for (const page of Object.keys(PAGES) as LegalPage[]) {
    it(`${page}: the text rendered today is the one pinned under its LEGAL_DATES date`, () => {
      const date = LEGAL_DATES[page]
      const text = rendered(page)
      expect(text).toContain(`Last updated: ${date}`)
      const rows = LEGAL_TEXT[page]
      expect(
        { date, sha256: textHash(text, date) },
        `the ${page} page's text or date changed: move LEGAL_DATES.${page} to the date of the change and append that date and this hash to LEGAL_TEXT.${page}, in the same commit`,
      ).toEqual(rows[rows.length - 1])
    })
  }

  it('the ledger only appends: each page’s dates rise, and no two of its rows share a text', () => {
    for (const page of Object.keys(PAGES) as LegalPage[]) {
      const rows = LEGAL_TEXT[page]
      const times = rows.map((row) => Date.parse(row.date))
      expect(times.every((t) => Number.isFinite(t)), page).toBe(true)
      expect(times.every((t, i) => i === 0 || t > times[i - 1]), page).toBe(true)
      expect(new Set(rows.map((row) => row.sha256)).size, page).toBe(rows.length)
    }
  })
})
