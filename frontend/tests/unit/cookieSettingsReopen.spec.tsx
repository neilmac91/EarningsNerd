import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ts from 'typescript'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CookieConsent, {
  browserSendsDoNotTrack,
  getCookiePreferences,
  saveCookiePreferences,
  type CookiePreferences,
} from '@/components/CookieConsent'
import Footer from '@/components/Footer'

vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))

/**
 * The footer's "Cookie settings" reopens the consent dialog after a first choice (D-046). /privacy says consent can
 * be withdrawn "through our cookie consent banner or settings", and the bar shows only until a visitor chooses. With
 * a choice stored the bar stays hidden; the footer's control opens CookieConsent's own dialog on the stored toggles,
 * not the defaults; Save writes the new choice and fires cookieConsentChanged, as the bar's Save does (so PostHog
 * follows it); and focus comes back to the control however the dialog closes. The control's brand ring is held by
 * siteChromeFocusRing.spec.ts, which scans the footer.
 *
 * Do Not Track wins while the browser sends it (D-046): /privacy says "We respect the 'Do Not Track' browser setting
 * and will not track users who have enabled it", and the footer's control reaches every visitor. The rule sits at
 * the two consent functions, so every reader follows it: getCookiePreferences() reads analytics and session
 * recording as off (storage keeps what was written, so the visitor's own choice is back once the browser stops
 * sending it), saveCookiePreferences() writes them off, and the dialog shows both boxes unticked and disabled under a
 * note that says why. browserSendsDoNotTrack() is the one reader of the signal and CookieConsent.tsx the one reader
 * of the stored choice, so no module can step around the rule.
 */

const STORAGE_KEY = 'cookie_consent'
const CHOSEN: CookiePreferences = { essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }
const DNT_NOTE = 'Your browser sends Do Not Track, so analytics and session recording stay off.'

const stored = (): CookiePreferences | null => {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? (JSON.parse(raw) as CookiePreferences) : null
}

/** A category box's own description, as its paragraph reads (whitespace collapsed, as the computed description is). */
const ownDescription = (id: string) => (document.getElementById(id)?.textContent ?? '').replace(/\s+/g, ' ').trim()

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const APP_ROOTS = ['app', 'components', 'features', 'hooks', 'lib']

const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name)
    if (statSync(full).isDirectory()) return walk(full)
    return /\.tsx?$/.test(name) ? [full] : []
  })

/** What a module's code reads of the rule's inputs: Do Not Track by any spelling, or the stored choice's key.
 *  An identifier or a string, so a comment or a sentence of copy that names either is not a read. */
