import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import type { Mock } from 'vitest'
import LoginPage from '@/app/login/page'
import RegisterForm from '@/features/auth/components/RegisterForm'
import ContactForm from '@/features/contact/components/ContactForm'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import TurnstileWidget from '@/features/auth/components/TurnstileWidget'

/**
 * E152: with Turnstile on, each form waits for its token, and the backend refuses a missing one (it fails open only
 * when siteverify is unreachable). When the browser cannot load Cloudflare's script (a content blocker, a lost
 * connection), the widget now says so in place of the check, with a Try again that loads the script afresh; once it
 * loads, the check renders where the notice was, focus comes there from the Try again, and the token it issues sends.
 * Before, the widget rendered nothing and kept the failed load, so the submit waited with no end and no word why.
 *
 * The real TurnstileWidget runs in each form. Cloudflare's script is the one stand-in: jsdom loads no external
 * script, so a case fires the element's error or load event itself, and a load first puts the Turnstile global in
 * place, as the real script does. The widget's own cases hold the other ways a load fails: a request that stalls
 * (no event at all), a load that brings no Turnstile (a content blocker's empty stand-in), and an offline browser.
 */

vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: 'site-key',
  TURNSTILE_ENABLED: true,
}))
const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  submitContactForm: vi.fn(),
  joinWaitlist: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  login: api.login,
  register: api.register,
  getCurrentUserSafe: async () => ({ id: 1, email: 'reader@example.com' }),
  startOAuthWithInvite: vi.fn(),
}))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: api.submitContactForm }))
vi.mock('@/features/waitlist/api/waitlist-api', () => ({ joinWaitlist: api.joinWaitlist }))
const searchParams = new URLSearchParams()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => searchParams,
}))
vi.mock('@/lib/analytics', () => ({
  default: { loginCompleted: vi.fn(), signupStarted: vi.fn(), signupSubmitted: vi.fn() },
}))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}))
vi.mock('@/features/auth/components/SocialAuthButtons', () => ({ default: () => null }))
// The login page's registration read is answered here, never by the network.
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: async () => null }))

const TITLE = "The security check didn't load"
/** TurnstileWidget's SCRIPT_LOAD_TIMEOUT_MS: how long a load may stall before the widget says it did not load. */
const LOAD_TIMEOUT_MS = 15_000
const SCRIPT = 'script[src^="https://challenges.cloudflare.com/turnstile"]'
const scripts = () => [...document.head.querySelectorAll<HTMLScriptElement>(SCRIPT)]
/** The element of the one load in flight. */
const inFlight = () => {
  const all = scripts()
  expect(all).toHaveLength(1)
  return all[0]
}
/** The browser could not load Cloudflare's script. */
const failLoad = () =>
  act(async () => {
    inFlight().dispatchEvent(new Event('error'))
  })
/** Each widget Cloudflare renders passes its check at once, with a token of its own. */
const cloudflare = { rendered: 0 }
/** Cloudflare's script loads: its global first, as the real script sets it before its load event. */
const loadScript = () =>
  act(async () => {
    window.turnstile = {
      render: vi.fn((_container: HTMLElement, options: Record<string, unknown>) => {
        const widget = ++cloudflare.rendered
        ;(options.callback as (token: string) => void)(`token-${widget}`)
        return `widget-${widget}`
      }),
      reset: vi.fn(),
      remove: vi.fn(),
    }
    inFlight().dispatchEvent(new Event('load'))
  })
const notice = () => screen.queryByText(TITLE)?.closest<HTMLElement>('[role="alert"]') ?? null
/** The notice, once the failed load reaches the widget: a query's observers hear of it on a later tick. */
const noticeShown = async () => {
  await waitFor(() => expect(notice()).not.toBeNull())
  return notice()!
}
const check = () => screen.queryByRole('group', { name: 'Security check' })
const inProvider = (children: ReactNode) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
)

afterEach(() => {
  vi.useRealTimers()
  onlineManager.setOnline(true)
  for (const script of scripts()) script.remove()
  delete window.turnstile
  cloudflare.rendered = 0
  api.login.mockReset()
  api.register.mockReset()
  api.submitContactForm.mockReset()
  api.joinWaitlist.mockReset()
})

