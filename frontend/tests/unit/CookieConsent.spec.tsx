import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import CookieConsent, { CONSENT_VERSION, getCookiePreferences, clearCookiePreferences, type CookiePreferences } from '@/components/CookieConsent'
import { buttonVariants } from '@/components/ui'
import { ANALYTICS_CONSENT_CLAUSE } from '@/lib/consentCopy'

// The "Cookie preferences saved" confirmation is a sonner toast (top-centre Toaster in app/providers.tsx)
// since EN-02: it must not share the bottom-right corner with the "Ask this Filing" launcher.
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

/**
 * The cookie settings panel is a ui/Modal dialog (DESIGN_SYSTEM §4, gated by dialogAllowlist.spec.ts).
 * The migration changed the shell: these cases pin that the consent handlers still write the same
 * preferences, fire the same `cookieConsentChanged` event PostHog listens for, and call
 * `onPreferencesChanged` exactly as before — and that Escape, Cancel and the X close without saving.
 * The banner stays mounted beneath the dialog, so those return focus to its Customize button.
 */

const STORAGE_KEY = 'cookie_consent'

function stored(): CookiePreferences | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? (JSON.parse(raw) as CookiePreferences) : null
}

describe('CookieConsent settings dialog', () => {
  let consentEvents: CookiePreferences[]
  const onConsentEvent = (e: Event) => consentEvents.push((e as CustomEvent<CookiePreferences>).detail)

  beforeEach(() => {
    localStorage.clear()
    consentEvents = []
    vi.mocked(toast.success).mockClear()
    window.addEventListener('cookieConsentChanged', onConsentEvent)
  })
  afterEach(() => {
    window.removeEventListener('cookieConsentChanged', onConsentEvent)
    localStorage.clear()
  })

  const openSettings = async (onPreferencesChanged = vi.fn()) => {
    const user = userEvent.setup()
    render(<CookieConsent onPreferencesChanged={onPreferencesChanged} />)
    const customize = await screen.findByRole('button', { name: 'Customize' })
    await user.click(customize)
    return { user, onPreferencesChanged, customize, dialog: screen.getByRole('dialog', { name: 'Cookie preferences' }) }
  }

  it('opens a labelled modal dialog with named category switches, and focus moves inside it', async () => {
    const { dialog } = await openSettings()
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    expect(screen.getByText('Cookies on this site')).toBeInTheDocument() // the banner stays beneath it
    expect(screen.getByRole('checkbox', { name: 'Essential cookies' })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: 'Analytics cookies' })).not.toBeChecked()
    expect(within(dialog).getByText(/Session recording is disabled\./)).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Session recording' })).not.toBeInTheDocument()
    // Checkbox lists its props by name, so each category's description reaches the input only through its
    // aria-describedby forward; a dropped forward would strip these from screen readers.
    expect(screen.getByRole('checkbox', { name: 'Essential cookies' })).toHaveAccessibleDescription(/^Required for the website to function properly\./)
    // D-046 (F33): the clause names PostHog, its purpose and the account link, in the words /privacy also reads.
    expect(screen.getByRole('checkbox', { name: 'Analytics cookies' })).toHaveAccessibleDescription(ANALYTICS_CONSENT_CLAUSE)
  })

  it('Save preferences stores the choices, fires cookieConsentChanged and calls onPreferencesChanged', async () => {
    const { user, onPreferencesChanged } = await openSettings()
    await user.click(screen.getByRole('checkbox', { name: 'Analytics cookies' }))
    await user.click(screen.getByRole('button', { name: 'Save preferences' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText('Cookies on this site')).not.toBeInTheDocument() // Save dismisses both
    expect(stored()).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
    expect(consentEvents).toHaveLength(1)
    expect(consentEvents[0]).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
    expect(onPreferencesChanged).toHaveBeenCalledTimes(1)
    expect(onPreferencesChanged).toHaveBeenCalledWith(
      expect.objectContaining({ essential: true, analytics: true, sessionRecording: false }),
    )
    expect(toast.success).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith('Cookie preferences saved')
  })

  it.each([
    ['Escape', async (user: ReturnType<typeof userEvent.setup>) => user.keyboard('{Escape}')],
    ['Cancel', async (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole('button', { name: 'Cancel' }))],
    ['the ✕', async (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole('button', { name: 'Close' }))],
  ])('%s closes without saving anything and returns focus to Customize on the banner', async (_how, close) => {
    const { user, onPreferencesChanged, customize } = await openSettings()
    await user.click(screen.getByRole('checkbox', { name: 'Analytics cookies' }))
    await close(user)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Cookies on this site')).toBeInTheDocument()
    expect(document.activeElement).toBe(customize)
    expect(stored()).toBeNull()
    expect(consentEvents).toHaveLength(0)
    expect(onPreferencesChanged).not.toHaveBeenCalled()
    expect(document.body.style.overflow).toBe('')

    // The dismissed edit does not come back on the next open, and a Save there stores the saved choices.
    await user.click(customize)
    expect(screen.getByRole('checkbox', { name: 'Analytics cookies' })).not.toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Save preferences' }))
    expect(stored()).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
  })

  it('each bar button names what its handler sets: Allow analytics opts into analytics only, Essential only into neither', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<CookieConsent />)
    // chrome/F2: "Accept All" promised every category while session recording stayed off. The bar
    // offers exactly these three, and no label claims "all".
    const bar = await screen.findByRole('region', { name: 'Cookie consent' })
    const labels = within(bar).getAllByRole('button').map((b) => b.textContent?.trim())
    expect(labels).toEqual(['Customize', 'Essential only', 'Allow analytics'])
    expect(labels.filter((l) => /\ball\b/i.test(l ?? ''))).toEqual([])
    await user.click(await screen.findByRole('button', { name: 'Allow analytics' }))
    expect(stored()).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
    unmount()

    localStorage.clear()
    render(<CookieConsent />)
    await user.click(await screen.findByRole('button', { name: 'Essential only' }))
    expect(stored()).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
    expect(consentEvents.map((e) => e.analytics)).toEqual([true, false])
    expect(toast.success).toHaveBeenCalledTimes(2)
  })

  it('the two choices carry equal weight: Essential only and Allow analytics are both secondary, Customize the ghost', async () => {
    // Refusing must be as easy and as visible as allowing (the EDPB, CNIL and ICO reading of consent): the
    // two choices share one recipe, and the third action, Customize, sits a step below both.
    render(<CookieConsent />)
    const bar = await screen.findByRole('region', { name: 'Cookie consent' })
    const cls = (name: string) => within(bar).getByRole('button', { name }).className
    expect(cls('Essential only')).toBe(buttonVariants({ variant: 'secondary' }))
    expect(cls('Allow analytics')).toBe(buttonVariants({ variant: 'secondary' }))
    expect(cls('Customize')).toBe(buttonVariants({ variant: 'ghost' }))
  })
})