function consentInputsRead(fileName: string, text: string): string[] {
  const kind = fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const source = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, kind)
  const found: string[] = []
  const visit = (node: ts.Node) => {
    const name = ts.isIdentifier(node) || ts.isStringLiteralLike(node) ? node.text : null
    if (name === 'doNotTrack' || name === STORAGE_KEY) found.push(name)
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

describe("the footer's Cookie settings reopens the consent dialog after a choice (D-046)", () => {
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

  describe('while the browser sends Do Not Track, analytics and session recording stay off (D-046)', () => {
    // jsdom reports no Do Not Track; a case defines it where a browser would, and every case ends with it gone.
    const sendDoNotTrack = (on: Navigator | Window = navigator, value: string | null = '1') =>
      Object.defineProperty(on, 'doNotTrack', { value, configurable: true })
    const stopDoNotTrack = () => {
      delete (navigator as { doNotTrack?: string | null }).doNotTrack
      delete (window as { doNotTrack?: string | null }).doNotTrack
    }
    afterEach(stopDoNotTrack)

    it('the footer opens the dialog with both boxes unticked and disabled, each described by its own text and the note', async () => {
      sendDoNotTrack()
      const { user, control } = renderChrome()
      await user.click(control)
      const dialog = screen.getByRole('dialog', { name: 'Cookie preferences' })
      expect(within(dialog).getByText(DNT_NOTE)).toBeInTheDocument()

      for (const [name, descId] of [['Analytics cookies', 'cookie-analytics-desc'], ['Session recording', 'cookie-recording-desc']]) {
        const box = within(dialog).getByRole('checkbox', { name })
        expect(box).not.toBeChecked()
        expect(box).toBeDisabled()
        expect(box).toHaveAccessibleDescription(`${ownDescription(descId)} ${DNT_NOTE}`)
      }
    })

    it.each([
      ['navigator.doNotTrack', () => navigator],
      ['window.doNotTrack', () => window],
    ])('a stored allow reads back as off through %s, storage untouched, and as stored once the browser stops', (_where, on) => {
      const allowed: CookiePreferences = { ...CHOSEN, sessionRecording: true }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(allowed))
      sendDoNotTrack(on())

      expect(browserSendsDoNotTrack()).toBe(true)
      expect(getCookiePreferences()).toEqual({ ...allowed, analytics: false, sessionRecording: false })
      expect(stored()).toEqual(allowed)

      stopDoNotTrack()
      expect(getCookiePreferences()).toEqual(allowed)
    })

    it.each(['0', 'unspecified', null])('a browser reporting %s does not send it: the stored choice reads back as written', (value) => {
      sendDoNotTrack(navigator, value)
      expect(browserSendsDoNotTrack()).toBe(false)
      expect(getCookiePreferences()).toEqual(CHOSEN)
    })

    it('a save writes analytics and session recording off, and the cookieConsentChanged detail carries off', () => {
      sendDoNotTrack()
      saveCookiePreferences({ essential: true, analytics: true, sessionRecording: true, timestamp: 'x' })

      expect(stored()).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
      expect(consentEvents).toEqual([expect.objectContaining({ essential: true, analytics: false, sessionRecording: false })])
    })

    it("the dialog's Save stores the choice as off, fires the event with off and returns focus to the control", async () => {
      sendDoNotTrack()
      const { user, control } = renderChrome()
      await user.click(control)
      await user.click(screen.getByRole('button', { name: 'Save preferences' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(stored()).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
      expect(consentEvents).toEqual([expect.objectContaining({ essential: true, analytics: false, sessionRecording: false })])
      expect(control).toHaveFocus()
    })

    it('without it nothing changes: the boxes open enabled on the stored choice, with their own descriptions and no note', async () => {
      const { user, control } = renderChrome()
      expect(browserSendsDoNotTrack()).toBe(false)
      expect(getCookiePreferences()).toEqual(CHOSEN)

      await user.click(control)
      const dialog = screen.getByRole('dialog', { name: 'Cookie preferences' })
      expect(within(dialog).queryByText(DNT_NOTE)).not.toBeInTheDocument()
      const analytics = within(dialog).getByRole('checkbox', { name: 'Analytics cookies' })
      const recording = within(dialog).getByRole('checkbox', { name: 'Session recording' })
      expect(analytics).toBeEnabled()
      expect(analytics).toBeChecked()
      expect(analytics).toHaveAccessibleDescription(ownDescription('cookie-analytics-desc'))
      expect(recording).toBeEnabled()
      expect(recording).not.toBeChecked()
      expect(recording).toHaveAccessibleDescription(ownDescription('cookie-recording-desc'))
    })

    it('browserSendsDoNotTrack is the one reader of the signal, and CookieConsent.tsx the one reader of the stored choice', () => {
      // Self-check: the scan reads code; a comment or a sentence of copy that names either input is not a read.
      const probe = [
        "if (navigator.doNotTrack === '1') stop()",
        "const legacy = 'doNotTrack' in window",
        "const raw = localStorage.getItem('cookie_consent')",
        '// the `cookie_consent` key and navigator.doNotTrack, named in a comment',
        'const copy = <p>Your browser sends Do Not Track</p>',
      ].join('\n')
      expect(consentInputsRead('probe.tsx', probe)).toEqual(['doNotTrack', 'doNotTrack', STORAGE_KEY])

      const readers = APP_ROOTS.flatMap((root) => walk(path.join(FRONTEND, root))).filter((file) => {
        const text = readFileSync(file, 'utf8')
        return /doNotTrack|cookie_consent/.test(text) && consentInputsRead(file, text).length > 0
      })
      expect(readers.map((file) => path.relative(FRONTEND, file).split(path.sep).join('/'))).toEqual(['components/CookieConsent.tsx'])
    })
  })
})
