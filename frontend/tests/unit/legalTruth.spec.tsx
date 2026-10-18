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
 * rule 12; lessons/brand-a-promise-names-what-the-code-enforces.md, lessons/test-gates-must-be-as-wide-as-their-rule.md).
 *
 * 1. /security's claims that nothing in the repository supported stay out (REMOVED_CLAIMS), each read as its family:
 *    a Redis cache (production runs none, ADR-0004); an uptime figure or guarantee (a percentage beside uptime,
 *    availability or an SLA, or a guarantee of uptime; none is offered); firewalls or intrusion detection or
 *    prevention (nothing configures them); every endpoint behind authentication, with or without "API" (search,
 *    company pages and summaries are public); a Content Security Policy against XSS or cross-site scripting (the site
 *    sends frame-ancestors only); role-based access, permissions or authorisation, or RBAC (one administrator flag);
 *    an adjective in place of a fact (enterprise, military or bank grade or level, industry standard, hyphenated or
 *    not); no financial data stored (payment records are kept); post-incident reviews and vetting the providers
 *    (no process in the repository does either); and an analytics-consent promise not scoped to the browser in its
 *    own sentence (the API sends account events whatever the reader chose: F50). The scan reads /security's rendered
 *    text and the waitlist page's copy (strings and JSX text outside className), sentence by sentence, a sentence
 *    ending only at ".", "!" or "?", so a `<strong>Label:</strong> body` item is read whole. The planted forms run
 *    through the same render, text and splitter and score the reach: main's sentences and their close rewordings fail,
 *    the page's new sentences and class names pass. Out of reach, planted as gaps: a claim split across two sentences,
 *    one said in other words, and an unscoped consent promise in a sentence that also names the browser.
 * 2. The PostHog line says what each half does: PostHog in the browser waits for the reader's choice, and the API's
 *    account events, keyed on the account id, do not.
 * 3. The consent dialog's analytics clause and /privacy's analytics cookies line are one constant,
 *    ANALYTICS_CONSENT_CLAUSE (lib/consentCopy.ts), in D-046's words: each of the two places it once, /privacy
 *    renders it, and no other copy literal types its account-id sentence. CookieConsent.spec.tsx reads it as the
 *    dialog's analytics checkbox description. F33's rule itself holds everywhere: no copy literal under app,
 *    components, features, hooks or lib calls the analytics anonymous.
 * 4. A legal page's date moves with its text. LEGAL_TEXT lists, per page, the dates its text took, oldest first, each
 *    with the hash of the text the page rendered under it (the "Last updated" date itself read as {date}). The gate
 *    holds: the last row is the page as it renders now, under its LEGAL_DATES date, so a changed text or a moved date
 *    fails until the last row says so; each row's hash differs from the row before it, so a row appended for a date
 *    moved with no text change fails, and a later return to an earlier text is recorded by appending; dates rise; and
 *    LEGAL_DATES, the pages rendered here and the ledger list the same pages (checked at run time, since CI does not
 *    type-check the specs). Out of reach, review-checked: the last row edited in place (a new hash, a new date or both
 *    written over it instead of appended), which passes; the diff shows the row rewritten.
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
 * Each legal page's dated texts, oldest first; append a row in the commit that changes a page's text, with the page's
 * LEGAL_DATES key moved to that row's date. The hash is the first 16 hex digits of the SHA-256 of pageText() with the
 * page's date read as {date}.
 */
const LEGAL_TEXT: Record<LegalPage, Array<{ date: string; sha256: string }>> = {
  terms: [{ date: 'June 16, 2026', sha256: '82ecb15a746bee66' }],
  privacy: [{ date: 'October 18, 2026', sha256: '628571d3d40dd705' }],
  security: [{ date: 'October 18, 2026', sha256: 'b07e688cfb36da50' }],
}

