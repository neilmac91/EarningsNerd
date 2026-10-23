import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RegisterForm from '@/features/auth/components/RegisterForm'
import SocialAuthButtons from '@/features/auth/components/SocialAuthButtons'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import ContactForm from '@/features/contact/components/ContactForm'
import PricingPage from '@/app/pricing/page'
import { LegalOperatorNotice } from '@/features/legal/components/LegalOperatorNotice'
import { useLegalReadiness } from '@/features/legal/hooks/useLegalReadiness'
import { legalReady } from './fixtures/legalReady'

const mocks = vi.hoisted(() => ({
  get: vi.fn(), register: vi.fn(), oauth: vi.fn(), join: vi.fn(), contact: vi.fn(), checkout: vi.fn(),
  push: vi.fn(), search: new URLSearchParams(), isBeta: false,
}))
vi.mock('@/lib/api/client', async (original) => ({
  ...(await original<typeof import('@/lib/api/client')>()), default: { get: mocks.get },
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  register: mocks.register, startOAuthWithInvite: mocks.oauth,
  getCurrentUserSafe: async () => ({ id: 1, email: 'reader@example.test', is_beta: mocks.isBeta }),
}))
vi.mock('@/features/waitlist/api/waitlist-api', () => ({ joinWaitlist: mocks.join }))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: mocks.contact }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  createCheckoutSession: mocks.checkout,
  getSubscriptionStatus: async () => ({ is_pro: false, status: null }),
  getUsage: async () => ({ summaries_used: 0, summaries_limit: 5 }),
}))
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: async () => ({ mode: 'public' }) }))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push, refresh: vi.fn(), replace: vi.fn() }), useSearchParams: () => mocks.search,
}))
vi.mock('@/lib/featureFlags', async (original) => ({
  ...(await original<typeof import('@/lib/featureFlags')>()), TURNSTILE_ENABLED: false, ENABLE_APPLE_SIGNIN: true,
}))
vi.mock('@/lib/analytics', () => ({ default: { signupStarted: vi.fn(), signupSubmitted: vi.fn(), pricingViewed: vi.fn(), checkoutStarted: vi.fn() } }))
vi.mock('@/features/auth/components/AuthShell', () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }))
vi.mock('@/components/SecondaryHeader', () => ({ default: () => null }))
vi.mock('@/features/auth/components/TurnstileWidget', () => ({ default: () => <div data-testid="captcha" /> }))

const closed = { ...legalReady, collection_available: false, checkout_available: false, operator: null }
const agreement = { adult_eligible: true, terms_accepted: true, terms_version: legalReady.terms_version, eligibility_version: legalReady.eligibility_version }
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}
const signup = () => render(<RegisterForm inviteOnly={false} betaPromoActive={false} />)
const accept = () => {
  fireEvent.click(screen.getByRole('checkbox', { name: /at least 18/i }))
  fireEvent.click(screen.getByRole('checkbox', { name: /agree to the/i }))
}
const openEmail = async () => {
  fireEvent.click(await screen.findByRole('button', { name: /sign up with email/i }))
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-long-enough-password' } })
}

beforeEach(() => {
  Object.values(mocks).forEach((value) => { if (vi.isMockFunction(value)) value.mockReset() })
  mocks.search = new URLSearchParams()
  mocks.isBeta = false
  mocks.get.mockResolvedValue({ data: legalReady })
  mocks.register.mockResolvedValue({})
  mocks.oauth.mockReturnValue(new Promise(() => {}))
})

