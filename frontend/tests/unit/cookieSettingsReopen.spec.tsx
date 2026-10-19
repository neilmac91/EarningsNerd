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
 * No app module reads a signal. The no-reader scan reads every module the app runs (appModules) for each name
 * a signal is read by, as code: Do Not Track on navigator or window (`doNotTrack`, and `msDoNotTrack` in Internet
 * Explorer), Global Privacy Control (`globalPrivacyControl`), the `DNT` and `Sec-GPC` request headers by name,
 * without case, as a string, a Node request's property or a pattern, in middleware, a route handler, a server
 * component or a routing rule, and PostHog's `respect_dnt`, which has the SDK read Do Not Track itself. A comment and
 * copy that name a signal are not reads. /privacy's sentence, in the founder's words, is pinned beside the scan, so
 * the two move together: a change that reads a signal fails the scan, whose message says /privacy's sentence changes
 * in the same PR, and a change to the sentence fails the pin. The planted forms score the reach. Out of reach,
 * planted as a gap: a name assembled at run time. Outside the scan: the API (backend/, another stack), review-checked.
 */

const STORAGE_KEY = 'cookie_consent'
const CHOSEN: CookiePreferences = { essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }
/** /privacy's sentence on the banner and Do Not Track, as the founder approved it (D-049). */
const PRIVACY_SENTENCE =
  "Analytics and session recording stay off until you allow them, and you can change your choice at any time in Cookie settings. We don't change this based on your browser's Do Not Track setting."

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

/** Every module the app runs, from git's own list (tracked and new files, ignored ones left out): each JavaScript or
 *  TypeScript module under frontend/ (app, components, features, hooks, lib, the root-level modules Next loads, and
 *  any directory added later) and vercel.json, whose routing rules can match a request header. */
const appModules = () =>
  execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], { cwd: FRONTEND, encoding: 'utf8' })
    .split('\0')
    .filter((rel) => (/\.[mc]?[jt]sx?$/.test(rel) || rel === 'vercel.json') && !NOT_APP.test(rel) && existsSync(path.join(FRONTEND, rel)))

/** The names a browser privacy signal is read by, matched without case (a header's name is case-insensitive). */
const SIGNAL_NAMES = new Set(['donottrack', 'msdonottrack', 'globalprivacycontrol', 'dnt', 'sec-gpc', 'respect_dnt'])
/** The same names inside a regular expression's pattern, a header matched by pattern (`/^sec-gpc$/i`). */
const SIGNAL_IN_PATTERN = /donottrack|globalprivacycontrol|respect_dnt|sec-gpc|(?<![a-z0-9_])dnt(?![a-z0-9_])/

/** What a module's code reads of a browser privacy signal: an identifier or a string that is one of the names, or a
 *  regular expression whose pattern names one. Comments, JSX text and a sentence of copy are not reads. */
