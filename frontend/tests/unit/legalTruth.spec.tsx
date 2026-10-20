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
import { CONSENT_VERSION } from '@/components/CookieConsent'
import { ACCOUNT_EVENTS_DISCLOSURE, ANALYTICS_CONSENT_CLAUSE } from '@/lib/consentCopy'
import { LEGAL_DATES } from '@/lib/legalDates'

/**
 * The legal pages say what the code and the hosting do, and their dates move with their text (D-046; CLAUDE.md
 * rule 12; lessons/brand-a-promise-names-what-the-code-enforces.md, lessons/test-gates-must-be-as-wide-as-their-rule.md).
 *
 * 1. /security's claims that nothing in the repository supported stay out (REMOVED_CLAIMS), each read as its family:
 *    a Redis cache (production runs none, ADR-0004); an uptime figure or guarantee (a percentage, written with % or as
 *    percent or per cent, beside uptime, availability or an SLA, or a guarantee beside uptime or availability, in
 *    either order; none is offered); firewalls or intrusion detection or prevention (nothing configures them); every
 *    endpoint behind authentication, with or without "API" (search, company pages and summaries are public); a Content
 *    Security Policy against XSS or cross-site scripting (the site sends frame-ancestors only); role-based access,
 *    permissions or authorisation, or RBAC (one administrator flag); an adjective in place of a fact (enterprise,
 *    military or bank grade or level, industry standard or standards, hyphenated or not); no financial data stored, a
 *    negation, contracted or not, on either side (payment records are kept); post-incident reviews or post-mortems and
 *    vetting the providers (no process in the repository does either); and an analytics-consent promise not scoped to
 *    the browser in its own sentence, the analytics named on either side of "only after you allow" or "only with your
 *    consent" (the API sends account events whatever the reader chose: D-051). The scan reads /security's rendered
 *    tree, as one text (a heading runs into the body under it) and block by block (blockTexts: a list item or a
 *    paragraph on its own, so a provider's item is not read through the PostHog line's "in your browser"), the page
 *    module's literals (its metadata, which no render shows) and the waitlist page's copy (strings, JSX text and each
 *    element's run across its inline elements, outside className), sentence by sentence, a sentence ending only at
 *    ".", "!" or "?", so a `<strong>Label:</strong> body` item is read whole. The planted forms run through the same
 *    render, text, blocks and splitter and score the reach: main's sentences and their close rewordings fail, the
 *    page's new sentences and class names pass. Out of reach, planted as gaps: a claim split across two sentences, one
 *    said in other words, and an unscoped consent promise in a sentence that also names the browser.
 * 2. The account events (D-051). /security's PostHog line scopes the consent to the browser, and a sentence of
 *    its own, ACCOUNT_EVENTS_DISCLOSURE (lib/consentCopy.ts), names no provider and says the service records how
 *    accounts use it against the internal account id, whatever the reader chose. /security and /privacy each place
 *    it once and render it, and no other copy literal types it. Each example it gives stands on events the API sends
 *    with the account id and no consent read (EVENTS_BY_EXAMPLE): an example with none fails, and so does an event no
 *    caller sends any more. The reader of backend/app (eventsSent) counts a send keyed on the account id
 *    (`str(<x>.id)` or `str(<x>_id)`) in a function that reads no consent above it, the function around a closure
 *    included: each capture_event call's event, each call to the two inference wrappers, and each payload tuple
 *    `(str(<id>), <event>, {...})` that reaches a loop handing its tuples to capture_event (the Stripe webhook's), built
 *    in the loop's function or in one that a module with such a loop calls; a client function that reads consent
 *    counts nothing. capture_funnel_event's events wait for the summary stream's consent and do not count; docstrings
 *    and comments are skipped. Planted modules score the reader: callers keyed on an email, an anonymous id or an
 *    address, behind a consent check, after a consent return or in a consent reader's closure, and tuples no loop
 *    takes, fail. Out of reach, review-checked: a tuple whose builder a loop's module calls without feeding the loop.
 * 3. The consent dialog's analytics clause and /privacy's analytics cookies line are one constant,
 *    ANALYTICS_CONSENT_CLAUSE (lib/consentCopy.ts), in D-046's words: each of the two places it once, /privacy
 *    renders it, and no other copy literal types its account-id sentence. CookieConsent.spec.tsx reads it as the
 *    dialog's analytics checkbox description. F33's rule itself holds everywhere: no copy literal under app,
 *    components, features, hooks or lib calls the analytics anonymous or anonymised, a word an inline element sets
 *    apart read in its element's run (literalsOf). The clause is pinned beside CONSENT_VERSION
 *    (components/CookieConsent.tsx), the clause a stored choice was made under: an allow made under an earlier one
 *    reads as no choice, so the bar asks again (CookieConsent.spec.tsx plants the stored choices). The pin fails on any
 *    change to the clause, but whether a change widens what an allow covers, and so moves the version, is
 *    review-checked: updating the pinned clause alone passes, as an in-place ledger row does.
 * 4. A legal page's date moves with its text. LEGAL_TEXT lists, per page, the texts readers see, oldest first (main's
 *    published text before D-046 first), each with its date and the hash of the text the page rendered under it (the
 *    "Last updated" date itself read as {date}). The gate
 *    holds: the last row is the page as it renders now, under its LEGAL_DATES date, so a changed text or a moved date
 *    fails until the last row says so; each row's hash differs from the row before it, so a row appended for a date
 *    moved with no text change fails, and a later return to an earlier text is recorded by appending; dates never
 *    fall, and a row on the day of the row before it names the pull request that shares the day (sameDay), which the
 *    pin leaves out (pinnedRow), since the page shows a day and two pull requests can each change it on one day,
 *    while a later change moves the date: a row
 *    written under an old date for a later change fails unless it names one, and whether the named pull request
 *    changed the page that day is review-checked; and LEGAL_DATES, the pages rendered here and the ledger list the
 *    same pages (checked at run time, since CI does not type-check the specs). Out of reach,
 *    review-checked: the last row edited in place (a new hash, a new date or both written over it instead of
 *    appended), which passes; the diff shows the row rewritten.
 * 5. A /security claim that stands on a document, not the code, names it in a comment beside the claim,
 *    `{/* Source: <path> §<n>, "<heading>" ... *\/}`, and the document must exist, hold that numbered section, and
 *    say each word the claim names in a numbered step of it, its label, its text or a line that carries it on
 *    (SOURCED_STEPS): the runbook bullet stands on tasks/security_privacy_runbook.md §3's steps that contain and assess,
 *    gather evidence and rotate keys, and the notification bullet on its step 2, which notifies the supervisory
 *    authority and the affected users. Which claims stand on a document is review-checked; each one SOURCED_STEPS lists
 *    must carry its comment. Planted documents score the reader: a missing file, a renamed heading, a missing step and a
 *    step's words gone fail.
 * 6. The audit-log item names only what an audit_logs row records (AUDITED): each thing it names stands on actions
 *    the backend writes, read from each create_audit_log call and each audit_service helper another module calls.
 *    Administrator actions are named one by one, since six of them write a log line and no row
 *    (admin_filing_service.py's filing maintenance and stale-XBRL bulk reset, the XBRL cache clear, the test mail).
 * 7. /security promises nothing of refresh tokens and logging out that the code does not enforce when requests
 *    overlap (E127_PROMISES): a refresh token that works once, a reused one revoking the account, or a session that
 *    ends within a time after logging out. The page is read on every run, whatever tasks/todo.md records: E127's race
 *    is fixed (#1422), but E121 still records a login that straddles a password reset keeping a token the reset
 *    cannot reach, and the stronger wording returns only in a pull request that carries the founder's go-ahead and
 *    changes this check. Each family is read in one list item or paragraph (blockTexts). Planted forms score the
 *    reach; out of reach, planted as a gap: a promise split across two items.
 * 8. /security's numbers repeat the backend's defaults (NUMBERS): the session token's 30 minutes
 *    (ACCESS_TOKEN_EXPIRE_MINUTES), the refresh token's 30 days (REFRESH_TOKEN_EXPIRE_DAYS), the lockout's ten failures
 *    (LOCKOUT_THRESHOLD) and its two 15 minutes (LOCKOUT_SECONDS), and HSTS's year (main.py's max-age), so a change to
 *    either side fails until the two agree. The deploy overrides none of them; a value set by hand on the service is
 *    out of reach.
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
 * Each legal page's texts as readers see them, oldest first: the first row is the text main published before D-046,
 * under its date, and each later row a text a merge ships, under the date it took. Append a row in the commit that
 * changes a page's text, with the page's LEGAL_DATES key moved to that row's date; while a pull request is open, its
 * later round's row takes the place of an earlier round's, which no reader saw (review-checked). The hash is the first
 * 16 hex digits of the SHA-256 of pageText() with the page's date read as {date}.
 */
