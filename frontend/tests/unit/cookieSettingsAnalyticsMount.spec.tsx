import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CookieConsent, { CONSENT_VERSION, type CookiePreferences } from '@/components/CookieConsent'
import Footer from '@/components/Footer'
import { GlobalErrorBoundary } from '@/components/GlobalErrorBoundary'
import { PostHogProvider } from '@/app/posthog-provider'
import { usePostHogUserIdentification } from '@/hooks/usePostHogUserIdentification'
import { queryKeys } from '@/lib/queryKeys'

/**
 * A first allow from the footer's Cookie settings starts PostHog on a page the visitor is already using, so
 * the provider's tree must not change shape when the SDK loads: the page keeps its state (a draft) and the control
 * gets its focus back. With no remount, a reader already signed in is identified because identification waits on
 * PostHog being ready (lib/posthogReady.ts), not on a fresh mount. The real provider and identification hook run here
 * with posthog-js/react's own provider and a stand-in SDK, whose `loaded` callback comes back in the same call as
 * init or only when the case lets the load finish, as a network load can take its time. As posthog-js does, the
 * stand-in calls `loaded` once per page: a second init is a no-op.
 *
 * Identification also holds where no allow happens on the page: a returning visitor who allowed analytics on an
 * earlier visit (with a PostHog key, and with none, where the account id still reaches Sentry), and a provider that
 * mounts again after the SDK has loaded (GlobalErrorBoundary's "Try again").
 */

const sdk = vi.hoisted(() => ({
  mode: 'sync' as 'sync' | 'deferred',
  isPro: true,
  setSentryUser: vi.fn(),
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
vi.mock('@sentry/nextjs', async (original) => ({ ...(await original<object>()), setUser: sdk.setSentryUser }))
vi.mock('next/navigation', () => ({ usePathname: () => '/contact', useSearchParams: () => new URLSearchParams() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
// A reader signed in on Pro (Free where a case says so), whose account and plan resolve while analytics is still off.
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => ({ id: 7, email: 'reader@example.test', is_pro: sdk.isPro }) }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getSubscriptionStatus: async () => ({ is_pro: sdk.isPro }) }))

const ESSENTIAL_ONLY: CookiePreferences = { essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }
const ANALYTICS_ALLOWED: CookiePreferences = { essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z', version: CONSENT_VERSION }
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

// The app mounts the hook inside the provider and React Query (app/providers.tsx' UserIdentificationSync).
function IdentificationSync() {
  usePostHogUserIdentification()
  return null
}

// Each case starts from a reader who chose Essential only, a PostHog key and a stand-in SDK that has not loaded.
beforeEach(() => {
  mounts = 0
  localStorage.clear()
  localStorage.setItem('cookie_consent', JSON.stringify(ESSENTIAL_ONLY))
  vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', 'phc_synthetic_project')
  sdk.isPro = true
  sdk.setSentryUser.mockClear()
  sdk.client.__loaded = false
  sdk.finishLoad = undefined
  sdk.client.identify = vi.fn()
  sdk.client.init = vi.fn((_key, options) => {
    if (sdk.client.__loaded) return
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
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('a first allow from the footer keeps the page mounted while PostHog starts', () => {
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

describe('identification holds where no allow happens on the page', () => {
  // Most readers: analytics allowed on an earlier visit, so the provider applies the stored allow as it mounts. With a
  // key the reader is identified once the SDK has loaded; with none there is nothing to load, and identification still
  // runs so the account id reaches Sentry.
  it.each([
    ['with a PostHog key', 'phc_synthetic_project'],
    ['with no PostHog key', ''],
  ] as const)('identifies a returning visitor who already allowed analytics, %s', async (_case, key) => {
    sdk.mode = 'deferred'
    vi.stubEnv('NEXT_PUBLIC_POSTHOG_KEY', key)
    localStorage.setItem('cookie_consent', JSON.stringify(ANALYTICS_ALLOWED))
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queries}>
        <PostHogProvider>
          <IdentificationSync />
        </PostHogProvider>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(queries.getQueryState(queryKeys.subscription.byUser(7))?.status).toBe('success'))

    if (key) {
      expect(sdk.client.init).toHaveBeenCalledTimes(1)
      // Not before the SDK has loaded.
      expect(sdk.client.identify).not.toHaveBeenCalled()
      await act(async () => {
        sdk.finishLoad?.()
      })
    } else {
      expect(sdk.client.init).not.toHaveBeenCalled()
    }
    await waitFor(() => expect(sdk.client.identify).toHaveBeenCalledTimes(1))
    expect(sdk.client.identify).toHaveBeenCalledWith('7', { is_pro: true, plan: 'pro' })
    expect(sdk.setSentryUser).toHaveBeenCalledWith({ id: '7' })
  })

  // GlobalErrorBoundary's "Try again" (app/providers.tsx puts the provider inside it) mounts a fresh provider after
  // PostHog has loaded, and so does a global-error reset. No second `loaded` comes, so the provider takes the SDK's own
  // state: the remounted tree identifies the reader, and a plan change later in the page session reaches PostHog.
  it('identifies again after the provider remounts with PostHog already loaded, and follows a plan change', async () => {
    sdk.mode = 'sync'
    sdk.isPro = false
    localStorage.setItem('cookie_consent', JSON.stringify(ANALYTICS_ALLOWED))
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    function Fragile({ failing }: { failing: boolean }) {
      if (failing) throw new Error('A render error the boundary catches')
      return null
    }
    const user = userEvent.setup()
    // The query client lives outside the boundary, as in app/providers.tsx, so it survives the retry.
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const app = (failing: boolean) => (
      <GlobalErrorBoundary>
        <PostHogProvider>
          <QueryClientProvider client={queries}>
            <Fragile failing={failing} />
            <IdentificationSync />
          </QueryClientProvider>
        </PostHogProvider>
      </GlobalErrorBoundary>
    )
    const { rerender } = render(app(false))
    await waitFor(() => expect(sdk.client.identify).toHaveBeenCalledWith('7', { is_pro: false, plan: 'free' }))
    expect(sdk.client.identify).toHaveBeenCalledTimes(1)

    // React rethrows the render error through a window error event; jsdom reports it unless it is handled.
    const handled = (event: ErrorEvent) => event.preventDefault()
    window.addEventListener('error', handled)
    rerender(app(true))
    window.removeEventListener('error', handled)
    // The boundary keeps its fallback until the reader tries again.
    rerender(app(false))
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(sdk.client.init).toHaveBeenCalledTimes(1)
    // The remounted tree identifies the reader again.
    await waitFor(() => expect(sdk.client.identify).toHaveBeenCalledTimes(2))

    // The reader upgrades later in the same page session.
    act(() => queries.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true }))
    await waitFor(() => expect(sdk.client.identify).toHaveBeenLastCalledWith('7', { is_pro: true, plan: 'pro' }))
  })
})