/** A rendered tree's text: its text nodes in order, joined by a space, whitespace collapsed. */
function pageText(container: HTMLElement): string {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  const parts: string[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.nodeValue ?? '')
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

const textOf = (element: ReactElement) => {
  const { container, unmount } = render(element)
  const text = pageText(container)
  unmount()
  return text
}

const rendered = (page: LegalPage) => textOf(PAGES[page]())

const textHash = (text: string, date: string) =>
  createHash('sha256').update(text.split(date).join('{date}')).digest('hex').slice(0, 16)

/** A text's sentences: split only where a sentence ends, so a `Label: body` item stays one sentence. */
const sentencesOf = (text: string) => text.split(/(?<=[.!?])\s+/)

const PERCENT = String.raw`\b\d{2,3}(?:\.\d+)?\s?(?:%|percent)`
const CSP = String.raw`(?:\bCSP\b|\bContent[- ]Security[- ]Polic(?:y|ies)\b)`
const XSS = String.raw`(?:\bXSS\b|\bcross[- ]site[- ]scripting\b)`

const REMOVED_CLAIMS: Array<[string, RegExp]> = [
  ['a Redis cache', /\bredis\b/i],
  [
    'an uptime figure or guarantee',
    new RegExp(String.raw`\b(?:uptime|availability|SLA)\b[^.]*${PERCENT}|${PERCENT}[^.]*\b(?:uptime|availability|available|SLA)\b|\buptime guarantees?\b|\bguarantee(?:s|d)?\b[^.]*\buptime\b`, 'i'),
  ],
  ['firewalls or intrusion detection', /\bfirewalls?\b|\bintrusion[- ](?:detection|prevention)\b/i],
  ['every endpoint behind authentication', /\b(?:all|every)\b(?:\s+of)?(?:\s+(?:our|the))?(?:\s+API)?\s+endpoints?\b/i],
  ['a Content Security Policy against XSS', new RegExp(`${CSP}[^.]*${XSS}|${XSS}[^.]*${CSP}`, 'i')],
  ['role-based access control', /\brole[- ]based (?:access|permissions?|authori[sz]ation)\b|\bRBAC\b/i],
  ['an adjective in place of a fact', /\b(?:enterprise|military|bank)[- ](?:grade|level)\b|\bindustry[- ]standard\b/i],
  ['no financial data stored', /\b(?:no|never|not)\b[^.]{0,40}\bfinancial data\b|\bfinancial data\b[^.]{0,40}\b(?:never|not)\b/i],
  ['post-incident reviews', /\bpost[- ]incident (?:reviews?|post[- ]?mortems?)\b/i],
  ['vetting the providers', /\bvet(?:s|ted|ting)?\b/i],
  [
    'an analytics-consent promise not scoped to the browser',
    /^(?!.*\bin your browser\b).*\bonly (?:after|once|when|if) you (?:allow|accept|agree to|consent to|opt in to)\b[^.]*\b(?:analytics|tracking|statistics)\b/i,
  ],
]

const claimsIn = (where: string, text: string) =>
  REMOVED_CLAIMS.filter(([, re]) => re.test(text)).map(([label]) => `${where} (${label}): ${JSON.stringify(text)}`)

/** Every removed claim in a text, read sentence by sentence. */
const claimsInText = (where: string, text: string) => sentencesOf(text).flatMap((sentence) => claimsIn(where, sentence))

/** Every copy literal of a module: strings, templates (`{x}` for each substitution) and JSX text, class names skipped. */
function literals(rel: string): string[] {
  const sf = ts.createSourceFile(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'), ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const out: string[] = []
  const visit = (node: ts.Node) => {
    if (ts.isJsxAttribute(node) && ts.isIdentifier(node.name) && /^(?:className|class)$/.test(node.name.text)) return
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) out.push(node.text)
    else if (ts.isTemplateExpression(node)) out.push([node.head.text, ...node.templateSpans.map((s) => `{x}${s.literal.text}`)].join(''))
    else if (ts.isJsxText(node) && !node.containsOnlyTriviaWhiteSpaces) out.push(node.text)
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out.map((text) => text.replace(/\s+/g, ' ').trim())
}

const copyModules = () =>
  execFileSync('git', ['ls-files', '--', ...SCAN_DIRS], { cwd: FRONTEND, encoding: 'utf8' })
    .split('\n')
    .filter((rel) => /\.tsx?$/.test(rel) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(rel))

/** Analytics called anonymous, in either order: F33's rule (a logged-in reader's statistics carry the account id). */
const ANONYMOUS_ANALYTICS =
  /\banonymous(?:ly)?\b[^.]*\b(?:usage|statistics|analytics|PostHog|tracking|telemetry|data)\b|\b(?:usage|statistics|analytics|PostHog|tracking|telemetry)\b[^.]*\banonymous(?:ly)?\b/i

describe("/security says what the code and the hosting do (D-046)", () => {
  it('names none of the claims D-046 removed, and neither does the waitlist page', () => {
    const text = rendered('security')
    expect(text.length).toBeGreaterThan(4000)
    const waitlist = literals('app/waitlist/page.tsx')
    expect(waitlist).toContain('Security') // the trust panel's tile title: the scan reads the tile's copy
    expect(waitlist.some((l) => /\bmt-\d|\bgrid\b/.test(l))).toBe(false) // and none of its class names
    expect([...claimsInText('/security', text), ...waitlist.flatMap((l) => claimsInText('app/waitlist/page.tsx', l))]).toEqual([])
  })

  it('reads each claim’s family through the page’s own render and splitter, and passes the new sentences (a self-check on planted forms)', () => {
    const planted: Array<[string, boolean | 'gap']> = [
      // Main's sentences.
      ['<p>Our Redis cache is configured with authentication and access controls to prevent unauthorized access.</p>', true],
      ['<p>Our application is hosted on secure, enterprise-grade cloud infrastructure with 99.9% uptime guarantees.</p>', true],
      ['<p>We implement firewalls, intrusion detection systems, and other network security measures.</p>', true],
      ['<p>All API endpoints are protected with authentication and authorization mechanisms.</p>', true],
      ['<p>We use Content Security Policy (CSP) headers to prevent XSS attacks.</p>', true],
      ['<p>User permissions are managed through role-based access control (RBAC).</p>', true],
      ['<p>We implement industry-standard security measures to protect your personal information.</p>', true],
      ['<p>Encrypted data in transit and at rest. No personal financial data stored.</p>', true],
      ['<li>We conduct post-incident reviews to improve our security practices</li>', true],
      ['<p>We carefully vet all third-party services to ensure they meet our security standards.</p>', true],
      ['<li><strong>PostHog:</strong> Usage statistics, only after you allow analytics, and session recordings only if you allow those too</li>', true],
      // Close rewordings (the review's).
      ['<p>We use Content Security Policy headers to prevent cross-site scripting attacks.</p>', true],
      ['<ul><li><strong>Content Security Policy:</strong> Headers that block XSS attacks.</li></ul>', true],
      ['<p>We send a strict CSP; it stops XSS.</p>', true],
      ['<p>Enterprise grade infrastructure, built to industry standard algorithms.</p>', true],
      ['<p>Access is managed with role based access control.</p>', true],
      ['<p>Role-based permissions ensure users only see their data.</p>', true],
      ['<p>We use an intrusion-detection system.</p>', true],
      ['<p>Hosted with 99.9 percent uptime.</p>', true],
      ['<p>We guarantee 100% uptime.</p>', true],
      ['<p>Our hosting offers an uptime SLA of 99.9 percent.</p>', true],
      ['<p>All endpoints are protected with authentication and authorization mechanisms.</p>', true],
      ['<p>All our API endpoints require authentication.</p>', true],
      ['<p>Every endpoint requires you to be logged in.</p>', true],
      ['<p>We use bank-level, military-grade encryption.</p>', true],
      ['<p>We never store personal financial data.</p>', true],
      ['<p>No financial data is stored.</p>', true],
      ['<p>Product analytics, only once you accept tracking.</p>', true],
      // The page's new sentences and look-alikes, which pass.
      ["<p>The site sends X-Frame-Options DENY and a Content-Security-Policy of frame-ancestors 'none', so other sites cannot show its pages in a frame.</p>", false],
      ["<p>The API's responses under /api carry a Content-Security-Policy of default-src 'none'.</p>", false],
      ['<p>The API caps how often logins, new accounts and filing-text searches can be used. Each API server keeps its own count.</p>', false],
      ['<p>The database runs on Google Cloud SQL, which encrypts the data it stores by default.</p>', false],
      ['<p>Administrator tools need an administrator account, and the API checks Pro features against your plan.</p>', false],
      ['<p>Your data travels over HTTPS and is kept in Google Cloud SQL, which encrypts it at rest. Card details stay with Stripe.</p>', false],
      ["<p>Payments go through Stripe Checkout, so your card details never reach EarningsNerd's servers.</p>", false],
      ['<li><strong>PostHog:</strong> Usage statistics: PostHog in your browser runs only after you allow analytics, and records sessions only if you allow that too</li>', false],
      ['<p>Save 20% with annual billing.</p>', false],
      ['<p>max-w-[85%] from-10% via-50%</p>', false],
      // Out of reach.
      ['<p>Our pages use a Content Security Policy. It blocks XSS.</p>', 'gap'],
      ['<p>Nobody outside our network can reach the servers.</p>', 'gap'],
      ['<p>PostHog in your browser runs only after you allow analytics, and so does every server event.</p>', 'gap'],
    ]
    const flagged = planted.map(([html]) => {
      const { container, unmount } = render(<div dangerouslySetInnerHTML={{ __html: html }} />)
      const found = claimsInText('planted', pageText(container))
      unmount()
      return found.length > 0
    })
    expect(flagged).toEqual(planted.map(([, expected]) => expected === true))
  })

  it('the PostHog line says what the browser and the API each send', () => {
    const sentence = sentencesOf(rendered('security')).find((s) => /\bPostHog in your browser runs only after you allow analytics\b/i.test(s))
    expect(sentence, 'the PostHog line scopes the consent to the browser').toBeDefined()
    expect(sentence).toMatch(/\bthe API also records account events\b[^.]*\binternal account id\b[^.]*\bwhether or not you allow analytics\b/i)
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
    const modules = copyModules().filter((rel) => rel !== 'lib/consentCopy.ts')
    expect(modules.length).toBeGreaterThan(300)
    const typed = modules.flatMap((rel) =>
      literals(rel).filter((l) => /\btied to an internal account id\b|\busage statistics through posthog\b/i.test(l)).map((l) => `${rel}: ${l}`),
    )
    expect(typed).toEqual([])
  })

  it('no copy calls the analytics anonymous (F33), and the rule reads its forms (a self-check on planted forms)', () => {
    const modules = copyModules()
    expect(modules.length).toBeGreaterThan(300)
    expect(modules.flatMap((rel) => literals(rel).filter((l) => ANONYMOUS_ANALYTICS.test(l)).map((l) => `${rel}: ${l}`))).toEqual([])
    const planted: Array<[string, boolean]> = [
      ['Help us understand how visitors interact with our website by collecting anonymous usage statistics (PostHog).', true],
      ['Anonymous usage statistics (PostHog) help us improve the site.', true],
      ['We collect anonymous data to improve the product.', true],
      ['Analytics are anonymous.', true],
      ['PostHog tracking stays anonymous.', true],
      ['Anonymous', false],
      ['anonymous', false],
      ['Anonymous visitors can read any summary.', false],
      [ANALYTICS_CONSENT_CLAUSE, false],
    ]
    expect(planted.map(([text]) => ANONYMOUS_ANALYTICS.test(text))).toEqual(planted.map(([, expected]) => expected))
  })
})

describe('a legal page’s date moves with its text (D-046)', () => {
  it('LEGAL_DATES, the pages rendered here and the ledger list the same pages', () => {
    const dated = Object.keys(LEGAL_DATES).sort()
    expect(Object.keys(PAGES).sort()).toEqual(dated)
    expect(Object.keys(LEGAL_TEXT).sort()).toEqual(dated)
  })

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

  it('the ledger reads forward: each page’s dates rise, and each row’s text differs from the row before it', () => {
    for (const page of Object.keys(LEGAL_TEXT) as LegalPage[]) {
      const rows = LEGAL_TEXT[page]
      expect(rows.length, page).toBeGreaterThan(0)
      const times = rows.map((row) => Date.parse(row.date))
      expect(times.every((t) => Number.isFinite(t)), page).toBe(true)
      expect(times.every((t, i) => i === 0 || t > times[i - 1]), page).toBe(true)
      // Against the row before only: a date moved with no text change fails, a return to an earlier text appends.
      expect(rows.every((row, i) => i === 0 || row.sha256 !== rows[i - 1].sha256), page).toBe(true)
    }
  })
})