interface FormUnderTest {
  /** Renders the form with its fields filled, its widget mounted. */
  open: () => void
  submit: string
  call: Mock
  /** The Turnstile token each call sent. */
  tokens: () => unknown[]
}

const FORMS: Array<[string, FormUnderTest]> = [
  ['the sign-in form', {
    open: () => {
      render(inProvider(<LoginPage />))
      fireEvent.click(screen.getByRole('button', { name: 'Continue with email' }))
      fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader@example.com' } })
      fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } })
    },
    submit: 'Log in',
    call: api.login,
    tokens: () => api.login.mock.calls.map(([, , token]) => token),
  }],
  ['the register form', {
    open: () => {
      render(inProvider(<RegisterForm inviteOnly={false} betaPromoActive={false} />))
      fireEvent.click(screen.getByRole('button', { name: /sign up with email/i }))
      fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'person@example.com' } })
      fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-long-enough-passphrase' } })
    },
    submit: 'Create account',
    call: api.register,
    tokens: () => api.register.mock.calls.map(([, , , token]) => token),
  }],
  ['the contact form', {
    open: () => {
      render(inProvider(<ContactForm />))
      fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
      fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.com' } })
      fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: 'A message long enough.' } })
    },
    submit: 'Send message',
    call: api.submitContactForm,
    tokens: () => api.submitContactForm.mock.calls.map(([, token]) => token),
  }],
  ['the waitlist form', {
    open: () => {
      render(inProvider(<WaitlistForm />))
      fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'reader@example.com' } })
    },
    submit: 'Join the waitlist',
    call: api.joinWaitlist,
    tokens: () => api.joinWaitlist.mock.calls.map(([, token]) => token),
  }],
]

describe.each(FORMS)('%s with Turnstile on', (_, form) => {
  it("says the check didn't load, and a Try again loads the script afresh; the check then renders there and its token sends", async () => {
    form.call.mockReturnValue(new Promise(() => {}))
    form.open()
    await failLoad()
    const alert = await noticeShown()
    expect(alert).toHaveTextContent('Allow challenges.cloudflare.com in your content blocker')
    // The domain breaks at its dots, never inside a word, where the notice is narrower than it.
    expect(alert!.querySelectorAll('wbr')).toHaveLength(2)
    // The failed element is gone, so a later load is a new one and never waits on it.
    expect(scripts()).toHaveLength(0)
    expect(check()).toBeNull()
    // The submit still waits for its token, and a press sends nothing.
    const submit = screen.getByRole('button', { name: form.submit })
    expect(submit).toHaveAttribute('aria-disabled', 'true')
    fireEvent.click(submit)
    expect(form.call).not.toHaveBeenCalled()

    const retry = within(alert!).getByRole('button', { name: 'Try again' })
    retry.focus()
    await userEvent.keyboard('{Enter}')
    // A new load: the notice holds, its Retry busy, until it lands.
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    expect(scripts()).toHaveLength(1)
    expect(notice()).not.toBeNull()

    await loadScript()
    await waitFor(() => expect(notice()).toBeNull())
    const group = check()
    expect(group).not.toBeNull()
    expect(window.turnstile!.render).toHaveBeenCalledTimes(1)
    expect(vi.mocked(window.turnstile!.render).mock.calls[0][0]).toBe(group)
    // The Try again left with the notice while it held focus, and focus came to the check, never to <body>.
    await waitFor(() => expect(document.activeElement).toBe(group))

    await waitFor(() => expect(submit).not.toHaveAttribute('aria-disabled'))
    fireEvent.click(submit)
    await waitFor(() => expect(form.call).toHaveBeenCalledTimes(1))
    expect(form.tokens()).toEqual(['token-1'])
  })

  it('keeps the notice and its Try again through a load that fails again', async () => {
    form.open()
    await failLoad()
    const retry = within(await noticeShown()).getByRole('button', { name: 'Try again' })
    fireEvent.click(retry)
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    expect(scripts()).toHaveLength(1)
    await failLoad()
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(notice()).not.toBeNull()
    expect(scripts()).toHaveLength(0)
    expect(retry).toHaveTextContent('Try again')
    expect(screen.getByRole('button', { name: form.submit })).toHaveAttribute('aria-disabled', 'true')
  })

  it('renders the check with no notice when the script loads, and its token sends', async () => {
    form.call.mockReturnValue(new Promise(() => {}))
    form.open()
    await loadScript()
    await waitFor(() => expect(window.turnstile!.render).toHaveBeenCalledTimes(1))
    expect(notice()).toBeNull()
    const submit = screen.getByRole('button', { name: form.submit })
    await waitFor(() => expect(submit).not.toHaveAttribute('aria-disabled'))
    fireEvent.click(submit)
    await waitFor(() => expect(form.call).toHaveBeenCalledTimes(1))
    expect(form.tokens()).toEqual(['token-1'])
  })
})