function signalReads(fileName: string, text: string): string[] {
  const kind = fileName.endsWith('.json')
    ? ts.ScriptKind.JSON
    : /\.[jt]sx$/.test(fileName)
      ? ts.ScriptKind.TSX
      : /\.[mc]?js$/.test(fileName)
        ? ts.ScriptKind.JS
        : ts.ScriptKind.TS
  const source = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, kind)
  const found: string[] = []
  const visit = (node: ts.Node) => {
    if ((ts.isIdentifier(node) || ts.isStringLiteralLike(node)) && SIGNAL_NAMES.has(node.text.toLowerCase())) found.push(node.text)
    if (ts.isRegularExpressionLiteral(node)) {
      // The pattern between the slashes, a letter escape (`\b`) read as a gap and any other backslash dropped.
      const pattern = node.text.slice(1, node.text.lastIndexOf('/')).replace(/\\[a-z]/gi, ' ').replace(/\\/g, '').toLowerCase()
      if (SIGNAL_IN_PATTERN.test(pattern)) found.push(node.text)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

/** What a module's code reads of the stored choice: its storage key, as a string. */
function storedChoiceReads(fileName: string, text: string): number {
  const source = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, /\.[jt]sx$/.test(fileName) ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  let reads = 0
  const visit = (node: ts.Node) => {
    if (ts.isStringLiteralLike(node) && node.text === STORAGE_KEY) reads += 1
    ts.forEachChild(node, visit)
  }
  visit(source)
  return reads
}

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
    // [the form, the module it is planted in, its code, the names the scan reads]
    const planted: Array<[string, string, string, string[]]> = [
      ['Do Not Track on navigator', 'probe.tsx', "if (navigator.doNotTrack === '1') stop()", ['doNotTrack']],
      ['Do Not Track on window, by its string', 'probe.tsx', "const legacy = 'doNotTrack' in window", ['doNotTrack']],
      ["Internet Explorer's Do Not Track", 'probe.tsx', "const ie = navigator.msDoNotTrack === '1'", ['msDoNotTrack']],
      ['Global Privacy Control', 'probe.tsx', 'if (navigator.globalPrivacyControl) stop()', ['globalPrivacyControl']],
      ['the DNT header in middleware', 'middleware.ts', "if (request.headers.get('DNT') === '1') return NextResponse.next()", ['DNT']],
      ['the Sec-GPC header in a server component', 'page.tsx', "const gpc = (await headers()).get('sec-gpc')", ['sec-gpc']],
      ['the Sec-GPC header matched by pattern', 'route.ts', 'request.headers.forEach((_v, name) => { if (/^Sec-GPC$/i.test(name)) stop() })', ['/^Sec-GPC$/i']],
      ["the DNT header as a Node request's property", 'handler.js', 'const sent = req.headers.dnt', ['dnt']],
      ['the DNT header in a routing rule', 'vercel.json', '{ "rewrites": [{ "source": "/(.*)", "has": [{ "type": "header", "key": "DNT" }], "destination": "/" }] }', ['DNT']],
      ['the Sec-GPC header in a routing rule', 'next.config.js', "module.exports = { rewrites: async () => [{ source: '/:path*', has: [{ type: 'header', key: 'Sec-GPC' }], destination: '/' }] }", ['Sec-GPC']],
      ['PostHog told to read Do Not Track', 'probe.tsx', 'posthog.init(key, { respect_dnt: true })', ['respect_dnt']],
      ['a comment that names the signals', 'probe.tsx', '// navigator.doNotTrack, navigator.globalPrivacyControl and the DNT and Sec-GPC headers, named in a comment', []],
      ['copy that names them', 'probe.tsx', "const note = \"Your browser's Do Not Track (DNT) and Global Privacy Control (Sec-GPC) change nothing here.\"", []],
      ['JSX copy that names one', 'probe.tsx', "const copy = <p>We don't change this based on your browser's Do Not Track setting.</p>", []],
      // Out of reach: the scan reads a name written whole, as Tailwind classes are written; one assembled at run time
      // is review-checked.
      ['a gap: a name assembled at run time', 'route.ts', "const gpc = request.headers.get(['sec', 'gpc'].join('-'))", []],
    ]
    expect(planted.map(([form, file, code]) => [form, signalReads(file, code)])).toEqual(planted.map(([form, , , names]) => [form, names]))
  })

  it('no app module reads one', () => {
    const modules = appModules()
    expect(modules.length).toBeGreaterThan(350)
    expect(modules).toEqual(
      expect.arrayContaining([
        'components/CookieConsent.tsx',
        'app/posthog-provider.tsx',
        'lib/analytics.ts',
        'instrumentation-client.ts',
        'instrumentation.ts',
        'middleware.ts',
        'next.config.js',
        'vercel.json',
      ]),
    )
    const reads = modules.flatMap((rel) => {
      const text = readFileSync(path.join(FRONTEND, rel), 'utf8')
      if (!/donottrack|globalprivacycontrol|dnt|sec-gpc/i.test(text)) return []
      return signalReads(rel, text).map((name) => `${rel}: ${name}`)
    })
    expect(
      reads,
      `a browser privacy signal is read in app code. The cookie banner is the only analytics control for every visitor (docs/brand/decisions-log.md D-049), and /privacy (app/privacy/page.tsx) says: "${PRIVACY_SENTENCE}" A change that reads a signal changes that sentence, and its pin below, in the same PR.`,
    ).toEqual([])
  })

  it("/privacy's sentence on the banner and Do Not Track, pinned beside the scan", () => {
    const { container } = render(<PrivacyPage />)
    expect(
      (container.textContent ?? '').replace(/\s+/g, ' '),
      "/privacy's sentence on the banner and Do Not Track changed. The no-reader scan above holds the code to it (D-049): change the two together, in the same PR.",
    ).toContain(PRIVACY_SENTENCE)
  })

  it('CookieConsent.tsx is the one reader of the stored choice, so every consent reader takes it through getCookiePreferences()', () => {
    const readers = appModules().filter((rel) => {
      const text = readFileSync(path.join(FRONTEND, rel), 'utf8')
      return text.includes(STORAGE_KEY) && storedChoiceReads(rel, text) > 0
    })
    expect(readers).toEqual(['components/CookieConsent.tsx'])
    // Self-check: the key read as code counts; the key named in a comment does not.
    expect(storedChoiceReads('probe.tsx', "const raw = localStorage.getItem('cookie_consent') // the cookie_consent key")).toBe(1)
  })
})
