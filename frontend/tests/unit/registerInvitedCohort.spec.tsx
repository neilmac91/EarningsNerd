import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import RegisterForm from '@/features/auth/components/RegisterForm'
import { getInvitedCohortAvailable } from '@/features/auth/api/auth-api'
import { useInvitedCohort } from '@/features/auth/hooks/useInvitedCohort'
import { legalReady } from './fixtures/legalReady'

/**
 * Invited-cohort registration on the register page (EN-BETA PB-01; docs/LEGAL_READINESS.md, "Invited-cohort
 * registration"). While collection is held, the page offers the form to a visitor holding an invitation only when a
 * fresh read of GET /api/auth/registration says `invited_cohort_available: true`, exactly, in an invite-only answer;
 * any other answer, and a failed read, keep it closed. It reads the answer again before each sign-up, by email or a
 * provider, and sends nothing once it answers closed. An uninvited visitor meets the closure as before and the read is
 * never made for them. The API client is the one stand-in: each answer goes through the real reader.
 */

const mocks = vi.hoisted(() => ({
  get: vi.fn(), register: vi.fn(), oauth: vi.fn(), search: new URLSearchParams(),
}))
vi.mock('@/lib/api/client', async (original) => ({
  ...(await original<typeof import('@/lib/api/client')>()), default: { get: mocks.get },
}))
vi.mock('@/features/auth/api/auth-api', async (original) => ({
  ...(await original<typeof import('@/features/auth/api/auth-api')>()),
  register: mocks.register,
  startOAuthWithInvite: mocks.oauth,
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }), useSearchParams: () => mocks.search,
}))
vi.mock('@/lib/featureFlags', async (original) => ({
  ...(await original<typeof import('@/lib/featureFlags')>()), TURNSTILE_ENABLED: false, ENABLE_APPLE_SIGNIN: true,
}))
vi.mock('@/lib/analytics', () => ({ default: { signupStarted: vi.fn(), signupSubmitted: vi.fn() } }))
vi.mock('@/features/auth/components/AuthShell', () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }))
vi.mock('@/features/auth/components/TurnstileWidget', () => ({ default: () => null }))

/** Collection held, as the public readiness answer stays while only the exception is open. */
const held = { ...legalReady, collection_available: false, checkout_available: false, operator: null }
const open = { mode: 'invite_only', beta_promo_enabled: false, invited_cohort_available: true }
const closedAnswer = { mode: 'invite_only', beta_promo_enabled: false, invited_cohort_available: false }
const agreement = {
  adult_eligible: true, terms_accepted: true, terms_version: legalReady.terms_version,
  eligibility_version: legalReady.eligibility_version,
}
const INVITE = 'synthetic-invite-token'

/** Route the client's reads: legal readiness, and the registration answer (a value, a function of the call, or an
 *  Error to reject with). */
function answer(readiness: unknown, registration: unknown) {
  let calls = 0
  mocks.get.mockImplementation(async (url: string) => {
    if (url === '/api/legal/readiness') return { data: readiness }
    if (url === '/api/auth/registration') {
      calls += 1
      const value = typeof registration === 'function' ? (registration as (n: number) => unknown)(calls) : registration
      if (value instanceof Error) throw value
      return { data: value }
    }
    throw new Error(`unexpected read ${url}`)
  })
}
const registrationReads = () => mocks.get.mock.calls.filter(([url]) => url === '/api/auth/registration').length
const invited = () => {
  mocks.search = new URLSearchParams({ invite: INVITE })
  return render(<RegisterForm inviteOnly betaPromoActive={false} />)
}
const accept = () => {
  fireEvent.click(screen.getByRole('checkbox', { name: /at least 18/i }))
  fireEvent.click(screen.getByRole('checkbox', { name: /agree to the/i }))
}
const fill = () => {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'invitee@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-long-enough-password' } })
}

beforeEach(() => {
  for (const mock of [mocks.get, mocks.register, mocks.oauth]) mock.mockReset()
  mocks.search = new URLSearchParams()
  mocks.register.mockResolvedValue({})
  mocks.oauth.mockReturnValue(new Promise(() => {}))
  window.history.replaceState({}, '', '/register')
})

describe('the reader fails closed', () => {
  it('opens only on an exact true in an invite-only answer, through the shared client', async () => {
    mocks.get.mockResolvedValue({ data: open })
    const signal = new AbortController().signal
    await expect(getInvitedCohortAvailable(signal)).resolves.toBe(true)
    expect(mocks.get).toHaveBeenCalledWith('/api/auth/registration', { signal })
  })

  it.each([
    ['a string', { ...open, invited_cohort_available: 'true' }],
    ['a number', { ...open, invited_cohort_available: 1 }],
    ['no flag', { mode: 'invite_only', beta_promo_enabled: false }],
    ['a public answer', { ...open, mode: 'public' }],
    ['no body', null],
    ['a list', [open]],
    ['false', closedAnswer],
  ])('reads %s as closed', async (_name, body) => {
    mocks.get.mockResolvedValue({ data: body })
    await expect(getInvitedCohortAvailable()).resolves.toBe(false)
  })
})

