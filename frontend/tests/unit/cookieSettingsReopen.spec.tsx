import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CookieConsent, { type CookiePreferences } from '@/components/CookieConsent'
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
 */

const STORAGE_KEY = 'cookie_consent'
const CHOSEN: CookiePreferences = { essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }

const stored = (): CookiePreferences | null => {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? (JSON.parse(raw) as CookiePreferences) : null
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
})
