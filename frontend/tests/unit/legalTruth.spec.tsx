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
 * 1. /security's claims that nothing in the repository supported stay out (REMOVED_CLAIMS), each read as its family: a
 *    Redis cache (production runs none, ADR-0004); an uptime figure or guarantee (a percentage, written with % or as
 *    percent or per cent, beside uptime, availability or an SLA, or a guarantee beside uptime or availability, in
 *    either order; none is offered); firewalls or intrusion detection or prevention (nothing configures them); every
 *    endpoint behind authentication (ENDPOINT_CLAIM: "all" or "every" endpoints as main's reading has them; "all",
 *    "every", "each" or "any" with up to three words before "endpoints", as in "all of the API's endpoints", whose own
 *    predicate says they need a login, after them in their clause ("each endpoint requires a login", "sits behind a
 *    login", "can only be called with a token") or before them as their requirement ("a login is required for each
 *    endpoint"), not after a negation, unless a relative clause or a participle narrows them, as "any endpoint
 *    returning account data" does; and "no endpoint" answering without authentication in its clause, the claim the
 *    other way round; login words in another role or clause pass ("Each API endpoint documents the token format.", "Any
 *    endpoint may accept an optional token."), and so does "No API endpoints require authentication.", which says the
 *    opposite; search, company pages and summaries are public); a Content Security Policy against XSS or cross-site
 *    scripting (the site sends frame-ancestors only); role-based access, permissions or authorisation, or RBAC (one
 *    administrator flag); an adjective in place of a fact (enterprise, military or bank grade or level, industry
 *    standard or standards, hyphenated or not); no financial data stored, a negation, contracted or not, on either side
 *    (payment records are kept); post-incident reviews or post-mortems and vetting the providers (no process in the
 *    repository does either); and an analytics-consent promise not scoped to the browser in its own sentence
 *    (CONSENT_PROMISE; the API sends account events whatever the reader chose: D-051). That promise names the analytics
 *    by a name the F33 check reads them by (analytics, tracking, statistics, PostHog, usage, telemetry), or as the
 *    account's, the server's or the API's events ("your data" and "event invitations" are not the analytics), and makes
 *    them wait for a yes: "only" up to 60 characters before "after (once, when, if or until) you allow" (accept, agree,
 *    consent, opt in, give consent, say yes, turn or switch on, enable), before "with (after, upon, on or by) your
 *    consent" with up to three words before the consent (permission, agreement, approval, opt-in, each read by its
 *    start, so "only after consenting" fails too), or before "once allowed", a sentence that names the browser ("in
 *    your browser") reading as scoped; or, in the forms the "only" ones miss, "until you allow", a negation, contracted
 *    or not, before "without your consent", "requires (needs, waits for, is or are subject to) your consent",
 *    "consent-gated" or "opt-in", where a sentence that names the browser or its part, its analytics cookies or session
 *    recording (the consent dialog's own "Analytics cookies and session recording stay off until you allow them", and
 *    "Session recording with PostHog is opt-in"), reads as scoped, and where the verb says the promise, a denial before
 *    it or on the subject passes ("No server events require your consent", "Server events do not need your consent"),
 *    while "No analytics run until you allow them" and "No usage data is sent without your permission" still promise.
 *    The scan reads /security's rendered tree, as one text (a heading runs into the body under it) and block by block
 *    (blockTexts: a list item or a paragraph on its own, so a provider's item is not read through the PostHog line's
 *    "in your browser"), /privacy's and /terms' rendered trees the same way (/privacy carries the account-events
 *    sentence too), the page module's literals (its metadata, which no render shows) and the waitlist page's copy
 *    (strings, JSX text and each element's run across its inline elements, outside className), sentence by sentence, a
 *    sentence ending only at ".", "!" or "?", so a `<strong>Label:</strong> body` item is read whole. The planted forms
 *    run through the same render, text, blocks and splitter and score the reach: main's sentences and their close
 *    rewordings fail, the page's new sentences and class names pass, and so do true or unrelated sentences a wider
 *    reading once refused (#1456's review and Codex: "We delete your data only with your consent.", "Any endpoint may
 *    return 503."). Out of reach, planted as gaps: a claim split across two sentences, one said in other words
 *    ("PostHog runs after you allow it", "the whole API sits behind authentication", "each endpoint checks that the
 *    caller holds a token"), and an unscoped consent promise in a sentence that also names the browser or its part.
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
 *    appended), which passes, since the diff shows the row rewritten; and whether a row's date is the day main's
 *    history gives the merge that shipped it (lib/legalDates.ts), since no run reads the clock or the history.
 * 5. A /security claim that stands on a document, not the code, names it in a comment beside the claim,
 *    `{/* Source: <path> §<n>, "<heading>"[, step <m>] ... *\/}`, and the document must exist, hold that numbered
 *    section, and say each word the claim names in a numbered step of it (in step <m> alone, when the comment cites
 *    one), its label, its text or a line that carries it on (SOURCED_STEPS, which lists each claim's cited step): the
 *    runbook bullet stands on tasks/security_privacy_runbook.md §3's steps that contain and assess, gather evidence and
 *    rotate keys, and the notification bullet on its step 2, which notifies the supervisory authority and the affected
 *    users. Which claims stand on a document is review-checked; each one SOURCED_STEPS lists must carry its comment,
 *    citing the step listed. Planted documents score the reader: a missing file, a renamed heading, a missing step, a
 *    step's words gone, a cited step that lacks them while another step holds them, and a cited step that is not there
 *    fail.
 * 6. The audit-log item names only what an audit_logs row records (AUDITED): each thing it names stands on actions the
 *    backend writes, read from each create_audit_log call and each audit_service helper another module calls. The item
 *    names part of what the rows record, and AUDITED_UNNAMED holds the rest, each with what it records: a Google or
 *    Apple sign-in linked to an existing account or unlinked from it (oauth_linked, oauth_unlinked), and two
 *    administrator actions on summaries, a bulk reset and a regeneration of stale ones (summaries_bulk_reset,
 *    summaries_refresh_stale). Every action written is in one map or the other, so a new one fails until it is placed;
 *    naming one on the page changes the page's sentence, which is the founder's. Administrator actions are named one by
 *    one, since six of them write a log line and no row (admin_filing_service.py's filing maintenance and stale-XBRL
 *    bulk reset, the XBRL cache clear, the test mail). This reader sees only that some module writes a named action,
 *    not that every path of the event does; that is the backend's to pin. For logouts (E137),
 *    test_auth_token_flows.py's logout cases and the logout_signed_in and logout_cookie_only cases in
 *    test_cached_filings_pool_lifetime.py pin that a logout that ends a session writes its row, under the user whose
 *    session it ended.
 * 7. /security promises nothing of refresh tokens and logging out that the code does not enforce when requests overlap
 *    (E127_PROMISES): a refresh token that works once (one-time, cannot be used twice, read beyond main's phrases only
 *    in a sentence about the refresh or session token: "a one-time recovery code" is another credential), a reused one
 *    revoking the account or sweeping its sessions (every session ended, signed out on every device; a session that
 *    ends on its own beside "again" is no sweep), or a session that ends after logging out or a password change, within
 *    a time or with none named (every session, everywhere, a session token revoked), a logout in each spelling (logout,
 *    logged out, a sign-out; a revocation alone, as a renewal's of the token it replaces, is none), and what ends named
 *    before its verb ("a session open elsewhere then ends", "every device is signed out") or signed out with no pronoun
 *    ("signs out every device"). A denial passes, a negation before the verb with an aside or not ("does not, by
 *    itself, end") or on the subject ("No sessions are ended", "None of your sessions", "Not every device"), and so
 *    does an end at its token's expiry ("that session ends when its token expires"). Main's timed and untimed readings
 *    keep main's verdicts where main's logging-out words call them; where only the wider ones do ("a logout", "a
 *    sign-out", "every device"), a denial passes there too ("No session ends within 30 minutes of a logout"). The page
 *    is read on every run, whatever tasks/todo.md records: E127's race is fixed (#1422) and so is a login that
 *    straddled a password reset (#1431), but a session token already issued runs to its expiry, and E96 (how a reused
 *    token's sweep reads) and E133 (a logout that does not wait for an in-flight renewal) are open; the stronger
 *    wording returns only in a pull request that carries the founder's go-ahead (tasks/todo.md F53) and changes this
 *    check. Each family is read in one list item or paragraph (blockTexts). Planted forms score the reach; out of
 *    reach, planted as gaps: a promise split across two items, and one said in other words ("nobody stays signed in").
 * 8. /security's numbers repeat the repository's facts (NUMBERS): the session token's 30 minutes
 *    (ACCESS_TOKEN_EXPIRE_MINUTES), the refresh token's 30 days (REFRESH_TOKEN_EXPIRE_DAYS), the lockout's ten failures
 *    (LOCKOUT_THRESHOLD) and its two 15 minutes (LOCKOUT_SECONDS), HSTS's year (main.py's max-age), the breach check's
 *    first five characters (pwned_passwords.py's prefix) and the export on the first of each month (its workflow's
 *    cron), so a change to either side fails until the two agree; and Dependabot's weekly checks of npm, pip and the
 *    GitHub Actions (dependabot.yml) stand beside "every week". The deploy overrides none of the backend's defaults; a
 *    value set by hand on the service is out of reach.
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
 * under its date, and each later row a text a merge ships, under the day main's history gives that merge
 * (lib/legalDates.ts). Append a row in the commit that
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
    { date: 'October 21, 2026', sha256: '865b53735c88175d' },
  ],
  security: [
    { date: 'June 22, 2026', sha256: '13d1b7070566bf07' },
    { date: 'October 21, 2026', sha256: '7e03a05b33c1cf00' },
    { date: 'October 21, 2026', sha256: '272031790b35816d', sameDay: '#1397 changed the page that day too' },
    { date: 'October 21, 2026', sha256: 'f01e686b3c5afee8', sameDay: '#1449 changed the page that day too' },
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

/** A clause whose subject is denied, from its start up to the verb: "No sessions are ended", "None of your devices is
    signed out", "Not every session ends", "No server events require your consent", "Nothing the API records waits
    for your consent" ("no matter" and "no sooner" deny nothing). */
const DENIED_SUBJECT = String.raw`(?:^|[;:]\s*|,\s+|\b(?:and|but|so|while|whereas)\s+)(?:no(?!\s+(?:matter|sooner)\b)|none|nothing|neither|nobody|not\s+(?:every|all|one|any|each|a\s+single|even\s+one))\b(?:(?!,\s*(?:and|but|so|or|while|whereas|then)\b)[^.;:!?])*`
/** Not after a negation: "does not end your other sessions", "never signs you out", "does not, by itself, end a
    session" and "do not need your consent" deny what the verb says, and so does a clause whose subject is denied
    (DENIED_SUBJECT). The end forms and the consent forms whose verb says the promise read it. */
const NOT = String.raw`(?<!\b(?:not|never|nor|cannot|no longer)\s+(?:\w+\s+)?|n['’]t\s+(?:\w+\s+)?|(?:\b(?:not|never|cannot)|n['’]t)\s*,[^,.;:!?]{1,40},\s*|${DENIED_SUBJECT})`
/** The analytics by any name ANONYMOUS_ANALYTICS reads them by, and events only as the account, the server or the API
    names them ("account events", "the events the API records"; "usage data" and "usage events" are usage), so "your
    data" and "event invitations" are not the analytics. */
const ANALYTICS_NAMES = String.raw`(?:\b(?:analytics|tracking|statistics|PostHog|usage|telemetry)\b|\b(?:account|server|API)\s+events?\b|\bevents?\s+(?:that\s+)?the\s+(?:API|service|server|backend)\s+(?:records?|sends?|captures?|logs?)\b)`
/** The browser's part of the analytics, which does wait for the reader's yes: its analytics cookies and session
    recording (the consent dialog: "Analytics cookies and session recording stay off until you allow them"). */
const BROWSER_PART = String.raw`\b(?:analytics|tracking) cookies\b|\bsession (?:recording|replay)s?\b`
/** The reader's yes, as a clause after "you" says it. */
const YES = String.raw`(?:allow|accept|agree|consent|opt(?:ed)?[- ]in|giv(?:e|en) (?:your |us )?(?:\w+ )?(?:consent|permission)|say yes|turn (?:it |them )?on|switch (?:it |them )?on|enable)`
/** The reader's yes, as a noun. */
const CONSENT = String.raw`(?:consent|permission|agreement|approval|opt[- ]in|say-so)s?`

/** An analytics-consent promise not scoped to the browser, in one sentence (header item 1 lists its forms). The
    "only" forms read a sentence that names the browser as scoped, and read the consent word by its start, so "only
    after consenting" fails as "only after consent" does; the forms that wait for a yes another way read the browser's
    part (BROWSER_PART) as scoped too, so the consent dialog's own sentence and "Session recording with PostHog is
    opt-in." pass. A negation before "without your consent" may be contracted ("doesn't", "won't"). The forms whose
    verb says the promise (requires, needs, waits for or until, is subject to, consent-gated, opt-in) read a denial
    as NOT does, before the verb or on the subject, so "No server events require your consent." passes; "until you
    allow" after another verb and "without your consent" take a denied subject as part of the promise ("No analytics
    run until you allow them", "No usage data is sent without your permission"). */
const CONSENT_PROMISE = new RegExp(
  String.raw`^(?!.*\bin your browser\b)(?=.*${ANALYTICS_NAMES}).*\bonly\b.{0,60}?(?:\b(?:after|once|when|if|until) you(?: have|['’]ve)? ${YES}|\b(?:with|after|upon|on|by) (?:[\w'’-]+ ){0,3}${CONSENT}|\b(?:once|if|when|after) (?:it is |they are |it['’]s |they['’]re )?(?:allowed|accepted|enabled|consented)\b)` +
    String.raw`|^(?!.*(?:\bin your browser\b|${BROWSER_PART}))(?=.*${ANALYTICS_NAMES})(?:` +
    String.raw`.*(?<!\bwait(?:s|ing)?\s)\buntil you(?: have|['’]ve)? ${YES}` +
    String.raw`|.*${NOT}\bwait(?:s|ing)?\s+until you(?: have|['’]ve)? ${YES}` +
    String.raw`|.*(?:\b(?:never|not|no|nothing|none)\b|n['’]t\b).{0,60}?\bwithout (?:your )?(?:[\w-]+ )?${CONSENT}\b` +
    String.raw`|.*${NOT}\b(?:requires?|needs?|waits? for|(?:is|are) subject to) (?:your )?(?:[\w-]+ )?${CONSENT}\b` +
    String.raw`|.*${NOT}\bconsent[- ]gated\b|.*${NOT}\bgated (?:on|by|behind) (?:your |the )?(?:[\w-]+ )?(?:consent|choice)\b` +
    String.raw`|.*${NOT}\b(?:is|are) (?:strictly |only )?opt[- ]in\b` +
    ')',
  'i',
)

/** Endpoints that what follows them narrows, a relative clause or a participle ("any endpoint that returns account
    data", "any endpoint returning account data"): a scoped claim, not every one. A verb of their own ("each endpoint
    returns JSON and requires a login") narrows nothing. */
const NARROWED = String.raw`(?!\s+(?:that|which|returning|serving|handling|exposing|reading|writing|for|with)\b)`
/** The endpoints the removed claim speaks of: all, every, each or any with up to three words before "endpoints"
    ("all of the API's endpoints", "every single endpoint", "each API endpoint"), unless what follows narrows them. */
const SOME_ENDPOINTS = String.raw`\b(?:all|every|each|any)\b(?:\s+[\w'’-]+){0,3}?\s+endpoints?\b${NARROWED}`
/** A login, as the claim says the endpoints need one: authentication, a login or sign-in, a token, an account. */
const A_LOGIN = String.raw`(?:(?:a|an|the|your|valid|prior|its own)\s+)*(?:authentication|auth|log[- ]?in|logging in|sign[- ]?in|signing in|(?:bearer\s+|session\s+|access\s+)?tokens?|account|credentials?)\b`
/** The words between the endpoints and their predicate, in their own clause: none opens another clause (which, that,
    when, because, but, or, ", and the login page ..."), up to six of them. */
const IN_THEIR_CLAUSE = String.raw`(?:(?:\s*,)?\s+(?!(?:which|that|who|whom|whose|where|when|while|whereas|because|if|unless|so|but|or)\b|and\s+(?:the|a|an|its|their|your|our|we|you|it|they|this|these|those)\b)[\w'’-]+){0,6}?(?:\s*,)?\s+`
/** The endpoints' own predicate when it says they need a login, not after a negation (NOT): a requirement with the
    login ("requires a login", "needs a token", "requires you to be logged in"), a state ("is protected", "is
    authenticated", "sits behind a login"), or a use only with one ("can only be called with a token", "answers only to
    a signed-in reader"). */
const NEEDS_A_LOGIN = String.raw`${NOT}\b(?:` +
  String.raw`(?:requires?|required|needs?|demands?|expects?|takes?)\s+${A_LOGIN}` +
  String.raw`|(?:requires?|needs?)\s+(?:you|the reader|readers|callers?|users?)\s+to\s+(?:(?:be\s+)?(?:logged|signed)\s+in|(?:log|sign)\s+in|authenticate)\b` +
  String.raw`|(?:is|are|stays?|remains?)\s+(?:all\s+|always\s+|only\s+)?(?:protected|authenticated|locked|gated|private)\b` +
  String.raw`|(?:is|are|sits?|stands?|lives?|stays?)\s+(?:all\s+|always\s+|only\s+)?behind\s+${A_LOGIN}` +
  String.raw`|(?:can|may|will)\s+only\s+be\s+(?:called|reached|used|accessed|queried|opened)\s+(?:with|by|after|once|when)\s+(?:a\s+|an\s+)?(?:valid\s+)?(?:token|login|logging in|signing in|authentication|account|signed[- ]in|logged[- ]in|authenticated)\b` +
  String.raw`|(?:answers?|responds?|works?|opens?)\s+(?:only\s+)?(?:to|for|with|after|once)\s+(?:a\s+|an\s+)?(?:logged[- ]in|signed[- ]in|authenticated|valid\s+token)` +
  ')'
/** The login said before the endpoints as their requirement: "a login is required for each endpoint", "you need a
    token for any endpoint", "authentication is mandatory on each endpoint", "you must log in to call any endpoint". */
const LOGIN_FOR = String.raw`(?:` +
  String.raw`\b${A_LOGIN}\s+(?:is|are)\s+(?:always\s+|strictly\s+)?(?:required|needed|mandatory|necessary|enforced|checked|expected)\s+(?:for|on|by|at|in|to\s+(?:call|reach|use|query|open))\s+(?:the\s+)?` +
  String.raw`|${NOT}\b(?:you|readers?|callers?|clients?|users?)\s+(?:need|needs|require|requires|must\s+(?:have|present|send|hold|show))\s+${A_LOGIN}\s+(?:for|on|to\s+(?:call|reach|use|query|open))\s+(?:the\s+)?` +
  String.raw`|${NOT}\b(?:you|readers?|callers?|clients?|users?)\s+(?:must|have to|need to)\s+(?:log|sign)\s+in\s+(?:to|before|first to)\s+(?:call|calling|reach|reaching|use|using|query|querying|open|opening)\s+(?:the\s+)?` +
  ')'
/** Every endpoint behind authentication: main's reading (all or every, with "of", "our" or "the" and "API" between);
    SOME_ENDPOINTS with their own predicate saying they need a login, after them in their clause (NEEDS_A_LOGIN) or
    before them as their requirement (LOGIN_FOR); and the claim the other way round, "no endpoint" answering without
    authentication, unauthenticated or to anonymous requests, in its clause. "Each API endpoint documents the token
    format.", "Any endpoint may accept an optional token." and "No API endpoints require authentication." pass. */
const ENDPOINT_CLAIM = new RegExp(
  String.raw`\b(?:all|every)\b(?:\s+of)?(?:\s+(?:our|the))?(?:\s+API)?\s+endpoints?\b` +
    String.raw`|${SOME_ENDPOINTS}${IN_THEIR_CLAUSE}${NEEDS_A_LOGIN}` +
    String.raw`|${LOGIN_FOR}${SOME_ENDPOINTS}` +
    String.raw`|\bno\b(?:\s+[\w'’-]+){0,3}?\s+endpoints?\b${NARROWED}${IN_THEIR_CLAUSE}(?:without\s+(?:an?\s+)?(?:authentication|log[- ]?in|logging in|sign[- ]?in|signing in|token|account)\b|unauthenticated\b|(?:\w+\s+)?anonymous(?:ly\b|\s+(?:users?|requests?|callers?|readers?|access|visitors?)\b))`,
  'i',
)

const REMOVED_CLAIMS: Array<[string, RegExp]> = [
  ['a Redis cache', /\bredis\b/i],
  [
    'an uptime figure or guarantee',
    new RegExp(String.raw`\b(?:uptime|availability|SLA)\b[^.]*${PERCENT}|${PERCENT}[^.]*\b(?:uptime|availability|available|SLA)\b|\b(?:uptime|availability)\b[^.]*\bguarantee(?:s|d)?\b|\bguarantee(?:s|d)?\b[^.]*\b(?:uptime|availability|available)\b`, 'i'),
  ],
  ['firewalls or intrusion detection', /\bfirewalls?\b|\bintrusion[- ](?:detection|prevention)\b/i],
  ['every endpoint behind authentication', ENDPOINT_CLAIM],
  ['a Content Security Policy against XSS', new RegExp(`${CSP}[^.]*${XSS}|${XSS}[^.]*${CSP}`, 'i')],
  ['role-based access control', /\brole[- ]based (?:access|permissions?|authori[sz]ation)\b|\bRBAC\b/i],
  ['an adjective in place of a fact', /\b(?:enterprise|military|bank)[- ](?:grade|level)\b|\bindustry[- ]standards?\b/i],
  ['no financial data stored', /(?:\b(?:no|never|not|none)\b|n['’]t\b)[^.]{0,40}\bfinancial data\b|\bfinancial data\b[^.]{0,40}(?:\b(?:never|not)\b|n['’]t\b)/i],
  ['post-incident reviews', /\bpost[- ]incident reviews?\b|\bpost[- ]?mortems?\b/i],
  ['vetting the providers', /\bvet(?:s|ted|ting)?\b/i],
  ['an analytics-consent promise not scoped to the browser', CONSENT_PROMISE],
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
 * refresh token both succeeding, a renewal racing a logout leaving a live token) is fixed by #1422, and a login that
 * straddled a password reset by #1431, but nothing revokes a session token already issued (get_current_user keeps no
 * list of revoked ones), so "logging out of all devices ends every session" is untrue as said, and E96 (how a reused
 * token's sweep reads) and E133 (a logout that does not wait for an in-flight renewal) are open. The stronger wording
 * returns only in a pull request that carries the founder's go-ahead (tasks/todo.md F53) and changes this check. Each
 * family is read in one block (a list item or a paragraph), so a promise split across the sentences of one item is
 * read whole.
 */
const SESSION_END_TIMED =
  /\b(?:ends?|ended|expires?|stops?|closes?|(?:signs?|logs?|signed|logged) (?:you )?out|(?:is|are) (?:revoked|ended))\b.*(?:\b(?:within|after|in)\s+(?:\d+|a|an|one|ten|fifteen|thirty|sixty)\s+(?:seconds?|minutes?|hours?|days?)\b|\b(?:immediately|at once|instantly|right away)\b)/i

/** The same promise with no time named: every, all, each, any or other sessions ended, you signed out everywhere or of
    every device, or a session token revoked. A verb with a negation at most three words before it ("None of these
    revokes a session token") promises nothing. */
const SESSION_END_UNTIMED = new RegExp(
  String.raw`(?<!\b(?:none of (?:these|them|this)|not|never|no longer|cannot|can't|does not|doesn't|do not|don't|won't|will not)\s+(?:\S+\s+){0,3})` +
    String.raw`\b(?:(?:ends?|ended|closes?|closed|terminates?|terminated|stops?|stopped|revokes?|revoked|invalidates?|invalidated|kills?|killed)\b.*\b(?:every|all|each|any|other)\b(?:\s+\w+)?\s+sessions?\b` +
    String.raw`|(?:signs?|logs?|signed|logged)\s+you\s+out\s+(?:of\s+)?(?:everywhere|every|all|each|other|any)\b` +
    String.raw`|(?:ends?|ended|revokes?|revoked|invalidates?|invalidated|kills?|killed)\b[^.;]*\bsession tokens?\b)`,
  'i',
)

/** What a promise of logging out says ends: a session (a session token is a token, not a session), a device, a tab or
    a browser, with a word that says which ("every session", "your other sessions", "all of your devices"), or
    everywhere, elsewhere or the others. */
const ENDED = String.raw`(?:\b(?:every|all|each|any|your|the|other|open)\b(?:\s+(?:of|your|the|other|open|active|remaining))*\s+(?:sessions?(?![- ]tokens?)|devices?|tabs?|browsers?)\b|\b(?:everywhere|elsewhere|the others)\b)`
/** A verb that ends one ("the end of" is a noun). */
const ENDS = String.raw`${NOT}\b(?:end(?:s|ed|ing)?(?!\s+of\b)|clos(?:e|es|ed|ing)|stop(?:s|ped|ping)?|terminat(?:e|es|ed|ing)|kill(?:s|ed|ing)?|invalidat(?:e|es|ed|ing)|expir(?:e|es|ed|ing)|times? out|timed out|cuts? off)\b`
/** A time an end comes within: a span, or at once. */
const WITHIN = String.raw`(?:\b(?:within|after|in|under|inside)\s+(?:(?:\d+|a|an|one|two|three|five|ten|fifteen|twenty|thirty|forty|sixty|a few|a couple of|half an?)\s+)?(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b|\b(?:immediately|at once|instantly|right away|straight away|straightaway|without delay|on the spot)\b)`
/** A logging-out action, as a block names it: a logout and a sign-out in their spellings (log out, logged out,
    logout, log-out, signing out, sign-out), all devices or every device, everywhere, a password. A revocation alone is
    none: a renewal revokes the token it replaces, and the Token renewal item says so. */
const LOGGING_OUT = /\b(?:log(?:s|ged|ging)?[- ]?outs?|sign(?:s|ed|ing)?[- ]?outs?|all (?:of )?(?:your |the )?devices|every device|everywhere|passwords?)\b/i
/** An end at its token's expiry ("that session ends when its token expires"): the expiry, not a logout's end. */
const AT_EXPIRY = String.raw`(?!\s+(?:only\s+)?(?:when|once|as soon as|after)\s+(?:its|the|that|their|your)\s+(?:own\s+)?(?:session\s+)?tokens?\s+(?:expires?|has expired|have expired|runs? out)\b)`
/** The forms of an end the two above miss: the verb before what it ends with no "every" ("ends your sessions", "ends
    the others"), a sign-out with no pronoun or not after "of" ("signs out every device", "signs you out on every
    device", "you are logged out"), what ends named before its verb ("a session open elsewhere then ends", "every
    device is signed out"), and an end within a time in more verbs and spans ("within half an hour", "straight away"). A
    session "keeps working until its session token expires" promises no end: what ends before its verb takes no
    "expires", which reads its token's expiry, and an end when its token expires ("that session ends when its token
    expires") is the expiry, not a logout's. */
const SESSION_END_MORE = new RegExp(
  [
    String.raw`${ENDS}(?:[^\w.;!?]+[\w'’-]+){0,3}?[^\w.;!?]+${ENDED}`,
    String.raw`${NOT}\brevok(?:e|es|ed|ing)\b(?:[^\w.;!?]+[\w'’-]+){0,3}?[^\w.;!?]+\b(?:every|all|each|any|your|the|other|open)\b(?:\s+(?:of|your|the|other|open|active))*\s+sessions?\b(?![- ]tokens?)`,
    String.raw`${NOT}\b(?:signs?|logs?|signed|logged)\s+(?:you|everyone|everybody)\s+out\b`,
    String.raw`${NOT}\b(?:signs|logs|signed|logged)\s+out\s+(?:of\s+|from\s+|on\s+|across\s+)?${ENDED}`,
    String.raw`\b(?:you|everyone|everybody)(?:['’]re|\s+are|\s+will be|\s+get|\s+are then)\s+(?:signed|logged)\s+out\b`,
    String.raw`\b(?:sessions?(?![- ]tokens?)|devices?|tabs?|browsers?|the others)\b[^.;!?]*?${NOT}\b(?:end(?:s|ed)?(?!\s+of\b)|clos(?:e|es|ed)|stop(?:s|ped)?|terminat(?:e|es|ed)|times? out|timed out|(?:is|are|get|gets|will be|would be|be)\s+(?:ended|closed|terminated|revoked|invalidated|killed|cut off|signed out|logged out))\b${AT_EXPIRY}`,
    String.raw`${NOT}(?:\b(?:ends?|ended|expires?|stops?|closes?|(?:signs?|logs?|signed|logged) (?:you )?out|(?:is|are) (?:revoked|ended))\b|\b(?:ending|expired|stopped|closed|terminat(?:e|es|ed|ing)|kill(?:s|ed)?|invalidat(?:e|es|ed)|times? out|timed out|cuts? off|(?:signs?|logs?|signed|logged)\s+(?:you\s+)?out)\b).*${WITHIN}`,
  ].join('|'),
  'i',
)
/** A reuse, as a sentence names it. */
const REUSED = String.raw`\b(?:a second time|again|twice|more than once|re-?us(?:e|ed|es|ing)|replay(?:s|ed|ing)?|already (?:been )?used|used before|(?:old|used|rotated(?:[- ]away)?|stale|spent) (?:refresh )?tokens?)\b`
/** Every session or device the account has ("every session on the account", "all of your devices"), or everywhere. */
const EVERY_SESSION = String.raw`(?:\b(?:every|all|each)\b(?:\s+(?:of|your|the|its|other|open|active|remaining))*\s+(?:sessions?(?![- ]tokens?)|devices?)\b|\beverywhere\b)`
/** A sweep of the account's sessions, as a reuse's consequence: what ends every session, signs you out on every device
    or everywhere, or logs everyone out, and every session named before the verb that ends it. A session that ends on
    its own beside a reuse word ("your session ends and you log in again") is no sweep. */
const SWEEP = [
  String.raw`${ENDS}(?:[^\w.;!?]+[\w'’-]+){0,3}?[^\w.;!?]+${EVERY_SESSION}`,
  String.raw`${NOT}\b(?:signs?|logs?|signed|logged)\s+(?:(?:you|everyone|everybody)\s+)?out\b(?:[^\w.;!?]+[\w'’-]+){0,3}?[^\w.;!?]+${EVERY_SESSION}`,
  String.raw`${NOT}\b(?:signs?|logs?|signed|logged)\s+(?:everyone|everybody)\s+out\b`,
  String.raw`${EVERY_SESSION}[^.;!?]*?${NOT}\b(?:end(?:s|ed)?|clos(?:e|es|ed)|terminat(?:e|es|ed)|(?:is|are|get|gets|will be)\s+(?:ended|closed|terminated|revoked|invalidated|signed out|logged out))\b`,
].join('|')
/** Main's works-once phrases, read as main reads them, in any block. */
const WORKS_ONCE = /\bworks? (?:only )?once\b|\bsingle[- ]use\b|\b(?:used|usable|valid|good) (?:only )?(?:once|one time)\b|\bonly once\b|\bone time only\b/i
/** The one-use forms main's phrases miss ("one-time", "good for one use", "cannot be used twice", "cannot be reused",
    "after one use"), read only in a sentence about the refresh or session token: one that names it (TOKEN_CONTEXT), or
    one in a block that names it and names no other credential (OTHER_CREDENTIAL), as "Each one cannot be reused." in
    the Token renewal item. "A one-time recovery code", a reset link and a verification code are other credentials. */
const ONE_USE = /\bone-time\b|\b(?:used|usable|valid|good)(?: only)? for (?:one|a single) use\b|\b(?:can(?:not|['’]t)|can never|may not|never|won['’]t) be (?:used|presented|accepted) (?:twice|again|more than once|a second time)\b|\b(?:can(?:not|['’]t)|can never|won['’]t) be re-?used\b|\bafter (?:one|a single|its first) use\b/i
/** The refresh or session token, or token renewal, named. */
const TOKEN_CONTEXT = /\b(?:refresh|session)[- ]tokens?\b|\btoken renewal\b/i
/** A credential that is not the refresh or session token: a code, a link, a password, a key, an invite, a PIN. */
const OTHER_CREDENTIAL = /\b(?:codes?|links?|passwords?|passcodes?|passphrases?|keys?|invit\w*|OTPs?|PINs?)\b/i
/** A one-use form about the refresh or session token, in one sentence of the block. */
const oneUseOfTheToken = (block: string) =>
  sentencesOf(block).some((sentence) => ONE_USE.test(sentence) && (TOKEN_CONTEXT.test(sentence) || (TOKEN_CONTEXT.test(block) && !OTHER_CREDENTIAL.test(sentence))))
/** Main's logging-out words, which call its timed and untimed readings with main's verdicts as they stand. */
const MAIN_LOGGING_OUT = /\b(?:log(?:ging|s)? out|sign(?:ing|s)? out|all (?:of your )?devices|everywhere|password)\b/i
/** Main's timed and untimed readings where only the wider words call them (LOGGING_OUT: "a logout", "a sign-out",
    "every device"), with a denial read as SESSION_END_MORE reads one: "No session ends within 30 minutes of a logout."
    denies the end. */
const SESSION_END_TIMED_DENIABLE = new RegExp(NOT + SESSION_END_TIMED.source, 'i')
const SESSION_END_UNTIMED_DENIABLE = new RegExp(NOT + SESSION_END_UNTIMED.source, 'i')

const E127_PROMISES: Array<[string, (block: string) => boolean]> = [
  [
    'a refresh token that works once',
    (block) => inASentence(WORKS_ONCE)(block) || oneUseOfTheToken(block),
  ],
  [
    'a reused refresh token revoking the account',
    inASentence(new RegExp(String.raw`^(?=.*${REUSED})(?=.*(?:\brevok|${SWEEP}|\block(?:s|ed)?\s+(?:the account|you out)\b))`, 'i')),
  ],
  [
    'a session that ends after logging out, within a time or with none named',
    (block) =>
      (MAIN_LOGGING_OUT.test(block) && (inASentence(SESSION_END_TIMED)(block) || inASentence(SESSION_END_UNTIMED)(block))) ||
      (LOGGING_OUT.test(block) &&
        (inASentence(SESSION_END_TIMED_DENIABLE)(block) || inASentence(SESSION_END_UNTIMED_DENIABLE)(block) || inASentence(SESSION_END_MORE)(block))),
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

/** The /security claims that stand on a document, the step each cites (none: any step of the section), and what each
    says the step holds, word for word. Which claims stand on a document is review-checked; each one listed must carry
    its comment, citing the step listed here. */
const SOURCED_STEPS: Record<string, { step?: string; words: string[] }> = {
  'A written runbook covers containing it, finding what it touched, gathering evidence and rotating keys': { words: ['Contain', 'assess', 'Evidence', 'Rotate'] },
  'When the law requires it, we notify the users affected and the data protection authority': { step: '2', words: ['notify', 'supervisory authority', 'affected users'] },
}

/** A `{/* Source: <path> §<n>, "<heading>"[, step <m>] ... *\/}` comment and the list item right after it, in a page's
    source: the path, the section, the heading, the step it cites (if any) and the claim. */
const SOURCE_COMMENT = /\{\/\*\s*Source:\s*(\S+)\s+§(\d+),\s*"([^"]+)"(?:,\s*step\s+(\d+))?[^*]*\*\/\}\s*<li>([^<]+)<\/li>/g

const escapeRe = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** What a source lacks: the file, its numbered section (a heading `## <n>. <heading>`), the step a comment cites, or a
    word the claim names (in the cited step, or with none cited in any numbered step of the section: a step's label, its
    text and the lines that carry it on). */
function sourceFaults(rel: string, doc: string | null, section: string, heading: string, words: string[], step?: string): string[] {
  if (doc === null) return [`${rel} is missing`]
  const lines = doc.split('\n')
  const start = lines.findIndex((line) => new RegExp(String.raw`^#{1,6}\s+${section}\.\s+${escapeRe(heading)}\b`).test(line))
  if (start < 0) return [`${rel} has no §${section} "${heading}" heading`]
  const next = lines.findIndex((line, i) => i > start && /^#{1,6}\s/.test(line))
  const items: Array<{ n: string; text: string }> = []
  for (const line of lines.slice(start + 1, next < 0 ? undefined : next)) {
    const numbered = line.match(/^\s*(\d+)\.\s/)
    if (numbered) items.push({ n: numbered[1], text: line.trim() })
    else if (items.length > 0 && /^\s+\S/.test(line)) items[items.length - 1].text += ` ${line.trim()}`
    else if (!line.trim()) items.push({ n: '', text: '' })
  }
  const cited = step === undefined ? items : items.filter((item) => item.n === step)
  if (step !== undefined && cited.length === 0) return [`${rel} §${section} has no step ${step}`]
  return words
    .filter((word) => !cited.some((item) => new RegExp(String.raw`\b${escapeRe(word)}\b`, 'i').test(item.text)))
    .map((word) => (step === undefined ? `${rel} §${section} has no step that says "${word}"` : `${rel} §${section} step ${step} does not say "${word}"`))
}

/** What the audit-log item names, and the audit_logs actions the backend writes for each. A sign-up through Google or
    Apple writes only an oauth_login row, read under logins. */
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

/** The audit_logs actions the backend writes that the item does not name, and what each records. The item names part
    of what the rows record; naming one of these on the page changes the page's sentence, which is the founder's. */
const AUDITED_UNNAMED: Record<string, string> = {
  oauth_linked: 'a Google or Apple sign-in linked to an existing account',
  oauth_unlinked: 'a Google or Apple sign-in unlinked in the account settings',
  summaries_bulk_reset: "an administrator's bulk reset of generated summaries, so they regenerate",
  summaries_refresh_stale: "an administrator's regeneration of stale summaries in place",
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

/** /security's numbers, each beside the repository fact it repeats: a backend default (the deploy overrides none of
    them), the breach check's hash prefix or the export's day of the month. A change to either side fails until the two
    agree. A number the page writes as a word reads through NUMBER_WORDS, the day of the month as "first". */
const NUMBERS: Array<{ says: RegExp; file: string; value: RegExp; per: number }> = [
  { says: /\bThe session token expires after (\w+) minutes\b/, file: 'backend/app/config.py', value: /^\s*ACCESS_TOKEN_EXPIRE_MINUTES: int = (\d+)\b/m, per: 1 },
  { says: /\ba refresh token that lasts (\w+) days\b/, file: 'backend/app/config.py', value: /^\s*REFRESH_TOKEN_EXPIRE_DAYS: int = (\d+)\b/m, per: 1 },
  { says: /\b(\w+) failed logins for one email address\b/, file: 'backend/app/services/login_lockout.py', value: /^LOCKOUT_THRESHOLD = (\d+)\b/m, per: 1 },
  { says: /\beach within (\w+) minutes of the last\b/, file: 'backend/app/services/login_lockout.py', value: /^LOCKOUT_SECONDS = (\d+)\b/m, per: 60 },
  { says: /\bblock password logins for that address for (\w+) minutes\b/, file: 'backend/app/services/login_lockout.py', value: /^LOCKOUT_SECONDS = (\d+)\b/m, per: 60 },
  { says: /\bonly over HTTPS for (\w+) years? \(HSTS\)/, file: 'backend/main.py', value: /^\s*headers\["Strict-Transport-Security"\] = "max-age=(\d+)\b/m, per: 365 * 24 * 3600 },
  { says: /\bsending only the first (\w+) characters of its SHA-1 hash\b/, file: 'backend/app/services/pwned_passwords.py', value: /^\s*prefix, suffix = sha1\[:(\d+)\], sha1\[\1:\]/m, per: 1 },
  { says: /\bbucket on the (\w+) of each month\b/, file: '.github/workflows/monthly-sql-export.yml', value: /^\s*- cron: '\d+ \d+ (\d+) \* \*'/m, per: 1 },
]

const NUMBER_WORDS: Record<string, number> = { a: 1, an: 1, one: 1, first: 1, two: 2, three: 3, five: 5, ten: 10, fifteen: 15, twenty: 20, thirty: 30 }

/** A page number as a value: digits, or a word NUMBER_WORDS reads. */
const numberOf = (word: string) => (/^\d+$/.test(word) ? Number(word) : NUMBER_WORDS[word.toLowerCase()])

describe("/security says what the code and the hosting do (D-046)", () => {
  it('names none of the claims D-046 removed, and neither do /privacy, /terms or the waitlist page', () => {
    const { container, unmount } = render(<SecurityPage />)
    const text = pageText(container)
    const page = claimsInTree('/security', container)
    unmount()
    expect(text.length).toBeGreaterThan(4000)
    // /privacy carries the account-events sentence too, so an unscoped consent promise there contradicts it as it would
    // on /security; /terms is read for the same families.
    const others = (['privacy', 'terms'] as const).flatMap((key) => {
      const { container: other, unmount: close } = render(PAGES[key]())
      expect(pageText(other).length, `/${key} renders`).toBeGreaterThan(4000)
      const found = claimsInTree(`/${key}`, other)
      close()
      return found
    })
    const security = literals('app/security/page.tsx')
    expect(security).toContain('Security practices and data protection at EarningsNerd.') // the metadata, which no render shows
    const waitlist = literals('app/waitlist/page.tsx')
    expect(waitlist).toContain('Security') // the trust panel's tile title: the scan reads the tile's copy
    expect(waitlist.some((l) => /\bmt-\d|\bgrid\b/.test(l))).toBe(false) // and none of its class names
    expect([
      ...page,
      ...others,
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
      // One form apiece for the branches no other form reaches alone (round 6's review): an SLA, "available" after a
      // figure and after a guarantee, "level", the other two forms of vetting, tracking as the analytics, and a heading
      // read into the body under it, which only the whole-text reading sees.
      ['<p>Our SLA covers 99.9% of each month.</p>', true],
      ['<p>The site is 99.9% available.</p>', true],
      ['<p>We guarantee the site stays available.</p>', true],
      ['<p>We use bank-level encryption.</p>', true],
      ['<p>Every provider is vetted.</p>', true],
      ['<p>We keep vetting our providers.</p>', true],
      ['<p>Tracking runs only after you allow it.</p>', true],
      ['<h3>Content Security Policy</h3><p>It blocks XSS attacks.</p>', true],
      // A provider item in the list beside the PostHog line: list items carry no full stop, so the list's text runs
      // on as one sentence and the PostHog line's "in your browser" covered the item; each block is read on its own.
      ['<ul><li><strong>Vercel:</strong> Hosts the site, and counts page views only after you allow analytics</li><li><strong>PostHog:</strong> Usage statistics: PostHog in your browser runs only after you allow analytics, and records sessions only if you allow that too</li></ul>', true],
      // The consent promise with the analytics named as PostHog, usage, events or data (D-051's contradiction itself),
      // "only" before the verb, and an adjective before the consent (#1397's last review, its nine forms).
      ['<p>PostHog runs only after you allow it.</p>', true],
      ['<li><strong>PostHog:</strong> Runs only after you allow it, and records sessions only if you allow that too</li>', true],
      ['<p>The API records account events only with your consent.</p>', true],
      ['<li><strong>PostHog:</strong> Usage statistics: PostHog in your browser runs only after you allow analytics. Server events run only with your consent.</li>', true],
      ['<p>PostHog receives events only with your consent.</p>', true],
      ['<p>Usage data is collected only with your consent.</p>', true],
      ['<p>We only collect usage statistics after you allow analytics.</p>', true],
      ['<p>Analytics only run once you allow them.</p>', true],
      ['<p>Product analytics run only with your explicit consent.</p>', true],
      // The rest of the family, taken from the language: other names, other clauses, other ways to wait for a yes.
      ['<p>Account events are sent only after you allow it.</p>', true],
      ['<p>Telemetry is sent only after you allow it.</p>', true],
      ['<p>We track usage only after you allow cookies.</p>', true],
      ['<p>We collect usage statistics only after you give consent.</p>', true],
      ['<p>Usage data is collected only with the reader’s prior consent.</p>', true],
      ['<p>Analytics run only once allowed.</p>', true],
      ['<p>Analytics run only after consenting.</p>', true],
      ['<p>Analytics stay off until you allow them.</p>', true],
      ['<p>PostHog never runs without your consent.</p>', true],
      ['<p>No usage data is sent without your permission.</p>', true],
      ['<p>Usage tracking requires your consent.</p>', true],
      ['<p>Our analytics are consent-gated.</p>', true],
      ['<p>Analytics are opt-in.</p>', true],
      // A contracted negation before "without your consent" (#1456's review).
      ["<p>The API doesn't record account events without your consent.</p>", true],
      ['<p>PostHog won’t run without your consent.</p>', true],
      ["<p>We don't send usage events without your consent.</p>", true],
      // The removed promise in its plainest words, "are subject to" with it, and "No" where the promise needs it
      // (#1456's third round).
      ['<p>Server events require your consent.</p>', true],
      ['<p>Server events are subject to your consent.</p>', true],
      ['<p>Server events wait until you allow them.</p>', true],
      ['<p>No analytics run until you allow them.</p>', true],
      // Every endpoint with other words before "endpoints" (#1397's last review), each and any with a login said, and
      // the claim the other way round.
      ["<p>All of the API's endpoints require authentication.</p>", true],
      ['<p>All of the API’s endpoints require authentication.</p>', true],
      ['<p>Every single endpoint requires authentication.</p>', true],
      ['<p>All REST API endpoints require authentication.</p>', true],
      ['<p>No API endpoint answers without authentication.</p>', true],
      ['<p>Each endpoint requires a login.</p>', true],
      ['<p>No endpoint can be reached unauthenticated.</p>', true],
      // The login need as the endpoints' own predicate, after them in their clause or before them as their requirement
      // (#1456's fourth round, Codex's thread 4335911303).
      ['<p>Any endpoint needs a token.</p>', true],
      ['<p>Each endpoint sits behind a login.</p>', true],
      ['<p>Each endpoint is authenticated.</p>', true],
      ['<p>Each endpoint can only be called with a token.</p>', true],
      ['<p>Each endpoint returns JSON and requires a login.</p>', true],
      ['<p>A login is required for each endpoint.</p>', true],
      ['<p>You need a token for any endpoint.</p>', true],
      ['<p>Authentication is mandatory on each endpoint.</p>', true],
      ['<p>No endpoint accepts anonymous requests.</p>', true],
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
      // The consent dialog's own sentence (its analytics cookies are the browser's), /privacy's D-049 sentence, and a
      // sentence that says the events wait for no consent, the account-events sentence among them.
      ['<p>Analytics cookies and session recording stay off until you allow them.</p>', false],
      ['<p>Analytics and session recording in your browser stay off until you allow them, and you can change your choice at any time in Cookie settings.</p>', false],
      ['<p>The service also records how accounts use it, such as sign-ups, plan changes, payments, feedback and feature use, against your internal account id, to run and improve it. This does not depend on your analytics choice.</p>', false],
      ['<p>Account events do not need your consent.</p>', false],
      ['<p>The API serves your profile, watchlist, alerts, saved summaries and billing only to your logged-in session.</p>', false],
      ["<p>The API's endpoints for search, company pages and summaries are open to everyone.</p>", false],
      // True or unrelated sentences the wider readings refused (#1456's review, Codex's threads 4333431432 and
      // 4333431438, and the design recheck's negative controls): data and events the analytics do not name, a
      // browser-only opt-in, and endpoints with no login said, the opposite said, or narrowed.
      ['<p>We delete your data only with your consent.</p>', false],
      ['<p>Your data export requires your consent.</p>', false],
      ['<p>We share your data with third parties only with your consent.</p>', false],
      ['<p>We use your data for marketing emails only with your consent.</p>', false],
      ['<p>Processing your data for marketing requires your consent.</p>', false],
      ['<p>Event invitations are opt-in.</p>', false],
      ['<p>Session recording with PostHog is opt-in.</p>', false],
      ['<p>Each API endpoint is documented publicly.</p>', false],
      ['<p>Any endpoint may return 503.</p>', false],
      ['<p>No API endpoints require authentication.</p>', false],
      ['<p>Any endpoint returning account data requires authentication.</p>', false],
      ['<p>No more endpoints are planned.</p>', false],
      // A denied subject before the verb that says the promise, D-051 in other words (#1456's third round, Codex's
      // thread 4335683393).
      ['<p>No server events require your consent.</p>', false],
      ['<p>None of the account events the API records require your consent.</p>', false],
      ['<p>Nothing the API records waits for your consent.</p>', false],
      ['<p>Nothing the API records about account events waits for your consent.</p>', false],
      ['<p>No server events are consent-gated.</p>', false],
      ['<p>No account events are opt-in.</p>', false],
      ['<p>No server event waits until you allow it.</p>', false],
      ['<p>None of the server events need your permission.</p>', false],
      ['<p>Not every account event is subject to your consent.</p>', false],
      // Login words in another role or another clause than the endpoints' predicate (#1456's fourth round, Codex's
      // thread 4335911303), a denial in either order, and "no endpoint" with "without a token" in another clause.
      ['<p>Each API endpoint documents the token format.</p>', false],
      ['<p>Any endpoint may accept an optional token.</p>', false],
      ['<p>Each endpoint logs its latency, and the login page is public.</p>', false],
      ["<p>Each endpoint's documentation explains token renewal.</p>", false],
      ['<p>Each endpoint documents which calls require a token.</p>', false],
      ['<p>A login is not required for each endpoint.</p>', false],
      ['<p>No endpoint changed this month, and the login page still works without a token.</p>', false],
      ['<p>No endpoint logs anonymous data.</p>', false],
      // Out of reach.
      ['<p>Our pages use a Content Security Policy. It blocks XSS.</p>', 'gap'],
      ['<p>Nobody outside our network can reach the servers.</p>', 'gap'],
      ['<p>PostHog in your browser runs only after you allow analytics, and so does every server event.</p>', 'gap'],
      ['<p>Analytics cookies stay off until you allow them, and so do server events.</p>', 'gap'],
      ['<p>PostHog runs after you allow it.</p>', 'gap'],
      ['<p>The whole API sits behind authentication.</p>', 'gap'],
      ['<p>Each endpoint checks that the caller holds a token.</p>', 'gap'],
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
    // A schedule the page states in words: Dependabot checks npm, pip and the GitHub Actions every week.
    expect(text).toMatch(/\bDependabot checks\b[^.]*\bGitHub Actions, for updates every week\./)
    const dependabot = readFileSync(path.join(REPO, '.github/dependabot.yml'), 'utf8')
    expect([...dependabot.matchAll(/package-ecosystem: "([\w-]+)"/g)].map((m) => m[1]).sort()).toEqual(['github-actions', 'npm', 'pip'])
    expect([...dependabot.matchAll(/^\s*interval: "(\w+)"/gm)].map((m) => m[1])).toEqual(['weekly', 'weekly', 'weekly'])
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
      // Untimed: every session ended, signed out everywhere, a session token revoked, a token usable one time.
      ['<li>Logging out of all devices ends every session.</li>', true],
      ['<li><strong>Logging out:</strong> Logging out of all devices signs you out everywhere.</li>', true],
      ['<li>Changing your password signs you out of every device.</li>', true],
      ['<li><strong>Logging out:</strong> Logging out revokes your session tokens.</li>', true],
      ['<li>Resetting your password ends all your other sessions, with no delay.</li>', true],
      ['<li><strong>Logging out:</strong> Logging out revokes the refresh token your browser sends with it. Logging out of all devices, from your account settings, revokes every refresh token your account holds at that moment, and so does changing or resetting your password. Each of these ends every session.</li>', true],
      ['<li>A refresh token can be used one time.</li>', true],
      // The forms the readings above let through (#1397's last review and its refuters): an end named before its verb,
      // a logout's other spellings, a reuse that ends the sessions or signs you out, "one-time", a sign-out with no
      // pronoun or on every device, and a passive sign-out.
      ['<li><strong>Logging out:</strong> Logging out revokes that browser’s refresh token. Logging out of all devices, from your account settings, revokes all of your refresh tokens, and so does changing or resetting your password; a session open elsewhere then ends.</li>', true],
      ['<li>After a logout, every other session ends within 30 minutes.</li>', true],
      ['<li>Once logged out, every session ends within 30 minutes.</li>', true],
      ['<li><strong>Logout:</strong> Every session on the account ends within 30 minutes.</li>', true],
      ['<li>A sign-out ends every session within 30 minutes.</li>', true],
      ['<li>A sign-out on one device ends the others within 30 minutes.</li>', true],
      ['<li>A refresh token presented a second time ends every session on the account.</li>', true],
      ['<li>Presenting a used refresh token again signs you out on every device.</li>', true],
      ['<li>Refresh tokens are one-time tokens.</li>', true],
      ['<li>A refresh token cannot be used twice.</li>', true],
      ['<li>Resetting your password signs you out on every device.</li>', true],
      ['<li>Logging out signs out every device.</li>', true],
      ['<li>After a password reset, every device is signed out.</li>', true],
      // "No matter" denies nothing (#1456's review).
      ['<li>Once you log out, no matter where, every device is signed out.</li>', true],
      // A one-use form about the refresh token, in its sentence or in a sentence of its item (#1456's third round).
      ['<li>Each refresh token is good for one use.</li>', true],
      ['<li><strong>Token renewal:</strong> The session token expires after 30 minutes and is renewed from a refresh token that lasts 30 days. Each one cannot be reused.</li>', true],
      // The items as they read now, and look-alikes, which pass.
      ['<li><strong>Token renewal:</strong> The session token expires after 30 minutes and is renewed from a refresh token that lasts 30 days. Each renewal replaces the refresh token with a new one, and refresh tokens are stored only as hashes.</li>', false],
      ['<li><strong>Logging out:</strong> Logging out revokes the refresh token your browser sends with it. Logging out of all devices, from your account settings, revokes every refresh token your account holds at that moment, and so does changing or resetting your password. None of these revokes a session token already issued.</li>', false],
      ['<li><strong>Failed logins:</strong> Ten failed logins for one email address, each within 15 minutes of the last, block password logins for that address for 15 minutes.</li>', false],
      ['<li>Log out of your account when using shared or public computers</li>', false],
      ['<li>Log out of all devices, in your account settings, revokes every refresh token your account holds.</li>', false],
      ['<li><strong>Logging out:</strong> None of these revokes a session token already issued; a session open elsewhere keeps working until its session token expires.</li>', false],
      ['<li>Logging out of one device does not end your other sessions.</li>', false],
      ['<li>Use Sign out of all devices in your account settings.</li>', false],
      ['<li>Registrations, logins, failed logins, logouts, data exports and account deletions are written to an audit log</li>', false],
      // True sentences the wider readings refused (#1456's review, Codex's thread 4333431444 and the design recheck's
      // controls): a renewal's revocation, an end at its token's expiry, a session that ends on its own beside "again",
      // and a denial on the subject.
      ['<li><strong>Token renewal:</strong> The session token expires after 30 minutes and is renewed from a refresh token that lasts 30 days. Each renewal replaces the refresh token with a new one and revokes the one it replaced, and refresh tokens are stored only as hashes.</li>', false],
      ['<li>Logging out of all devices does not, by itself, end a session already open; that session ends when its token expires.</li>', false],
      ['<li>After 30 days without a visit, your session ends and you log in again.</li>', false],
      ['<li>No sessions are ended by logging out.</li>', false],
      ['<li>No device is signed out when you change your password.</li>', false],
      ['<li>None of your sessions end when you log out.</li>', false],
      ['<li>Not every device is signed out when you change your password.</li>', false],
      // A denial that only the wider logging-out words call main's timed reading on.
      ['<li>No session ends within 30 minutes of a logout.</li>', false],
      // One-use forms about other credentials, alone and beside a refresh-token sentence (#1456's third round,
      // Codex's thread 4335683402).
      ['<li>Use a one-time recovery code.</li>', false],
      ['<li>Password reset links are one-time links.</li>', false],
      ['<li>A verification code cannot be reused.</li>', false],
      ['<li>An invite link cannot be used twice.</li>', false],
      ['<li>A verification code is good for one use.</li>', false],
      ['<li>Each magic link expires after one use.</li>', false],
      ['<li>Refresh tokens are stored only as hashes. A recovery code cannot be reused.</li>', false],
      // Out of reach: a promise split across two items, and one said in other words.
      ['<ul><li>Logging out of all devices revokes your refresh tokens.</li><li>Each session then ends within 30 minutes.</li></ul>', 'gap'],
      ['<li>After a password reset, nobody stays signed in.</li>', 'gap'],
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
    expect(
      sourced.map((m) => [m[5], m[4]]),
      'each sourced claim names its document beside it, citing the step SOURCED_STEPS lists',
    ).toEqual(Object.entries(SOURCED_STEPS).map(([claim, { step }]) => [claim, step]))
    const text = rendered('security')
    for (const [, rel, section, heading, step, claim] of sourced) {
      expect(text).toContain(claim)
      const file = path.join(REPO, rel)
      expect(sourceFaults(rel, existsSync(file) ? readFileSync(file, 'utf8') : null, section, heading, SOURCED_STEPS[claim].words, step)).toEqual([])
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
    // The notification bullet's words stand in the step its comment cites, step 2, on the line that carries it on.
    const notify = (text: string | null, step?: string) =>
      sourceFaults('r.md', text, '3', 'Breach-notification readiness', ['notify', 'supervisory authority', 'affected users'], step)
    expect(notify(doc, '2')).toEqual([])
    expect(notify(doc.replace('notify affected users without undue delay', 'tell nobody'), '2')).toEqual(['r.md §3 step 2 does not say "affected users"'])
    expect(notify(doc.replace('\n   72 hours', '\n\n72 hours'), '2')).toEqual(['r.md §3 step 2 does not say "affected users"']) // a line outside the list
    // The words gone from step 2 while step 5 says them: the cited step fails, where any step of §3 would pass.
    const moved = doc
      .replace(/2\. \*\*Clock starts\*\*[\s\S]*?if high risk\./, '2. **Clock starts** when you become aware.')
      .replace('4. **Rotate** - SECRET_KEY, and any leaked keys.', '4. **Rotate** - SECRET_KEY, and any leaked keys.\n5. **Comms** - notify affected users and the supervisory authority from a template.')
    expect(notify(moved, '2')).toEqual([
      'r.md §3 step 2 does not say "notify"',
      'r.md §3 step 2 does not say "supervisory authority"',
      'r.md §3 step 2 does not say "affected users"',
    ])
    expect(notify(moved)).toEqual([])
    expect(notify(doc, '9')).toEqual(['r.md §3 has no step 9']) // a cited step that is not there
  })

  it('the audit-log item names only what an audit_logs row records (a self-check on planted items and modules)', () => {
    const { container, unmount } = render(<SecurityPage />)
    const item = [...container.querySelectorAll('li')].map((li) => (li.textContent ?? '').replace(/\s+/g, ' ').trim()).find((t) => /\baudit log\b/.test(t))
    unmount()
    expect(item).toBeDefined()
    const written = auditActionsWritten(backendModules())
    expect(auditFaults(item ?? '', written)).toEqual([])
    // Every action a row records is one the item names or one AUDITED_UNNAMED holds, so a new one is placed before it
    // ships, and the header's split of the actions stays true.
    expect(
      [...written].sort(),
      'an audit_logs action the item does not name: add it to AUDITED_UNNAMED with what it records (naming it on the page is the founder’s change)',
    ).toEqual([...new Set([...Object.values(AUDITED).flat(), ...Object.keys(AUDITED_UNNAMED)])].sort())
    const planted: Array<[string, string[]]> = [
      // Round 2's item, and a rewording that names an administrator action no row records.
      ['Registrations, logins, failed logins, logouts, data exports, account deletions and administrator actions are written to an audit log', ['"administrator actions": no audit_logs row is known to record it']],
      // Round 3's item named logouts while a logout after the session token's expiry wrote no row (Codex's r4331250317
      // on a0f511aa); since E137 every logout that ends a session writes one.
      ["Registrations, logins, failed logins, logouts, data exports and account deletions are written to an audit log, and so are administrators' invites, feedback status changes and new free accounts", []],
      ["Logins are written to an audit log, and so are administrators' summary deletions", [`"administrators' summary deletions": no audit_logs row is known to record it`]],
      ['Registrations and logins are written to an audit log', []],
    ]
    for (const [text, faults] of planted) expect(auditFaults(text, written), text).toEqual(faults)
    // Were no logout row written, the item could not name logouts: round 2's item then has both faults.
    const noLogoutRow = new Set([...written].filter((action) => action !== 'logout'))
    expect(auditFaults(planted[0][0], noLogoutRow)).toEqual([
      '"logouts": nothing writes the logout row',
      '"administrator actions": no audit_logs row is known to record it',
    ])
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
      ['We use anonymous tracking.', true],
      ['Our telemetry is anonymised.', true],
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
