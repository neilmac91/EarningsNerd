import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CookieConsent from '@/components/CookieConsent'
import FilingWorkspace from '@/features/filings/components/copilot/FilingWorkspace'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'
import { useConsentLayer } from '@/hooks/useConsentLayer'
import {
  BOTTOM_CHROME_OFFSET,
  CONSENT_INSET_PROPERTY,
  CONSENT_LAYER_EVENT,
  CONSENT_VISIBLE_ATTRIBUTE,
  publishConsentLayer,
  type ConsentLayerDetail,
} from '@/lib/consentLayer'

/**
 * EN-02: the cookie-consent bar sits BENEATH the research chrome (z-consent) and, while mounted,
 * publishes its height as `--consent-inset` + `data-consent-visible` on <html>; the bottom chrome
 * adds that inset to its offset and FilingWorkspace keeps the first-run coachmark quiet. These cases
 * pin the publish / clear contract on every state transition (fresh storage, a choice, the settings
 * dialog opened and dismissed, stored preferences, Do Not Track), the hook, and the coachmark
 * deferral. Geometry (that nothing overlaps in a real viewport) is tests/e2e/consent-bar-yields.spec.ts.
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))

const root = () => document.documentElement
const inset = () => root().style.getPropertyValue(CONSENT_INSET_PROPERTY)
const layerVisible = () => root().hasAttribute(CONSENT_VISIBLE_ATTRIBUTE)
const COACH_KEY = 'en:copilot-coachmark-v1'
const COACH_TEXT = 'New: ask this filing anything'

describe('lib/consentLayer', () => {
  afterEach(() => publishConsentLayer(null))

  it('publishes the bar height as a CSS inset + attribute, dispatches the event, and clears both', () => {
    const seen: ConsentLayerDetail[] = []
    const onEvent = (e: Event) => seen.push((e as CustomEvent<ConsentLayerDetail>).detail)
    window.addEventListener(CONSENT_LAYER_EVENT, onEvent)
    publishConsentLayer(96.4)
    expect(inset()).toBe('97px') // ceil: the chrome never overlaps by a sub-pixel
    expect(layerVisible()).toBe(true)
    publishConsentLayer(null)
    expect(inset()).toBe('')
    expect(layerVisible()).toBe(false)
    window.removeEventListener(CONSENT_LAYER_EVENT, onEvent)
    expect(seen).toEqual([
      { visible: true, height: 96.4 },
      { visible: false, height: 0 },
    ])
  })

  it('the shared bottom offset keeps the safe-area gap and adds the inset', () => {
    expect(BOTTOM_CHROME_OFFSET).toContain('env(safe-area-inset-bottom)')
    expect(BOTTOM_CHROME_OFFSET).toContain(`var(${CONSENT_INSET_PROPERTY}, 0px)`)
    expect(BOTTOM_CHROME_OFFSET.startsWith('calc(')).toBe(true)
  })

  it('useConsentLayer follows the layer', () => {
    function Probe() {
      return <output>{String(useConsentLayer())}</output>
    }
    render(<Probe />)
    expect(screen.getByRole('status')).toHaveTextContent('false')
    act(() => publishConsentLayer(120))
    expect(screen.getByRole('status')).toHaveTextContent('true')
    act(() => publishConsentLayer(null))
    expect(screen.getByRole('status')).toHaveTextContent('false')
  })
})

describe('CookieConsent owns the consent layer', () => {
  let consentEvents: number
  const count = () => (consentEvents += 1)
  beforeEach(() => {
    localStorage.clear()
    consentEvents = 0
    window.addEventListener('cookieConsentChanged', count)
  })
  afterEach(() => {
    window.removeEventListener('cookieConsentChanged', count)
    localStorage.clear()
    publishConsentLayer(null)
  })

  it('fresh storage: the bar is a named region on the consent layer; a choice clears the layer and persists exactly as before', async () => {
    const user = userEvent.setup()
    render(<CookieConsent />)
    const bar = await screen.findByRole('region', { name: 'Cookie consent' })
    expect(bar).toBeInTheDocument()
    expect(layerVisible()).toBe(true)
    expect(inset()).toMatch(/^\d+px$/) // jsdom measures 0; the attribute, not the number, is the contract here
    expect(consentEvents).toBe(0) // nothing is accepted by the layout

    await user.click(screen.getByRole('button', { name: 'Accept All' }))
    expect(screen.queryByRole('region', { name: 'Cookie consent' })).not.toBeInTheDocument()
    expect(layerVisible()).toBe(false)
    expect(inset()).toBe('')
    expect(JSON.parse(localStorage.getItem('cookie_consent') as string)).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
    expect(consentEvents).toBe(1)
  })

  it('the settings dialog leaves the bar (and its layer) mounted; Cancel keeps it, Save clears it', async () => {
    const user = userEvent.setup()
    render(<CookieConsent />)
    await user.click(await screen.findByRole('button', { name: 'Customize' }))
    expect(screen.getByRole('dialog', { name: 'Cookie Preferences' })).toBeInTheDocument()
    expect(layerVisible()).toBe(true) // inert under the modal, still laid out beneath it
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(layerVisible()).toBe(true)
    expect(screen.getByRole('button', { name: 'Customize' })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Customize' }))
    await user.click(screen.getByRole('button', { name: 'Save Preferences' }))
    expect(layerVisible()).toBe(false)
    expect(inset()).toBe('')
    expect(consentEvents).toBe(1)
  })

  it('stored preferences: no bar, no layer, no event', async () => {
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: 'x' }))
    render(<CookieConsent />)
    await act(async () => {})
    expect(screen.queryByRole('region', { name: 'Cookie consent' })).not.toBeInTheDocument()
    expect(layerVisible()).toBe(false)
    expect(inset()).toBe('')
    expect(consentEvents).toBe(0)
  })

  it('Do Not Track: defaults are saved silently (as before) and no layer is published', async () => {
    // jsdom's navigator has no doNotTrack; define the non-standard property the component reads.
    Object.defineProperty(navigator, 'doNotTrack', { value: '1', configurable: true })
    try {
      render(<CookieConsent />)
      await act(async () => {})
      expect(screen.queryByRole('region', { name: 'Cookie consent' })).not.toBeInTheDocument()
      expect(layerVisible()).toBe(false)
      expect(JSON.parse(localStorage.getItem('cookie_consent') as string)).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
      expect(consentEvents).toBe(1)
    } finally {
      delete (navigator as { doNotTrack?: string }).doNotTrack
    }
  })
})

describe('FilingWorkspace defers the coachmark while the consent bar is visible', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => publishConsentLayer(null))

  const renderClosed = () =>
    render(
      <FilingViewerProvider>
        <FilingWorkspace
          open={false}
          onOpenChange={vi.fn()}
          summaryAvailable
          secUrl="https://sec.gov/x"
          copilotBody={<div>copilot</div>}
          filingBody={<div>filing</div>}
        >
          <div>summary</div>
        </FilingWorkspace>
      </FilingViewerProvider>,
    )

  it('no coachmark while the bar is up; it appears, pointing at the visible launcher, once the bar is gone', () => {
    publishConsentLayer(97)
    renderClosed()
    expect(screen.getByRole('button', { name: 'Ask this Filing' })).toBeInTheDocument()
    expect(screen.queryByText(COACH_TEXT)).not.toBeInTheDocument()
    act(() => publishConsentLayer(null))
    expect(screen.getByText(COACH_TEXT)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask this Filing' })).toBeInTheDocument()
    expect(localStorage.getItem(COACH_KEY)).toBeNull() // deferred, not dismissed
  })

  it('a bar that appears after mount hides a showing coachmark without dismissing it', () => {
    renderClosed()
    expect(screen.getByText(COACH_TEXT)).toBeInTheDocument()
    act(() => publishConsentLayer(97))
    expect(screen.queryByText(COACH_TEXT)).not.toBeInTheDocument()
    expect(localStorage.getItem(COACH_KEY)).toBeNull()
    act(() => publishConsentLayer(null))
    expect(screen.getByText(COACH_TEXT)).toBeInTheDocument()
  })

  it('a coachmark the user dismissed does not nag again when the bar goes', async () => {
    const user = userEvent.setup()
    renderClosed()
    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(localStorage.getItem(COACH_KEY)).toBe('1')
    act(() => publishConsentLayer(97))
    act(() => publishConsentLayer(null))
    expect(screen.queryByText(COACH_TEXT)).not.toBeInTheDocument()
  })
})
