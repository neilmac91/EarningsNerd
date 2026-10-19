import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import PrivacyPage from '@/app/privacy/page'
import SecurityPage from '@/app/security/page'
import TermsPage from '@/app/terms/page'
import { ACCOUNT_EVENTS_DISCLOSURE, ANALYTICS_CONSENT_CLAUSE } from '@/lib/consentCopy'
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
 *    own sentence (the API sends account events whatever the reader chose: D-051). The scan reads /security's rendered
 *    text and the waitlist page's copy (strings and JSX text outside className), sentence by sentence, a sentence
 *    ending only at ".", "!" or "?", so a `<strong>Label:</strong> body` item is read whole. The planted forms run
 *    through the same render, text and splitter and score the reach: main's sentences and their close rewordings fail,
 *    the page's new sentences and class names pass. Out of reach, planted as gaps: a claim split across two sentences,
 *    one said in other words, and an unscoped consent promise in a sentence that also names the browser.
 * 2. The account events (D-051, F50). /security's PostHog line scopes the consent to the browser, and a sentence of
 *    its own, ACCOUNT_EVENTS_DISCLOSURE (lib/consentCopy.ts), names no provider and says the service records how
 *    accounts use it against the internal account id, whatever the reader chose. /security and /privacy each place
 *    it once and render it, and no other copy literal types it. Each example it gives stands on events the API sends
 *    with the account id and no consent read (EVENTS_BY_EXAMPLE): an example with none fails, and so does an event no
 *    caller sends any more. The reader of backend/app takes each capture_event call's event, each payload tuple
 *    `(str(<id>), <event>, {...})` the Stripe webhook hands to capture_event, and each call to the two inference
 *    wrappers; capture_funnel_event's events wait for the summary stream's consent and do not count; docstrings and
 *    comments are skipped. Planted modules score the reader.
 * 3. The consent dialog's analytics clause and /privacy's analytics cookies line are one constant,
 *    ANALYTICS_CONSENT_CLAUSE (lib/consentCopy.ts), in D-046's words: each of the two places it once, /privacy
 *    renders it, and no other copy literal types its account-id sentence. CookieConsent.spec.tsx reads it as the
 *    dialog's analytics checkbox description. F33's rule itself holds everywhere: no copy literal under app,
 *    components, features, hooks or lib calls the analytics anonymous.
 * 4. A legal page's date moves with its text. LEGAL_TEXT lists, per page, the dates its text took, oldest first, each
 *    with the hash of the text the page rendered under it (the "Last updated" date itself read as {date}). The gate
 *    holds: the last row is the page as it renders now, under its LEGAL_DATES date, so a changed text or a moved date
 *    fails until the last row says so; each row's hash differs from the row before it, so a row appended for a date
 *    moved with no text change fails, and a later return to an earlier text is recorded by appending; dates never
 *    fall, and a row may share the day of the row before it, since the page shows a day and a second change that day
 *    leaves it true (two pull requests can each change a page on one day); and LEGAL_DATES, the pages rendered here
 *    and the ledger list the same pages (checked at run time, since CI does not type-check the specs). Out of reach,
 *    review-checked: the last row edited in place (a new hash, a new date or both written over it instead of
 *    appended), which passes; the diff shows the row rewritten.
 * 5. A /security claim that stands on a document, not the code, names it in a comment beside the claim,
 *    `{/* Source: <path> §<n>, "<heading>" ... *\/}`, and the document must exist, hold that numbered section, and
 *    name each step the claim names (SOURCED_STEPS): the runbook bullet stands on tasks/security_privacy_runbook.md
 *    §3, whose steps contain and assess, gather evidence and rotate keys. Planted documents score the reader: a
 *    missing file, a renamed heading and a missing step fail.
 * 6. The audit-log item names only what an audit_logs row records (AUDITED): each thing it names stands on actions
 *    the backend writes, read from each create_audit_log call and each audit_service helper another module calls.
 *    Administrator actions are named one by one, since six of them write a log line and no row
 *    (admin_filing_service.py's filing maintenance and stale-XBRL bulk reset, the XBRL cache clear, the test mail).
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const REPO = path.resolve(FRONTEND, '..')
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
  privacy: [
    { date: 'October 18, 2026', sha256: '628571d3d40dd705' },
    { date: 'October 19, 2026', sha256: '40cc493ae300e1db' },
  ],
  security: [
    { date: 'October 18, 2026', sha256: 'b07e688cfb36da50' },
    { date: 'October 19, 2026', sha256: 'b0d7d5339d1fd802' },
  ],
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

/** How a module brings in a constant of lib/consentCopy.ts: whether it imports it by name, and how many JSX
    expressions place it. */
function placements(rel: string, name: string) {
  const sf = ts.createSourceFile(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  let imported = false
  let placed = 0
  const visit = (node: ts.Node) => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier) && node.moduleSpecifier.text === '@/lib/consentCopy') {
      const named = node.importClause?.namedBindings
      imported = !!named && ts.isNamedImports(named) && named.elements.some((el) => el.name.text === name && !el.propertyName)
    }
    if (ts.isJsxExpression(node) && node.expression && ts.isIdentifier(node.expression) && node.expression.text === name) placed++
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { rel, imported, placed }
}