describe('collection readiness is fresh and fails closed', () => {
  it.each([RegisterForm, WaitlistForm, ContactForm])('mounts no collection fields or CAPTCHA while pending or closed: %s', async (Component) => {
    const request = deferred<{ data: typeof closed }>()
    mocks.get.mockReturnValue(request.promise)
    const props = Component === RegisterForm ? { inviteOnly: false, betaPromoActive: false } : {}
    render(<Component {...props as { inviteOnly: boolean; betaPromoActive: boolean }} />)
    expect(document.querySelector('form')).toBeNull()
    expect(screen.queryByTestId('captcha')).toBeNull()
    const pending = screen.getByRole('status', { name: /Checking .* availability/ })
    expect(pending.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0)
    expect(screen.queryByText('Checking availability')).toBeNull()
    await act(async () => request.resolve({ data: closed }))
    expect(document.querySelector('form')).toBeNull()
    expect(screen.queryByTestId('captcha')).toBeNull()
    expect(screen.getByRole('link', { name: 'privacy@earningsnerd.io' })).toHaveAttribute('href', 'mailto:privacy@earningsnerd.io')
    expect(mocks.register).not.toHaveBeenCalled()
    expect(mocks.join).not.toHaveBeenCalled()
    expect(mocks.contact).not.toHaveBeenCalled()
  })

  it('does not carry successful readiness across mounts and closes on a failed recheck', async () => {
    const first = signup()
    await openEmail()
    accept()
    mocks.get.mockRejectedValueOnce(new Error('unavailable'))
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await screen.findByText('Registration is currently closed')
    expect(screen.queryByTestId('captcha')).toBeNull()
    expect(mocks.register).not.toHaveBeenCalled()
    first.unmount()
    mocks.get.mockResolvedValue({ data: closed })
    signup()
    expect(screen.queryByRole('checkbox')).toBeNull()
    await screen.findByText('Registration is currently closed')
    expect(mocks.get).toHaveBeenCalledTimes(3)
  })

  it('ignores an older ready response after a newer closed decision', async () => {
    const old = deferred<{ data: typeof legalReady }>()
    mocks.get.mockReturnValueOnce(old.promise).mockResolvedValueOnce({ data: closed })
    const { result } = renderHook(() => useLegalReadiness())
    await act(async () => { await result.current.recheck() })
    await act(async () => old.resolve({ data: legalReady }))
    expect(result.current.readiness?.collection_available).toBe(false)
  })

  it('removes the contact form and keeps support available when collection closes before send', async () => {
    render(<ContactForm />)
    fireEvent.change(await screen.findByLabelText(/^Name/), { target: { value: 'A Reader' } })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'reader@example.test' } })
    fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: 'Please help with my existing account.' } })
    mocks.get.mockResolvedValue({ data: closed })
    const send = screen.getByRole('button', { name: 'Send message' })
    send.focus()
    fireEvent.click(send)
    await screen.findByText('General contact is currently closed')
    expect(mocks.contact).not.toHaveBeenCalled()
    expect(screen.queryByTestId('captcha')).toBeNull()
    expect(document.activeElement).not.toBe(document.body)
    expect(screen.getByRole('link', { name: 'support@earningsnerd.io' })).toBeInTheDocument()
  })
})

