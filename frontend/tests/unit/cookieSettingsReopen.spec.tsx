import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ts from 'typescript'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrivacyPage from '@/app/privacy/page'
import CookieConsent, { getCookiePreferences, type CookiePreferences } from '@/components/CookieConsent'
import Footer from '@/components/Footer'

vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))

/**
 * The footer's "Cookie settings" reopens the consent dialog after a first choice, so /privacy's withdrawal sentence
 * holds: "You can withdraw consent for analytics and session recording at any time through our cookie consent banner
 * or settings." The bar shows only until a visitor chooses. With a choice stored the bar stays hidden; the footer's
 * control opens CookieConsent's own dialog on the stored toggles, not the defaults; Save writes the new choice and
 * fires cookieConsentChanged, as the bar's Save does (so PostHog follows it); and focus comes back to the control
 * however the dialog closes. The control's brand ring is held by siteChromeFocusRing.spec.ts, which scans the footer.
 *
 * The cookie banner (the bar, its dialog and this control) is the only analytics control, for every visitor
 * (docs/brand/decisions-log.md D-049): analytics and session recording stay off until the visitor allows them, and a
 * browser privacy signal changes nothing in either direction. With Do Not Track and Global Privacy Control sent, a
 * stored allow reads back as an allow, the dialog's boxes are enabled and Save stores what the visitor ticked;
 * consentLayer.spec.tsx holds the first visit, where the bar shows.
 *
 * No app module reads a signal. The no-reader scan reads every module the app runs and the markup it serves
 * (appModules) for each name a signal is read by, as code: Do Not Track on navigator or window (`doNotTrack`, and
 * `msDoNotTrack` in Internet Explorer), Global Privacy Control (`globalPrivacyControl`), the `DNT` and `Sec-GPC`
 * request headers by name, without case, as a string, a Node request's property or a pattern, in middleware, a route
 * handler, a server component or a routing rule, and PostHog's `respect_dnt`, which has the SDK read Do Not Track
 * itself. A name is read with its escapes (`'\x64oNotTrack'`); a pattern with its escapes and the separators between
 * a name's words (`/^sec.gpc$/i`, `/^[Dd][Nn][Tt]$/`), whether a regular expression or a string that `RegExp`,
 * `match`, `matchAll` or `search` builds one from.
 *
 * Code a module carries in a string is read too, in the same walk: a string, a template or a script element's text
 * that parses as a script is read as code (an inline script, as app/layout.tsx carries THEME_BOOTSTRAP, or code
 * handed to `new Function`). Where it does not parse, its text still reads when it spells a signal as code does
 * (`doNotTrack`, `globalPrivacyControl` or `respect_dnt`, in one word), names a header in quotes or as a property, or
 * holds no space and names one (a key, a token, or a pattern's source held in a name). A comment, JSX text outside a
 * script element and copy (a sentence naming the signals in words, or a header in brackets) are not reads. The
 * stored-choice check reads the storage key the same way, in the same walk.
 *
 * /privacy's sentence, in the founder's words, is pinned beside the scan both ways: the page carries the sentence and
 * names a browser privacy signal nowhere else, so the promise D-049 replaced, or a draft's, cannot come back beside it.
 * The two move together: a change that reads a signal fails the scan, whose message says /privacy's sentence changes
 * in the same PR, and a change to what the page says of a signal fails the pin. The planted forms score the reach.
 * Out of reach, planted as gaps: a name assembled at run time, and a header's name in a string with a space in it that
 * does not parse, outside quotes and not handed to `RegExp` (copy names the headers that way: "Do Not Track (DNT)").
 * Outside the scan: the API (backend/, another stack), review-checked.
 */

const STORAGE_KEY = 'cookie_consent'
const CHOSEN: CookiePreferences = { essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }
/** /privacy's sentence on the banner and Do Not Track, as the founder approved it (D-049). */
const PRIVACY_SENTENCE =
  "Analytics and session recording stay off until you allow them, and you can change your choice at any time in Cookie settings. We don't change this based on your browser's Do Not Track setting."
/** A browser privacy signal named in copy: Do Not Track or Global Privacy Control, in words or by abbreviation. */
const SIGNAL_MENTION = /do not track|global privacy control|\bdnt\b|\bgpc\b/gi
/** What a page's text says of the signals: whether it carries the founder's sentence, and each signal it names. */
const signalCopy = (text: string) => ({ sentence: text.includes(PRIVACY_SENTENCE), mentions: text.match(SIGNAL_MENTION) ?? [] })