/** backend/app's Python modules (tracked files), by repository path. */
const backendModules = (): Record<string, string> =>
  Object.fromEntries(
    execFileSync('git', ['ls-files', '--', 'backend/app'], { cwd: REPO, encoding: 'utf8' })
      .split('\n')
      .filter((rel) => rel.endsWith('.py'))
      .map((rel) => [rel, readFileSync(path.join(REPO, rel), 'utf8')]),
  )

/** A Python module's code, its docstrings and comments dropped, so a mention is not read as a call. */
const pythonCode = (src: string) => src.replace(/"""[\s\S]*?"""|'''[\s\S]*?'''/g, '""').replace(/(^|\s)#.*$/gm, '$1')

/** The PostHog wrappers that send one event each, and the constant that names it. */
const EVENT_WRAPPERS: Record<string, string> = {
  capture_copilot_inference: 'EVENT_COPILOT_INFERENCE',
  capture_analysis_inference: 'EVENT_ANALYSIS_INFERENCE',
}

/**
 * The events the API sends with an account id whatever the reader chose: the event of each capture_event call, of
 * each payload tuple `(str(<id>), <event>, {...})` (the Stripe webhook collects them and hands each to capture_event
 * after its commit), and of each call to an inference wrapper. capture_funnel_event is not read: the summary stream
 * calls it only when the reader allowed analytics (routers/summaries.py, analytics_consent). The client module's own
 * calls are its wrappers' bodies, so they count only through a caller.
 */
function eventsSent(modules: Record<string, string>): Set<string> {
  const constants = new Map<string, string>()
  for (const src of Object.values(modules)) {
    for (const [, name, value] of pythonCode(src).matchAll(/^(EVENT_[A-Z_]+)\s*=\s*"([a-z_$]+)"/gm)) constants.set(name, value)
  }
  const EVENT = String.raw`("[a-z_$]+"|EVENT_[A-Z_]+)`
  const SENDS = [
    new RegExp(String.raw`\bcapture_event\(\s*(?:str\([^()]*\)|[a-z_][\w.]*)\s*,\s*${EVENT}`, 'g'),
    new RegExp(String.raw`(?<![\w.])\(\s*str\([^()]*\)\s*,\s*${EVENT}\s*,\s*\{`, 'g'),
  ]
  const sent = new Set<string>()
  for (const [rel, src] of Object.entries(modules)) {
    if (/(?:^|\/)posthog_client\.py$/.test(rel)) continue
    const code = pythonCode(src)
    for (const re of SENDS) {
      for (const [, token] of code.matchAll(re)) {
        const event = token.startsWith('"') ? token.slice(1, -1) : constants.get(token)
        if (event) sent.add(event)
      }
    }
    for (const [wrapper, constant] of Object.entries(EVENT_WRAPPERS)) {
      const event = constants.get(constant)
      if (event && new RegExp(String.raw`\b${wrapper}\(`).test(code)) sent.add(event)
    }
  }
  return sent
}

/** Each example the account-events sentence gives, and the events that make it true. */
const EVENTS_BY_EXAMPLE: Record<string, string[]> = {
  'sign-ups': ['signup_completed', 'invite_redeemed'],
  'plan changes': ['subscription_activated', 'trial_started'],
  payments: ['invoice_payment_recorded'],
  feedback: ['feedback_submitted'],
  'feature use': ['copilot_inference_cost', 'analysis_inference_cost', 'alert_email_clicked'],
}

/** The examples a sentence gives: the list between "such as" and "against your internal account id". */
const examplesOf = (sentence: string) => sentence.match(/\bsuch as (.+?), against your internal account id\b/)?.[1].split(/, | and /) ?? []

/** An example no event stands behind, or an event of an example that no caller sends. */
const exampleFaults = (examples: string[], sent: Set<string>) =>
  examples.flatMap((example) =>
    !Object.keys(EVENTS_BY_EXAMPLE).includes(example)
      ? [`"${example}": no capture_event caller is known to send it`]
      : EVENTS_BY_EXAMPLE[example].filter((event) => !sent.has(event)).map((event) => `"${example}": no capture_event caller sends ${event}`),
  )

/** The /security claims that stand on a document, and the steps each names, as the document's bold step labels say them. */
const SOURCED_STEPS: Record<string, string[]> = {
  'A written runbook covers containing it, finding what it touched, gathering evidence and rotating keys': ['Contain', 'assess', 'Evidence', 'Rotate'],
}

/** A `{/* Source: <path> §<n>, "<heading>" ... *\/}` comment and the list item right after it, in a page's source. */
const SOURCE_COMMENT = /\{\/\*\s*Source:\s*(\S+)\s+§(\d+),\s*"([^"]+)"[^*]*\*\/\}\s*<li>([^<]+)<\/li>/g