describe("TurnstileWidget's script load", () => {
  it('waits on a load already in flight rather than add a second element, and its failure reaches both', async () => {
    // Two widgets under two clients each start a load: the second finds the first's element and waits on it.
    render(
      <>
        {inProvider(<TurnstileWidget onToken={() => {}} />)}
        {inProvider(<TurnstileWidget onToken={() => {}} />)}
      </>,
    )
    expect(scripts()).toHaveLength(1)
    await failLoad()
    await waitFor(() => expect(screen.getAllByText(TITLE)).toHaveLength(2))
    expect(scripts()).toHaveLength(0)
  })

  it('says so when a load stalls past its time, and removes the element it waited on', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    render(inProvider(<TurnstileWidget onToken={() => {}} />))
    expect(scripts()).toHaveLength(1)
    // Neither event fires. Short of the bound nothing is said; at it, the notice, and the element is gone.
    await act(() => vi.advanceTimersByTimeAsync(LOAD_TIMEOUT_MS - 100))
    expect(notice()).toBeNull()
    expect(scripts()).toHaveLength(1)
    await act(() => vi.advanceTimersByTimeAsync(200))
    expect(notice()).not.toBeNull()
    expect(scripts()).toHaveLength(0)
  })

  it('says so when the script loads but brings no Turnstile, and removes its element', async () => {
    render(inProvider(<TurnstileWidget onToken={() => {}} />))
    // A content blocker's empty stand-in: the element loads, and no global comes with it.
    await act(async () => {
      inFlight().dispatchEvent(new Event('load'))
    })
    await noticeShown()
    expect(scripts()).toHaveLength(0)
  })

  it('offline, fails into the notice, and a reconnect loads the script again on its own', async () => {
    onlineManager.setOnline(false)
    const tokens: string[] = []
    render(inProvider(<TurnstileWidget onToken={(token) => tokens.push(token)} />))
    // The load starts though the browser reports no connection, and the request fails.
    expect(scripts()).toHaveLength(1)
    await failLoad()
    await noticeShown()
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(scripts()).toHaveLength(1))
    await loadScript()
    await waitFor(() => expect(notice()).toBeNull())
    expect(tokens).toEqual(['token-1'])
  })

  it('keeps its place when Cloudflare cannot render the check, rather than give the form to an error boundary', async () => {
    render(inProvider(<TurnstileWidget onToken={() => {}} />))
    await act(async () => {
      window.turnstile = {
        render: vi.fn(() => {
          throw new Error('Invalid container')
        }),
        reset: vi.fn(),
        remove: vi.fn(),
      }
      inFlight().dispatchEvent(new Event('load'))
    })
    await waitFor(() => expect(window.turnstile!.render).toHaveBeenCalledTimes(1))
    expect(check()).not.toBeNull()
    expect(notice()).toBeNull()
  })

  it('renders each widget once on a load both waited on', async () => {
    const tokens: string[] = []
    render(
      <>
        {inProvider(<TurnstileWidget onToken={(token) => tokens.push(token)} />)}
        {inProvider(<TurnstileWidget onToken={(token) => tokens.push(token)} />)}
      </>,
    )
    expect(scripts()).toHaveLength(1)
    await loadScript()
    await waitFor(() => expect(tokens).toHaveLength(2))
    expect(window.turnstile!.render).toHaveBeenCalledTimes(2)
    expect(tokens.sort()).toEqual(['token-1', 'token-2'])
  })
})