const stored = (): CookiePreferences | null => {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? (JSON.parse(raw) as CookiePreferences) : null
}

/** A category box's own description, as its paragraph reads (whitespace collapsed, as the computed description is). */
const ownDescription = (id: string) => (document.getElementById(id)?.textContent ?? '').replace(/\s+/g, ' ').trim()

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

/** Left out of the scan, as nothing in them runs in a browser or a request: the specs, the operator scripts, type
 *  declarations and the configs of the lint, style and test tools. Next's own config runs in the server, so it stays. */
const NOT_APP = /^(tests|scripts)\/|\.d\.[mc]?ts$|^(eslint\.[^/]+|postcss\.config\.js|tailwind\.config\.js|vitest\.[^/]+|playwright\.config\.ts)$/

/** Markup the app serves as it is (public/), which can carry a script of its own. */
const MARKUP = /\.(html?|svg)$/

/** Every module the app runs, from git's own list (tracked and new files, ignored ones left out): each JavaScript or
 *  TypeScript module under frontend/ (app, components, features, hooks, lib, the root-level modules Next loads, and
 *  any directory added later), vercel.json, whose routing rules can match a request header, and the HTML and SVG the
 *  app serves. */
const appModules = () =>
  execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], { cwd: FRONTEND, encoding: 'utf8' })
    .split('\0')
    .filter((rel) => (/\.[mc]?[jt]sx?$/.test(rel) || MARKUP.test(rel) || rel === 'vercel.json') && !NOT_APP.test(rel) && existsSync(path.join(FRONTEND, rel)))

/** The names a browser privacy signal is read by, matched without case (a header's name is case-insensitive). */
const SIGNAL_NAMES = new Set(['donottrack', 'msdonottrack', 'globalprivacycontrol', 'dnt', 'sec-gpc', 'respect_dnt'])
/** The same names inside a pattern, read through patternText, a name's words joined by anything but a letter or a
 *  digit: a header matched by pattern (`/^sec-gpc$/i`, `/^sec.gpc$/i`, `new RegExp('\\bdnt\\b')`). */
const SIGNAL_IN_PATTERN = /do[^a-z0-9]*not[^a-z0-9]*track|global[^a-z0-9]*privacy[^a-z0-9]*control|respect[^a-z0-9]*dnt|sec[^a-z0-9]*gpc|(?<![a-z0-9])dnt(?![a-z0-9])/
/** A signal spelled as code spells it, in one word. Copy writes "Do Not Track" and "Global Privacy Control" in words,
 *  so a string that holds one of these carries code, even a fragment that does not parse. */