const escapeRe = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** What a source lacks: the file, its numbered section (a heading `## <n>. <heading>`), or a step the claim names (a
    numbered item of that section whose bold label holds the word). */
function sourceFaults(rel: string, doc: string | null, section: string, heading: string, steps: string[]): string[] {
  if (doc === null) return [`${rel} is missing`]
  const lines = doc.split('\n')
  const start = lines.findIndex((line) => new RegExp(String.raw`^#{1,6}\s+${section}\.\s+${escapeRe(heading)}\b`).test(line))
  if (start < 0) return [`${rel} has no §${section} "${heading}" heading`]
  const next = lines.findIndex((line, i) => i > start && /^#{1,6}\s/.test(line))
  const labels = lines.slice(start + 1, next < 0 ? undefined : next).flatMap((line) => line.match(/^\s*\d+\.\s+\*\*(.+?)\*\*/)?.[1] ?? [])
  return steps
    .filter((step) => !labels.some((label) => new RegExp(String.raw`\b${escapeRe(step)}\b`, 'i').test(label)))
    .map((step) => `${rel} §${section} names no "${step}" step`)
}

/** What the audit-log item names, and the audit_logs actions the backend writes for each. */
const AUDITED: Record<string, string[]> = {
  registrations: ['register'],
  logins: ['login_success', 'oauth_login'],
  'failed logins': ['login_failed'],
  logouts: ['logout'],
  'data exports': ['data_exported'],
  'account deletions': ['user_deleted'],
  "administrators' invites": ['invite_minted', 'invite_revoked', 'invite_resent'],
  "administrators' feedback status changes": ['feedback_status_changed'],
  "administrators' new free accounts": ['free_account_created'],
}

/** The audit_logs actions the backend writes: each create_audit_log call's action, and the action of each audit_service
    helper another module calls. */
function auditActionsWritten(modules: Record<string, string>): Set<string> {
  const isService = (rel: string) => /(?:^|\/)audit_service\.py$/.test(rel)
  const helpers = new Map<string, string>()
  for (const [rel, src] of Object.entries(modules)) {
    if (!isService(rel)) continue
    for (const chunk of pythonCode(src).split(/^def /m).slice(1)) {
      const name = chunk.match(/^(log_\w+)\(/)?.[1]
      const action = chunk.match(/\baction="(\w+)"/)?.[1]
      if (name && action) helpers.set(name, action)
    }
  }
  const written = new Set<string>()
  for (const [rel, src] of Object.entries(modules)) {
    if (isService(rel)) continue
    const code = pythonCode(src)
    for (const call of code.matchAll(/\bcreate_audit_log\b/g)) {
      const action = code.slice(call.index, (call.index ?? 0) + 600).match(/\baction="(\w+)"/)?.[1]
      if (action) written.add(action)
    }
    for (const [name, action] of helpers) if (new RegExp(String.raw`\b${name}\(`).test(code)) written.add(action)
  }
  return written
}

/** What an audit-log item names: the list before "are written to an audit log", and the administrators' list after. */
function auditNames(item: string): string[] {
  const m = item.match(/^(.+?) (?:are|is) written to an audit log(?:, and so are administrators['’] (.+))?$/)
  if (!m) return [item]
  const list = (text: string) => text.split(/, | and /).map((name) => name.trim().toLowerCase())
  return [...list(m[1]), ...(m[2] ? list(m[2]).map((name) => `administrators' ${name}`) : [])]
}

/** A thing the item names that no audit_logs row records, or an action of it that nothing writes. */
const auditFaults = (item: string, written: Set<string>) =>
  auditNames(item).flatMap((name) =>
    !Object.keys(AUDITED).includes(name)
      ? [`"${name}": no audit_logs row is known to record it`]
      : AUDITED[name].filter((action) => !written.has(action)).map((action) => `"${name}": nothing writes the ${action} row`),
  )

/** What breaks a page's ledger: an unreadable date, a date that falls, or a text that repeats the row before. A row may
    share the day of the row before it: the page shows a day, and a second change that day leaves it true. */
function ledgerFaults(rows: Array<{ date: string; sha256: string }>): string[] {
  const faults: string[] = []
  rows.forEach((row, i) => {
    const time = Date.parse(row.date)
    if (!Number.isFinite(time)) faults.push(`row ${i + 1} has no readable date`)
    else if (i > 0 && time < Date.parse(rows[i - 1].date)) faults.push(`row ${i + 1} is dated before the row above it`)
    if (i > 0 && row.sha256 === rows[i - 1].sha256) faults.push(`row ${i + 1} repeats the text of the row before it`)
  })
  return faults
}

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

  it('the PostHog line scopes the consent to the browser', () => {
    const sentence = sentencesOf(rendered('security')).find((s) => /\bPostHog in your browser runs only after you allow analytics\b/i.test(s))
    expect(sentence, 'the PostHog line scopes the consent to the browser').toBeDefined()
  })

  it('a claim that stands on a document names it beside the claim, and the document holds the section and its steps (a self-check on planted documents)', () => {
    const source = readFileSync(path.join(FRONTEND, 'app/security/page.tsx'), 'utf8')
    const sourced = [...source.matchAll(SOURCE_COMMENT)]
    expect(sourced.map((m) => m[4]), 'each sourced claim names its document beside it').toEqual(Object.keys(SOURCED_STEPS))
    const text = rendered('security')
    for (const [, rel, section, heading, claim] of sourced) {
      expect(text).toContain(claim)
      const file = path.join(REPO, rel)
      expect(sourceFaults(rel, existsSync(file) ? readFileSync(file, 'utf8') : null, section, heading, SOURCED_STEPS[claim])).toEqual([])
    }
    const doc = [
      '## 3. Breach-notification readiness (GDPR Art. 33/34)',
      '',
      'Minimal runbook:',
      '1. **Contain & assess** - what data, how many subjects?',
      '2. **Clock starts** when you become aware.',
      '3. **Evidence** - audit_logs, application logs, Sentry.',
      '4. **Rotate** - SECRET_KEY, and any leaked keys.',
      '',
      '## 4. Data retention',
      '1. **Rotate** - a step of another section.',
    ].join('\n')
    const steps = ['Contain', 'assess', 'Evidence', 'Rotate']
    const faults = (text: string | null) => sourceFaults('r.md', text, '3', 'Breach-notification readiness', steps)
    expect(faults(doc)).toEqual([])
    expect(faults(null)).toEqual(['r.md is missing'])
    expect(faults(doc.replace('Breach-notification readiness', 'Breach readiness'))).toEqual(['r.md has no §3 "Breach-notification readiness" heading'])
    expect(faults(doc.replace('4. **Rotate** - SECRET_KEY, and any leaked keys.\n', ''))).toEqual(['r.md §3 names no "Rotate" step'])
    expect(faults(doc.replace('**Contain & assess**', '**Assess**'))).toEqual(['r.md §3 names no "Contain" step'])
  })

  it('the audit-log item names only what an audit_logs row records (a self-check on planted items and modules)', () => {
    const { container, unmount } = render(<SecurityPage />)
    const item = [...container.querySelectorAll('li')].map((li) => (li.textContent ?? '').replace(/\s+/g, ' ').trim()).find((t) => /\baudit log\b/.test(t))
    unmount()
    expect(item).toBeDefined()
    const written = auditActionsWritten(backendModules())
    expect(auditFaults(item ?? '', written)).toEqual([])
    const planted: Array<[string, string[]]> = [
      // Round 2's item, and a rewording that names an administrator action no row records.
      ['Registrations, logins, failed logins, logouts, data exports, account deletions and administrator actions are written to an audit log', ['"administrator actions": no audit_logs row is known to record it']],
      ["Logins are written to an audit log, and so are administrators' summary deletions", [`"administrators' summary deletions": no audit_logs row is known to record it`]],
      ['Registrations and logins are written to an audit log', []],
    ]
    for (const [text, faults] of planted) expect(auditFaults(text, written), text).toEqual(faults)
    const fromPlanted = auditActionsWritten({
      'app/services/audit_service.py': [
        'def create_audit_log(db, action):',
        '    """>>> create_audit_log(db, action="in_a_docstring")"""',
        'def log_register(db):',
        '    return create_audit_log(db, action="register")',
        'def log_unused(db):',
        '    return create_audit_log(db, action="never_called")',
      ].join('\n'),
      'app/routers/a.py': [
        'audit_service.log_register(db)',
        'audit_service.create_audit_log(',
        '    db,',
        '    action="invite_minted",',
        ')',
        '# create_audit_log(db, action="commented_out")',
        'logger.info(f"Admin {actor.id} deleted summary for filing {filing_id}")',
      ].join('\n'),
    })
    expect([...fromPlanted].sort()).toEqual(['invite_minted', 'register'])
  })
})

describe('the account events have a sentence of their own, true of the API (D-051, F50)', () => {
  it('names no provider, and says the recording does not wait for the analytics choice', () => {
    expect(ACCOUNT_EVENTS_DISCLOSURE).not.toMatch(/\b(?:PostHog|Stripe|Resend|DeepSeek|Sentry|Vercel|Google)\b/i)
    expect(ACCOUNT_EVENTS_DISCLOSURE).toMatch(/\bagainst your internal account id\b[^.]*\. This does not depend on your analytics choice\.$/)
  })

  it('/security and /privacy each place it once, and render it', () => {
    for (const rel of ['app/security/page.tsx', 'app/privacy/page.tsx']) {
      expect(placements(rel, 'ACCOUNT_EVENTS_DISCLOSURE')).toEqual({ rel, imported: true, placed: 1 })
    }
    for (const page of ['security', 'privacy'] as const) expect(rendered(page)).toContain(ACCOUNT_EVENTS_DISCLOSURE)
  })

  it('no other copy types it', () => {
    const modules = copyModules().filter((rel) => rel !== 'lib/consentCopy.ts')
    expect(modules.length).toBeGreaterThan(300)
    const typed = modules.flatMap((rel) =>
      literals(rel).filter((l) => /\brecords how accounts use it\b|\bdoes not depend on your analytics choice\b/i.test(l)).map((l) => `${rel}: ${l}`),
    )
    expect(typed).toEqual([])
  })

  it('each example it gives stands on events the API sends with the account id, whatever the reader chose (a self-check on planted modules)', () => {
    const examples = examplesOf(ACCOUNT_EVENTS_DISCLOSURE)
    expect(exampleFaults(examples, eventsSent(backendModules()))).toEqual([])
    expect(examples, 'EVENTS_BY_EXAMPLE lists the examples the sentence gives, no more').toEqual(Object.keys(EVENTS_BY_EXAMPLE))
    const sent = eventsSent({
      'app/services/posthog_client.py': [
        'EVENT_SIGNED_UP = "signed_up"',
        'EVENT_COPILOT_INFERENCE = "copilot_inference_cost"',
        'EVENT_ANALYSIS_INFERENCE = "analysis_inference_cost"',
        'def capture_copilot_inference(distinct_id):',
        '    capture_event(distinct_id, EVENT_COPILOT_INFERENCE, {})',
      ].join('\n'),
      'app/routers/a.py': [
        'capture_event(',
        '    str(user.id),',
        '    EVENT_SIGNED_UP,',
        '    {"invited": True},',
        ')',
        'capture_event(str(user.id), "literal_sent", {"type": kind})',
        'analytics.append((str(user.id), "tuple_sent", {"plan": plan}))',
        'capture_funnel_event(str(user.id), "funnel_only", {})',
        '# capture_event(str(user.id), "commented_out", {})',
        '"""capture_event(str(user.id), "in_a_docstring", {})"""',
        'capture_analysis_inference(distinct_id=str(user.id), model=model)',
      ].join('\n'),
    })
    expect([...sent].sort()).toEqual(['analysis_inference_cost', 'literal_sent', 'signed_up', 'tuple_sent'])
    expect(exampleFaults(['sign-ups', 'searches'], new Set(['signup_completed']))).toEqual([
      '"sign-ups": no capture_event caller sends invite_redeemed',
      '"searches": no capture_event caller is known to send it',
    ])
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
      expect(placements(rel, 'ANALYTICS_CONSENT_CLAUSE')).toEqual({ rel, imported: true, placed: 1 })
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

  it('the ledger reads forward: no page’s date falls, and each row’s text differs from the row before it', () => {
    for (const page of Object.keys(LEGAL_TEXT) as LegalPage[]) {
      expect(LEGAL_TEXT[page].length, page).toBeGreaterThan(0)
      expect(ledgerFaults(LEGAL_TEXT[page]), page).toEqual([])
    }
    // The rule on planted ledgers: a revert (A, B, then A again) appends, and so does a second change on one day; a
    // date moved with no text change, a falling date and an unreadable date fail.
    const A = 'aaaaaaaaaaaaaaaa'
    const B = 'bbbbbbbbbbbbbbbb'
    expect(ledgerFaults([{ date: 'June 16, 2026', sha256: A }, { date: 'November 2, 2026', sha256: B }, { date: 'December 7, 2026', sha256: A }])).toEqual([])
    expect(ledgerFaults([{ date: 'October 18, 2026', sha256: A }, { date: 'October 19, 2026', sha256: B }, { date: 'October 19, 2026', sha256: A }])).toEqual([])
    expect(ledgerFaults([{ date: 'June 16, 2026', sha256: A }, { date: 'November 2, 2026', sha256: A }])).toEqual(['row 2 repeats the text of the row before it'])
    expect(ledgerFaults([{ date: 'October 19, 2026', sha256: A }, { date: 'October 19, 2026', sha256: A }])).toEqual(['row 2 repeats the text of the row before it'])
    expect(ledgerFaults([{ date: 'November 2, 2026', sha256: A }, { date: 'June 16, 2026', sha256: B }])).toEqual(['row 2 is dated before the row above it'])
    expect(ledgerFaults([{ date: 'Someday', sha256: A }])).toEqual(['row 1 has no readable date'])
  })
})
