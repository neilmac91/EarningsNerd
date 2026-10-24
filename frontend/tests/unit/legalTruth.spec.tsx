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
 *    "every", "each" or "any" with up to three words before "endpoints" that leave the set whole (WHOLE_SET, so "every
 *    administrative endpoint" claims nothing of every one), as in "all of the API's endpoints", whose own
 *    predicate says they need a login, after them in their clause ("each endpoint requires a login", "sits behind a
 *    login", "can only be called with a token", "cannot be called without a token"; "and" carries them on only directly
 *    before it, so "Each endpoint returns JSON and administrators need a login." passes) or before them as their
 *    requirement ("a login is required for each
 *    endpoint"), not after a negation, unless a relative clause or a participle narrows them, as "any endpoint
 *    returning account data" does, or a condition after the login need narrows when they need it ("only when
 *    accessing private records": ONLY_WHEN, unless it restates every request, RESTATED: "only when you call it";
 *    main's reading of all and every endpoints reads no condition); and "no endpoint" answering without authentication
 *    in its clause, the claim the
 *    other way round; login words in another role or clause pass ("Each API endpoint documents the token format.", "Any
 *    endpoint may accept an optional token."), an account or a token counts as a login only as the credential itself
 *    ("requires an account", "a signed-in account", "requires a token"), so "Each endpoint requires an account ID." and
 *    "Each endpoint expects a token parameter, but it is optional." pass, and so does "No API endpoints require
 *    authentication.", which says the opposite; search, company pages and summaries are public); a Content Security
 *    Policy against XSS or cross-site
 *    scripting (the site sends frame-ancestors only); role-based access, permissions or authorisation, or RBAC (one
 *    administrator flag); an adjective in place of a fact (enterprise, military or bank grade or level, industry
 *    standard or standards, hyphenated or not); no financial data stored, a negation, contracted or not, on either side
 *    (payment records are kept); post-incident reviews or post-mortems and vetting the providers (no process in the
 *    repository does either); and an analytics-consent promise not scoped to the browser in its own sentence
 *    (CONSENT_PROMISE; the API sends account events whatever the reader chose: D-051). That promise names the analytics
 *    by a name the F33 check reads them by (analytics, tracking, statistics, PostHog, telemetry, and usage as the
 *    analytics: usage data, statistics or events, product or anonymous usage, usage tracked or collected), or as the
 *    account's, the server's or the API's events ("your data", "event invitations" and "usage of this website" are not
 *    the analytics), and makes
 *    them wait for a yes: "only" up to 60 characters before "after (once, when, if or until) you allow" (accept, agree,
 *    consent, opt in, give consent, say yes, turn or switch on, enable), before "with (after, upon, on or by) your
 *    consent" with up to three words before the consent (permission, agreement, approval, opt-in, each read by its
 *    start, so "only after consenting" fails too), or before "once allowed", a sentence that names the browser ("in
 *    your browser") reading as scoped, and a negation on the verb passing (NOT_NEAR: "Analytics are not collected only
 *    with your consent."); or, in the forms the "only" ones miss, "until you allow", a negation, contracted
 *    or not, before "without your consent", "requires (needs, waits for, is or are subject to) your consent",
 *    "consent-gated" or "opt-in", where a sentence that names the browser or its part, its analytics cookies or session
 *    recording (the consent dialog's own "Analytics cookies and session recording stay off until you allow them", and
 *    "Session recording with PostHog is opt-in"), reads as scoped, and where the verb says the promise, a denial before
 *    it, on the subject or on the consent passes ("No server events require your consent", "Server events do not need
 *    your consent", "Server events require no consent"), and so does consent bound to another operation, a gerund of
 *    one opening the sentence ("Sharing analytics data with another user requires your consent": ITS_OPERATION) but
 *    for one whose recipient is the analytics provider ("Sharing account events with PostHog requires your consent":
 *    TO_THE_ANALYTICS), while "No analytics run until you allow them" and "No usage data is sent without your
 *    permission" still promise.
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
 *    backend writes (auditActions), read so that none is missed: each create_audit_log call by its own argument list,
 *    each audit_service function that calls create_audit_log as a helper with a literal action or a template one
 *    (`subscription_{action}`, composed from the caller's literal keyword), a callable passed with its arguments to
 *    run_in_threadpool, which runs it (`run_in_threadpool(audit_service.create_audit_log, db, action=...)`), from them,
 *    an import not as a call; and it follows a module's bindings, not names, so a writer imported under an alias (`create_audit_log as write_audit`)
 *    and the service imported as a module (`import app.services.audit_service as audit`) are read, and a name counts
 *    only where the module binds it to the service: a function of its own, another module's import or another
 *    object's attribute under a helper's name writes no row. Whatever the walk cannot read or follow (a variable, an
 *    f-string or a positional action, a name mentioned but not called or reassigned, a writer passed to any call but
 *    run_in_threadpool (a stored `partial` may never run), a star import of the service,
 *    the service reached through a binding it does not read (`services.audit_service.<name>`, or `audit_service`
 *    never imported), the service module used other than as `<module>.<name>`, a service function that uses another
 *    helper, whether or not it writes a row of its own, a create_audit_log in the service outside the one call of a
 *    top-level function, in a class's method or at the module's top level, a second call or the writer passed on, a
 *    helper used outside a top-level function, and an AuditLog row built anywhere but as create_audit_log's own row,
 *    from its action parameter, under its name, an import's alias or an assignment's) is listed by module and line,
 *    and that list is held empty, so a new write fails until its action is a literal or taught to the walk. Out of its
 *    reach: a row written without building an AuditLog (a bulk or core insert on the table, or SQL, which CLAUDE.md
 *    forbids), a writer re-exported by another module, whose name the walk reads as that module's, and the model bound
 *    to another name in one module and imported into another, or passed as a value. The item names part of what
 *    the rows record, and
 *    AUDITED_UNNAMED holds the rest, each with what it records: a Google or Apple sign-in linked to an existing account
 *    or unlinked from it (oauth_linked, oauth_unlinked), and two administrator actions on summaries, a bulk reset and a
 *    regeneration of stale ones (summaries_bulk_reset, summaries_refresh_stale). Every action written is in one map or
 *    the other, so a new one fails until it is placed; naming one on the page changes the page's sentence, which is the
 *    founder's. Administrator actions are named one by one, since six of them write a log line and no row
 *    (admin_filing_service.py's filing maintenance and stale-XBRL bulk reset, the XBRL cache clear, the test mail).
 *    This reader sees only that some module writes a named action, not that every path of the event does; that is the
 *    backend's to pin. For logouts (E137), test_auth_token_flows.py's logout cases and the logout_signed_in and
 *    logout_cookie_only cases in test_cached_filings_pool_lifetime.py pin that a logout that ends a session writes its
 *    row, under the user whose session it ended.
 * 7. /security promises nothing of refresh tokens and logging out that the code does not enforce when requests overlap
 *    (E127_PROMISES): a refresh token that works once (one-time, cannot be used twice, read beyond main's phrases only
 *    in a sentence about the refresh or session token: "a one-time recovery code" is another credential, beside the
 *    token too, ONE_TIME_OF_ANOTHER: "Refresh tokens are reusable, unlike one-time recovery codes."; a negation
 *    near "one-time", "good for one use" or "after one use" passes, NOT_NEAR: "Refresh tokens are not one-time
 *    credentials."), a reused one
 *    revoking the account or sweeping its sessions (every session ended, signed out on every device; a session that
 *    ends on its own beside "again" is no sweep; read beyond main's words only in a sentence about the token, as the
 *    one-use forms are: "A verification code cannot be used more than once and can be revoked from settings." is
 *    another credential's), or a session that ends after logging out or a password change, within a time or with none
 *    named (every session, everywhere, a session token revoked), a logout in each spelling (logout,
 *    logged out, a sign-out; a revocation alone, as a renewal's of the token it replaces, is none), and what ends named
 *    before its verb ("a session open elsewhere then ends", "every device is signed out") or signed out with no pronoun
 *    ("signs out every device"). A denial passes, in main's logging-out words as in the wider ones: a negation before
 *    the verb with up to four words between them, with or without commas ("does not by itself end", "does not in normal
 *    use end", "does not yet end"; not "not only ... but", not past "and", a relative word or a verb that turns it back
 *    into a promise, as "never fails to end" does, and with "to" among them no further than main's three words, the
 *    verb's own complement, "does not need to end", or its person, "does not require you to be signed out", so a
 *    purpose infinitive after its object promises: "does not take any time to end every session"), with a longer
 *    aside in commas ("does not, as a rule of thumb, end"),
 *    on the subject ("No sessions are ended", "None of your sessions", "Not every device", where the subject stops at
 *    another clause, so "No password is stored and logging out ends every session" fails), or on the object ("ends no
 *    other session"), and so does an end at its token's expiry ("that session ends when its token expires"), and a
 *    negation on a causative verb whose object names what ends ("does not cause your other sessions to end": CAUSED;
 *    "does not cause any noticeable delay to end every session" promises). A denial stops at "but" that goes on to a
 *    time or to what ends ("does not end your sessions in a day but within 30 minutes", "does not end this session but
 *    every session": BUT_AFFIRMS). Main's timed and untimed readings read the same denial, so "Logging out does not end
 *    every session within 30 minutes" passes, and every promise they refuse in main's spec is refused here too. The page is read on every run, whatever
 *    tasks/todo.md records: E127's race is fixed (#1422), and so are a login that straddled a password reset (#1431)
 *    and a logout that did not wait for an in-flight renewal (#1465), but a session token already issued runs to its
 *    expiry, and E96 (how a reused token's sweep reads) is open; the stronger wording returns only in a pull request
 *    that carries the founder's go-ahead (tasks/todo.md F53) and changes this check. Each family is read in one list
 *    item or paragraph (blockTexts), and a promise of logging out in its own sentence or in the one after a sentence
 *    that names a logging-out action (a logout, a sign-out, a password changed or reset, or acted on in other words,
 *    "pick a fresh password", "submit the password form": PASSWORD_ACTED_ON; a new password counts in its own sentence,
 *    and before a noun it names, "our new password policy", only for main's timed and untimed readings, as main reads
 *    its password word anywhere: ANY_NEW_PASSWORD), and beside a password only named, in the password's own clause,
 *    which a conjunction ends unless an
 *    end follows it or it joins the password to another noun (CLAUSE_JOIN), so a word in a neighbouring sentence or
 *    clause makes no context: "Passwords are hashed. Idle sessions end after 30 minutes." and "Passwords are hashed and
 *    idle sessions end after 30 minutes." pass. Planted forms score the
 *    reach; out of reach, planted as gaps: a promise split across two
 *    items, one said in other words ("nobody stays signed in"), and a negation that only restricts where no reading
 *    sees it ("does not clear cookies and revokes your session tokens").
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
  terms: [
    { date: 'June 16, 2026', sha256: '82ecb15a746bee66' },
    { date: 'October 24, 2026', sha256: '89066f92fb69856d' },
    { date: 'October 24, 2026', sha256: 'eb7c1fb1123812fe', sameDay: '#1547 changes the page after #1121 on the same day' },
  ],
  privacy: [
    { date: 'June 22, 2026', sha256: '455802b5d59fad8f' },
    { date: 'October 20, 2026', sha256: 'c1bc2d9daec940d1' },
    { date: 'October 21, 2026', sha256: '865b53735c88175d' },
    { date: 'October 24, 2026', sha256: '41094b4709f20a10' },
    { date: 'October 24, 2026', sha256: 'db18a4591671aa83', sameDay: '#1547 changes the page after #1121 on the same day' },
    { date: 'October 24, 2026', sha256: '6ed68d37e514f0bd', sameDay: '#1552 changes the page after #1547 on the same day' },
  ],
  security: [
    { date: 'June 22, 2026', sha256: '13d1b7070566bf07' },
    { date: 'October 21, 2026', sha256: '7e03a05b33c1cf00' },
    { date: 'October 21, 2026', sha256: '272031790b35816d', sameDay: '#1397 changed the page that day too' },
    { date: 'October 21, 2026', sha256: 'f01e686b3c5afee8', sameDay: '#1449 changed the page that day too' },
    { date: 'October 24, 2026', sha256: '1fdda29a88473317' },
    { date: 'October 24, 2026', sha256: '6b266b1d62f0e9b7', sameDay: '#1547 changes the page after #1121 on the same day' },
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

/** The words that end a denied subject (DENIED_SUBJECT) where another clause starts: a conjunction that starts one,
    and a verb that turns the denial back into a promise of what follows ("Nothing stops a logout from ending", "No
    logout fails to end"). */
const CLAUSE_STOP = String.raw`(?:but|so|yet|because|although|though|whereas|while|unless|then|if|when|whenever)`
const UNDENIED = String.raw`(?:stops?|stopped|prevents?|prevented|keeps?|kept|blocks?|blocked|fails?|failed|forgets?|neglects?|hesitates?|refuses?|ceases?|without)`
/** An aside in commas inside a denied subject ("No session, on any device, ends"), with no verb of its own: a comma
    alone, or an aside with "is" in it, starts another clause ("No setup is needed, a logout ends every session"). */
const SUBJECT_ASIDE = String.raw`,(?!\s*(?:and|but|so|or|nor|while|whereas|then|yet)\b)(?:(?!\b(?:is|are|was|were|be|been|has|have|had|do|does|did|will|would|can|could|may|might|must|should)\b)[^,.;:!?]){1,40},`
/** A clause whose subject is denied, from its start up to the verb: "No sessions are ended", "None of your devices is
    signed out", "Not every session ends", "No server events require your consent", "Nothing the API records waits
    for your consent" ("no matter" and "no sooner" deny nothing). The subject runs through its own words, "or" and "nor"
    between them ("No session on your phone or laptop"), "and" before another denial ("No session and no device"), a
    relative clause ("None of the sessions that you open elsewhere") and an aside (SUBJECT_ASIDE), and stops where
    another clause starts: at a comma, at "and" before anything else ("No password is stored and logging out ends every
    session"), and at CLAUSE_STOP and UNDENIED. */
const DENIED_SUBJECT = String.raw`(?:^|[;:]\s*|,\s+|\b(?:and|but|so|while|whereas)\s+)(?:no(?!\s+(?:matter|sooner)\b)|none|nothing|neither|nobody|not\s+(?:every|all|one|any|each|a\s+single|even\s+one))\b` +
  String.raw`(?:(?!\b(?:${CLAUSE_STOP}|${UNDENIED})\b)(?!\band\s+(?!(?:no|none|nothing|neither|nor|not)\b))[^,.;:!?]|${SUBJECT_ASIDE})*`
/** A word a negation reaches across to its verb (NEGATION_REACH): not a conjunction or a relative or subordinating
    word, which would start another predicate or clause ("does not clear cookies and ends every session"), and not a
    verb that turns the negation back into a promise ("never fails to end", "cannot help ending", "never stops short of
    ending", "does not happen without ending"). */
const REACH_WORD = String.raw`(?!(?:and|but|or|nor|so|then|yet|which|that|who|whom|whose|where|when|while|whereas|because|though|although|if|unless|fail|fails|failed|forget|forgets|neglect|neglects|hesitate|hesitates|refuse|refuses|cease|ceases|help|stop|stops|stopped|without)\b)[\w'’-]+\s+`
/** How far a negation reaches to its verb: up to four words between them (REACH_WORD), an adverbial phrase ("does not
    by itself end", "does not in normal use end", "does not on its own end", "does not of its own accord end"), with or
    without commas, "yet" or "then" first among them ("does not yet end"). Four covers the phrases a page uses for "in
    itself"; a fifth word is where a negated verb's own object or a second predicate begins. The first may not be
    "only", "just", "merely" or "simply", which deny a restriction, not the act ("does not only end this session but
    every session on the account"). A span with "to" in it keeps to main's three words (#1456's thirteenth round): the
    verb's own complement ("does not need to end", "does not have to end") is a denial, while a purpose infinitive
    after the verb's object ("does not take any time to end every session", "does not force a reload to end every
    session") promises the end, which main's reach refuses past three words. The one longer complement is the verb's
    person and their own end ("does not require you to be signed out", "does not cause everyone to get logged out"). */
const NEGATION_REACH = String.raw`(?!(?:only|just|merely|simply)\b)(?:(?:yet|then)\s+(?:(?!to\b)${REACH_WORD}){0,3}|(?:(?!to\b)${REACH_WORD}){0,4}|(?:${REACH_WORD}){0,3}|${REACH_WORD}(?:you|everyone|everybody)\s+to\s+(?:be|get)\s+)`
/** A word of a causative verb's object (CAUSED): no word that opens a clause of time or comparison, nor "to". */
const OBJECT_WORD = String.raw`(?!(?:before|after|until|till|once|since|as|than|to)\b)${REACH_WORD}`
/** What a causative's object names when it is what ends (#1456's thirteenth round), as ENDED and SWEEP read it: a
    session (not a session token), a device, a tab or a browser, the others, or you, everyone or everybody. */
const WHAT_ENDS = String.raw`(?:sessions?(?![- ]tokens?)|devices?|tabs?|browsers?|others|you|everyone|everybody)\b`
/** A preposition, which ends an object's head noun phrase: what follows it qualifies the object ("on your phone"),
    and does not name what ends ("any action from you"). */
const PREPOSITION = String.raw`(?:about|across|at|by|for|from|in|into|of|on|onto|over|per|through|under|via|with|within|without)\b`
/** A causative's object of up to six words whose head names what ends (WHAT_ENDS), no preposition before it: "your
    other sessions", "every session on your phone", "you", not "any action from you". */
const ENDING_OBJECT = [0, 1, 2, 3, 4, 5].map((before) => String.raw`(?:(?!${PREPOSITION})${OBJECT_WORD}){${before}}(?=${WHAT_ENDS})(?:${OBJECT_WORD}){1,${6 - before}}?`).join('|')
/** A negation on a causative verb (#1456's twelfth round): "does not cause your other sessions to end", "never forces
    a session to end" and "does not make the sessions on your other devices end" deny the end the verb governs, as
    "does not end" does. One word at most stands between the negation and the verb, not "only", "just", "merely" or
    "simply", and a negation earlier in the sentence makes the two a promise (NOT_NEAR's rules); up to six words of the
    verb's object follow it, then "to" (cause, force, lead) or the end at once (make), with no word among them that
    opens a clause of time or comparison ("does not cause any delay before every session ends" still promises). The
    object names what ends (ENDING_OBJECT; #1456's thirteenth round): where it does not, the "to" is a purpose
    infinitive and the end its purpose, so "does not cause any noticeable delay to end every session" promises. */
const CAUSED = String.raw`(?<!(?:\b(?:not|never|no|none|nothing|nobody|neither|nor|cannot)\b|n['’]t\b)[^.;:!?]*)(?:\b(?:not|never|nor|cannot|no\s+longer)|n['’]t)\s+(?!(?:only|just|merely|simply)\b)(?:${REACH_WORD})?(?:(?:caus(?:e|es|ed|ing)|forc(?:e|es|ed|ing)|lead(?:s|ing)?|led)\s+(?:${ENDING_OBJECT})to\s+(?:(?:be|get)\s+)?|(?:mak(?:e|es|ing)|made)\s+(?:${ENDING_OBJECT}))`
/** Not after a negation: "does not end your other sessions", "never signs you out", "does not by itself end a
    session" (NEGATION_REACH), "does not, by itself, end a session" and "do not need your consent" deny what the verb
    says, and so does a clause whose subject is denied (DENIED_SUBJECT) and a negation on a causative verb before it
    (CAUSED: "does not cause your other sessions to end"). The end forms, main's timed and untimed readings among them,
    and the consent forms whose verb says the promise read it. */
const NOT = String.raw`(?<!\b(?:not|never|nor|cannot|no longer)\s+${NEGATION_REACH}|n['’]t\s+${NEGATION_REACH}|(?:\b(?:not|never|cannot)|n['’]t)\s*,[^,.;:!?]{1,40},\s*|${DENIED_SUBJECT}|${CAUSED})`
/** A negation on the word itself (#1456's tenth round), for three branches that read no denial before: the consent
    forms' "only" where the yes follows it at once, the login said as the subject before the endpoints, and the one-use
    forms that are no denial themselves. One word at most stands between them (REACH_WORD), with "be", "been" or
    "being" before it ("are not collected only with", "will not be collected only with", "are not one-time", "do not
    expire after one use"), or "no" stands directly before it ("no login is required"; "no doubt" denies nothing);
    the first word may not be "only", "just", "merely" or "simply" (NEGATION_REACH), and a negation earlier in the
    sentence makes the two a promise ("It is not true that refresh tokens are not one-time."). NOT's four words and a
    denied subject's clause would carry a negation from a relative or a complement clause to the verb after it:
    "Analytics that do not identify you are collected only with your consent." and "Nobody doubts that refresh tokens
    are one-time." still promise. */
const NOT_NEAR = String.raw`(?<!(?<!(?:\b(?:not|never|no|none|nothing|nobody|neither|nor|cannot)\b|n['’]t\b)[^.;:!?]*)(?:(?:\b(?:not|never|nor|cannot|no\s+longer)|n['’]t)\s+(?!(?:only|just|merely|simply)\b)(?:(?:be|been|being)\s+)?(?:${REACH_WORD})?|\bno\s+))`
/** Usage as the analytics (#1456's eighth round): qualified ("usage data", "usage statistics", "product usage",
    "anonymous usage") or as what is tracked, collected or sent ("we track usage", "usage is collected", with a modal
    or a negation on the verb: "usage can be collected", "usage isn't collected", "usage cannot be collected"), not the
    word's ordinary sense ("usage of this website", "fair usage"). */
const USAGE =
  String.raw`\busage\s+(?:data|statistics|stats|events?|analytics|metrics|tracking|information|patterns|logs?)\b` +
  String.raw`|\b(?:product|site|app|feature|anonymous|anonymi[sz]ed|aggregated?)\s+usage\b` +
  String.raw`|\b(?:track|collect|measur|record|monitor|logg?)(?:s|ed|e|es|ing)?\s+(?:(?:your|our|the|its|their)\s+)?usage\b` +
  String.raw`|\busage\s+(?:(?:is|are|was|were)(?:n['’]t)?|gets|(?:cannot|can['’]t|won['’]t|(?:could|would|should|must|might)n['’]t|can|could|may|might|must|will|would|shall|should)(?:\s+(?:only|also|never|not|ever))?\s+be)\s+(?:(?:only|also|not|never)\s+)?(?:tracked|collected|measured|recorded|monitored|logged|sent|shared|stored|processed)\b`
/** The analytics by any name ANONYMOUS_ANALYTICS reads them by, usage only as the analytics (USAGE), and events only
    as the account, the server or the API names them ("account events", "the events the API records"; "usage data" and
    "usage events" are usage), so "your data" and "event invitations" are not the analytics. */
const ANALYTICS_NAMES = String.raw`(?:\b(?:analytics|tracking|statistics|PostHog|telemetry)\b|${USAGE}|\b(?:account|server|API)\s+events?\b|\bevents?\s+(?:that\s+)?the\s+(?:API|service|server|backend)\s+(?:records?|sends?|captures?|logs?)\b)`
/** The browser's part of the analytics, which does wait for the reader's yes: its analytics cookies and session
    recording (the consent dialog: "Analytics cookies and session recording stay off until you allow them"). */
const BROWSER_PART = String.raw`\b(?:analytics|tracking) cookies\b|\bsession (?:recording|replay)s?\b`
/** The reader's yes, as a clause after "you" says it. */
const YES = String.raw`(?:allow|accept|agree|consent|opt(?:ed)?[- ]in|giv(?:e|en) (?:your |us )?(?:\w+ )?(?:consent|permission)|say yes|turn (?:it |them )?on|switch (?:it |them )?on|enable)`
/** The reader's yes, as a noun. */
const CONSENT = String.raw`(?:consent|permission|agreement|approval|opt[- ]in|say-so)s?`

/** The yes an "only" form waits for: "after (once, when, if or until) you allow", "with (after, upon, on or by) your
    consent", with up to three words before the consent, or "once allowed". */
const YES_AFTER_ONLY = String.raw`(?:\b(?:after|once|when|if|until) you(?: have|['’]ve)? ${YES}|\b(?:with|after|upon|on|by) (?:[\w'’-]+ ){0,3}${CONSENT}|\b(?:once|if|when|after) (?:it is |they are |it['’]s |they['’]re )?(?:allowed|accepted|enabled|consented)\b)`

/** The analytics provider as an operation's recipient (#1456's thirteenth round): "with PostHog", "to our analytics
    provider", "with analytics", not a group the name only qualifies ("with PostHog users on your team"). Account
    events shared with PostHog are the analytics D-051 records whatever the reader chose, so a consent bound to that
    sharing is the contradiction itself, not another operation's. */
const TO_THE_ANALYTICS = String.raw`\b(?:with|to)\s+(?:(?:our|the|its|an?|your)\s+)?(?:PostHog|(?:product\s+)?analytics(?:\s+(?:providers?|vendors?|services?|platforms?|partners?|tools?|compan(?:y|ies)))?)\b(?!\s+(?:users?|reports?|dashboards?|projects?|teams?|members?|accounts?|admins?|staff|customers?|employees?|colleagues?)\b)`
/** Consent bound to another operation on the analytics (#1456's twelfth round): a sentence that opens with a gerund of
    an operation other than collecting or running them, with "any" or "the" before it at most ("Sharing analytics data
    with another user requires your consent.", "Any selling of usage data needs your permission."), puts the consent on
    that operation, up to the verb with no comma, colon, semicolon or conjunction (and, but, or) between, and with no
    recipient that is the analytics provider (TO_THE_ANALYTICS): "Sharing account events with PostHog requires your
    consent." still promises. */
const ITS_OPERATION = String.raw`(?<!^\s*(?:(?:any|the)\s+)?(?:sharing|selling|exporting|deleting|erasing|disclosing|transferring|publishing|showing|displaying|revealing|renting|licensing|downloading)\b(?![-'’])(?:(?!\b(?:and|but|or)\b|${TO_THE_ANALYTICS})[^,;:.!?])*)`
/** An analytics-consent promise not scoped to the browser, in one sentence (header item 1 lists its forms). The
    "only" forms read a sentence that names the browser as scoped, and read the consent word by its start, so "only
    after consenting" fails as "only after consent" does; the forms that wait for a yes another way read the browser's
    part (BROWSER_PART) as scoped too, so the consent dialog's own sentence and "Session recording with PostHog is
    opt-in." pass. A negation before "without your consent" may be contracted ("doesn't", "won't") or fused with its
    modal ("cannot"; #1456's ninth round). The forms whose verb says the promise (requires, needs, waits for or until,
    is subject to, consent-gated, opt-in) read a denial as NOT does, before the verb or on the subject, so "No server
    events require your consent." passes, and "no" before the consent denies it ("Server events require no consent.");
    "until you allow" after another verb and "without your consent" take a denied subject as part of the promise ("No
    analytics run until you allow them", "No usage data is sent without your permission"). Where the yes follows
    "only" at once, the "only" forms read a negation on the verb before it (NOT_NEAR; #1456's tenth round), so
    "Analytics are not collected only with your consent." passes. The forms with requires, needs, waits for or is
    subject to read no consent bound to another operation (ITS_OPERATION), so "Collecting analytics data requires your
    consent." still promises and "Sharing analytics data with another user requires your consent." passes. */
const CONSENT_PROMISE = new RegExp(
  String.raw`^(?!.*\bin your browser\b)(?=.*${ANALYTICS_NAMES}).*(?:${NOT_NEAR}\bonly\s+|\bonly\b(?!\s+${YES_AFTER_ONLY}).{0,60}?)${YES_AFTER_ONLY}` +
    String.raw`|^(?!.*(?:\bin your browser\b|${BROWSER_PART}))(?=.*${ANALYTICS_NAMES})(?:` +
    String.raw`.*(?<!\bwait(?:s|ing)?\s)\buntil you(?: have|['’]ve)? ${YES}` +
    String.raw`|.*${NOT}\bwait(?:s|ing)?\s+until you(?: have|['’]ve)? ${YES}` +
    String.raw`|.*(?:\b(?:never|not|no|nothing|none|cannot)\b|n['’]t\b).{0,60}?\bwithout (?:your )?(?:[\w-]+ )?${CONSENT}\b` +
    String.raw`|.*${NOT}${ITS_OPERATION}\b(?:requires?|needs?|waits? for|(?:is|are) subject to) (?:your )?(?:(?!no\b)[\w-]+ )?${CONSENT}\b` +
    String.raw`|.*${NOT}\bconsent[- ]gated\b|.*${NOT}\bgated (?:on|by|behind) (?:your |the )?(?:[\w-]+ )?(?:consent|choice)\b` +
    String.raw`|.*${NOT}\b(?:is|are) (?:strictly |only )?opt[- ]in\b` +
    ')',
  'i',
)

/** Endpoints that what follows them narrows, a relative clause or a participle ("any endpoint that returns account
    data", "any endpoint returning account data"): a scoped claim, not every one. A verb of their own ("each endpoint
    returns JSON and requires a login") narrows nothing. */
const NARROWED = String.raw`(?!\s+(?:that|which|returning|serving|handling|exposing|reading|writing|for|with)\b)`
/** The words that may stand between the endpoints' quantifier and "endpoints" and leave the set whole (#1456's
    eleventh round): "all of the API's endpoints", "every one of our endpoints", "each of its endpoints", "every
    single endpoint", "each individual endpoint", "each REST endpoint", "every EarningsNerd endpoint". Any other word
    there picks some of them out, so "every administrative endpoint" and "each private endpoint" claim nothing of every
    endpoint, and "all of these endpoints" speaks of a set named before. */
const WHOLE_SET = String.raw`(?:of|the|our|its|one|single|individual|API|API['’]s|REST|EarningsNerd(?:['’]s)?)`
/** The endpoints the removed claim speaks of: all, every, each or any with up to three words of WHOLE_SET before
    "endpoints" ("all of the API's endpoints", "every single endpoint", "each API endpoint"), unless what follows
    narrows them. */
const SOME_ENDPOINTS = String.raw`\b(?:all|every|each|any)\b(?:\s+${WHOLE_SET}){0,3}?\s+endpoints?\b${NARROWED}`
/** A credential as the thing required, not a word before what it names: followed by an end, a comma or a word that
    does not take it as a modifier ("a token to call it", "an account first"), not by a possessive or another noun ("a
    token parameter", "the token format", "an account ID", "the account holder's name"). */
const ITSELF = String.raw`(?!['’]s\b|\s+(?!(?:and|or|but|nor|to|for|on|in|at|with|before|first|that|which|who|when|whenever|if|is|are|so|then|only|from|via)\b)[\w'’-])`
/** An account as a login: the account itself ("an account", "a signed-in account", "your account first"), not before
    what it names (ITSELF) or a hyphen ("account-level"). */
const AS_LOGIN = String.raw`(?!-\w)${ITSELF}`
/** A login, as the claim says the endpoints need one: authentication, a login or sign-in, a token or an account as the
    credential itself (ITSELF, AS_LOGIN). */
const A_LOGIN = String.raw`(?:(?:a|an|the|your|valid|prior|its own|signed[- ]in|logged[- ]in|authenticated|registered|verified|user|account)\s+)*(?:authentication|auth|log[- ]?in|logging in|sign[- ]?in|signing in|(?:bearer\s+|session\s+|access\s+)?tokens?${ITSELF}|account${AS_LOGIN}|credentials?)\b`
/** A conjunction that joins clauses inside a sentence (#1456's eighth round). It carries a reading on only directly
    before the predicate the reading looks for, an adverb at most between them (CARRIED_ON: "each endpoint returns JSON
    and also requires a login", "sends a reset link and ends every session"); before anything else it starts another
    clause, with a subject of its own ("each endpoint returns JSON and administrators need a login", "passwords are
    hashed and idle sessions end after 30 minutes"). */
const CLAUSE_JOIN = String.raw`(?:and|but|or)`
/** The adverb a conjunction may carry a predicate on through (CLAUSE_JOIN). */
const CARRIED_ON = String.raw`(?:(?:also|always|then|still|only|likewise)\s+)?`
/** The words between the endpoints and their predicate, in their own clause: none opens another clause (which, that,
    when, because, so, or a conjunction: CLAUSE_JOIN), up to six of them, and "and" only directly before the predicate
    (CARRIED_ON). */
const IN_THEIR_CLAUSE = String.raw`(?:(?:\s*,)?\s+(?!(?:which|that|who|whom|whose|where|when|while|whereas|because|if|unless|so)\b|${CLAUSE_JOIN}\b)[\w'’-]+){0,6}?(?:\s*,)?\s+(?:and\s+${CARRIED_ON})?`
/** The endpoints' own predicate when it says they need a login, not after a negation (NOT): a requirement with the
    login ("requires a login", "needs a token", "requires you to be logged in"), a state ("is protected", "is
    authenticated", "sits behind a login"), or a use only with one ("can only be called with a token", "answers only to
    a signed-in reader") or not without one ("cannot be called without a token"; #1456's ninth round). */
const NEEDS_A_LOGIN = String.raw`${NOT}\b(?:` +
  String.raw`(?:requires?|required|needs?|demands?|expects?|takes?)\s+${A_LOGIN}` +
  String.raw`|(?:requires?|needs?)\s+(?:you|the reader|readers|callers?|users?)\s+to\s+(?:(?:be\s+)?(?:logged|signed)\s+in|(?:log|sign)\s+in|authenticate)\b` +
  String.raw`|(?:is|are|stays?|remains?)\s+(?:all\s+|always\s+|only\s+)?(?:protected|authenticated|locked|gated|private)\b` +
  String.raw`|(?:is|are|sits?|stands?|lives?|stays?)\s+(?:all\s+|always\s+|only\s+)?behind\s+${A_LOGIN}` +
  String.raw`|(?:can|may|will)\s+only\s+be\s+(?:called|reached|used|accessed|queried|opened)\s+(?:with|by|after|once|when)\s+(?:a\s+|an\s+)?(?:valid\s+)?(?:token${ITSELF}|login|logging in|signing in|authentication|account${AS_LOGIN}|signed[- ]in|logged[- ]in|authenticated)\b` +
  String.raw`|(?:cannot|can['’]t|can\s+not|may\s+not|will\s+not|won['’]t)\s+be\s+(?:called|reached|used|accessed|queried|opened)\s+without\s+(?:${A_LOGIN}|being\s+(?:logged|signed)\s+in\b)` +
  String.raw`|(?:answers?|responds?|works?|opens?)\s+(?:only\s+)?(?:to|for|with|after|once)\s+(?:a\s+|an\s+)?(?:logged[- ]in|signed[- ]in|authenticated|valid\s+token${ITSELF})` +
  ')'
/** The login said before the endpoints as their requirement: "a login is required for each endpoint", "you need a
    token for any endpoint", "authentication is mandatory on each endpoint", "you must log in to call any endpoint".
    The login as the subject reads a denial on itself (NOT_NEAR; #1456's tenth round), so "No login is required for
    each endpoint." passes; the forms with "you" read NOT. */
const LOGIN_FOR = String.raw`(?:` +
  String.raw`${NOT_NEAR}\b${A_LOGIN}\s+(?:is|are)\s+(?:always\s+|strictly\s+)?(?:required|needed|mandatory|necessary|enforced|checked|expected)\s+(?:for|on|by|at|in|to\s+(?:call|reach|use|query|open))\s+(?:the\s+)?` +
  String.raw`|${NOT}\b(?:you|readers?|callers?|clients?|users?)\s+(?:need|needs|require|requires|must\s+(?:have|present|send|hold|show))\s+${A_LOGIN}\s+(?:for|on|to\s+(?:call|reach|use|query|open))\s+(?:the\s+)?` +
  String.raw`|${NOT}\b(?:you|readers?|callers?|clients?|users?)\s+(?:must|have to|need to)\s+(?:log|sign)\s+in\s+(?:to|before|first to)\s+(?:call|calling|reach|reaching|use|using|query|querying|open|opening)\s+(?:the\s+)?` +
  ')'
/** What a condition after "only when", "only if", "only for" or "only to" restates rather than narrows (#1456's
    twelfth round): the endpoint itself called, used or accessed ("only when you call it", "only when it is called"), a
    caller with no login ("only if you are not signed in", "only for anonymous requests", "only when your session has
    expired") or a purpose ("only for your safety", "only to keep your data safe"), each of which is every request. */
const RESTATED = String.raw`(?:\s+[\w'’-]+){0,3}?\s+(?:(?:call|use|access|reach|query|open)(?:s|es|ing)?\s+(?:it|them|the\s+API|(?:the|an|this|that|each|any)\s+endpoints?)|(?:called|used|accessed|reached|queried|opened)|not\s+(?:yet\s+)?(?:signed|logged)[- ]in|(?:signed|logged)[- ]out|anonymous(?:ly)?|unauthenticated|unauthori[sz]ed|guests?|visitors?|(?:session|token|login)\s+(?:has\s+|is\s+)?expired|(?:without|lack(?:s|ing)?|ha(?:ve|s)\s+no|with\s+no|no)\s+(?:an?\s+)?(?:valid\s+)?(?:login|token|session|credentials?|authentication|account))\b|\s+(?:(?:your|our|its|their)\s+)?(?:keep|protect|secure|safeguard|safety|security|protection|privacy)\b`
/** A condition after the endpoints' login need, in its clause, that narrows when they need it (#1456's twelfth round):
    "only when", "only if", "only for" or "only to" ("requires a login only when accessing private records"), not one
    that restates every request (RESTATED), so the claim is not every request; "even when it is public" and "not only
    when" narrow nothing. Main's reading of all and every endpoints is not narrowed: it would pass restatements
    RESTATED does not list, which main refuses ("Every endpoint requires a login only if we do not know you."). */
const ONLY_WHEN = String.raw`(?:\s+(?!(?:and|but|or|nor|so|not|never|which|that|who|while|whereas|because|although|though|unless|even)\b)[\w'’-]+){0,4}?(?:\s*,)?\s+only\s+(?:when|if|for|to)\b(?!${RESTATED})`
/** Every endpoint behind authentication: main's reading (all or every, with "of", "our" or "the" and "API" between);
    SOME_ENDPOINTS with their own predicate saying they need a login, after them in their clause (NEEDS_A_LOGIN) or
    before them as their requirement (LOGIN_FOR); and the claim the other way round, "no endpoint" (WHOLE_SET's words
    between, as in SOME_ENDPOINTS) answering without authentication, unauthenticated or to anonymous requests, in its
    clause. "Each API endpoint documents the token format.", "Any endpoint may accept an optional token.", "No API
    endpoints require authentication." and "Every administrative endpoint requires authentication." pass, and so does
    this pull request's forms' login need with a condition that narrows it (ONLY_WHEN). */
const ENDPOINT_CLAIM = new RegExp(
  String.raw`\b(?:all|every)\b(?:\s+of)?(?:\s+(?:our|the))?(?:\s+API)?\s+endpoints?\b` +
    String.raw`|${SOME_ENDPOINTS}${IN_THEIR_CLAUSE}${NEEDS_A_LOGIN}(?!${ONLY_WHEN})` +
    String.raw`|${LOGIN_FOR}${SOME_ENDPOINTS}(?!${ONLY_WHEN})` +
    String.raw`|\bno\b(?:\s+${WHOLE_SET}){0,3}?\s+endpoints?\b${NARROWED}${IN_THEIR_CLAUSE}(?:without\s+(?:an?\s+)?(?:authentication|log[- ]?in|logging in|sign[- ]?in|signing in|token${ITSELF}|account${AS_LOGIN})\b|unauthenticated\b|(?:\w+\s+)?anonymous(?:ly\b|\s+(?:users?|requests?|callers?|readers?|access|visitors?)\b))`,
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
  ['no financial data stored', /(?:\b(?:no|never|not|none|cannot)\b|n['’]t\b)[^.]{0,40}\bfinancial data\b|\bfinancial data\b[^.]{0,40}(?:\b(?:never|not|cannot)\b|n['’]t\b)/i],
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
 * refresh token both succeeding, a renewal racing a logout leaving a live token) is fixed by #1422, a login that
 * straddled a password reset by #1431, and a logout that did not wait for an in-flight renewal by #1465, but nothing
 * revokes a session token already issued (get_current_user keeps no list of revoked ones), so "logging out of all
 * devices ends every session" is untrue as said, and E96 (how a reused token's sweep reads) is open. The stronger
 * wording returns only in a pull request that carries the founder's go-ahead (tasks/todo.md F53) and changes this check.
 * Each family is read in one block (a list item or a paragraph), so a promise split across the sentences of one item is
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
/** A denied object after the verb ("ends no other session", "revokes none of your session tokens"): "no" or "none of"
    before what ends, with only the words that say which between them, so "ends in no time every session" denies
    nothing, unless the clause goes on to the promise ("ends no session but every other one"). */
const DENIED_OBJECT = String.raw`\s+(?:(?:of|on|from|across|in)\s+)?(?:no|none\s+of)\s+(?:(?:other|open|active|remaining|single|more|your|the|their|its|these|those|our|my|session)\s+){0,3}(?:sessions?|devices?|tabs?|browsers?|tokens?)\b(?![^.;:!?]*\b(?:but|except|only|yet)\b)`
/** A time an end comes within: a span, or at once. */
const WITHIN = String.raw`(?:\b(?:within|after|in|under|inside)\s+(?:(?:\d+|a|an|one|two|three|five|ten|fifteen|twenty|thirty|forty|sixty|a few|a couple of|half an?)\s+)?(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b|\b(?:immediately|at once|instantly|right away|straight away|straightaway|without delay|on the spot)\b)`
/** Every session or device the account has ("every session on the account", "all of your devices"), or everywhere. */
const EVERY_SESSION = String.raw`(?:\b(?:every|all|each)\b(?:\s+(?:of|your|the|its|other|open|active|remaining))*\s+(?:sessions?(?![- ]tokens?)|devices?)\b|\beverywhere\b)`
/** "Not X but Y" (#1456's thirteenth round): a denied verb whose sentence goes on to "but" and a time an end comes
    within or every session the account has ("does not end your sessions in a day but within 30 minutes", "does not
    end sessions slowly, but at once", "does not end this session but every session") affirms the end there, so the
    denial stops at "but". What ends after "but" (every session, the others, your other sessions, elsewhere) closes
    its clause or takes a phrase that says where or when: with a verb of its own it opens another clause ("does not
    end your other sessions, but every session ends when its token expires"), read where that verb stands. */
const BUT_AFFIRMS = String.raw`(?=[^.;:!?]*?\bbut\s+(?:(?:also|rather|instead|even)\s+)?(?:${WITHIN}|(?:${EVERY_SESSION}|\bthe others\b|\belsewhere\b|\b(?:your|the)\s+other\s+(?:sessions?(?![- ]tokens?)|devices?|tabs?|browsers?)\b)(?=\s*(?:[.;:!?,]|$)|\s+(?:on|of|in|across|from|at|for|within|after|too)\b|\s+${WITHIN})))`
/** Not after a negation (NOT), or affirmed past one by "but" (BUT_AFFIRMS): the end readings' shared step. */
const AFFIRMED = String.raw`(?:${NOT}|${BUT_AFFIRMS})`
/** A verb that ends one ("the end of" is a noun), unless what it ends is denied (DENIED_OBJECT). */
const ENDS = String.raw`${AFFIRMED}\b(?:end(?:s|ed|ing)?(?!\s+of\b)|clos(?:e|es|ed|ing)|stop(?:s|ped|ping)?|terminat(?:e|es|ed|ing)|kill(?:s|ed|ing)?|invalidat(?:e|es|ed|ing)|expir(?:e|es|ed|ing)|times? out|timed out|cuts? off)\b(?!${DENIED_OBJECT})`
/** A logging-out action, as a block names it: a logout and a sign-out in their spellings (log out, logged out,
    logout, log-out, signing out, sign-out), all devices or every device, everywhere; a password only named gives its
    context to its own clause (PASSWORD). A revocation alone is none: a renewal revokes the token it replaces, and the
    Token renewal item says so. */
const LOGGING_OUT = /\b(?:log(?:s|ged|ging)?[- ]?outs?|sign(?:s|ed|ing)?[- ]?outs?|all (?:of )?(?:your |the )?devices|every device|everywhere)\b/i
/** A password only named (#1456's eighth round), which gives a logout's context to its own clause, where a
    conjunction ends it (CLAUSE_JOIN, the stop the endpoint claim reads): in "Passwords are hashed and idle sessions end
    after 30 minutes." the idle timeout is no logout's end. A password changed or reset (LOGGING_OUT_ACTION), or
    replaced (NEW_PASSWORD), gives it to its whole sentence. */
const PASSWORD = /\bpasswords?\b/i
/** A verb the session-end readings take for an end, which a conjunction carries a clause on to (CLAUSE_JOIN). */
const END_VERB = String.raw`(?:end(?:s|ed|ing)?|clos(?:e|es|ed|ing)|stop(?:s|ped|ping)?|terminat(?:e|es|ed|ing)|kill(?:s|ed|ing)?|invalidat(?:e|es|ed|ing)|expir(?:e|es|ed|ing)|revok(?:e|es|ed|ing)|(?:signs?|logs?|signed|logged)\s+(?:you\s+)?out|times? out|timed out|cuts? off)\b`
/** A sentence's clauses: split at a semicolon, and at a conjunction (CLAUSE_JOIN) that does not carry it on to an end
    (CARRIED_ON, END_VERB) and does not, right after the password with no comma, join it to one more noun before an end
    ("your password or email ends every session"). */
const clausesOf = (sentence: string) =>
  sentence.split(
    new RegExp(String.raw`\s*;\s*|,?\s+${CLAUSE_JOIN}\s+(?!${CARRIED_ON}${END_VERB})(?!(?<=\bpasswords?\s+${CLAUSE_JOIN}\s+)[\w'’-]+\s+${CARRIED_ON}${END_VERB})`, 'i'),
  )
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
    String.raw`${AFFIRMED}\brevok(?:e|es|ed|ing)\b(?!${DENIED_OBJECT})(?:[^\w.;!?]+[\w'’-]+){0,3}?[^\w.;!?]+\b(?:every|all|each|any|your|the|other|open)\b(?:\s+(?:of|your|the|other|open|active))*\s+sessions?\b(?![- ]tokens?)`,
    String.raw`${AFFIRMED}\b(?:signs?|logs?|signed|logged)\s+(?:you|everyone|everybody)\s+out\b(?!${DENIED_OBJECT})`,
    String.raw`${AFFIRMED}\b(?:signs|logs|signed|logged)\s+out\s+(?:of\s+|from\s+|on\s+|across\s+)?${ENDED}`,
    String.raw`\b(?:you|everyone|everybody)(?:['’]re|\s+are|\s+will be|\s+get|\s+are then)\s+(?:signed|logged)\s+out\b`,
    String.raw`\b(?:sessions?(?![- ]tokens?)|devices?|tabs?|browsers?|the others)\b[^.;!?]*?${AFFIRMED}\b(?:end(?:s|ed)?(?!\s+of\b)|clos(?:e|es|ed)|stop(?:s|ped)?|terminat(?:e|es|ed)|times? out|timed out|(?:is|are|get|gets|will be|would be|be)\s+(?:ended|closed|terminated|revoked|invalidated|killed|cut off|signed out|logged out))\b(?!${DENIED_OBJECT})${AT_EXPIRY}`,
    String.raw`${AFFIRMED}(?:\b(?:ends?|ended|expires?|stops?|closes?|(?:signs?|logs?|signed|logged) (?:you )?out|(?:is|are) (?:revoked|ended))\b|\b(?:ending|expired|stopped|closed|terminat(?:e|es|ed|ing)|kill(?:s|ed)?|invalidat(?:e|es|ed)|times? out|timed out|cuts? off|(?:signs?|logs?|signed|logged)\s+(?:you\s+)?out)\b)(?!${DENIED_OBJECT}).*${WITHIN}`,
  ].join('|'),
  'i',
)
/** A reuse, as a sentence names it. */
const REUSED = String.raw`\b(?:a second time|again|twice|more than once|re-?us(?:e|ed|es|ing)|replay(?:s|ed|ing)?|already (?:been )?used|used before|(?:old|used|rotated(?:[- ]away)?|stale|spent) (?:refresh )?tokens?)\b`
/** A sweep of the account's sessions, as a reuse's consequence: what ends every session, signs you out on every device
    or everywhere, or logs everyone out, and every session named before the verb that ends it. A session that ends on
    its own beside a reuse word ("your session ends and you log in again") is no sweep. */
const SWEEP = [
  String.raw`${ENDS}(?:[^\w.;!?]+[\w'’-]+){0,3}?[^\w.;!?]+${EVERY_SESSION}`,
  String.raw`${AFFIRMED}\b(?:signs?|logs?|signed|logged)\s+(?:(?:you|everyone|everybody)\s+)?out\b(?:[^\w.;!?]+[\w'’-]+){0,3}?[^\w.;!?]+${EVERY_SESSION}`,
  String.raw`${AFFIRMED}\b(?:signs?|logs?|signed|logged)\s+(?:everyone|everybody)\s+out\b`,
  String.raw`${EVERY_SESSION}[^.;!?]*?${AFFIRMED}\b(?:end(?:s|ed)?|clos(?:e|es|ed)|terminat(?:e|es|ed)|(?:is|are|get|gets|will be)\s+(?:ended|closed|terminated|revoked|invalidated|signed out|logged out))\b`,
].join('|')
/** Main's works-once phrases, read as main reads them, in any block. */
const WORKS_ONCE = /\bworks? (?:only )?once\b|\bsingle[- ]use\b|\b(?:used|usable|valid|good) (?:only )?(?:once|one time)\b|\bonly once\b|\bone time only\b/i
/** A credential that is not the refresh or session token, by its noun: a code, a link, a password, a key, an invite, a
    PIN. */
const CREDENTIAL = String.raw`(?:codes?|links?|passwords?|passcodes?|passphrases?|keys?|invit\w*|OTPs?|PINs?)`
/** The words of another credential's name before its noun: "recovery codes", "password reset links", "sign-in
    links". */
const CREDENTIAL_NAME = String.raw`(?:recovery|verification|backup|login|log-in|sign-in|signin|magic|reset|password|invite|invitation|confirmation|security|access|authentication|auth|email|e-mail|SMS|text|API)`
/** "One-time" as another credential's (#1456's eleventh round): directly before its noun, up to two words of its name
    between ("Refresh tokens are reusable, unlike one-time recovery codes."), unless it is said of something, after
    "is", "are" or "be", or "remain", "become" or "stay" (Codex's thread 4352450748 on fe07229a), or compared with it,
    after "like" or "as", where the token may be what is one-time ("Refresh tokens are one-time keys.", "Refresh
    tokens remain one-time access keys.", "Refresh tokens work like one-time codes."). Up to two words may stand
    between, an article, an adverb in -ly or one of a few others ("are still", "are effectively"). */
const ONE_TIME_OF_ANOTHER = String.raw`(?<!\b(?:is|are|was|were|be|been|being|remains?|remained|becomes?|became|stays?|stayed|like|as)\s+(?:(?:a|an|each|all|both|always|only|just|also|still|simply|now|already|\w+ly)\s+){0,2})\bone-time\s+(?:${CREDENTIAL_NAME}\s+){0,2}${CREDENTIAL}\b`
/** The one-use forms main's phrases miss ("one-time", "good for one use", "cannot be used twice", "cannot be reused",
    "after one use"), read only in a sentence about the refresh or session token: one that names it (TOKEN_CONTEXT), or
    one in a block that names it and names no other credential (OTHER_CREDENTIAL), as "Each one cannot be reused." in
    the Token renewal item. "A one-time recovery code", a reset link and a verification code are other credentials,
    and "one-time" directly before another credential's noun is that credential's in a sentence that names the token
    too (ONE_TIME_OF_ANOTHER). The forms that are no denial themselves read a negation near them (NOT_NEAR; #1456's
    tenth round): "Refresh tokens are not one-time credentials." passes. */
const ONE_USE = new RegExp(
  String.raw`${NOT_NEAR}(?:(?!${ONE_TIME_OF_ANOTHER})\bone-time\b|\b(?:used|usable|valid|good)(?: only)? for (?:one|a single) use\b|\bafter (?:one|a single|its first) use\b)` +
    String.raw`|\b(?:can(?:not|['’]t| not)|can never|may not|never|won['’]t) be (?:used|presented|accepted) (?:twice|again|more than once|a second time)\b|\b(?:can(?:not|['’]t| not)|can never|won['’]t) be re-?used\b`,
  'i',
)
/** The refresh or session token, or token renewal, named. */
const TOKEN_CONTEXT = /\b(?:refresh|session)[- ]tokens?\b|\btoken renewal\b/i
/** A credential that is not the refresh or session token (CREDENTIAL), named. */
const OTHER_CREDENTIAL = new RegExp(String.raw`\b${CREDENTIAL}\b`, 'i')
/** A sentence about the refresh or session token: one that names it (TOKEN_CONTEXT), or one in a block that names it
    and that names no other credential (OTHER_CREDENTIAL). */
const aboutTheToken = (block: string) => (sentence: string) => TOKEN_CONTEXT.test(sentence) || (TOKEN_CONTEXT.test(block) && !OTHER_CREDENTIAL.test(sentence))
/** A one-use form about the refresh or session token, in one sentence of the block. */
const oneUseOfTheToken = (block: string) => sentencesOf(block).some((sentence) => ONE_USE.test(sentence) && aboutTheToken(block)(sentence))
/** Main's reuse reading, as main reads it, in any sentence: a revocation beside main's reuse words. */
const MAIN_REUSE = /^(?=.*\brevok).*\b(?:a second time|again|twice|re-?us(?:e|ed|es|ing)|replay(?:s|ed|ing)?)\b/i
/** The reuse forms this pull request reads beyond main's (REUSED's other words, a sweep or a lock as what follows),
    read as the one-use forms are, only in a sentence about the refresh or session token (#1456's eighth round): "A
    verification code cannot be used more than once and can be revoked from settings." is another credential's. */
const REUSE_OF_THE_TOKEN = new RegExp(String.raw`^(?=.*${REUSED})(?=.*(?:\brevok|${SWEEP}|\block(?:s|ed)?\s+(?:the account|you out)\b))`, 'i')
/** Main's timed and untimed readings on every logging-out word (LOGGING_OUT and PASSWORD, main's own words among
    them), with a denial read as SESSION_END_MORE reads one, before the verb or on the subject (NOT) or on its object
    (DENIED_OBJECT): "Logging out does not end every session within 30 minutes", "No session ends within 30 minutes of
    logging out" and "Logging out ends no other session" deny the end, unless "but" affirms it past the denial
    (BUT_AFFIRMS: "Logging out does not end your sessions in a day but within 30 minutes"). A promise stays one:
    nothing else is taken from main's readings. */
const deniable = (re: RegExp) => new RegExp(String.raw`${AFFIRMED}(?![\w'’-]+${DENIED_OBJECT})` + re.source, 'i')
const SESSION_END_TIMED_DENIABLE = deniable(SESSION_END_TIMED)
const SESSION_END_UNTIMED_DENIABLE = deniable(SESSION_END_UNTIMED)

/** A logging-out action as a sentence names it: a logout or a sign-out in their spellings, or a password changed or
    reset. A password only named ("Passwords are hashed") is no action. */
const LOGGING_OUT_ACTION = /\b(?:log(?:s|ged|ging)?[- ]?outs?|sign(?:s|ed|ing)?[- ]?outs?)\b|\b(?:chang|reset|updat)\w*\b[^.;!?]{0,20}\bpasswords?\b|\bpasswords?\s+(?:(?:is|are|was|were|gets?|got)\s+)?(?:chang|reset|updat)\w*/i
/** A password replaced ("choose a new password"), a change in the sentence that names it (#1456's eighth round): the
    replacement itself, not "new password" before a noun it names ("our new password policy", "the new password
    field"), which this pull request's wider end forms read as a password only named (PASSWORD; #1456's eleventh
    round). */
const NEW_PASSWORD = /\b(?:new|another|different)\s+passwords?\b(?!\s+(?:policy|policies|requirements?|rules?|criteria|fields?|forms?|pages?|screens?|box(?:es)?|inputs?|prompts?|hints?|strength|length|managers?|settings?|format)\b)/i
/** A new password named, before a noun or not, whose sentence main's timed and untimed readings read whole, as main
    reads its password word anywhere in an item (#1456's eleventh round): read as a password only named there, it would
    pass a change said through the form that main refuses ("Submit the new password form and every session ends within
    30 minutes."), so "Our new password policy is documented and idle sessions end after 30 minutes." fails, as on main. */
const ANY_NEW_PASSWORD = /\b(?:new|another|different)\s+passwords?\b/i
/** A password acted on in other words (#1456's eleventh round), a logging-out action as a password changed or reset is
    (LOGGING_OUT_ACTION, which reads change, reset and update itself): a verb acting on the password, its object naming
    it after a determiner ("pick a fresh password", "type your password twice", "submit the password form", "comply
    with the password policy"; "a set of password rules" is no such object), or the password's form, page, field or
    screen saving it ("the password form saves your choice"). Its whole sentence, across "and", and the sentence after
    it are a logout's context. Main refuses these by its password word anywhere; read as a password only named, they had
    passed since round 8, and the sentence after since round 7. */
const PASSWORD_ACTED_ON = new RegExp(
  String.raw`\b(?:pick|choose|set|create|enter|type|retype|submit|save|fill in|meet|follow|comply with)\s+(?:a|an|the|your|its|their|this|that|one)\s+(?:(?!(?:and|or|but)\b)[\w'’-]+\s+){0,2}?passwords?\b` +
    String.raw`|\b(?:the|your|our)\s+(?:new\s+)?password\s+(?:form|page|field|screen)\s+saves\b`,
  'i',
)
/** What of a block a promise of logging out is read in: a sentence that names a logging-out word or action itself
    (LOGGING_OUT, LOGGING_OUT_ACTION, NEW_PASSWORD, PASSWORD_ACTED_ON), the one after a sentence that names a logging-out
    action or a password acted on, which
    goes on from it ("Logging out of all devices revokes your refresh tokens. Each session then ends within 30
    minutes."), and the clause of a password only named (PASSWORD, clausesOf). A word in a neighbouring sentence or
    clause is no context: in "Passwords are hashed. Idle sessions end after 30 minutes." the idle timeout is no logout's
    end. */
const loggingOutSentences = (block: string) =>
  sentencesOf(block).flatMap((sentence, i, all) =>
    LOGGING_OUT.test(sentence) || LOGGING_OUT_ACTION.test(sentence) || NEW_PASSWORD.test(sentence) || PASSWORD_ACTED_ON.test(sentence) || (i > 0 && (LOGGING_OUT_ACTION.test(all[i - 1]) || PASSWORD_ACTED_ON.test(all[i - 1])))
      ? [sentence]
      : clausesOf(sentence).filter((clause) => PASSWORD.test(clause)),
  )

const E127_PROMISES: Array<[string, (block: string) => boolean]> = [
  [
    'a refresh token that works once',
    (block) => inASentence(WORKS_ONCE)(block) || oneUseOfTheToken(block),
  ],
  [
    'a reused refresh token revoking the account',
    (block) =>
      inASentence(MAIN_REUSE)(block) || sentencesOf(block).some((sentence) => REUSE_OF_THE_TOKEN.test(sentence) && aboutTheToken(block)(sentence)),
  ],
  [
    'a session that ends after logging out, within a time or with none named',
    (block) =>
      loggingOutSentences(block).some((sentence) => SESSION_END_TIMED_DENIABLE.test(sentence) || SESSION_END_UNTIMED_DENIABLE.test(sentence) || SESSION_END_MORE.test(sentence)) ||
      sentencesOf(block).some((sentence) => ANY_NEW_PASSWORD.test(sentence) && (SESSION_END_TIMED_DENIABLE.test(sentence) || SESSION_END_UNTIMED_DENIABLE.test(sentence))),
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

/** A Python module's code, its docstrings and comments dropped, so a mention is not read as a call. A docstring's line
    breaks stay, so a line number in the code is the module's own. */
const pythonCode = (src: string) =>
  src.replace(/"""[\s\S]*?"""|'''[\s\S]*?'''/g, (doc) => '""' + '\n'.repeat(doc.split('\n').length - 1)).replace(/(^|\s)#.*$/gm, '$1')

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
    Apple writes the register row beside its oauth_login row (D-054), read under registrations and logins. */
const AUDITED: Record<string, string[]> = {
  registrations: ['register'],
  logins: ['login_success', 'oauth_login'],
  'failed logins': ['login_failed'],
  logouts: ['logout'],
  'data exports': ['data_exported'],
  'account deletions': ['user_deleted'],
  "administrators' invites": ['invite_minted', 'invite_revoked', 'invite_resent'],
  "administrators' feedback status changes": ['feedback_status_changed'],
}

/** The audit_logs actions the backend writes that the item does not name, and what each records. The item names part
    of what the rows record; naming one of these on the page changes the page's sentence, which is the founder's. */
const AUDITED_UNNAMED: Record<string, string> = {
  oauth_linked: 'a Google or Apple sign-in linked to an existing account',
  oauth_unlinked: 'a Google or Apple sign-in unlinked in the account settings',
  summaries_bulk_reset: "an administrator's bulk reset of generated summaries, so they regenerate",
  summaries_refresh_stale: "an administrator's regeneration of stale summaries in place",
}

/** Where a Python string literal that starts at `at` ends: its closing quote, or its line's end (pythonCode has dropped
    the triple-quoted ones). */
const pythonStringEnd = (code: string, at: number) => {
  let i = at + 1
  while (i < code.length && code[i] !== code[at] && code[i] !== '\n') i += code[i] === '\\' ? 2 : 1
  return i
}

/** The call whose opening parenthesis is at `open`: its argument list up to the matching closing parenthesis (strings
    and nested brackets read whole), split at its top-level commas, and where that parenthesis is; null when the module
    ends first. */
function pythonCall(code: string, open: number): { args: string[]; close: number } | null {
  const args: string[] = []
  let depth = 0
  let start = open + 1
  for (let i = open; i < code.length; i++) {
    const c = code[i]
    if (c === '"' || c === "'") i = pythonStringEnd(code, i)
    else if ('([{'.includes(c)) depth++
    else if (')]}'.includes(c)) {
      depth--
      if (depth === 0) {
        const last = code.slice(start, i).trim()
        return { args: last ? [...args, last] : args, close: i }
      }
    } else if (c === ',' && depth === 1) {
      args.push(code.slice(start, i).trim())
      start = i + 1
    }
  }
  return null
}

/** A module function's code from its def line: its signature, read to the parenthesis that closes it (a signature may
    close at the line's start, as `) -> AuditLog:` does), and its body, up to the next line that starts at the margin. */
function pythonFunctionAt(code: string, def: number, open: number): string {
  const close = pythonCall(code, open)?.close ?? open
  const bodyStart = code.indexOf('\n', close) + 1 || code.length
  const next = code.slice(bodyStart).search(/^\S/m)
  return code.slice(def, next < 0 ? code.length : bodyStart + next)
}

/** The opening parenthesis of the call whose argument list holds `index`, or -1 outside any call. */
function pythonEnclosingCall(code: string, index: number): number {
  let depth = 0
  for (let i = index - 1; i >= 0; i--) {
    const c = code[i]
    if (')]}'.includes(c)) depth++
    else if ('([{'.includes(c)) {
      if (depth === 0) return c === '(' ? i : -1
      depth--
    }
  }
  return -1
}

/** What a call passes as its `name` parameter: the keyword argument's value, or else the positional one at `position`
    (null when neither is there). */
function pythonArgument(args: string[], name: string, position: number): { value: string; positional: boolean } | null {
  const keyword = args.find((arg) => new RegExp(String.raw`^${name}\s*=(?!=)`).test(arg))
  if (keyword) return { value: keyword.replace(new RegExp(String.raw`^${name}\s*=\s*`), ''), positional: false }
  const positional = args.filter((arg) => !/^\w+\s*=(?!=)/.test(arg) && !arg.startsWith('*'))
  return position >= 0 && position < positional.length ? { value: positional[position], positional: true } : null
}

/** A Python string literal's text when it is a plain word ("register", 'logout'), else undefined. */
const pythonWord = (value: string) => value.match(/^(['"])(\w+)\1$/)?.[2]

/** An audit_service function that calls create_audit_log: the action it writes, or the template it fills from one of
    its parameters (`action=f"subscription_{action}"`), and its parameters in order. */
type AuditHelper = { params: string[] } & ({ action: string } | { prefix: string; param: string; suffix: string })

/** The audit_logs actions the backend writes, read so that none is missed: each create_audit_log call's action from
    its own argument list (a literal `action=` keyword), each audit_service function that calls create_audit_log (a
    helper) with a literal action or a template one, and each call of a helper from another module, a template helper's
    action composed from the call's literal keyword (`action="created"` gives subscription_created). A call or helper
    passed as a callable to run_in_threadpool (`run_in_threadpool(audit_service.create_audit_log, db, action=...)`),
    which runs it, is read from the arguments passed with it; passed to any other call, it is reported. An import is
    not a call, and a call is the service's only where the module binds its name to the service. Whatever the walk
    cannot read (a variable or an f-string action outside the service, a positional action, a helper whose action is
    neither, a name mentioned but not called) is listed in `unread`, with its module and line, and the test holds that
    list empty, so it fails closed. */
function auditActions(modules: Record<string, string>): { written: Set<string>; unread: string[] } {
  const isService = (rel: string) => /(?:^|\/)audit_service\.py$/.test(rel)
  const lineOf = (code: string, index: number) => code.slice(0, index).split('\n').length
  const helpers = new Map<string, AuditHelper>()
  const unread: string[] = []
  const serviceUses: Array<{ rel: string; code: string; spans: Array<{ name: string; start: number; end: number }>; readAt: number[] }> = []
  for (const [rel, src] of Object.entries(modules)) {
    if (!isService(rel)) continue
    const code = pythonCode(src)
    // The service's top-level functions, and the one create_audit_log call each helper is read by.
    const spans: Array<{ name: string; start: number; end: number }> = []
    const readAt: number[] = []
    for (const def of code.matchAll(/^(?:async\s+)?def\s+(\w+)\s*\(/gm)) {
      const name = def[1]
      const open = (def.index ?? 0) + def[0].length - 1
      const body = pythonFunctionAt(code, def.index ?? 0, open)
      spans.push({ name, start: def.index ?? 0, end: (def.index ?? 0) + body.length })
      const call = name === 'create_audit_log' ? null : body.match(/\bcreate_audit_log\s*\(/)
      if (!call) continue
      readAt.push((def.index ?? 0) + (call.index ?? 0))
      const params = (pythonCall(code, open)?.args ?? []).map((param) => param.split(/[:=]/)[0].trim())
      const action = pythonArgument(pythonCall(body, (call.index ?? 0) + call[0].length - 1)?.args ?? [], 'action', 1)
      const word = action && !action.positional ? pythonWord(action.value) : undefined
      const template = action && !action.positional ? action.value.match(/^[fF](['"])(\w*)\{(\w+)\}(\w*)\1$/) : null
      if (word) helpers.set(name, { params, action: word })
      else if (template && params.includes(template[3])) helpers.set(name, { params, prefix: template[2], param: template[3], suffix: template[4] })
      else unread.push(`${rel}:${lineOf(code, def.index ?? 0)} ${name} passes create_audit_log an action the walk cannot read (${action?.value ?? 'none'})`)
    }
    // Any other create_audit_log in the service is a write the walk does not read: one in a class's method or in code
    // at the module's top level, and inside a top-level function a second call or the writer passed on.
    serviceUses.push({ rel, code, spans, readAt })
  }
  for (const { rel, code, spans, readAt } of serviceUses) {
    for (const use of code.matchAll(new RegExp(String.raw`(?<!\bdef\s+)\b(?:${['create_audit_log', ...helpers.keys()].join('|')})\b`, 'g'))) {
      const at = use.index ?? 0
      if (readAt.includes(at)) continue
      const fn = spans.find(({ start, end }) => at >= start && at < end)
      if (!fn) unread.push(`${rel}:${lineOf(code, at)} ${use[0]} is used outside a top-level function of the service, which the walk does not read`)
      else if (use[0] === 'create_audit_log') unread.push(`${rel}:${lineOf(code, at)} ${fn.name} uses create_audit_log other than in the one call the walk reads`)
      // A helper used inside a function of the service, called or passed on, writes through it there, whether or not
      // the function writes a row of its own (#1456's thirteenth round): the walk follows no helper inside the service.
      else unread.push(`${rel}:${lineOf(code, at)} ${fn.name} uses ${use[0]} inside the service, which the walk does not follow`)
    }
  }
  const written = new Set<string>()
  const callees = ['create_audit_log', ...helpers.keys()]
  const IMPORT = /^[ \t]*(?:from[ \t]+([\w.]+)[ \t]+)?import[ \t]+(\([^)]*\)|[^\n]*)/gm
  const isServicePath = (path: string) => /(?:^|\.)audit_service$/.test(path)
  for (const [rel, src] of Object.entries(modules)) {
    if (isService(rel)) continue
    const raw = pythonCode(src)
    // The module's bindings, read from its imports before they are blanked (an import names a callee without calling
    // it): a writer under its own name (`own`) or an alias (`from ...audit_service import create_audit_log as
    // write_audit`), and the service as a module (`import app.services.audit_service as audit`, `from app.services
    // import audit_service`). A star import of the service binds every callee, under names the walk cannot follow.
    const writerOf = new Map(callees.map((name) => [name, name]))
    const own = new Set<string>()
    const aliases: string[] = []
    const services: string[] = []
    for (const statement of raw.matchAll(IMPORT)) {
      const [, from, list] = statement
      for (const part of list.replace(/[()]/g, '').split(',').map((piece) => piece.trim()).filter(Boolean)) {
        const [target, alias] = part.split(/\s+as\s+/).map((piece) => piece.trim())
        if (from !== undefined && isServicePath(from)) {
          if (target === '*') {
            unread.push(`${rel}:${lineOf(raw, statement.index ?? 0)} imports * from ${from}, which binds names the walk cannot follow`)
            for (const name of callees) own.add(name)
          } else if (alias && callees.includes(target)) {
            writerOf.set(alias, target)
            aliases.push(alias)
          } else if (callees.includes(target)) own.add(target)
        } else if (from !== undefined ? target === 'audit_service' : isServicePath(target)) services.push(alias ?? target)
      }
    }
    const code = raw.replace(IMPORT, (statement) => statement.replace(/[^\n]/g, ' '))
    // The service bound as a module is followed only through `<module>.<name>`; any other use of it (getattr, passed on,
    // reassigned) is a binding the walk cannot follow.
    for (const service of services) {
      for (const use of code.matchAll(new RegExp(String.raw`(?<![\w.])${escapeRe(service)}\b(?!\s*\.\s*\w)`, 'g'))) {
        unread.push(`${rel}:${lineOf(code, use.index ?? 0)} ${service} (the audit service) is used other than as ${service}.<name>, so the walk cannot follow what it calls`)
      }
    }
    // A writer under its own name may be an attribute (`audit_service.create_audit_log`); an alias is a bare name. A
    // name is the service's only where the module binds it so (Codex's r4352223779 on 3a72b4ef): imported from the
    // service, or an attribute of the service bound as a module. A function of the module's own, another module's
    // import or another object's attribute that shares a callee's name writes no row; the service reached through a
    // binding the walk does not read (`services.audit_service.<name>`, or `audit_service` never imported) is reported.
    const bound = aliases.length ? String.raw`|(?<![\w.])(?<alias>${aliases.map(escapeRe).join('|')})` : ''
    for (const mention of code.matchAll(new RegExp(String.raw`(?<!\bdef\s+)(?:(?<qualifier>(?<![\w.])\w+(?:\.\w+)*)\.)?(?:\b(?<own>${callees.join('|')})${bound})\b(?<called>\s*\()?`, 'g'))) {
      const spelled = mention.groups?.own ?? mention.groups?.alias ?? ''
      const qualifier = mention.groups?.qualifier
      const called = mention.groups?.called
      const name = writerOf.get(spelled) ?? spelled
      const at = mention.index ?? 0
      if (qualifier !== undefined ? !services.includes(qualifier) : mention.groups?.own !== undefined && !own.has(spelled)) {
        if (qualifier !== undefined && /(?:^|\.)audit_service$/.test(qualifier)) {
          unread.push(`${rel}:${lineOf(code, at)} ${qualifier}.${spelled} reaches the audit service through a binding the walk does not read`)
        }
        continue
      }
      const where = `${rel}:${lineOf(code, at)} ${spelled}`
      let args: string[] | null = null
      if (called) args = pythonCall(code, at + mention[0].length - 1)?.args ?? null
      else {
        // A callable passed first, with its arguments after it, to run_in_threadpool, the call the backend uses that runs
        // it. Passed to anything else (a stored `partial`, a callback registered), it may never run, and is reported
        // (Codex's r4353220551 on 9fc0f1b4).
        const open = pythonEnclosingCall(code, at)
        if (open >= 0 && /^\s*(?:[\w.]+\.)?$/.test(code.slice(open + 1, at))) {
          const runner = code.slice(0, open).match(/([\w.]+)\s*$/)?.[1] ?? 'a call'
          if (!/(?:^|\.)run_in_threadpool$/.test(runner)) {
            unread.push(`${where} is passed to ${runner}, which the walk does not know runs it`)
            continue
          }
          args = (pythonCall(code, open)?.args ?? []).slice(1)
        }
      }
      if (args === null) {
        unread.push(`${where} is named but not called, so the walk cannot read its action`)
        continue
      }
      const helper = helpers.get(name)
      if (helper && 'action' in helper) {
        written.add(helper.action)
        continue
      }
      const param = helper ? helper.param : 'action'
      const value = pythonArgument(args, param, helper ? helper.params.indexOf(param) : 1)
      const word = value && !value.positional ? pythonWord(value.value) : undefined
      if (word) written.add(helper ? `${helper.prefix}${word}${helper.suffix}` : word)
      else unread.push(`${where} passes ${param}=${value ? (value.positional ? `${value.value} positionally` : value.value) : 'nothing'}, which the walk cannot read`)
    }
  }
  // A row built directly is one no create_audit_log call writes (#1456's thirteenth round): any AuditLog(...) outside
  // create_audit_log's own body, under its own name or an import's alias, its class statement aside, with strings
  // blanked so a repr's text is no call. Inside the writer, only a row built from its own action parameter
  // (`action=action`) is the row its callers' actions name; any other there, a second row with an action of its own or
  // one from another value, is reported too (Codex's r4352385482 on 673e9d76).
  const writerSpan = serviceUses.flatMap(({ rel, spans }) => spans.filter(({ name }) => name === 'create_audit_log').map((span) => ({ rel, ...span })))
  for (const [rel, src] of Object.entries(modules)) {
    const code = pythonCode(src).replace(/(['"])(?:\\.|(?!\1)[^\\\n])*\1/g, (literal) => ' '.repeat(literal.length))
    const names = ['AuditLog']
    for (const statement of code.matchAll(IMPORT)) {
      for (const part of statement[2].replace(/[()]/g, '').split(',').map((piece) => piece.trim())) {
        const [target, alias] = part.split(/\s+as\s+/).map((piece) => piece.trim())
        if (target === 'AuditLog' && alias) names.push(alias)
      }
    }
    const scanned = code.replace(IMPORT, (statement) => statement.replace(/[^\n]/g, ' '))
    // An assignment binds the model to another name (`Row = AuditLog`), followed as an alias too (Codex's r4352450758
    // on fe07229a); bound in one module and imported into another, or passed as a value, it is out of reach.
    for (let grew = true; grew; ) {
      grew = false
      const assigned = new RegExp(String.raw`^[ \t]*(\w+)[ \t]*(?::[^=\n]*)?=[ \t]*(?:[\w.]*\.)?(?:${names.map(escapeRe).join('|')})[ \t]*$`, 'gm')
      for (const [, alias] of scanned.matchAll(assigned)) {
        if (!names.includes(alias)) {
          names.push(alias)
          grew = true
        }
      }
    }
    const rows = new RegExp(String.raw`(?<!\bclass\s+)(?<![\w])(?:[\w.]*\.)?(?:${names.map(escapeRe).join('|')})\s*\(`, 'g')
    for (const row of scanned.matchAll(rows)) {
      const at = row.index ?? 0
      if (writerSpan.some((span) => span.rel === rel && at >= span.start && at < span.end)) {
        const action = pythonArgument(pythonCall(scanned, at + row[0].length - 1)?.args ?? [], 'action', -1)
        if (action?.value.trim() !== 'action') {
          unread.push(`${rel}:${lineOf(code, at)} builds an AuditLog row in create_audit_log from an action other than its own parameter, which the walk does not read`)
        }
        continue
      }
      unread.push(`${rel}:${lineOf(code, at)} builds an AuditLog row outside create_audit_log, which the walk does not read`)
    }
  }
  return { written, unread }
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
      ['<p>Server events do not just require your consent; they require your explicit opt-in.</p>', true],
      // Usage as the analytics, beside the word's ordinary sense, which names no analytics (#1456's eighth round,
      // Codex's thread 4342548437).
      ['<p>Usage data requires your agreement.</p>', true],
      ['<p>Usage of this website requires your agreement to these Terms.</p>', false],
      // A negation fused with its modal ("cannot") or contracted onto the verb ("isn't") reads as the other negations
      // do (#1456's ninth round, Codex's thread 4344103141), beside look-alikes that stay clear.
      ['<p>Analytics cannot run without your consent.</p>', true],
      ['<p>Analytics cannot run in your browser without your consent.</p>', false],
      ["<p>Usage isn't collected without your consent.</p>", true],
      ["<p>Usage isn't billed without your agreement.</p>", false],
      ['<p>We cannot store your financial data.</p>', true],
      ['<p>We store your financial data with Stripe.</p>', false],
      // A modal on the usage verb reads as its negation does (#1456's ninth round), beside the word's ordinary sense.
      ['<p>Usage can be collected only with your consent.</p>', true],
      ['<p>Usage can be billed only with your agreement.</p>', false],
      // A negation on the verb before "only", beside the promise it denies (#1456's tenth round, Codex's thread
      // 4344569265).
      ['<p>Analytics are collected only with your consent.</p>', true],
      ['<p>Analytics are not collected only with your consent.</p>', false],
      // Consent bound to another operation on the analytics, a gerund that opens the sentence, puts the consent on that
      // operation, beside the analytics collected or tracked and "Usage data requires your agreement." above, which
      // still promise (#1456's twelfth round, Codex's thread 4350498600).
      ['<p>Sharing analytics data with another user requires your consent.</p>', false],
      ['<p>Collecting analytics data requires your consent.</p>', true],
      ['<p>Tracking usage requires your consent.</p>', true],
      // The analytics provider as that operation's recipient is the analytics itself, so D-051's contradiction said
      // through another operation's gerund still promises; a group the provider's name only qualifies is another
      // recipient (#1456's thirteenth round, the review of 730a2d76).
      ['<p>Sharing account events with PostHog requires your consent.</p>', true],
      ['<p>Disclosing usage data to PostHog requires your consent.</p>', true],
      ['<p>Sharing usage data with our analytics provider requires your consent.</p>', true],
      ['<p>Sharing analytics data with PostHog users on your team requires your consent.</p>', false],
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
      // The same with its subject denied, which passes (#1456's tenth round, Codex's thread 4344569268).
      ['<p>No login is required for each endpoint.</p>', false],
      ['<p>You need a token for any endpoint.</p>', true],
      ['<p>Authentication is mandatory on each endpoint.</p>', true],
      ['<p>No endpoint accepts anonymous requests.</p>', true],
      // An account as the login itself (#1456's sixth round, Codex's thread 4339665124).
      ['<p>Each endpoint requires an account.</p>', true],
      ['<p>Each endpoint requires a signed-in account.</p>', true],
      ['<p>Any endpoint needs an account login.</p>', true],
      ['<p>An account is required for each endpoint.</p>', true],
      // A token as the login itself (#1456's seventh round, Codex's thread 4342330091), a token-based login with it.
      ['<p>Each endpoint requires a token.</p>', true],
      ['<p>Each endpoint requires token-based authentication.</p>', true],
      // "And" carries the endpoints on only directly before their predicate, an adverb at most between, as in "Each
      // endpoint returns JSON and requires a login." above; before another subject it starts another clause (#1456's
      // eighth round, Codex's thread 4342548449).
      ['<p>Each endpoint returns JSON and also requires a login.</p>', true],
      ['<p>Each endpoint returns JSON and administrators need a login.</p>', false],
      // The endpoints that cannot be called without a login, in their own clause (#1456's ninth round), beside one
      // endpoint named, which says nothing of every endpoint.
      ['<p>Each endpoint cannot be called without a token.</p>', true],
      ['<p>The admin endpoint cannot be called without a token.</p>', false],
      // A word before the endpoints that picks some of them out narrows the claim, beside the words that leave the set
      // whole (#1456's eleventh round, Codex's thread 4346660304).
      ['<p>Every administrative endpoint requires authentication.</p>', false],
      ['<p>Each private endpoint requires a login.</p>', false],
      ['<p>No administrative endpoint answers without authentication.</p>', false],
      ['<p>Every API endpoint requires authentication.</p>', true],
      ['<p>Each REST endpoint requires a login.</p>', true],
      ['<p>Every one of our endpoints is protected.</p>', true],
      ['<p>Each of its endpoints requires a login.</p>', true],
      ['<p>Each individual endpoint requires a login.</p>', true],
      ['<p>Every EarningsNerd endpoint requires authentication.</p>', true],
      ["<p>All of EarningsNerd's endpoints require authentication.</p>", true],
      // A condition after the endpoints' login need that narrows when they need it says it of some requests, not every
      // one, beside "Each endpoint requires a login." above, a condition that narrows nothing and one that restates
      // every request; main's reading of every endpoint is not narrowed and still refuses the narrowed claim, as main
      // does (#1456's twelfth round, Codex's thread 4350498611).
      ['<p>Each endpoint requires a login only when accessing private records.</p>', false],
      ['<p>Each endpoint requires a login, even when it is public.</p>', true],
      ['<p>Each endpoint requires a login only when you call it.</p>', true],
      ['<p>Every endpoint requires a login only when accessing private records.</p>', true],
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
      // The same negation reach in the consent forms (#1456's fifth round).
      ['<p>Server events do not in any case require your consent.</p>', false],
      ['<p>Account events do not under any circumstances need your permission.</p>', false],
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
      // An account's identifier is an input the endpoint takes, not a login, wherever the family reads an account
      // (#1456's sixth round, Codex's thread 4339665124).
      ['<p>Each endpoint requires an account ID.</p>', false],
      ['<p>Any endpoint expects an account number.</p>', false],
      ['<p>Each endpoint can only be called with an account ID.</p>', false],
      ['<p>No endpoint answers without an account ID.</p>', false],
      // A token before what it names is an input too (#1456's seventh round, Codex's thread 4342330091).
      ['<p>Each endpoint expects a token parameter, but it is optional.</p>', false],
      // A denial on the consent itself, D-051 in other words (#1456's sixth round, Codex's thread 4339665110).
      ['<p>Server events require no consent.</p>', false],
      ['<p>Usage needs no consent.</p>', false],
      ['<p>Account events need no consent from you.</p>', false],
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
      // A negation that does not reach the end it seems to deny (#1456's fifth round): "not only ... but", "not
      // merely", a second predicate after "and", another clause; and a plain phrase past the reach's four words, which
      // the comma aside below lets through.
      ['<li>Logging out does not just log you out here; it ends every session.</li>', true],
      // The affirmative beside the denials the reach admits (the design recheck on 2b30fe47).
      ['<li>Logging out ends your other sessions.</li>', true],
      ['<li>Logging out not only clears this browser but ends every other session.</li>', true],
      ['<li>Logging out does not only end this session but every session on the account.</li>', true],
      ['<li>Logging out does not merely end this session but signs you out of every device.</li>', true],
      ['<li>Logging out does not clear cookies and ends every session.</li>', true],
      ['<li>A logout does not as a rule of thumb end your other sessions.</li>', true],
      // A denial that does not reach the end, now that main's own words read denials too (#1456's sixth round): a
      // denied subject that runs into another clause (after "and", a comma, "because", an aside with a verb of its
      // own), a double negation on the subject or in the reach, a denied object the clause goes on from, and "no" that
      // denies no object ("in no time").
      ['<li>No password is stored and logging out ends every session.</li>', true],
      ['<li>No setup is needed, logging out ends every session.</li>', true],
      ['<li>Nobody stays signed in because logging out ends every session.</li>', true],
      ['<li>Nothing is stored, nothing is shared, logging out ends every session.</li>', true],
      ['<li>Nothing stops logging out from ending every session within 30 minutes.</li>', true],
      ['<li>Logging out never fails to end every session within 30 minutes.</li>', true],
      ['<li>Logging out ends no session but every other one within 30 minutes.</li>', true],
      ['<li>Logging out ends in no time every session on the account.</li>', true],
      // A promise in its own sentence, and in the one after a sentence that names a logging-out action, which goes on
      // from it with nothing carrying it on (#1456's seventh round, Codex's thread 4342330097).
      ['<li>Changing your password ends every session within 30 minutes.</li>', true],
      ['<li>Logging out of all devices revokes your refresh tokens. A session open elsewhere ends within 30 minutes.</li>', true],
      // A reuse form read beyond main's words only about the refresh or session token, beside another credential's
      // (#1456's eighth round, Codex's thread 4342548457), and main's reuse words on any token, as main reads them.
      ['<li>A refresh token used more than once revokes all of the account’s refresh tokens.</li>', true],
      ['<li>A verification code cannot be used more than once and can be revoked from settings.</li>', false],
      ['<li>A token used twice revokes the account.</li>', true],
      // A password only named gives a logout's context to its own clause, which a conjunction ends unless an end
      // follows it or it joins the password to another noun; a password changed, reset or replaced gives it to the
      // sentence (#1456's eighth round, Codex's thread 4342548463). Main refuses the last two, on its password word
      // anywhere in the item.
      ['<li>Your password is reset and every session ends within 30 minutes.</li>', true],
      ['<li>Choose a new password and every other session ends within 30 minutes.</li>', true],
      ['<li>Forgetting your password sends a reset link and ends every session.</li>', true],
      ['<li>Forgetting your password or email ends every session.</li>', true],
      ['<li>Passwords are hashed and idle sessions end after 30 minutes.</li>', false],
      ['<li>Your password is hashed and the session token expires after 30 minutes.</li>', false],
      ['<li>Your password is hashed and every session ends within 30 minutes.</li>', false],
      // "New password" before a noun it names is a password only named for this pull request's wider end forms, while
      // main's timed and untimed readings read its sentence whole, as main does; a password replaced still fails
      // (#1456's eleventh round, Codex's thread 4346660324).
      ['<li>Our new password policy is documented and every other session ends.</li>', false],
      ['<li>The new password field accepts 128 characters and idle sessions end.</li>', false],
      ['<li>Submit the new password form and every session ends within 30 minutes.</li>', true],
      ['<li>Set a new password, and every session ends within 30 minutes.</li>', true],
      ['<li>Your new password ends every other session within 30 minutes.</li>', true],
      // A password acted on in other words, by a verb with the password as its object or by the password's form
      // saving it, is a logging-out action, as a password changed or reset is: its sentence, across "and", and the
      // sentence after give the logout's context, one flag a verb; with no end named it promises nothing, and "a set of
      // password rules" acts on nothing (#1456's eleventh round, the regression since round 8 and, in the sentence
      // after, round 7).
      ['<li>Pick a fresh password and every other session ends within 30 minutes.</li>', true],
      ['<li>Choose a strong password, and every other session ends within 30 minutes.</li>', true],
      ['<li>Set your password and all your other sessions end at once.</li>', true],
      ['<li>Create a password and every session ends within 30 minutes.</li>', true],
      ['<li>Enter a fresh password, and every other session ends within 30 minutes.</li>', true],
      ['<li>Type your password twice and every session ends within 30 minutes.</li>', true],
      ['<li>Retype your password and every other session ends within 30 minutes.</li>', true],
      ['<li>Submit the password form and every session ends within 30 minutes.</li>', true],
      ['<li>Save the password page, and every other session ends within 30 minutes.</li>', true],
      ['<li>Fill in the password field and all your other sessions end at once.</li>', true],
      ['<li>Meet the password requirements and every session ends within 30 minutes.</li>', true],
      ['<li>Follow the password rules, and every other session ends within 30 minutes.</li>', true],
      ['<li>Comply with the password policy and every session ends within 30 minutes.</li>', true],
      ['<li>The password form saves your choice and every session ends within 30 minutes.</li>', true],
      ['<li>Pick a fresh password and your other sessions end.</li>', true],
      ['<li>Pick a fresh password. Every other session ends within 30 minutes.</li>', true],
      ['<li>You can pick a fresh password and every session ends within 30 minutes.</li>', true],
      ['<li>Choose a strong password and enjoy the dashboard.</li>', false],
      ['<li>Each account has a set of password rules, and idle sessions end after 30 minutes.</li>', false],
      // A one-use form with the negation apart from its modal ("can not"), beside another credential's (#1456's ninth
      // round).
      ['<li>A refresh token can not be used twice.</li>', true],
      ['<li>A verification code can not be used twice.</li>', false],
      // A one-use form denied, beside the promise it denies (#1456's tenth round, Codex's thread 4344569270).
      ['<li>Refresh tokens are one-time credentials.</li>', true],
      ['<li>Refresh tokens are not one-time credentials.</li>', false],
      // "One-time" directly before another credential's noun is that credential's, in a sentence that names the refresh
      // token too, beside the token said to be one-time, as a credential's noun said of it or compared with it too
      // (#1456's eleventh round, Codex's thread 4346660313).
      ['<li>Refresh tokens are reusable, unlike one-time recovery codes.</li>', false],
      ['<li>Refresh tokens are one-time tokens, unlike recovery codes.</li>', true],
      ['<li>Unlike recovery codes, refresh tokens are one-time.</li>', true],
      ['<li>Refresh tokens are one-time.</li>', true],
      ['<li>Refresh tokens are one-time keys.</li>', true],
      ['<li>Refresh tokens work like one-time codes.</li>', true],
      // After "remain", "become" or "stay", or with an adverb between, the noun may be the token's too (Codex's thread
      // 4352450748 on fe07229a); a participle between still reads as another credential's.
      ['<li>Refresh tokens remain one-time access keys.</li>', true],
      ['<li>Refresh tokens become one-time recovery codes.</li>', true],
      ['<li>Refresh tokens stay one-time keys.</li>', true],
      ['<li>Refresh tokens are effectively one-time keys.</li>', true],
      ['<li>Refresh tokens are considered one-time keys.</li>', 'gap'],
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
      // A denied subject before main's timed reading, called by the wider logging-out words (main's own, below).
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
      // A negation with an adverbial phrase between it and the verb, with no commas (#1456's fifth round, Codex's
      // thread 4336218364), up to four words, and past them with commas.
      ['<li>Logging out does not by itself end your other sessions.</li>', false],
      ['<li>Logging out does not in normal use end your other sessions.</li>', false],
      ['<li>Changing your password does not on its own end every session.</li>', false],
      ['<li>A logout does not at any point sign you out of every device.</li>', false],
      ['<li>A logout does not of its own accord end your other sessions.</li>', false],
      ['<li>Logging out never by itself ends your other sessions.</li>', false],
      ['<li>A logout does not, as a rule of thumb, end your other sessions.</li>', false],
      // A denial in main's own logging-out words, read as in the wider ones (#1456's sixth round, Codex's thread
      // 4339665129): a negation before the verb, with a phrase or an aside, or "yet" after it, on the subject (its "or",
      // its "and no", its aside) and on the object.
      ['<li>Logging out does not end every session within 30 minutes.</li>', false],
      ['<li>Logging out does not of its own accord end your other sessions.</li>', false],
      ['<li>Logging out does not, by itself, end your other sessions.</li>', false],
      ['<li>Logging out does not yet end your other sessions.</li>', false],
      ['<li>Nothing ends your other sessions when you log out.</li>', false],
      ['<li>No session ends within 30 minutes of logging out.</li>', false],
      ['<li>No session on your phone or laptop ends when you log out.</li>', false],
      ['<li>No session and no device is signed out when you log out.</li>', false],
      ['<li>No session, on any device, ends when you log out.</li>', false],
      ['<li>Logging out ends no other session.</li>', false],
      ['<li>Logging out signs you out of no other device.</li>', false],
      // A password named in a neighbouring sentence is no logging-out context (#1456's seventh round, Codex's thread
      // 4342330097): the idle timeout is no logout's end.
      ['<li>Passwords are hashed. Idle sessions end after 30 minutes.</li>', false],
      // A negation on a causative verb denies the end it governs, as "does not end" does, beside the causative with no
      // negation and a negation that only restricts another verb; "does not make" within four words of the end denied
      // it before (#1456's twelfth round, Codex's thread 4350498620).
      ['<li>Logging out does not cause your other sessions to end.</li>', false],
      ['<li>Logging out causes your other sessions to end.</li>', true],
      ['<li>Logging out does not just end this session but causes every session to end.</li>', true],
      ['<li>Logging out does not make your other sessions end.</li>', false],
      // A causative whose object does not name what ends, a negation four words before a purpose "to" and "not ... but"
      // with a time or what ends promise the end they state, as main reads each; the verb's own complement, its person
      // and a "but" that opens a clause of its own still deny (#1456's thirteenth round, the review of 730a2d76).
      ['<li>Logging out does not cause any noticeable delay to end every session.</li>', true],
      ['<li>Logging out does not cause any noticeable delay to end every session within 30 minutes.</li>', true],
      ['<li>Changing your password does not cause any noticeable delay to end every other session.</li>', true],
      ['<li>Logging out does not force a full page reload to end every session.</li>', true],
      ['<li>Logging out does not cause any extra work for us to end every session.</li>', true],
      ['<li>Logging out does not make anyone wait to end every session.</li>', true],
      ['<li>Logging out does not cause any action from you to end every session.</li>', true],
      ['<li>Logging out does not take any time to end every session.</li>', true],
      ['<li>Logging out does not force a reload to end every session.</li>', true],
      ['<li>Logging out does not end your sessions in a day but within 30 minutes.</li>', true],
      ['<li>Logging out does not end sessions slowly, but at once.</li>', true],
      ['<li>Logging out does not end this session right away but the others.</li>', true],
      ['<li>Logging out does not end this session but every session.</li>', true],
      ['<li>Logging out does not need to end every session.</li>', false],
      ['<li>Logging out does not require you to be signed out of every device.</li>', false],
      ['<li>Logging out does not cause every session on your phone to end.</li>', false],
      ['<li>Logging out does not end your other sessions, but every session ends when its token expires.</li>', false],
      // Out of reach: a promise split across two items, and one said in other words.
      ['<ul><li>Logging out of all devices revokes your refresh tokens.</li><li>Each session then ends within 30 minutes.</li></ul>', 'gap'],
      ['<li>After a password reset, nobody stays signed in.</li>', 'gap'],
      // And a negation that only restricts where no reading sees the restriction: main's untimed reading reads a
      // negation up to three words before "revokes" as a denial.
      ['<li>Logging out does not clear cookies and revokes your session tokens.</li>', 'gap'],
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
    const { written, unread } = auditActions(backendModules())
    expect(
      unread,
      'an audit_logs action the walk cannot read: give the call a literal action= keyword (a template helper the literal its template takes), or teach auditActions its action and classify it',
    ).toEqual([])
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
      ["Registrations, logins, failed logins, logouts, data exports and account deletions are written to an audit log, and so are administrators' invites and feedback status changes", []],
      ["Logins are written to an audit log, and so are administrators' new free accounts", [`"administrators' new free accounts": no audit_logs row is known to record it`]],
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
    const fromPlanted = auditActions({
      'app/services/audit_service.py': [
        'def create_audit_log(db, action):',
        '    """>>> create_audit_log(db, action="in_a_docstring")"""',
        'def log_register(db):',
        '    return create_audit_log(db, action="register")',
        'def log_unused(db):',
        '    return create_audit_log(db, action="never_called")',
      ].join('\n'),
      'app/routers/a.py': [
        'from app.services import audit_service',
        'audit_service.log_register(db)',
        'audit_service.create_audit_log(',
        '    db,',
        '    action="invite_minted",',
        ')',
        '# create_audit_log(db, action="commented_out")',
        'logger.info(f"Admin {actor.id} deleted summary for filing {filing_id}")',
      ].join('\n'),
    })
    expect([...fromPlanted.written].sort()).toEqual(['invite_minted', 'register'])
    expect(fromPlanted.unread).toEqual([])
    // The walk fails closed (Codex's r4335911312 on 94fb37fe): a template helper's action is composed from its caller's
    // literal keyword, a callable passed with its arguments is read from them, and a call whose action it cannot read is
    // reported, by module and line, never skipped. An import names create_audit_log without calling it. The callable
    // counts only when run_in_threadpool runs it; a stored `partial` may never run, and is reported (Codex's
    // r4353220551 on 9fc0f1b4).
    const templated = auditActions({
      'app/services/audit_service.py': [
        'def create_audit_log(db, action, user_id=None):',
        '    return None',
        'def log_subscription_change(db, user_id, user_email, subscription_id, action, details=None):',
        '    """Log a subscription change."""',
        '    return create_audit_log(db=db, action=f"subscription_{action}", user_id=user_id)',
        'def record_admin(db, verb):',
        '    return create_audit_log(db, action=verb)',
        // A signature that closes at the margin, as the real module's multi-line ones do.
        'def log_data_export(',
        '    db,',
        '    user_id,',
        ') -> AuditLog:',
        '    return create_audit_log(',
        '        db=db,',
        '        action="data_exported",',
        '    )',
      ].join('\n'),
      'app/routers/b.py': [
        'from app.services.audit_service import create_audit_log, log_data_export',
        'from app.services import audit_service',
        'audit_service.log_subscription_change(db, user.id, user.email, sub.id, action="created")',
        'audit_service.log_subscription_change(db, user.id, user.email, sub.id, action=kind)',
        'create_audit_log(db, action=f"admin_{verb}")',
        'def record(db, action_name):',
        '    create_audit_log(db, action=action_name)',
        '    create_audit_log(db, action="feedback_status_changed")',
        '    create_audit_log(db, "invite_revoked")',
        '    await run_in_threadpool(audit_service.create_audit_log, db, action="free_account_created")',
        '    hook = audit_service.create_audit_log',
        '    log_data_export(db, user.id)',
        '    callback = partial(audit_service.create_audit_log, db, action="stored_action")',
      ].join('\n'),
    })
    expect([...templated.written].sort()).toEqual(['data_exported', 'feedback_status_changed', 'free_account_created', 'subscription_created'])
    expect(templated.unread).toEqual([
      'app/services/audit_service.py:6 record_admin passes create_audit_log an action the walk cannot read (verb)',
      'app/routers/b.py:4 log_subscription_change passes action=kind, which the walk cannot read',
      'app/routers/b.py:5 create_audit_log passes action=f"admin_{verb}", which the walk cannot read',
      'app/routers/b.py:7 create_audit_log passes action=action_name, which the walk cannot read',
      'app/routers/b.py:9 create_audit_log passes action="invite_revoked" positionally, which the walk cannot read',
      'app/routers/b.py:11 create_audit_log is named but not called, so the walk cannot read its action',
      'app/routers/b.py:13 create_audit_log is passed to partial, which the walk does not know runs it',
    ])
    // The walk follows bindings, not names (Codex's r4336218376 on 2b30fe47): a writer imported under an alias and the
    // service imported as a module are read; a star import, an alias reassigned, the module used other than as
    // `<module>.<name>` and a service function that writes through another helper are reported. The getattr is reported
    // as the module's use; its string binds no name (Codex's r4352223779 on 3a72b4ef).
    const aliased = auditActions({
      'app/services/audit_service.py': [
        'def create_audit_log(db, action, user_id=None):',
        '    return None',
        'def log_register(db, user_id):',
        '    return create_audit_log(db, action="register", user_id=user_id)',
        'def log_subscription_change(db, user_id, user_email, subscription_id, action):',
        '    return create_audit_log(db=db, action=f"subscription_{action}")',
        'def log_both(db, user_id):',
        '    return log_register(db, user_id)',
      ].join('\n'),
      'app/routers/c.py': [
        'from app.services.audit_service import create_audit_log as write_audit, log_register as register_row',
        'import app.services.audit_service as audit',
        'write_audit(db, action="invite_resent")',
        'register_row(db, user.id)',
        'audit.log_subscription_change(db, user.id, user.email, sub.id, action="cancelled")',
        'writer = write_audit',
      ].join('\n'),
      'app/routers/d.py': ['from app.services.audit_service import *', 'create_audit_log(db, action="feedback_status_changed")'].join('\n'),
      'app/routers/e.py': ['from app.services import audit_service', 'fn = getattr(audit_service, "create_audit_log")'].join('\n'),
    })
    expect([...aliased.written].sort()).toEqual(['feedback_status_changed', 'invite_resent', 'register', 'subscription_cancelled'])
    expect(aliased.unread).toEqual([
      'app/services/audit_service.py:8 log_both uses log_register inside the service, which the walk does not follow',
      'app/routers/c.py:6 write_audit is named but not called, so the walk cannot read its action',
      'app/routers/d.py:1 imports * from app.services.audit_service, which binds names the walk cannot follow',
      'app/routers/e.py:2 audit_service (the audit service) is used other than as audit_service.<name>, so the walk cannot follow what it calls',
    ])
    // The design recheck's pair on 2b30fe47: the same call imported directly and under an alias writes the same
    // action, and an alias imported but never used is neither written nor reported.
    const service = ['def create_audit_log(db, action):', '    return None'].join('\n')
    const recheck: Array<[string, string[]]> = [
      [['from app.services.audit_service import create_audit_log', 'create_audit_log(db, action="new_action")'].join('\n'), ['new_action']],
      [['from app.services.audit_service import create_audit_log as write_audit', 'write_audit(db, action="new_action")'].join('\n'), ['new_action']],
      ['from app.services.audit_service import create_audit_log as write_audit', []],
    ]
    for (const [router, actions] of recheck) {
      const walked = auditActions({ 'app/services/audit_service.py': service, 'app/routers/f.py': router })
      expect([...walked.written], router).toEqual(actions)
      expect(walked.unread, router).toEqual([])
    }
    // The service's own scopes (Codex's r4339665139 on e7ee4d95): a top-level function's call is read, a nested
    // function's with it; a call in a class's method or at the module's top level, a second call in one function, the
    // writer passed on and a helper used in a class are reported.
    const scoped = auditActions({
      'app/services/audit_service.py': [
        'def create_audit_log(db, action):',
        '    return None',
        'class AuditWriter:',
        '    def log_new(self, db):',
        '        return create_audit_log(db, action="new_action")',
        '    def log_again(self, db):',
        '        return log_register(db)',
        'def log_register(db):',
        '    def inner():',
        '        return create_audit_log(db, action="register")',
        '    return inner()',
        'def log_pair(db):',
        '    create_audit_log(db, action="first_action")',
        '    return create_audit_log(db, action="second_action")',
        'def log_later(db):',
        '    return run_in_threadpool(create_audit_log, db, action="later_action")',
        'create_audit_log(None, action="boot_action")',
      ].join('\n'),
      'app/routers/g.py': ['from app.services import audit_service', 'audit_service.log_register(db)', 'audit_service.log_pair(db)'].join('\n'),
    })
    expect([...scoped.written].sort()).toEqual(['first_action', 'register'])
    expect(scoped.unread).toEqual([
      'app/services/audit_service.py:5 create_audit_log is used outside a top-level function of the service, which the walk does not read',
      'app/services/audit_service.py:7 log_register is used outside a top-level function of the service, which the walk does not read',
      'app/services/audit_service.py:14 log_pair uses create_audit_log other than in the one call the walk reads',
      'app/services/audit_service.py:16 log_later uses create_audit_log other than in the one call the walk reads',
      'app/services/audit_service.py:17 create_audit_log is used outside a top-level function of the service, which the walk does not read',
    ])
    // A helper that writes its own row and uses another helper too, which writes one the router never names, and an
    // AuditLog row built directly, under its name, an alias or its module (#1456's thirteenth round, the review of
    // 730a2d76): each is reported where it stands, while create_audit_log's own row, the class statement and a repr's
    // text are not, and a query reads no row.
    const nested = auditActions({
      'app/services/audit_service.py': [
        'from app.models.audit_log import AuditLog',
        'def create_audit_log(db, action):',
        '    row = AuditLog(action=action)',
        '    return row',
        'def log_new_thing(db):',
        '    return create_audit_log(db, action="new_thing")',
        'def log_login(db):',
        '    log_new_thing(db)',
        '    return create_audit_log(db, action="login_success")',
      ].join('\n'),
      'app/models/audit_log.py': [
        'class AuditLog(Base):',
        '    def __repr__(self):',
        '        return f"<AuditLog(id={self.id}, action={self.action})>"',
      ].join('\n'),
      'app/routers/h.py': [
        'from app.models.audit_log import AuditLog',
        'from app.models import AuditLog as Row',
        'from app import models',
        'from app.services import audit_service',
        'audit_service.log_login(db)',
        'db.add(AuditLog(action="router_row"))',
        'db.add(Row(action="aliased_row"))',
        'db.add(models.AuditLog(action="module_row"))',
        'rows = db.query(AuditLog).all()',
      ].join('\n'),
    })
    expect([...nested.written]).toEqual(['login_success'])
    expect(nested.unread).toEqual([
      'app/services/audit_service.py:8 log_login uses log_new_thing inside the service, which the walk does not follow',
      'app/routers/h.py:6 builds an AuditLog row outside create_audit_log, which the walk does not read',
      'app/routers/h.py:7 builds an AuditLog row outside create_audit_log, which the walk does not read',
      'app/routers/h.py:8 builds an AuditLog row outside create_audit_log, which the walk does not read',
    ])
    // A callee's name is the service's only where the module binds it so (Codex's r4352223779 on 3a72b4ef): the
    // module's own function, another module's import and another object's attribute under a helper's name write no
    // row, so a register row nothing writes stays unwritten; the service reached through a binding the walk does not
    // read is reported.
    const collided = auditActions({
      'app/services/audit_service.py': [
        'def create_audit_log(db, action):',
        '    return None',
        'def log_register(db):',
        '    return create_audit_log(db, action="register")',
        'def log_logout(db):',
        '    return create_audit_log(db, action="logout")',
      ].join('\n'),
      'app/routers/i.py': [
        'from app.utils.metrics import log_logout',
        'from app import services',
        'def log_register(db):',
        '    return metrics.count("register")',
        'log_register(db)',
        'log_logout(db)',
        'metrics.create_audit_log(db, action="metric_row")',
        'audit_service.log_register(db)',
        'services.audit_service.create_audit_log(db, action="nested_row")',
      ].join('\n'),
      'app/routers/j.py': ['from app.services.audit_service import log_logout', 'log_logout(db)'].join('\n'),
    })
    expect([...collided.written]).toEqual(['logout'])
    expect(collided.unread).toEqual([
      'app/routers/i.py:8 audit_service.log_register reaches the audit service through a binding the walk does not read',
      'app/routers/i.py:9 services.audit_service.create_audit_log reaches the audit service through a binding the walk does not read',
    ])
    // Inside the writer, only the row built from its own action parameter is read at its callers (Codex's
    // r4352385482 on 673e9d76): a second row with an action of its own, or one from another value, is reported.
    const writerRows = auditActions({
      'app/services/audit_service.py': [
        'from app.models.audit_log import AuditLog',
        'def create_audit_log(db, action):',
        '    db.add(AuditLog(user_id=None, action=action))',
        '    db.add(AuditLog(action="shadow_copy"))',
        '    db.add(AuditLog(action=action.upper()))',
        '    return None',
      ].join('\n'),
      'app/routers/k.py': ['from app.services import audit_service', 'audit_service.create_audit_log(db, action="register")'].join('\n'),
    })
    expect([...writerRows.written]).toEqual(['register'])
    expect(writerRows.unread).toEqual([
      'app/services/audit_service.py:4 builds an AuditLog row in create_audit_log from an action other than its own parameter, which the walk does not read',
      'app/services/audit_service.py:5 builds an AuditLog row in create_audit_log from an action other than its own parameter, which the walk does not read',
    ])
    // The model bound to another name by assignment, and that name bound again, is followed as an alias (Codex's
    // r4352450758 on fe07229a); an attribute of it binds nothing.
    const assigned = auditActions({
      'app/services/audit_service.py': ['def create_audit_log(db, action):', '    return None'].join('\n'),
      'app/routers/l.py': [
        'from app.models.audit_log import AuditLog',
        'Row = AuditLog',
        'Again: type = Row',
        'column = AuditLog.action',
        'db.add(Row(action="new_action"))',
        'db.add(Again(action="other_action"))',
      ].join('\n'),
    })
    expect([...assigned.written]).toEqual([])
    expect(assigned.unread).toEqual([
      'app/routers/l.py:5 builds an AuditLog row outside create_audit_log, which the walk does not read',
      'app/routers/l.py:6 builds an AuditLog row outside create_audit_log, which the walk does not read',
    ])
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
  it("is D-046's sentence, pinned with the version a stored allow must carry (CONSENT_VERSION)", () => {
    expect(
      { clause: ANALYTICS_CONSENT_CLAUSE, version: CONSENT_VERSION },
      'a change to what the clause says an allow covers moves CONSENT_VERSION (components/CookieConsent.tsx) in the same commit, so a reader who allowed analytics under the old words chooses again',
    ).toEqual({
      clause: 'Usage statistics through PostHog, so we can see which pages work. When you are logged in they are tied to an internal account id.',
      version: 3,
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