const SIGNAL_AS_CODE = /donottrack|globalprivacycontrol|respect_dnt/i
/** A header's name in quotes or read as a property: a key in code, which copy does not write. */
const HEADER_AS_KEY = /(['"`])\s*(?:dnt|sec-gpc)\s*\1|\.\s*dnt(?![\w$])/i
/** The stored choice's key inside a string's text, as a whole word (`cookie_consent_history` would be another key). */
const KEY_IN_TEXT = /(?<![\w$-])cookie_consent(?![\w$-])/
/** String's methods that build a pattern from a string they are handed, as `RegExp` does. */
const PATTERN_METHODS = new Set(['match', 'matchAll', 'search'])
/** The elements whose text is a script: HTML's own, and next/script's. */
const SCRIPT_TAGS = new Set(['script', 'Script'])

/** What a module reads: each name, pattern or string a signal is read through, and each read of the stored choice. */
interface Reads {
  signals: string[]
  storedChoice: number
}

const scriptKind = (fileName: string) =>
  fileName.endsWith('.json')
    ? ts.ScriptKind.JSON
    : /\.[jt]sx$/.test(fileName)
      ? ts.ScriptKind.TSX
      : /\.[mc]?js$/.test(fileName)
        ? ts.ScriptKind.JS
        : ts.ScriptKind.TS

/** A pattern's text as the scan reads it: lowercased, an escaped character as itself (`\-`, `\x2d`, `\u002d`), a
 *  class or property escape and a backreference (`\b`, `\s`, `\p{L}`, `\1`) as a separator, and a class of one letter
 *  in either case (`[Ss]`) as that letter. */
function patternText(source: string): string {
  let text = ''
  for (let i = 0; i < source.length; i += 1) {
    if (source[i] !== '\\') {
      text += source[i]
      continue
    }
    const rest = source.slice(i + 1)
    const code = /^u\{([0-9a-f]+)\}|^u([0-9a-f]{4})|^x([0-9a-f]{2})/i.exec(rest)
    const separator = /^[pP]\{[^}]*\}|^k<[^>]*>|^c[A-Za-z]|^[bBdDsSwWnrtfv]|^\d+/.exec(rest)
    if (code) {
      text += String.fromCodePoint(parseInt(code[1] ?? code[2] ?? code[3] ?? '', 16))
      i += code[0].length
    } else if (separator) {
      text += ' '
      i += separator[0].length
    } else {
      text += rest[0] ?? ''
      i += 1
    }
  }
  return text.toLowerCase().replace(/\[([a-z])\1*\]/g, '$1')
}

/** Whether a string is the source of a pattern a call builds: the first argument of `RegExp(…)`, `new RegExp(…)` or a
 *  string's `match`, `matchAll` or `search`. */
function isPatternSource(node: ts.Node): boolean {
  const call = node.parent
  if (!call || !(ts.isCallExpression(call) || ts.isNewExpression(call)) || call.arguments?.[0] !== node) return false
  const callee = call.expression
  const name = ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : undefined
  return name === 'RegExp' || (ts.isPropertyAccessExpression(callee) && name !== undefined && PATTERN_METHODS.has(name))
}

/** The text a node carries as a string: a string's, a template's (each substitution read as a name, `__`), or a script
 *  element's own text. JSX text anywhere else is copy. */
function carriedText(node: ts.Node): string | undefined {
  if (ts.isStringLiteralLike(node)) return node.text
  if (ts.isTemplateExpression(node)) return node.head.text + node.templateSpans.map((span) => `__${span.literal.text}`).join('')
  if (ts.isJsxElement(node) && SCRIPT_TAGS.has(node.openingElement.tagName.getText())) {
    const text = node.children.filter(ts.isJsxText).map((child) => child.text).join('')
    return text.trim() ? text : undefined
  }
  return undefined
}

/** What a string reads: a signal's name, or the stored choice's key, as its whole text; a pattern, where a call
 *  builds one from it; otherwise the code it carries, read as a module of its own where it parses, and by its text
 *  where it does not (a fragment of code, or copy). */
function readString(text: string, patternSource: boolean): Reads {
  if (SIGNAL_NAMES.has(text.toLowerCase())) return { signals: [text], storedChoice: 0 }
  if (text === STORAGE_KEY) return { signals: [], storedChoice: 1 }
  if (patternSource) return { signals: SIGNAL_IN_PATTERN.test(patternText(text)) ? [text] : [], storedChoice: 0 }
  const code = readsOf('carried.tsx', text, true)
  const named = SIGNAL_AS_CODE.test(text) || HEADER_AS_KEY.test(text) || (!/\s/.test(text) && SIGNAL_IN_PATTERN.test(patternText(text)))
  return {
    signals: code.signals.length > 0 ? code.signals : named ? [text] : [],
    storedChoice: code.storedChoice || (KEY_IN_TEXT.test(text) ? 1 : 0),
  }
}

/** What a module reads of a browser privacy signal and of the stored choice, in one walk: its code, and the code its
 *  strings carry (`carried`: a string's text, read as code only where it parses as a script with no syntax error,
 *  which copy does not). Markup the app serves is read as a string's text. Comments are not read. */
function readsOf(fileName: string, text: string, carried = false): Reads {
  if (MARKUP.test(fileName)) return readString(text, false)
  const reads: Reads = { signals: [], storedChoice: 0 }
  const source = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, scriptKind(fileName))
  if (carried && (source as unknown as { parseDiagnostics: readonly ts.Diagnostic[] }).parseDiagnostics.length > 0) return reads
  const visit = (node: ts.Node) => {
    if (ts.isIdentifier(node) && SIGNAL_NAMES.has(node.text.toLowerCase())) reads.signals.push(node.text)
    if (ts.isRegularExpressionLiteral(node) && SIGNAL_IN_PATTERN.test(patternText(node.text.slice(1, node.text.lastIndexOf('/'))))) {
      reads.signals.push(node.text)
    }
    const carriedBy = carriedText(node)
    if (carriedBy !== undefined) {
      const read = readString(carriedBy, isPatternSource(node))
      reads.signals.push(...read.signals)
      reads.storedChoice += read.storedChoice
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return reads
}

/** One walk of every app module, shared by the no-reader scan and the one-reader check. */
let scanned: Array<[string, Reads]> | undefined
const scan = () => (scanned ??= appModules().map((rel): [string, Reads] => [rel, readsOf(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'))]))

describe("the footer's Cookie settings reopens the consent dialog after a choice", () => {
  let consentEvents: CookiePreferences[]
  const onConsentEvent = (e: Event) => consentEvents.push((e as CustomEvent<CookiePreferences>).detail)

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(CHOSEN))
    consentEvents = []
    window.addEventListener('cookieConsentChanged', onConsentEvent)
  })
  afterEach(() => {
    window.removeEventListener('cookieConsentChanged', onConsentEvent)
    localStorage.clear()
  })

  // The site chrome as app/layout.tsx mounts it: the footer, and the one CookieConsent beside it.
  const renderChrome = () => {
    const user = userEvent.setup()
    render(
      <>
        <Footer />
        <CookieConsent />
      </>,
    )
    return { user, control: screen.getByRole('button', { name: 'Cookie settings' }) }
  }

  it('opens the dialog on the stored choice, and Save with analytics off writes it, fires the event and returns focus', async () => {
    const { user, control } = renderChrome()
    expect(screen.queryByRole('region', { name: 'Cookie consent' })).not.toBeInTheDocument()

    await user.click(control)
    const dialog = screen.getByRole('dialog', { name: 'Cookie preferences' })
    expect(within(dialog).getByRole('checkbox', { name: 'Analytics cookies' })).toBeChecked()
    expect(within(dialog).getByRole('checkbox', { name: 'Session recording' })).not.toBeChecked()

    await user.click(within(dialog).getByRole('checkbox', { name: 'Analytics cookies' }))
    await user.click(within(dialog).getByRole('button', { name: 'Save preferences' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Cookie consent' })).not.toBeInTheDocument()
    expect(stored()).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
    expect(consentEvents).toEqual([expect.objectContaining({ essential: true, analytics: false, sessionRecording: false })])
    expect(control).toHaveFocus()
  })

  it.each([
    ['Escape', async (user: ReturnType<typeof userEvent.setup>) => user.keyboard('{Escape}')],
    ['Cancel', async (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole('button', { name: 'Cancel' }))],
  ])('opened from the keyboard and closed with %s, it changes nothing and focus returns to the control', async (_how, close) => {
    const { user, control } = renderChrome()
    control.focus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('dialog', { name: 'Cookie preferences' })).toContainElement(document.activeElement as HTMLElement)

    await user.click(screen.getByRole('checkbox', { name: 'Analytics cookies' }))
    await close(user)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(control).toHaveFocus()
    expect(stored()).toEqual(CHOSEN)
    expect(consentEvents).toEqual([])

    // Opened again from the footer, the dialog starts from the stored choice: the dismissed edit does not come back,
    // so a later Save cannot store it.
    await user.click(control)
    const reopened = screen.getByRole('dialog', { name: 'Cookie preferences' })
    expect(within(reopened).getByRole('checkbox', { name: 'Analytics cookies' })).toBeChecked()
    expect(within(reopened).getByRole('checkbox', { name: 'Session recording' })).not.toBeChecked()
  })

  it('sits in the Legal column beside the links, a button with their recipe', () => {
    const { control } = renderChrome()
    const privacy = screen.getByRole('link', { name: 'Privacy' })
    expect(control.closest('ul')).toBe(privacy.closest('ul'))
    expect(control).toHaveAttribute('type', 'button')
    expect(control.className).toBe(privacy.className)
  })

  describe('a browser privacy signal changes nothing: the banner is the only control (D-049)', () => {
    // jsdom sends no signal. Each case sends every one a browser can, where the browser reports it, and ends with
    // them gone.
    const SIGNALS: Array<[object, string, unknown]> = [
      [navigator, 'doNotTrack', '1'],
      [window, 'doNotTrack', '1'],
      [navigator, 'msDoNotTrack', '1'],
      [navigator, 'globalPrivacyControl', true],
    ]
    beforeEach(() => {
      for (const [on, name, value] of SIGNALS) Object.defineProperty(on, name, { value, configurable: true })
    })
    afterEach(() => {
      for (const [on, name] of SIGNALS) delete (on as Record<string, unknown>)[name]
    })

    it('a stored allow reads back as an allow', () => {
      const allowed: CookiePreferences = { ...CHOSEN, sessionRecording: true }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(allowed))
      expect(navigator.doNotTrack).toBe('1')

      expect(getCookiePreferences()).toEqual(allowed)
      expect(stored()).toEqual(allowed)
    })

    it("the dialog's boxes are enabled on the stored choice, each described by its own text alone", async () => {
      const { user, control } = renderChrome()
      await user.click(control)
      const dialog = screen.getByRole('dialog', { name: 'Cookie preferences' })

      const analytics = within(dialog).getByRole('checkbox', { name: 'Analytics cookies' })
      const recording = within(dialog).getByRole('checkbox', { name: 'Session recording' })
      expect(analytics).toBeEnabled()
      expect(analytics).toBeChecked()
      expect(analytics).toHaveAccessibleDescription(ownDescription('cookie-analytics-desc'))
      expect(recording).toBeEnabled()
      expect(recording).not.toBeChecked()
      expect(recording).toHaveAccessibleDescription(ownDescription('cookie-recording-desc'))
      expect(within(dialog).queryByText(/Do Not Track/)).not.toBeInTheDocument()
    })

    it('Save stores what the visitor ticked, the event carries it and focus returns to the control', async () => {
      const { user, control } = renderChrome()
      await user.click(control)
      await user.click(screen.getByRole('checkbox', { name: 'Session recording' }))
      await user.click(screen.getByRole('button', { name: 'Save preferences' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(stored()).toMatchObject({ essential: true, analytics: true, sessionRecording: true })
      expect(consentEvents).toEqual([expect.objectContaining({ essential: true, analytics: true, sessionRecording: true })])
      expect(control).toHaveFocus()
    })
  })
})

describe('no app module reads a browser privacy signal, and /privacy says so (D-049)', () => {
  it('reads each form of a read and passes a comment and copy that name a signal (a self-check on planted forms)', () => {
    // [the form, the module it is planted in, its code, the signal reads the scan reports, its reads of the stored choice]
    const planted: Array<[string, string, string, string[], number?]> = [
      // Code.
      ['Do Not Track on navigator', 'probe.tsx', "if (navigator.doNotTrack === '1') stop()", ['doNotTrack']],
      ['Do Not Track on window, by its string', 'probe.tsx', "const legacy = 'doNotTrack' in window", ['doNotTrack']],
      ["Internet Explorer's Do Not Track", 'probe.tsx', "const ie = navigator.msDoNotTrack === '1'", ['msDoNotTrack']],
      ['Global Privacy Control', 'probe.tsx', 'if (navigator.globalPrivacyControl) stop()', ['globalPrivacyControl']],
      ['a name written with escapes', 'probe.tsx', "const sent = navigator['\\x64oNotTrack'] ?? navigator.\\u0064oNotTrack", ['doNotTrack', 'doNotTrack']],
      ['the DNT header in middleware', 'middleware.ts', "if (request.headers.get('DNT') === '1') return NextResponse.next()", ['DNT']],
      ['the Sec-GPC header in a server component', 'page.tsx', "const gpc = (await headers()).get('sec-gpc')", ['sec-gpc']],
      ["the DNT header as a Node request's property", 'handler.js', 'const sent = req.headers.dnt', ['dnt']],
      ['the DNT header in a routing rule', 'vercel.json', '{ "rewrites": [{ "source": "/(.*)", "has": [{ "type": "header", "key": "DNT" }], "destination": "/" }] }', ['DNT']],
      ['the Sec-GPC header in a routing rule', 'next.config.js', "module.exports = { rewrites: async () => [{ source: '/:path*', has: [{ type: 'header', key: 'Sec-GPC' }], destination: '/' }] }", ['Sec-GPC']],
      ['PostHog told to read Do Not Track', 'probe.tsx', 'posthog.init(key, { respect_dnt: true })', ['respect_dnt']],
      // Patterns.
      ['the Sec-GPC header matched by pattern', 'route.ts', 'request.headers.forEach((_v, name) => { if (/^Sec-GPC$/i.test(name)) stop() })', ['/^Sec-GPC$/i']],
      ["a pattern's escapes and separators", 'route.ts', 'const gpc = /^sec[-_]gpc$/i.test(name) || /^sec\\x2dgpc$/i.test(name) || /^[Dd][Nn][Tt]$/.test(name)', ['/^sec[-_]gpc$/i', '/^sec\\x2dgpc$/i', '/^[Dd][Nn][Tt]$/']],
      ['a pattern RegExp builds from a string', 'route.ts', "const gpc = new RegExp('^sec-gpc$', 'i').test(name) || RegExp(`\\\\bdnt\\\\b`, 'i').test(name)", ['^sec-gpc$', '\\bdnt\\b']],
      ["a pattern a string's match builds", 'route.ts', "if (name.match('^dnt$')) stop()", ['^dnt$']],
      ["a pattern's source held in a name", 'route.ts', "const SOURCE = '^sec-gpc$'\nexport const sent = (name: string) => new RegExp(SOURCE, 'i').test(name)", ['^sec-gpc$']],
      // Code carried in a string.
      ['an inline script in a template, as app/layout.tsx carries its own', 'layout.tsx', "const BOOTSTRAP = `(function(){try{if (navigator.doNotTrack === '1') window.__off = 1}catch(e){}})()`\nexport const boot = <script dangerouslySetInnerHTML={{ __html: BOOTSTRAP }} />", ['doNotTrack']],
      ['an inline script in a string', 'layout.tsx', 'export const boot = <script dangerouslySetInnerHTML={{ __html: "if (navigator.globalPrivacyControl) window.__off = 1" }} />', ['globalPrivacyControl']],
      ['an inline script in a template with a substitution', 'layout.tsx', "export const boot = (key: string) => `window.__key = '${key}'; if (navigator.msDoNotTrack === '1') window.__off = 1`", ['msDoNotTrack']],
      ["next/script's child", 'layout.tsx', 'export const boot = <Script id="analytics">{`posthog.init(\'k\', { respect_dnt: true })`}</Script>', ['respect_dnt']],
      ["a script element's own text", 'layout.tsx', 'export const boot = <script>window.__gpc = navigator.globalPrivacyControl</script>', ['globalPrivacyControl']],
      ['code handed to new Function', 'probe.tsx', "const read = new Function(\"return navigator['doNotTrack']\")", ['doNotTrack']],
      ['a fragment of code that does not parse alone', 'probe.tsx', "const code = \"if (navigator.doNotTrack === '1') {\" + ' stop() }'", ["if (navigator.doNotTrack === '1') {"]],
      ['a header read in a fragment', 'handler.js', "const code = \"if (req.headers['dnt'] === '1') {\" + ' next() }'", ["if (req.headers['dnt'] === '1') {"]],
      ['a script in an SVG the app serves', 'public/badge.svg', '<svg xmlns="http://www.w3.org/2000/svg"><script>if (navigator.doNotTrack === "1") document.documentElement.remove()</script></svg>', ['doNotTrack']],
      // The stored choice, read by the same walk.
      ['the stored choice read as code', 'probe.tsx', "const raw = localStorage.getItem('cookie_consent') // the cookie_consent key", [], 1],
      ['the stored choice read in an inline script', 'layout.tsx', "const BOOTSTRAP = `(function(){try{var c = localStorage.getItem('cookie_consent')}catch(e){}})()`", [], 1],
      ['the stored choice read in a fragment', 'probe.tsx', "const code = \"var c = localStorage.getItem('cookie_consent'\" + ')'", [], 1],
      ["the stored choice's key written with an escape", 'probe.tsx', "const raw = localStorage.getItem('cookie\\x5fconsent')", [], 1],
      // Look-alikes: not reads.
      ['a comment that names them', 'probe.tsx', '// navigator.doNotTrack, navigator.globalPrivacyControl, the DNT and Sec-GPC headers and the cookie_consent key, named in a comment', []],
      ['copy that names them', 'probe.tsx', "const note = \"Your browser's Do Not Track (DNT) and Global Privacy Control (Sec-GPC) change nothing here.\"", []],
      ['copy that would read DNT if a sentence were code', 'probe.tsx', "const note = 'Do Not Track (DNT) changes nothing here.'", []],
      ['JSX copy that names one', 'probe.tsx', "const copy = <p>We don't change this based on your browser's Do Not Track setting.</p>", []],
      ['an inline script that reads no signal, as THEME_BOOTSTRAP', 'layout.tsx', "const BOOTSTRAP = `(function(){try{var t = localStorage.getItem('theme'); if (t === 'dark') document.documentElement.classList.add('dark')}catch(e){}})();`", []],
      ['a pattern built from a string that names none', 'probe.tsx', 'const own = (utility: string) => new RegExp(`(^|\\\\s)${utility}`).test(className)', []],
      ['another storage key', 'probe.tsx', "const raw = localStorage.getItem('cookie_consent_history')", []],
      // Out of reach: the scan reads a name written whole, as Tailwind classes are written; one assembled at run time
      // is review-checked. A header's name in a string with a space in it is read only where the string parses, quotes
      // it or is handed to RegExp, since copy names the headers the same way.
      ['a gap: a name assembled at run time', 'route.ts', "const gpc = request.headers.get(['sec', 'gpc'].join('-'))", []],
      ['a gap: a header in a pattern with a space, held in a name', 'route.ts', "const LINE = '^dnt: ?1$'\nexport const sent = (line: string) => new RegExp(LINE, 'i').test(line)", []],
    ]
    expect(planted.map(([form, file, code]) => [form, readsOf(file, code)])).toEqual(
      planted.map(([form, , , signals, storedChoice = 0]) => [form, { signals, storedChoice }]),
    )
  })

  it('no app module reads one', () => {
    const modules = scan()
    expect(modules.length).toBeGreaterThan(350)
    expect(modules.map(([rel]) => rel)).toEqual(
      expect.arrayContaining([
        'components/CookieConsent.tsx',
        'app/posthog-provider.tsx',
        'app/layout.tsx',
        'lib/analytics.ts',
        'instrumentation-client.ts',
        'instrumentation.ts',
        'middleware.ts',
        'next.config.js',
        'vercel.json',
        'public/assets/earningsnerd-mark-sage.svg',
      ]),
    )
    const reads = modules.flatMap(([rel, { signals }]) => signals.map((name) => `${rel}: ${name}`))
    expect(
      reads,
      `a browser privacy signal is read in app code. The cookie banner is the only analytics control for every visitor (docs/brand/decisions-log.md D-049), and /privacy (app/privacy/page.tsx) says: "${PRIVACY_SENTENCE}" A change that reads a signal changes that sentence, and its pin below, in the same PR.`,
    ).toEqual([])
  }, 30_000)

  it("/privacy's sentence on the banner and Do Not Track, pinned beside the scan both ways", () => {
    // A self-check on planted pages: the founder's sentence passes alone, and fails with a second promise on a
    // signal beside it (main's old sentence, a draft's), or with the old sentence in its place.
    const OLD = 'We respect the "Do Not Track" browser setting and will not track users who have enabled it.'
    const pins = (text: string) => {
      const { sentence, mentions } = signalCopy(text)
      return sentence && mentions.length === 1
    }
    const planted: Array<[string, string, boolean]> = [
      ["the founder's sentence alone", `Cookies. ${PRIVACY_SENTENCE}`, true],
      ["main's old promise beside it", `${PRIVACY_SENTENCE} ${OLD}`, false],
      ["a draft's promise beside it", `${PRIVACY_SENTENCE} A browser "Do Not Track" signal sets PostHog analytics and session recording off.`, false],
      ['a Global Privacy Control promise beside it', `${PRIVACY_SENTENCE} We honour Global Privacy Control (GPC) signals.`, false],
      ['the old promise in its place', `Cookies. ${OLD}`, false],
    ]
    expect(planted.map(([form, text]) => [form, pins(text)])).toEqual(planted.map(([form, , pinned]) => [form, pinned]))

    const { container } = render(<PrivacyPage />)
    expect(
      signalCopy((container.textContent ?? '').replace(/\s+/g, ' ')),
      "/privacy's sentence on the banner and Do Not Track changed, or the page names a browser privacy signal beside it. The no-reader scan above holds the code to it (D-049): change the two together, in the same PR.",
    ).toEqual({ sentence: true, mentions: ['Do Not Track'] })
  })

  it('CookieConsent.tsx is the one reader of the stored choice, so every consent reader takes it through getCookiePreferences()', () => {
    expect(scan().filter(([, { storedChoice }]) => storedChoice > 0).map(([rel]) => rel)).toEqual(['components/CookieConsent.tsx'])
  }, 30_000)
})