describe('the fresh read', () => {
  const deferred = <T,>() => {
    let resolve!: (value: T) => void
    const promise = new Promise<T>((yes) => { resolve = yes })
    return { promise, resolve }
  }

  it('lets no superseded read open the exception, and none that answers after an unmount', async () => {
    const mounted = deferred<{ data: unknown }>()
    mocks.get.mockImplementationOnce(() => mounted.promise)
    const { result, unmount } = renderHook(() => useInvitedCohort(true))
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1))

    // A recheck supersedes the mount's read and answers closed; the mount's read answering open later opens nothing.
    mocks.get.mockResolvedValueOnce({ data: closedAnswer })
    let fresh: boolean | undefined
    await act(async () => { fresh = await result.current.recheck() })
    expect(fresh).toBe(false)
    await act(async () => { mounted.resolve({ data: open }) })
    expect(result.current.available).toBe(false)

    // A read still out at an unmount answers closed, whatever the server says.
    const late = deferred<{ data: unknown }>()
    mocks.get.mockImplementationOnce(() => late.promise)
    let pending: Promise<boolean> | undefined
    act(() => { pending = result.current.recheck() })
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(3))
    unmount()
    late.resolve({ data: open })
    await expect(pending).resolves.toBe(false)
  })

  it('reads nothing for a visitor without an invitation', async () => {
    const { result } = renderHook(() => useInvitedCohort(false))
    await expect(result.current.recheck()).resolves.toBe(false)
    expect(result.current).toMatchObject({ available: false, loading: false })
    expect(mocks.get).not.toHaveBeenCalled()
  })
})

describe('an invitee while collection is held', () => {
  it('gets the form when a fresh read says the exception is open, and signs up with the invite', async () => {
    answer(held, open)
    invited()

    expect(await screen.findByRole('checkbox', { name: /at least 18/i })).toBeInTheDocument()
    expect(screen.getByText("You're invited to the private beta")).toBeInTheDocument()
    expect(screen.getByText('Your invite opens an account during the private beta.')).toBeInTheDocument()
    expect(screen.queryByText('Registration is currently closed')).toBeNull()
    expect(registrationReads()).toBe(1)

    accept()
    fill()
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(mocks.register).toHaveBeenCalledWith(
      'invitee@example.test', 'a-long-enough-password', '', '', INVITE, agreement,
    ))
    expect(registrationReads()).toBe(2) // read again before the sign-up
  })

  it.each([
    ['a string flag', { ...open, invited_cohort_available: 'true' }],
    ['no flag', { mode: 'invite_only', beta_promo_enabled: false }],
    ['a public answer', { ...open, mode: 'public' }],
    ['a closed answer', closedAnswer],
    ['a failed read', new Error('network')],
  ])('stays closed on %s', async (_name, registration) => {
    answer(held, registration)
    invited()

    expect(await screen.findByText('Registration is currently closed')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(document.querySelector('form')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Continue with Google' })).toBeNull()
  })

  it('stays closed when the readiness read itself fails, whatever the exception says', async () => {
    mocks.get.mockImplementation(async (url: string) => {
      if (url === '/api/auth/registration') return { data: open }
      throw new Error('network')
    })
    invited()

    expect(await screen.findByText('Registration is currently closed')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  it('reads afresh on each visit rather than keep an earlier answer', async () => {
    answer(held, (call: number) => (call === 1 ? open : closedAnswer))
    const first = invited()
    expect(await screen.findByRole('checkbox', { name: /at least 18/i })).toBeInTheDocument()
    first.unmount()

    invited()
    expect(await screen.findByText('Registration is currently closed')).toBeInTheDocument()
    expect(registrationReads()).toBe(2)
  })

  it('sends nothing once the exception answers closed before the sign-up, and closes the form', async () => {
    answer(held, (call: number) => (call === 1 ? open : closedAnswer))
    invited()
    await screen.findByRole('checkbox', { name: /at least 18/i })
    accept()
    fill()

    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Registration is currently closed')).toBeInTheDocument()
    expect(mocks.register).not.toHaveBeenCalled()
    expect(registrationReads()).toBe(2)
  })

  it.each(['Google', 'Apple'])('starts no %s sign-up once the exception answers closed', async (provider) => {
    answer(held, (call: number) => (call === 1 ? open : new Error('network')))
    invited()
    await screen.findByRole('checkbox', { name: /at least 18/i })
    accept()

    fireEvent.click(screen.getByRole('button', { name: `Continue with ${provider}` }))

    expect(await screen.findByText('Registration is currently closed')).toBeInTheDocument()
    expect(mocks.oauth).not.toHaveBeenCalled()
  })

  it.each(['Google', 'Apple'])('starts a %s sign-up with the invite and assent while it stays open', async (provider) => {
    answer(held, open)
    invited()
    await screen.findByRole('checkbox', { name: /at least 18/i })
    accept()

    fireEvent.click(screen.getByRole('button', { name: `Continue with ${provider}` }))

    await waitFor(() => expect(mocks.oauth).toHaveBeenCalledWith(provider.toLowerCase(), INVITE, agreement))
  })

  it('asks for a refresh when the account requirements are newer than this page', async () => {
    answer({ ...held, terms_version: '2026-10-25' }, open)
    invited()

    expect(await screen.findByText('Registration needs a refresh')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })
})

describe('what the exception leaves as it was', () => {
  it('an uninvited visitor meets the closure, and the exception is never read for them', async () => {
    answer(held, open)
    render(<RegisterForm inviteOnly betaPromoActive={false} />)

    expect(await screen.findByText('Registration is currently closed')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(registrationReads()).toBe(0)
  })

  it('with collection open an invitee signs up on the general path, whatever the exception answers', async () => {
    answer(legalReady, new Error('network'))
    invited()

    await screen.findByRole('checkbox', { name: /at least 18/i })
    accept()
    fill()
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(mocks.register).toHaveBeenCalledWith(
      'invitee@example.test', 'a-long-enough-password', '', '', INVITE, agreement,
    ))
  })
})