describe('explicit account agreement', () => {
  it('requires both initially unchecked choices and sends the fresh versions', async () => {
    signup()
    await openEmail()
    for (const checkbox of screen.getAllByRole('checkbox')) expect(checkbox).not.toBeChecked()
    const submit = screen.getByRole('button', { name: 'Create account' })
    fireEvent.submit(submit.closest('form')!)
    expect(mocks.register).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Confirm both statements to create an account.')
    expect(screen.getByRole('checkbox', { name: /at least 18/i })).toHaveFocus()
    fireEvent.click(screen.getByRole('checkbox', { name: /at least 18/i }))
    fireEvent.click(submit)
    expect(mocks.register).not.toHaveBeenCalled()
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(screen.getByRole('checkbox', { name: /agree to the/i })).toHaveFocus()
    fireEvent.click(screen.getByRole('checkbox', { name: /agree to the/i }))
    expect(screen.queryByRole('alert')).toBeNull()
    fireEvent.click(submit)
    await waitFor(() => expect(mocks.register).toHaveBeenCalledWith('reader@example.test', 'a-long-enough-password', '', '', '', agreement))
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })

  it.each(['terms_version', 'eligibility_version'] as const)('keeps signup closed when the API initially reports a %s this bundle does not publish', async (version) => {
    mocks.get.mockResolvedValue({ data: { ...legalReady, [version]: '2026-10-25' } })
    const first = signup()
    await screen.findByText('Registration needs a refresh')
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(document.querySelector('form')).toBeNull()
    expect(screen.queryByTestId('captcha')).toBeNull()
    expect(mocks.register).not.toHaveBeenCalled()
    expect(mocks.oauth).not.toHaveBeenCalled()
    first.unmount()
    signup()
    await screen.findByText('Registration needs a refresh')
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  it('closes signup when versions change in an open tab instead of accepting unseen policy text', async () => {
    signup()
    await openEmail()
    accept()
    mocks.get.mockResolvedValue({ data: { ...legalReady, terms_version: '2026-10-25' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await screen.findByText('Registration needs a refresh')
    expect(mocks.register).not.toHaveBeenCalled()
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByTestId('captcha')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Create account' })).toBeNull()
  })

  it.each(['Google', 'Apple'])('binds %s signup to assent while keeping existing login independent', async (provider) => {
    const mounted = signup()
    const button = await screen.findByRole('button', { name: `Continue with ${provider}` })
    fireEvent.click(button)
    expect(mocks.oauth).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Confirm both statements to create an account.')
    expect(screen.getByRole('checkbox', { name: /at least 18/i })).toHaveFocus()
    fireEvent.click(screen.getByRole('checkbox', { name: /at least 18/i }))
    await waitFor(() => expect(button).not.toHaveAttribute('aria-busy', 'true'))
    fireEvent.click(button)
    expect(screen.getByRole('checkbox', { name: /agree to the/i })).toHaveFocus()
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    fireEvent.click(screen.getByRole('checkbox', { name: /agree to the/i }))
    await waitFor(() => expect(button).not.toHaveAttribute('aria-busy', 'true'))
    fireEvent.click(button)
    await waitFor(() => expect(mocks.oauth).toHaveBeenCalledWith(provider.toLowerCase(), undefined, agreement))
    mounted.unmount()
    mocks.get.mockClear()
    render(<SocialAuthButtons apiBase="" />)
    expect(screen.getByRole('link', { name: `Continue with ${provider}` })).toHaveAttribute('href', `/api/auth/${provider.toLowerCase()}`)
    expect(mocks.get).not.toHaveBeenCalled()
  })
})

it('keeps prices and existing billing accessible while blocking new checkout', async () => {
  mocks.get.mockResolvedValue({ data: closed })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PricingPage /></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: 'Checkout unavailable' })).toHaveAttribute('aria-disabled', 'true')
  fireEvent.click(screen.getByRole('button', { name: 'Checkout unavailable' }))
  expect(mocks.checkout).not.toHaveBeenCalled()
  expect(screen.getByRole('link', { name: 'Manage existing billing' })).toHaveAttribute('href', '/dashboard/settings#billing')
  expect(screen.getByRole('heading', { name: 'Pro', exact: true })).toBeInTheDocument()
})

it('does not promise a free beta upgrade while checkout is unavailable', async () => {
  mocks.isBeta = true
  mocks.get.mockResolvedValue({ data: { ...legalReady, checkout_available: false } })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PricingPage /></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: 'Checkout unavailable' })).toHaveAttribute('aria-disabled', 'true')
  const pro = within(screen.getByRole('heading', { name: 'Pro', exact: true }).closest('.rounded-xl')!)
  expect(pro.queryByText('$0', { exact: true })).toBeNull()
  expect(pro.queryByText(/no card required/i)).toBeNull()
  expect(screen.queryByText(/Pro is on us/i)).toBeNull()
  expect(screen.queryByText('Claim Pro', { exact: true })).toBeNull()
  expect(screen.getByRole('link', { name: 'Manage existing billing' })).toBeInTheDocument()
  expect(mocks.checkout).not.toHaveBeenCalled()
})

it('displays operator details only when the endpoint publishes them', async () => {
  mocks.get.mockResolvedValue({ data: closed })
  const hidden = render(<LegalOperatorNotice />)
  await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1))
  expect(screen.queryByText(/Example operator/)).toBeNull()
  expect(screen.getByRole('link', { name: 'privacy@earningsnerd.io' })).toBeInTheDocument()
  hidden.unmount()
  mocks.get.mockResolvedValue({ data: legalReady })
  render(<LegalOperatorNotice />)
  expect(await screen.findByText(/Example operator/)).toHaveTextContent('Example address')
})

it('retains focus and sends no checkout when readiness closes during the preflight', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PricingPage /></QueryClientProvider>)
  const upgrade = await screen.findByRole('button', { name: 'Upgrade to Pro' })
  mocks.get.mockResolvedValue({ data: closed })
  upgrade.focus()
  fireEvent.click(upgrade)
  await screen.findByRole('button', { name: 'Checkout unavailable' })
  expect(mocks.checkout).not.toHaveBeenCalled()
  expect(document.activeElement).toBe(upgrade)
  expect(upgrade).not.toBeDisabled()
})
