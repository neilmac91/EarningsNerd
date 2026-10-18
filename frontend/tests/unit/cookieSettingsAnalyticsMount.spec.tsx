import { useEffect, useState } from 'react'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CookieConsent, { type CookiePreferences } from '@/components/CookieConsent'
import Footer from '@/components/Footer'
import { PostHogProvider } from '@/app/posthog-provider'

/**
 * A first allow from the footer's Cookie settings (D-046) starts PostHog on a page the visitor is already using, so
 * the provider's tree must not change shape when the SDK loads: the page keeps its state (a draft) and the control
 * gets its focus back. The real provider runs here with posthog-js/react's own provider and a stand-in SDK, whose
 * `loaded` callback comes back in the same call as init or on a later task, as a network load does.
 */

const sdk = vi.hoisted(() => ({
  mode: 'sync' as 'sync' | 'deferred',
  client: {
    __loaded: false,
    init: (() => undefined) as (key: string, options: { loaded?: (client: unknown) => void }) => void,
    capture: () => undefined,
    opt_in_capturing: () => undefined,
    opt_out_capturing: () => undefined,
    startSessionRecording: () => undefined,
    stopSessionRecording: () => undefined,
    debug: () => undefined,
  },
}))
vi.mock('posthog-js', async (original) => ({ ...(await original<object>()), default: sdk.client }))
vi.mock('next/navigation', () => ({ usePathname: () => '/contact', useSearchParams: () => new URLSearchParams() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))

const ESSENTIAL_ONLY: CookiePreferences = { essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }
let mounts = 0

/** A page that holds what the visitor typed, as the contact form does, and counts its own mounts. */
function DraftPage() {
  const [draft, setDraft] = useState('')
  useEffect(() => {
    mounts += 1
  }, [])
  return (
    <label>
      Message
      <textarea value={draft} onChange={(event) => setDraft(event.target.value)} />
    </label>
  )
}

describe('a first allow from the footer keeps the page mounted while PostHog starts (D-046)', () => {
  beforeEach(() => {
    mounts = 0
    localStorage.clear()
    localStorage.setItem('cookie_consent', JSON.stringify(ESSENTIAL_ONLY))
    vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', 'phc_synthetic_project')
    sdk.client.__loaded = false
    sdk.client.init = vi.fn((_key, options) => {
      const load = () => {
        sdk.client.__loaded = true
        options.loaded?.(sdk.client)
      }
      if (sdk.mode === 'sync') load()
      else setTimeout(load, 0)
    })
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    localStorage.clear()
  })

  it.each(['sync', 'deferred'] as const)('keeps the draft and returns focus to Cookie settings when the SDK loads (%s)', async (mode) => {
    sdk.mode = mode
    const user = userEvent.setup()
    render(
      <PostHogProvider>
        <DraftPage />
        <Footer />
        <CookieConsent />
      </PostHogProvider>,
    )
    expect(sdk.client.init).not.toHaveBeenCalled()

    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'A question about the 10-K')
    await user.click(screen.getByRole('button', { name: 'Cookie settings' }))
    const dialog = screen.getByRole('dialog', { name: 'Cookie preferences' })
    await user.click(within(dialog).getByRole('checkbox', { name: 'Analytics cookies' }))
    await user.click(within(dialog).getByRole('button', { name: 'Save preferences' }))

    await waitFor(() => expect(sdk.client.init).toHaveBeenCalledTimes(1))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    expect(sdk.client.__loaded).toBe(true)

    expect(screen.getByRole('textbox', { name: 'Message' })).toHaveValue('A question about the 10-K')
    expect(screen.getByRole('button', { name: 'Cookie settings' })).toHaveFocus()
    expect(mounts).toBe(1)
  })
})