describe('a choice stored before the account-id clause (CONSENT_VERSION)', () => {
  // Until D-046 the dialog called the statistics anonymous; a reader who allowed them then never read the clause they
  // are identified under now. Such an allow reads as no choice, once; a refusal stands, since nothing is collected on it.
  const EARLIER: CookiePreferences = { essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }
  const bar = () => screen.queryByRole('region', { name: 'Cookie consent' })

  beforeEach(() => localStorage.clear())
  afterEach(() => localStorage.clear())

  it('an allow made before it reads as no choice: the bar asks again, the dialog starts unchecked, and the new choice holds', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(EARLIER))
    expect(getCookiePreferences()).toBeNull()
    const onPreferencesChanged = vi.fn()
    const user = userEvent.setup()
    const { unmount } = render(<CookieConsent onPreferencesChanged={onPreferencesChanged} />)
    await user.click(await screen.findByRole('button', { name: 'Customize' }))
    expect(screen.getByRole('checkbox', { name: 'Analytics cookies' })).not.toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onPreferencesChanged).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Allow analytics' }))
    expect(stored()).toMatchObject({ analytics: true, version: CONSENT_VERSION })
    unmount()

    const again = vi.fn()
    render(<CookieConsent onPreferencesChanged={again} />)
    expect(bar()).not.toBeInTheDocument()
    expect(again).toHaveBeenCalledWith(expect.objectContaining({ analytics: true, version: CONSENT_VERSION }))
  })

  it('an allow stored under an earlier version than the current one reads as no choice, so a later bump asks again', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...EARLIER, version: CONSENT_VERSION - 1 }))
    expect(getCookiePreferences()).toBeNull()
  })

  it('a refusal made before it stands: no bar, and the stored choice is read as it is', () => {
    const refused: CookiePreferences = { ...EARLIER, analytics: false }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(refused))
    const onPreferencesChanged = vi.fn()
    render(<CookieConsent onPreferencesChanged={onPreferencesChanged} />)
    expect(bar()).not.toBeInTheDocument()
    expect(onPreferencesChanged).toHaveBeenCalledWith(refused)
  })

  it('an allow made under the current clause holds: no bar, and the stored choice is read as it is', () => {
    const current: CookiePreferences = { ...EARLIER, version: CONSENT_VERSION }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(current))
    expect(getCookiePreferences()).toEqual(current)
    const onPreferencesChanged = vi.fn()
    render(<CookieConsent onPreferencesChanged={onPreferencesChanged} />)
    expect(bar()).not.toBeInTheDocument()
    expect(onPreferencesChanged).toHaveBeenCalledWith(current)
  })
})


describe('a failed preference write is not reported as saved', () => {
  afterEach(() => { vi.restoreAllMocks(); act(() => clearCookiePreferences()) })

  it('withdraws from the footer dialog in memory, shows truthful feedback and reopens on the refused choice', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-23T12:00:00.000Z', version: CONSENT_VERSION }))
    const user = userEvent.setup()
    render(<CookieConsent />)
    const { OPEN_COOKIE_SETTINGS_EVENT } = await import('@/lib/cookieSettings')
    act(() => window.dispatchEvent(new Event(OPEN_COOKIE_SETTINGS_EVENT)))
    await user.click(screen.getByRole('checkbox', { name: 'Analytics cookies' }))
    vi.mocked(toast.success).mockClear()
    vi.mocked(toast.error).mockClear()
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Unavailable') })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new DOMException('Unavailable') })
    await user.click(screen.getByRole('button', { name: 'Save preferences' }))
    expect(getCookiePreferences()?.analytics).toBe(false)
    expect(toast.success).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledWith('Cookie preferences could not be saved', expect.objectContaining({ description: expect.stringContaining('Your choice applies in this tab.') }))
    act(() => window.dispatchEvent(new Event(OPEN_COOKIE_SETTINGS_EVENT)))
    expect(screen.getByRole('checkbox', { name: 'Analytics cookies' })).not.toBeChecked()
  })
})