type LedgerRow = { date: string; sha256: string; sameDay?: string }

const LEGAL_TEXT: Record<LegalPage, LedgerRow[]> = {
  terms: [{ date: 'June 16, 2026', sha256: '82ecb15a746bee66' }],
  privacy: [
    { date: 'June 22, 2026', sha256: '455802b5d59fad8f' },
    { date: 'October 20, 2026', sha256: 'c1bc2d9daec940d1' },
    { date: 'October 20, 2026', sha256: '865b53735c88175d', sameDay: '#1399 changed /privacy that day too' },
  ],
  security: [
    { date: 'June 22, 2026', sha256: '13d1b7070566bf07' },
    { date: 'October 20, 2026', sha256: 'f01e686b3c5afee8' },
  ],
}

/** A rendered tree's text: its text nodes in order, joined by a space, whitespace collapsed. */
function pageText(container: HTMLElement): string {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  const parts: string[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.nodeValue ?? '')
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

/** The block elements a rendered tree's text is grouped by: an inline element is read with its block. */
const BLOCKS = 'p, li, h1, h2, h3, h4, h5, h6, dt, dd, td, th, caption, figcaption, blockquote, div, section, main, ul, ol, dl, table'

/** A rendered tree's blocks: each paragraph, list item, heading or cell's own text, its inline elements read with it
    (so a `<strong>Label:</strong> body` item is one block) and a nested block read on its own, so no sentence runs
    from one list item into the next. */
function blockTexts(container: HTMLElement): string[] {
  const groups = new Map<Element, string[]>()
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const block = node.parentElement?.closest(BLOCKS) ?? container
    groups.set(block, [...(groups.get(block) ?? []), node.nodeValue ?? ''])
  }
  return [...groups.values()].map((parts) => parts.join(' ').replace(/\s+/g, ' ').trim()).filter(Boolean)
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

const PERCENT = String.raw`\b\d{2,3}(?:\.\d+)?\s?(?:%|percent\b|per cent\b)`
const CSP = String.raw`(?:\bCSP\b|\bContent[- ]Security[- ]Polic(?:y|ies)\b)`
const XSS = String.raw`(?:\bXSS\b|\bcross[- ]site[- ]scripting\b)`

const REMOVED_CLAIMS: Array<[string, RegExp]> = [
  ['a Redis cache', /\bredis\b/i],
  [
    'an uptime figure or guarantee',
    new RegExp(String.raw`\b(?:uptime|availability|SLA)\b[^.]*${PERCENT}|${PERCENT}[^.]*\b(?:uptime|availability|available|SLA)\b|\b(?:uptime|availability)\b[^.]*\bguarantee(?:s|d)?\b|\bguarantee(?:s|d)?\b[^.]*\b(?:uptime|availability|available)\b`, 'i'),
  ],
  ['firewalls or intrusion detection', /\bfirewalls?\b|\bintrusion[- ](?:detection|prevention)\b/i],
  ['every endpoint behind authentication', /\b(?:all|every)\b(?:\s+of)?(?:\s+(?:our|the))?(?:\s+API)?\s+endpoints?\b/i],
  ['a Content Security Policy against XSS', new RegExp(`${CSP}[^.]*${XSS}|${XSS}[^.]*${CSP}`, 'i')],
  ['role-based access control', /\brole[- ]based (?:access|permissions?|authori[sz]ation)\b|\bRBAC\b/i],
  ['an adjective in place of a fact', /\b(?:enterprise|military|bank)[- ](?:grade|level)\b|\bindustry[- ]standards?\b/i],
  ['no financial data stored', /(?:\b(?:no|never|not|none)\b|n['’]t\b)[^.]{0,40}\bfinancial data\b|\bfinancial data\b[^.]{0,40}(?:\b(?:never|not)\b|n['’]t\b)/i],
  ['post-incident reviews', /\bpost[- ]incident reviews?\b|\bpost[- ]?mortems?\b/i],
  ['vetting the providers', /\bvet(?:s|ted|ting)?\b/i],
  [
    'an analytics-consent promise not scoped to the browser',
    /^(?!.*\bin your browser\b)(?=.*\b(?:analytics|tracking|statistics)\b).*\bonly (?:(?:after|once|when|if) you(?: have|['’]ve)? (?:allow|accept|agree|consent|opt(?:ed)?[- ]in)|(?:with|after|upon|on) (?:your )?(?:consent|permission|agreement|approval|opt[- ]in))/i,
  ],
]

const claimsIn = (where: string, text: string) =>
  REMOVED_CLAIMS.filter(([, re]) => re.test(text)).map(([label]) => `${where} (${label}): ${JSON.stringify(text)}`)

/** Every removed claim in a text, read sentence by sentence. */
const claimsInText = (where: string, text: string) => sentencesOf(text).flatMap((sentence) => claimsIn(where, sentence))

/** Every removed claim in a rendered tree: in its whole text, so a heading and the body under it read together, and in
    each block on its own (blockTexts), so a list item's sentence is read even where the list's items run together. */
const claimsInTree = (where: string, container: HTMLElement) => [
  ...claimsInText(where, pageText(container)),
  ...blockTexts(container).flatMap((block) => claimsInText(where, block)),
]

const inASentence = (re: RegExp) => (block: string) => sentencesOf(block).some((sentence) => re.test(sentence))

/**
 * What /security does not promise of refresh tokens and logging out, on every run. E127's race (two renewals with one
 * refresh token both succeeding, a renewal racing a logout leaving a live token) is fixed by #1422, but E121 still
 * records a login that straddles a password reset and mints a token the reset cannot reach, so "changing or resetting
 * your password ... ends every session" stays untrue. The stronger wording returns only in a pull request that carries
 * the founder's go-ahead and changes this check. Each family is read in one block (a list item or a paragraph), so a
 * promise split across the sentences of one item is read whole.
 */
const E127_PROMISES: Array<[string, (block: string) => boolean]> = [
  ['a refresh token that works once', inASentence(/\bworks? (?:only )?once\b|\bsingle[- ]use\b|\b(?:used|usable|valid|good) (?:only )?once\b|\bonly once\b/i)],
  ['a reused refresh token revoking the account', inASentence(/^(?=.*\brevok).*\b(?:a second time|again|twice|re-?us(?:e|ed|es|ing)|replay(?:s|ed|ing)?)\b/i)],
  [
    'a session that ends within a time after logging out',
    (block) =>
      /\b(?:log(?:ging|s)? out|sign(?:ing|s)? out|all (?:of your )?devices|everywhere|password)\b/i.test(block) &&
      inASentence(
        /\b(?:ends?|ended|expires?|stops?|closes?|(?:signs?|logs?|signed|logged) (?:you )?out|(?:is|are) (?:revoked|ended))\b.*(?:\b(?:within|after|in)\s+(?:\d+|a|an|one|ten|fifteen|thirty|sixty)\s+(?:seconds?|minutes?|hours?|days?)\b|\b(?:immediately|at once|instantly|right away)\b)/i,
      )(block),
  ],
]

const e127PromisesIn = (where: string, block: string) =>
  E127_PROMISES.filter(([, holds]) => holds(block)).map(([label]) => `${where} (${label}): ${JSON.stringify(block)}`)

/** The JSX tags read inline, whose text runs on with their parent's: HTML's text-level elements and next/link's Link. */
const INLINE_TAGS = new Set(['a', 'abbr', 'b', 'bdi', 'bdo', 'br', 'cite', 'code', 'data', 'dfn', 'em', 'i', 'kbd', 'mark', 'q', 's', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'time', 'u', 'var', 'wbr', 'Link'])

/** Every copy literal of a module's source: strings, templates (`{x}` for each substitution) and JSX text, class names
    skipped, and an element's text read as one run across its inline elements as well (`collecting
    <strong>anonymous</strong> usage statistics` is one literal, besides its three pieces), a placed value read as {x}. */
function literalsOf(rel: string, source: string): string[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const out: string[] = []
  const BREAK = '\u0000'
  const inline = (child: ts.Node) =>
    (ts.isJsxElement(child) && INLINE_TAGS.has(child.openingElement.tagName.getText(sf))) ||
    (ts.isJsxSelfClosingElement(child) && INLINE_TAGS.has(child.tagName.getText(sf)))
  const runOf = (node: ts.JsxElement | ts.JsxFragment): string =>
    node.children
      .map((child) => {
        if (ts.isJsxText(child)) return child.text
        if (ts.isJsxExpression(child)) return !child.expression ? '' : ts.isStringLiteralLike(child.expression) ? child.expression.text : '{x}'
        if (ts.isJsxElement(child) && inline(child)) return runOf(child)
        return inline(child) ? ' ' : BREAK
      })
      .join('')
  const visit = (node: ts.Node) => {
    if (ts.isJsxAttribute(node) && ts.isIdentifier(node.name) && /^(?:className|class)$/.test(node.name.text)) return
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) out.push(node.text)
    else if (ts.isTemplateExpression(node)) out.push([node.head.text, ...node.templateSpans.map((s) => `{x}${s.literal.text}`)].join(''))
    else if (ts.isJsxText(node) && !node.containsOnlyTriviaWhiteSpaces) out.push(node.text)
    if ((ts.isJsxElement(node) || ts.isJsxFragment(node)) && node.children.some(inline)) out.push(...runOf(node).split(BREAK))
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out.map((text) => text.replace(/\s+/g, ' ').trim()).filter(Boolean)
}

const literalsByModule = new Map<string, string[]>()

/** Every copy literal of a module under frontend/ (literalsOf), parsed once per run: three cases scan every module. */
function literals(rel: string): string[] {
  const known = literalsByModule.get(rel)
  if (known) return known
  const found = literalsOf(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'))
  literalsByModule.set(rel, found)
  return found
}

/** A case that parses every module under the scan directories: the default 5s times out on a loaded machine. */
const SCANS_EVERY_MODULE = { timeout: 30_000 }

const copyModules = () =>
  execFileSync('git', ['ls-files', '--', ...SCAN_DIRS], { cwd: FRONTEND, encoding: 'utf8' })
    .split('\n')
    .filter((rel) => /\.tsx?$/.test(rel) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(rel))

const ANONYMOUS = String.raw`\b(?:anonymous(?:ly)?|anonymi[sz](?:ed?|es|ing|ation))\b`

/** Analytics called anonymous or anonymised, in either order: F33's rule (a logged-in reader's statistics carry the
    account id). */
const ANONYMOUS_ANALYTICS = new RegExp(
  String.raw`${ANONYMOUS}[^.]*\b(?:usage|statistics|analytics|PostHog|tracking|telemetry|data)\b|\b(?:usage|statistics|analytics|PostHog|tracking|telemetry)\b[^.]*${ANONYMOUS}`,
  'i',
)

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

/** The account id as every caller keys an event on it: `str(<x>.id)` or `str(<x>_id)`. */
const ACCOUNT_ID = String.raw`str\(\s*[A-Za-z_][\w.]*(?:\.id|_id)\s*\)`

/** The function that holds `index` in a module's code: the innermost one's name, and the code from the outermost
    enclosing one's first line up to `index` (a closure is read with the function around it). Outside any function,
    the module's code up to `index`. */
function scopeAt(code: string, index: number): { name: string | null; text: string } {
  const lines = code.slice(0, index).split('\n')
  let indent = lines[lines.length - 1].length - lines[lines.length - 1].trimStart().length
  let name: string | null = null
  let start = 0
  for (let i = lines.length - 2; i >= 0; i--) {
    const def = lines[i].match(/^(\s*)(?:async\s+)?def\s+(\w+)/)
    if (def && def[1].length < indent) {
      name ??= def[2]
      start = i
      indent = def[1].length
    }
  }
  return { name, text: lines.slice(start).join('\n') }
}

/** Whether a scope's code reads the reader's consent (an analytics_consent flag, a consent check), anywhere above the send. */
const readsConsent = (scope: { text: string }) => /consent/i.test(scope.text)

/** A Python module function's code, from its def line to the next top-level statement. */
const functionCode = (code: string, name: string) =>
  code.match(new RegExp(String.raw`^(?:async\s+)?def\s+${name}\([\s\S]*?(?=^\S|(?![\s\S]))`, 'm'))?.[0] ?? ''

/**
 * The events the API sends with the account id whatever the reader chose. A send counts when it keys the event on
 * the account id (ACCOUNT_ID) and the function around it reads no consent: each capture_event call's event, each call
 * to an inference wrapper, and each payload tuple `(str(<id>), <event>, {...})` that reaches a send loop, a
 * `for <a>, <b>, <c> in <list>:` that hands each tuple to capture_event(<a>, <b>, <c>) (the Stripe webhook's, after
 * its commit): one built in the loop's own function, or in a function that a module with such a loop calls.
 * capture_funnel_event is not read: the summary stream calls it only when the reader allowed analytics
 * (routers/summaries.py, analytics_consent). The client module's own calls are its wrappers' bodies, so they count only
 * through a caller, and a client function that reads consent sends nothing whatever the reader chose.
 */
function eventsSent(modules: Record<string, string>): Set<string> {
  const constants = new Map<string, string>()
  for (const src of Object.values(modules)) {
    for (const [, name, value] of pythonCode(src).matchAll(/^(EVENT_[A-Z_]+)\s*=\s*"([a-z_$]+)"/gm)) constants.set(name, value)
  }
  const isClient = (rel: string) => /(?:^|\/)posthog_client\.py$/.test(rel)
  const client = pythonCode(Object.entries(modules).find(([rel]) => isClient(rel))?.[1] ?? '')
  const gated = (fn: string) => /consent/i.test(functionCode(client, fn))
  const EVENT = String.raw`("[a-z_$]+"|EVENT_[A-Z_]+)`
  const nameOf = (token: string) => (token.startsWith('"') ? token.slice(1, -1) : constants.get(token))
  const code = Object.fromEntries(Object.entries(modules).filter(([rel]) => !isClient(rel)).map(([rel, src]) => [rel, pythonCode(src)]))

  // The send loops, by module, and the functions they sit in.
  const loops = new Map<string, Set<string | null>>()
  for (const [rel, text] of Object.entries(code)) {
    for (const loop of text.matchAll(/\bfor\s+(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s+in\s+\w+\s*:/g)) {
      const body = text.slice((loop.index ?? 0) + loop[0].length, (loop.index ?? 0) + loop[0].length + 400)
      const scope = scopeAt(text, loop.index ?? 0)
      if (!new RegExp(String.raw`\bcapture_event\(\s*${loop[1]}\s*,\s*${loop[2]}\s*,\s*${loop[3]}\s*\)`).test(body) || readsConsent(scope)) continue
      loops.set(rel, new Set([...(loops.get(rel) ?? []), scope.name]))
    }
  }
  const reachesALoop = (rel: string, fn: string | null) =>
    (loops.get(rel)?.has(fn) ?? false) ||
    (fn !== null && [...loops.keys()].some((loopRel) => new RegExp(String.raw`(?<!def\s)\b${fn}\(`).test(code[loopRel])))

  const sent = new Set<string>()
  if (gated('capture_event')) return sent
  for (const [rel, text] of Object.entries(code)) {
    for (const call of text.matchAll(new RegExp(String.raw`\bcapture_event\(\s*${ACCOUNT_ID}\s*,\s*${EVENT}`, 'g'))) {
      const event = nameOf(call[1])
      if (event && !readsConsent(scopeAt(text, call.index ?? 0))) sent.add(event)
    }
    for (const tuple of text.matchAll(new RegExp(String.raw`(?<![\w.])\(\s*${ACCOUNT_ID}\s*,\s*${EVENT}\s*,\s*\{`, 'g'))) {
      const event = nameOf(tuple[1])
      const scope = scopeAt(text, tuple.index ?? 0)
      if (event && !readsConsent(scope) && reachesALoop(rel, scope.name)) sent.add(event)
    }
    for (const [wrapper, constant] of Object.entries(EVENT_WRAPPERS)) {
      const event = constants.get(constant)
      if (!event || gated(wrapper)) continue
      for (const call of text.matchAll(new RegExp(String.raw`\b${wrapper}\(\s*(?:distinct_id\s*=\s*)?${ACCOUNT_ID}`, 'g'))) {
        if (!readsConsent(scopeAt(text, call.index ?? 0))) sent.add(event)
      }
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

/** The /security claims that stand on a document, and what each says the document holds, word for word from its
    numbered steps. Which claims stand on a document is review-checked; each one listed must carry its comment. */
const SOURCED_STEPS: Record<string, string[]> = {
  'A written runbook covers containing it, finding what it touched, gathering evidence and rotating keys': ['Contain', 'assess', 'Evidence', 'Rotate'],
  'When the law requires it, we notify the users affected and the data protection authority': ['notify', 'supervisory authority', 'affected users'],
}

/** A `{/* Source: <path> §<n>, "<heading>" ... *\/}` comment and the list item right after it, in a page's source. */
const SOURCE_COMMENT = /\{\/\*\s*Source:\s*(\S+)\s+§(\d+),\s*"([^"]+)"[^*]*\*\/\}\s*<li>([^<]+)<\/li>/g

const escapeRe = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** What a source lacks: the file, its numbered section (a heading `## <n>. <heading>`), or a word the claim names (in a
    numbered step of that section, its label, its text and the lines that carry it on). */
function sourceFaults(rel: string, doc: string | null, section: string, heading: string, steps: string[]): string[] {
  if (doc === null) return [`${rel} is missing`]
  const lines = doc.split('\n')
  const start = lines.findIndex((line) => new RegExp(String.raw`^#{1,6}\s+${section}\.\s+${escapeRe(heading)}\b`).test(line))
  if (start < 0) return [`${rel} has no §${section} "${heading}" heading`]
  const next = lines.findIndex((line, i) => i > start && /^#{1,6}\s/.test(line))
  const items: string[] = []
  for (const line of lines.slice(start + 1, next < 0 ? undefined : next)) {
    if (/^\s*\d+\.\s/.test(line)) items.push(line.trim())
    else if (items.length > 0 && /^\s+\S/.test(line)) items[items.length - 1] += ` ${line.trim()}`
    else if (!line.trim()) items.push('')
  }
  return steps
    .filter((step) => !items.some((item) => new RegExp(String.raw`\b${escapeRe(step)}\b`, 'i').test(item)))
    .map((step) => `${rel} §${section} has no step that says "${step}"`)
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

/** What breaks a page's ledger: an unreadable date, a date that falls, a text that repeats the row before, or a row on
    the day of the row before that names no other change that day. The page shows a day, so a second change that day
    leaves it true, but a later change must move the date: a same-day row names the pull request that shares the day
    (`sameDay`), so one written under an old date for a later change fails, and the name is review-checked. */
function ledgerFaults(rows: LedgerRow[]): string[] {
  const faults: string[] = []
  rows.forEach((row, i) => {
    const time = Date.parse(row.date)
    if (!Number.isFinite(time)) faults.push(`row ${i + 1} has no readable date`)
    else if (i > 0 && time < Date.parse(rows[i - 1].date)) faults.push(`row ${i + 1} is dated before the row above it`)
    else if (i > 0 && time === Date.parse(rows[i - 1].date) && !/#\d+/.test(row.sameDay ?? ''))
      faults.push(`row ${i + 1} shares the day of the row before it and names no pull request that changed the page that day (sameDay)`)
    if (i > 0 && row.sha256 === rows[i - 1].sha256) faults.push(`row ${i + 1} repeats the text of the row before it`)
  })
  return faults
}

/** What the page as it renders is pinned to: its ledger's last row, its date and hash. A same-day row's sameDay names
    the other change that day for the forward rule, and is not part of the pin. */
const pinnedRow = (rows: LedgerRow[]) => {
  const { date, sha256 } = rows[rows.length - 1]
  return { date, sha256 }
}

/** /security's numbers, each beside the backend default it repeats (the deploy overrides none of them), so a change to
    either fails until the two agree. A number the page writes as a word reads through NUMBER_WORDS. */
const NUMBERS: Array<{ says: RegExp; file: string; value: RegExp; per: number }> = [
  { says: /\bThe session token expires after (\w+) minutes\b/, file: 'backend/app/config.py', value: /^\s*ACCESS_TOKEN_EXPIRE_MINUTES: int = (\d+)\b/m, per: 1 },
  { says: /\ba refresh token that lasts (\w+) days\b/, file: 'backend/app/config.py', value: /^\s*REFRESH_TOKEN_EXPIRE_DAYS: int = (\d+)\b/m, per: 1 },
  { says: /\b(\w+) failed logins for one email address\b/, file: 'backend/app/services/login_lockout.py', value: /^LOCKOUT_THRESHOLD = (\d+)\b/m, per: 1 },
  { says: /\beach within (\w+) minutes of the last\b/, file: 'backend/app/services/login_lockout.py', value: /^LOCKOUT_SECONDS = (\d+)\b/m, per: 60 },
  { says: /\bblock password logins for that address for (\w+) minutes\b/, file: 'backend/app/services/login_lockout.py', value: /^LOCKOUT_SECONDS = (\d+)\b/m, per: 60 },
  { says: /\bonly over HTTPS for (\w+) years? \(HSTS\)/, file: 'backend/main.py', value: /"Strict-Transport-Security", "max-age=(\d+)\b/, per: 365 * 24 * 3600 },
]

const NUMBER_WORDS: Record<string, number> = { a: 1, an: 1, one: 1, two: 2, three: 3, five: 5, ten: 10, fifteen: 15, twenty: 20, thirty: 30 }

/** A page number as a value: digits, or a word NUMBER_WORDS reads. */
const numberOf = (word: string) => (/^\d+$/.test(word) ? Number(word) : NUMBER_WORDS[word.toLowerCase()])

describe("/security says what the code and the hosting do (D-046)", () => {
  it('names none of the claims D-046 removed, and neither does the waitlist page', () => {
    const { container, unmount } = render(<SecurityPage />)
    const text = pageText(container)
    const page = claimsInTree('/security', container)
    unmount()
    expect(text.length).toBeGreaterThan(4000)
    const security = literals('app/security/page.tsx')
    expect(security).toContain('Security practices and data protection at EarningsNerd.') // the metadata, which no render shows
    const waitlist = literals('app/waitlist/page.tsx')
    expect(waitlist).toContain('Security') // the trust panel's tile title: the scan reads the tile's copy
    expect(waitlist.some((l) => /\bmt-\d|\bgrid\b/.test(l))).toBe(false) // and none of its class names
    expect([
      ...page,
      ...security.flatMap((l) => claimsInText('app/security/page.tsx', l)),
      ...waitlist.flatMap((l) => claimsInText('app/waitlist/page.tsx', l)),
    ]).toEqual([])
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
      // Round 4's review: the same families in other common forms.
      ['<p>Usage statistics are collected only after you allow it.</p>', true],
      ['<p>Analytics run only once you allow them.</p>', true],
      ['<p>Usage statistics are collected only with your consent.</p>', true],
      ["<p>We don't store your financial data.</p>", true],
      ['<p>Financial data isn’t stored on our servers.</p>', true],
      ['<p>We hold a post-mortem after every incident.</p>', true],
      ['<p>We hold blameless postmortems after every incident.</p>', true],
      ['<p>We guarantee high availability.</p>', true],
      ['<p>Uptime is guaranteed.</p>', true],
      ['<p>Our hosting comes with an availability guarantee.</p>', true],
      ['<p>Hosted with 99.9 per cent uptime.</p>', true],
      ['<p>We follow industry standards to keep your data safe.</p>', true],
      // A provider item in the list beside the PostHog line: list items carry no full stop, so the list's text runs
      // on as one sentence and the PostHog line's "in your browser" covered the item; each block is read on its own.
      ['<ul><li><strong>Vercel:</strong> Hosts the site, and counts page views only after you allow analytics</li><li><strong>PostHog:</strong> Usage statistics: PostHog in your browser runs only after you allow analytics, and records sessions only if you allow that too</li></ul>', true],
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
      const found = claimsInTree('planted', container)
      unmount()
      return found.length > 0
    })
    expect(flagged).toEqual(planted.map(([, expected]) => expected === true))
    // The module's literals reach what no render shows: a claim in the page's metadata fails.
    const metadata = literalsOf('probe.tsx', "export const metadata = { title: 'Security', description: 'Enterprise-grade security with 99.9% uptime.' }")
    expect(metadata.flatMap((l) => claimsInText('probe.tsx', l)).length).toBeGreaterThan(0)
  })

  it('states each number the backend sets, as the backend sets it (a self-check on a changed constant)', () => {
    const text = rendered('security')
    const read = (file: string, value: RegExp) => Number(readFileSync(path.join(REPO, file), 'utf8').match(value)?.[1])
    for (const { says, file, value, per } of NUMBERS) {
      const word = text.match(says)?.[1]
      expect(word, `/security states ${says}`).toBeDefined()
      expect(numberOf(word ?? ''), `/security's ${JSON.stringify(text.match(says)?.[0])} against ${file}`).toBe(read(file, value) / per)
    }
    // The two readers on planted text: the page's number as a word, and a changed constant read in its unit.
    const [, , lockout, , block] = NUMBERS
    expect(numberOf('Five failed logins for one email address'.match(lockout.says)?.[1] ?? '')).toBe(5)
    expect(Number('LOCKOUT_SECONDS = 1800\n'.match(block.value)?.[1]) / block.per).toBe(30)
  })

  it('the PostHog line scopes the consent to the browser', () => {
    const sentence = sentencesOf(rendered('security')).find((s) => /\bPostHog in your browser runs only after you allow analytics\b/i.test(s))
    expect(sentence, 'the PostHog line scopes the consent to the browser').toBeDefined()
  })

  it('promises nothing of refresh tokens or logging out that the code does not enforce, whatever the todo records (a self-check on planted forms)', () => {
    const { container, unmount } = render(<SecurityPage />)
    const blocks = blockTexts(container)
    unmount()
    expect(blocks.some((block) => block.startsWith('Logging out:'))).toBe(true)
    expect(blocks.flatMap((block) => e127PromisesIn('/security', block))).toEqual([])
    const planted: Array<[string, boolean | 'gap']> = [
      // Round 3's two items.
      ["<li><strong>Token renewal:</strong> The session token expires after 30 minutes and is renewed from a refresh token that lasts 30 days. Each refresh token works once and is stored only as a hash; one presented a second time revokes all of that account's refresh tokens.</li>", true],
      ['<li><strong>Logging out:</strong> Logging out revokes that browser’s refresh token. Logging out of all devices, from your account settings, revokes all of your refresh tokens, and so does changing or resetting your password; a session open elsewhere then ends within 30 minutes, when its session token expires.</li>', true],
      // Close rewordings.
      ['<li>Refresh tokens are single-use.</li>', true],
      ['<li>A refresh token can be used only once.</li>', true],
      ['<p>Reusing a refresh token revokes every session on the account.</p>', true],
      ['<li>Logging out of all devices signs you out everywhere within 30 minutes.</li>', true],
      ['<li>Changing your password ends every other session immediately.</li>', true],
      ['<li><strong>Logging out:</strong> Logging out of all devices revokes your refresh tokens. Each session then ends within 30 minutes.</li>', true],
      // The items as they read now, and look-alikes, which pass.
      ['<li><strong>Token renewal:</strong> The session token expires after 30 minutes and is renewed from a refresh token that lasts 30 days. Each renewal replaces the refresh token with a new one, and refresh tokens are stored only as hashes.</li>', false],
      ['<li><strong>Logging out:</strong> Logging out revokes the refresh token your browser sends with it. Logging out of all devices, from your account settings, revokes every refresh token your account holds at that moment, and so does changing or resetting your password. None of these revokes a session token already issued.</li>', false],
      ['<li><strong>Failed logins:</strong> Ten failed logins for one email address, each within 15 minutes of the last, block password logins for that address for 15 minutes.</li>', false],
      ['<li>Log out of your account when using shared or public computers</li>', false],
      // Out of reach: a promise split across two items.
      ['<ul><li>Logging out of all devices revokes your refresh tokens.</li><li>Each session then ends within 30 minutes.</li></ul>', 'gap'],
    ]
    const flagged = planted.map(([html]) => {
      const { container, unmount } = render(<div dangerouslySetInnerHTML={{ __html: html }} />)
      const found = blockTexts(container).flatMap((block) => e127PromisesIn('planted', block))
      unmount()
      return found.length > 0
    })
    expect(flagged).toEqual(planted.map(([, expected]) => expected === true))
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
      '2. **Clock starts** when you become aware. GDPR: notify the lead supervisory authority within',
      '   72 hours if there is risk; notify affected users without undue delay if high risk.',
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
    expect(faults(doc.replace('4. **Rotate** - SECRET_KEY, and any leaked keys.\n', ''))).toEqual(['r.md §3 has no step that says "Rotate"'])
    expect(faults(doc.replace('**Contain & assess**', '**Assess**'))).toEqual(['r.md §3 has no step that says "Contain"'])
    // The notification bullet's words stand in step 2's text, on the line that carries it on.
    const notify = (text: string | null) => sourceFaults('r.md', text, '3', 'Breach-notification readiness', ['notify', 'supervisory authority', 'affected users'])
    expect(notify(doc)).toEqual([])
    expect(notify(doc.replace('notify affected users without undue delay', 'tell nobody'))).toEqual(['r.md §3 has no step that says "affected users"'])
    expect(notify(doc.replace('\n   72 hours', '\n\n72 hours'))).toEqual(['r.md §3 has no step that says "affected users"']) // a line outside the list
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

describe('the account events have a sentence of their own, true of the API (D-051)', () => {
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

  it('no other copy types it', SCANS_EVERY_MODULE, () => {
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
    const CLIENT = [
      'EVENT_SIGNED_UP = "signed_up"',
      'EVENT_COPILOT_INFERENCE = "copilot_inference_cost"',
      'EVENT_ANALYSIS_INFERENCE = "analysis_inference_cost"',
      'def capture_event(distinct_id, event, properties=None):',
      '    client.capture(event, distinct_id=distinct_id, properties=properties or {})',
      'def capture_copilot_inference(distinct_id):',
      '    capture_event(distinct_id, EVENT_COPILOT_INFERENCE, {})',
      'def capture_analysis_inference(distinct_id, model):',
      '    capture_event(distinct_id, EVENT_ANALYSIS_INFERENCE, {})',
    ].join('\n')
    const ROUTER = [
      'def register(user, invite):',
      '    capture_event(',
      '        str(user.id),',
      '        EVENT_SIGNED_UP,',
      '        {"invited": True},',
      '    )',
      '    capture_event(str(current_user.id), "literal_sent", {"type": kind})',
      '    capture_funnel_event(str(user.id), "funnel_only", {})',
      '    # capture_event(str(user.id), "commented_out", {})',
      '    """capture_event(str(user.id), "in_a_docstring", {})"""',
      'def cost(user_id):',
      '    capture_analysis_inference(distinct_id=str(user_id), model=model)',
      'def keyed_elsewhere(user, anonymous_id, request):',
      '    capture_event(user.email, "keyed_on_the_email", {})',
      '    capture_event(str(user.email), "keyed_on_str_email", {})',
      '    capture_event(anonymous_id, "keyed_on_an_anonymous_id", {})',
      '    capture_event(str(request.client.host), "keyed_on_the_ip", {})',
      '    capture_copilot_inference(distinct_id=posthog_anon_id)',
      'def gated(user, analytics_consent):',
      '    if analytics_consent:',
      '        capture_event(str(user.id), "nested_under_consent", {})',
      'def guarded(user, analytics_consent):',
      '    if not analytics_consent:',
      '        return',
      '    capture_event(str(user.id), "after_a_consent_return", {})',
      'async def outer(user, analytics_consent):',
      '    def work():',
      '        capture_event(str(user.id), "in_a_closure_of_a_consent_reader", {})',
    ].join('\n')
    const WEBHOOK = [
      'def _collect(user):',
      '    out = []',
      '    out.append((str(user.id), "tuple_sent", {"plan": plan}))',
      '    return out',
      'def handle(event, user):',
      '    analytics = _collect(user) + [billing.record(user)]',
      '    for distinct_id, name, properties in analytics:',
      '        capture_event(distinct_id, name, properties)',
    ].join('\n')
    const BILLING = 'def record(user):\n    return (str(user.id), "returned_tuple_sent", {"amount": 1})\n'
    const ORPHAN = 'def _never_sent(user):\n    return [(str(user.id), "tuple_no_loop_takes", {"x": 1})]\n'
    const GATED_LOOP = [
      'def _gated_collect(user):',
      '    return [(str(user.id), "tuple_behind_a_consent_loop", {})]',
      'def handle_gated(user, analytics_consent):',
      '    items = _gated_collect(user)',
      '    if analytics_consent:',
      '        for a, b, c in items:',
      '            capture_event(a, b, c)',
    ].join('\n')
    const planted = {
      'app/services/posthog_client.py': CLIENT,
      'app/routers/a.py': ROUTER,
      'app/services/webhook.py': WEBHOOK,
      'app/services/billing.py': BILLING,
      'app/services/orphan.py': ORPHAN,
      'app/services/gated_loop.py': GATED_LOOP,
    }
    expect([...eventsSent(planted)].sort()).toEqual(['analysis_inference_cost', 'literal_sent', 'returned_tuple_sent', 'signed_up', 'tuple_sent'])
    // Without the send loop, neither tuple is sent; a client capture_event that read consent would send nothing.
    expect([...eventsSent({ ...planted, 'app/services/webhook.py': WEBHOOK.split('    for distinct_id')[0] })].sort()).toEqual(['analysis_inference_cost', 'literal_sent', 'signed_up'])
    expect([...eventsSent({ ...planted, 'app/services/posthog_client.py': CLIENT.replace('    client.capture(', '    if has_consent(distinct_id):\n        client.capture(') })]).toEqual([])
    expect(exampleFaults(['sign-ups', 'searches'], new Set(['signup_completed']))).toEqual([
      '"sign-ups": no capture_event caller sends invite_redeemed',
      '"searches": no capture_event caller is known to send it',
    ])
  })
})

describe('the consent clause and /privacy say the same thing, from one constant (D-046, F33)', () => {
  it("is D-046's sentence, pinned beside the version a stored allow must carry (CONSENT_VERSION)", () => {
    expect(
      { clause: ANALYTICS_CONSENT_CLAUSE, version: CONSENT_VERSION },
      'a change to what the clause says an allow covers moves CONSENT_VERSION (components/CookieConsent.tsx) in the same commit, so a reader who allowed analytics under the old words chooses again',
    ).toEqual({
      clause: 'Usage statistics through PostHog, so we can see which pages work. When you are logged in they are tied to an internal account id.',
      version: 2,
    })
  })

  it('the consent dialog and /privacy each place it once, and /privacy renders it', () => {
    for (const rel of ['components/CookieConsent.tsx', 'app/privacy/page.tsx']) {
      expect(placements(rel, 'ANALYTICS_CONSENT_CLAUSE')).toEqual({ rel, imported: true, placed: 1 })
    }
    expect(rendered('privacy')).toContain(`Analytics Cookies: ${ANALYTICS_CONSENT_CLAUSE}`)
  })

  it('no other copy types the clause', SCANS_EVERY_MODULE, () => {
    const modules = copyModules().filter((rel) => rel !== 'lib/consentCopy.ts')
    expect(modules.length).toBeGreaterThan(300)
    const typed = modules.flatMap((rel) =>
      literals(rel).filter((l) => /\btied to an internal account id\b|\busage statistics through posthog\b/i.test(l)).map((l) => `${rel}: ${l}`),
    )
    expect(typed).toEqual([])
  })

  it('no copy calls the analytics anonymous (F33), and the rule reads its forms (a self-check on planted forms)', SCANS_EVERY_MODULE, () => {
    const modules = copyModules()
    expect(modules.length).toBeGreaterThan(300)
    expect(modules.flatMap((rel) => literals(rel).filter((l) => ANONYMOUS_ANALYTICS.test(l)).map((l) => `${rel}: ${l}`))).toEqual([])
    const planted: Array<[string, boolean]> = [
      ['Help us understand how visitors interact with our website by collecting anonymous usage statistics (PostHog).', true],
      ['Anonymous usage statistics (PostHog) help us improve the site.', true],
      ['We collect anonymous data to improve the product.', true],
      ['Analytics are anonymous.', true],
      ['PostHog tracking stays anonymous.', true],
      ['We collect anonymized usage statistics.', true],
      ['Analytics data is anonymised.', true],
      ['Anonymised analytics help us improve the site.', true],
      ['Anonymous', false],
      ['anonymous', false],
      ['Anonymous visitors can read any summary.', false],
      [ANALYTICS_CONSENT_CLAUSE, false],
    ]
    expect(planted.map(([text]) => ANONYMOUS_ANALYTICS.test(text))).toEqual(planted.map(([, expected]) => expected))
    // The word set apart by an inline element is read in its sentence's run; a word in another block is not.
    const split = literalsOf('probe.tsx', 'export const P = () => <p>Help us improve by collecting <strong>anonymous</strong> usage statistics (PostHog).</p>')
    expect(split.filter((l) => ANONYMOUS_ANALYTICS.test(l))).toEqual(['Help us improve by collecting anonymous usage statistics (PostHog).'])
    const apart = literalsOf('probe.tsx', 'export const P = () => <div><h3>Anonymous</h3><p>Usage statistics through PostHog.</p></div>')
    expect(apart.filter((l) => ANONYMOUS_ANALYTICS.test(l))).toEqual([])
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
        `the ${page} page's text or date changed: move LEGAL_DATES.${page} to the date of the change and append that date and this hash to LEGAL_TEXT.${page}, in the same commit; a row on the day of the row before it names the pull request that shares the day in sameDay`,
      ).toEqual(pinnedRow(rows))
    })
  }

  it('the ledger reads forward: no page’s date falls, and each row’s text differs from the row before it', () => {
    for (const page of Object.keys(LEGAL_TEXT) as LegalPage[]) {
      expect(LEGAL_TEXT[page].length, page).toBeGreaterThan(0)
      expect(ledgerFaults(LEGAL_TEXT[page]), page).toEqual([])
    }
    // The rule on planted ledgers: a revert (A, B, then A again) appends, and so does a second change on one day that
    // names the pull request sharing the day; a same-day row that names none (a later change under an old date), a date
    // moved with no text change, a falling date and an unreadable date fail.
    const A = 'aaaaaaaaaaaaaaaa'
    const B = 'bbbbbbbbbbbbbbbb'
    expect(ledgerFaults([{ date: 'June 16, 2026', sha256: A }, { date: 'November 2, 2026', sha256: B }, { date: 'December 7, 2026', sha256: A }])).toEqual([])
    expect(ledgerFaults([{ date: 'October 18, 2026', sha256: A }, { date: 'October 19, 2026', sha256: B }, { date: 'October 19, 2026', sha256: A, sameDay: '#1399 changed the page that day too' }])).toEqual([])
    expect(ledgerFaults([{ date: 'October 19, 2026', sha256: A }, { date: 'October 19, 2026', sha256: B }])).toEqual([
      'row 2 shares the day of the row before it and names no pull request that changed the page that day (sameDay)',
    ])
    expect(ledgerFaults([{ date: 'June 16, 2026', sha256: A }, { date: 'November 2, 2026', sha256: A }])).toEqual(['row 2 repeats the text of the row before it'])
    expect(ledgerFaults([{ date: 'October 19, 2026', sha256: A }, { date: 'October 19, 2026', sha256: A, sameDay: '#1399' }])).toEqual(['row 2 repeats the text of the row before it'])
    // A same-day last row through the pin, as the page renders it: one that names the pull request sharing the day
    // passes both the pin and the forward rule; one that names none passes the pin and fails the forward rule.
    const C = 'cccccccccccccccc'
    const today = { date: 'October 20, 2026', sha256: C }
    const named: LedgerRow[] = [{ date: 'October 19, 2026', sha256: A }, { date: 'October 20, 2026', sha256: B }, { date: 'October 20, 2026', sha256: C, sameDay: '#1399 changed the page that day too' }]
    expect(today).toEqual(pinnedRow(named))
    expect(ledgerFaults(named)).toEqual([])
    const unnamed: LedgerRow[] = [{ date: 'October 19, 2026', sha256: A }, { date: 'October 20, 2026', sha256: B }, { date: 'October 20, 2026', sha256: C }]
    expect(today).toEqual(pinnedRow(unnamed))
    expect(ledgerFaults(unnamed)).toEqual(['row 3 shares the day of the row before it and names no pull request that changed the page that day (sameDay)'])
    expect(ledgerFaults([{ date: 'November 2, 2026', sha256: A }, { date: 'June 16, 2026', sha256: B }])).toEqual(['row 2 is dated before the row above it'])
    expect(ledgerFaults([{ date: 'Someday', sha256: A }])).toEqual(['row 1 has no readable date'])
  })
})
