import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CookieConsent, { type CookiePreferences } from '@/components/CookieConsent'
import Footer from '@/components/Footer'
import { PostHogProvider } from '@/app/posthog-provider'
import { usePostHogUserIdentification } from '@/hooks/usePostHogUserIdentification'
import { queryKeys } from '@/lib/queryKeys'

/**
 * A first allow from the footer's Cookie settings starts PostHog on a page the visitor is already using, so
 * the provider's tree must not change shape when the SDK loads: the page keeps its state (a draft) and the control
 * gets its focus back. With no remount, a reader already signed in is identified because identification waits on
 * PostHog being ready (lib/posthogReady.ts), not on a fresh mount. The real provider and identification hook run here
 * with posthog-js/react's own provider and a stand-in SDK, whose `loaded` callback comes back in the same call as
 * init or only when the case lets the load finish, as a network load can take its time.
 */

const sdk = vi.hoisted(() => ({
  mode: 'sync' as 'sync' | 'deferred',
  finishLoad: undefined as (() => void) | undefined,
  client: {
    __loaded: false,
    init: (() => undefined) as (key: string, options: { loaded?: (client: unknown) => void }) => void,
    capture: () => undefined,
    opt_in_capturing: () => undefined,
    opt_out_capturing: () => undefined,
    startSessionRecording: () => undefined,
    stopSessionRecording: () => undefined,
    debug: () => undefined,
    identify: (() => undefined) as (id: string, traits?: Record<string, unknown>) => void,
  },
}))
vi.mock('posthog-js', async (original) => ({ ...(await original<object>()), default: sdk.client }))
vi.mock('next/navigation', () => ({ usePathname: () => '/contact', useSearchParams: () => new URLSearchParams() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
// A reader signed in on Pro, whose account and plan resolve while analytics is still off.
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => ({ id: 7, email: 'reader@example.test', is_pro: true }) }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getSubscriptionStatus: async () => ({ is_pro: true }) }))

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

describe('a first allow from the footer keeps the page mounted while PostHog starts', () => {
  beforeEach(() => {
    mounts = 0
    localStorage.clear()
    localStorage.setItem('cookie_consent', JSON.stringify(ESSENTIAL_ONLY))
    vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', 'phc_synthetic_project')
    sdk.client.__loaded = false
    sdk.finishLoad = undefined
    sdk.client.identify = vi.fn()
    sdk.client.init = vi.fn((_key, options) => {
      const load = () => {
        sdk.client.__loaded = true
        options.loaded?.(sdk.client)
      }
      if (sdk.mode === 'sync') load()
      else sdk.finishLoad = load
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
      sdk.finishLoad?.()
    })
    expect(sdk.client.__loaded).toBe(true)

    expect(screen.getByRole('textbox', { name: 'Message' })).toHaveValue('A question about the 10-K')
    expect(screen.getByRole('button', { name: 'Cookie settings' })).toHaveFocus()
    expect(mounts).toBe(1)
  })

  // The app mounts the hook inside the provider and React Query (app/providers.tsx' UserIdentificationSync).
  function IdentificationSync() {
    usePostHogUserIdentification()
    return null
  }

  it.each(['sync', 'deferred'] as const)('identifies a reader already signed in once the SDK is ready, never before consent (%s)', async (mode) => {
    sdk.mode = mode
    const user = userEvent.setup()
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queries}>
        <PostHogProvider>
          <IdentificationSync />
          <Footer />
          <CookieConsent />
        </PostHogProvider>
      </QueryClientProvider>,
    )
    // The account and its plan resolve while analytics is off: nobody is identified.
    await waitFor(() => {
      expect(queries.getQueryState(queryKeys.currentUser())?.status).toBe('success')
      expect(queries.getQueryState(queryKeys.subscription.byUser(7))?.status).toBe('success')
    })
    expect(sdk.client.identify).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Cookie settings' }))
    const dialog = screen.getByRole('dialog', { name: 'Cookie preferences' })
    await user.click(within(dialog).getByRole('checkbox', { name: 'Analytics cookies' }))
    await user.click(within(dialog).getByRole('button', { name: 'Save preferences' }))
    await waitFor(() => expect(sdk.client.init).toHaveBeenCalledTimes(1))
    // Until the SDK has loaded, nothing is identified, however long its load takes.
    if (mode === 'deferred') expect(sdk.client.identify).not.toHaveBeenCalled()

    await act(async () => {
      sdk.finishLoad?.()
    })
    expect(sdk.client.__loaded).toBe(true)
    await waitFor(() => expect(sdk.client.identify).toHaveBeenCalledTimes(1))
    expect(sdk.client.identify).toHaveBeenCalledWith('7', { is_pro: true, plan: 'pro' })
  })
})
