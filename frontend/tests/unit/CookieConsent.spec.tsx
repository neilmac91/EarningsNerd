import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CookieConsent, { type CookiePreferences } from '@/components/CookieConsent'

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
    return { user, onPreferencesChanged, customize, dialog: screen.getByRole('dialog', { name: 'Cookie Preferences' }) }
  }

  it('opens a labelled modal dialog with named category switches, and focus moves inside it', async () => {
    const { dialog } = await openSettings()
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    expect(screen.getByText('We value your privacy')).toBeInTheDocument() // the banner stays beneath it
    expect(screen.getByRole('checkbox', { name: 'Essential Cookies' })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: 'Analytics Cookies' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Session Recording' })).not.toBeChecked()
  })

  it('Save Preferences stores the choices, fires cookieConsentChanged and calls onPreferencesChanged', async () => {
    const { user, onPreferencesChanged } = await openSettings()
    await user.click(screen.getByRole('checkbox', { name: 'Analytics Cookies' }))
    await user.click(screen.getByRole('button', { name: 'Save Preferences' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText('We value your privacy')).not.toBeInTheDocument() // Save dismisses both
    expect(stored()).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
    expect(consentEvents).toHaveLength(1)
    expect(consentEvents[0]).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
    expect(onPreferencesChanged).toHaveBeenCalledTimes(1)
    expect(onPreferencesChanged).toHaveBeenCalledWith(
      expect.objectContaining({ essential: true, analytics: true, sessionRecording: false }),
    )
    expect(screen.getByText('Cookie preferences saved')).toBeInTheDocument()
  })

  it.each([
    ['Escape', async (user: ReturnType<typeof userEvent.setup>) => user.keyboard('{Escape}')],
    ['Cancel', async (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole('button', { name: 'Cancel' }))],
    ['the ✕', async (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole('button', { name: 'Close' }))],
  ])('%s closes without saving anything and returns focus to Customize on the banner', async (_how, close) => {
    const { user, onPreferencesChanged, customize } = await openSettings()
    await user.click(screen.getByRole('checkbox', { name: 'Analytics Cookies' }))
    await close(user)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('We value your privacy')).toBeInTheDocument()
    expect(document.activeElement).toBe(customize)
    expect(stored()).toBeNull()
    expect(consentEvents).toHaveLength(0)
    expect(onPreferencesChanged).not.toHaveBeenCalled()
    expect(document.body.style.overflow).toBe('')

    // The dismissed edit does not come back on the next open, and a Save there stores the saved choices.
    await user.click(customize)
    expect(screen.getByRole('checkbox', { name: 'Analytics Cookies' })).not.toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Save Preferences' }))
    expect(stored()).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
  })

  it('the banner handlers are unchanged: Accept All opts into analytics only, Reject All into neither', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<CookieConsent />)
    await user.click(await screen.findByRole('button', { name: 'Accept All' }))
    expect(stored()).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
    unmount()

    localStorage.clear()
    render(<CookieConsent />)
    await user.click(await screen.findByRole('button', { name: 'Reject All' }))
    expect(stored()).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
    expect(consentEvents.map((e) => e.analytics)).toEqual([true, false])
  })
})
