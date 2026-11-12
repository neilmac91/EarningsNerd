import React, { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * The page a verification email's link opens, {FRONTEND_URL}/verify-email?token=<token>
 * (backend account_mail_service). It is safe for a link scanner: opening it sends nothing, the token leaves the
 * address bar at once (a `#token=` fragment too), and only a press of Verify email posts it
 * (POST /api/auth/verify-email), once per press. An answer about the link replaces the button and takes focus:
 * verified (the identity refreshed, then the home page after 3 s) or refused, a 400 (the reason readVerifyEmailFailure
 * gives). A press that got no answer about the link (no connection, a 5xx, a 429) keeps the button, focused, under an
 * error notice, and the next press posts the same token again. With no token it says the email's link is needed and
 * posts nothing.
 */

const { push, verifyEmail } = vi.hoisted(() => ({ push: vi.fn(), verifyEmail: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
vi.mock('@/features/auth/api/auth-api', () => ({ verifyEmail }))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

import VerifyEmailPage from '@/app/verify-email/page'
import { ApiError } from '@/lib/api/client'
import {
  VERIFY_FIRST_TRY_HINT,
  VERIFY_LINK_FALLBACK,
  VERIFY_UNANSWERED_DESCRIPTION,
  VERIFY_UNANSWERED_TITLE,
} from '@/features/auth/lib/verifyEmailFailure'
import { queryKeys } from '@/lib/queryKeys'

const openAt = (url: string, state: unknown = null) => window.history.replaceState(state, '', url)
const verifyButton = () => screen.getByRole('button', { name: 'Verify email' })

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => {
    resolve = yes
  })
  return { promise, resolve }
}

function renderPage({ strict = false } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  const page = <VerifyEmailPage />
  const { unmount } = render(<QueryClientProvider client={queryClient}>{strict ? <StrictMode>{page}</StrictMode> : page}</QueryClientProvider>)
  return { invalidate, unmount }
}

beforeEach(() => {
  push.mockReset()
  verifyEmail.mockReset()
  openAt('/verify-email')
})

afterEach(() => {
  vi.useRealTimers()
})

describe('opening the page sends nothing', () => {
  it('with ?token=: posts nothing, takes the token out of the address bar keeping the history state, and offers the button', async () => {
    openAt('/verify-email?token=abc', { kept: 'next-router-state' })
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Verify your email address' })).toBeInTheDocument()
    expect(screen.getByText('Press Verify email to confirm this address is yours.')).toBeInTheDocument()
    expect(verifyButton()).not.toHaveAttribute('aria-disabled')
    expect(window.location.pathname).toBe('/verify-email')
    expect(window.location.search).toBe('')
    expect(window.location.hash).toBe('')
    expect(window.history.state).toEqual({ kept: 'next-router-state' })
    expect(verifyEmail).not.toHaveBeenCalled()
  })

  it('with #token=: the same, and a press posts the fragment token', async () => {
    openAt('/verify-email#token=abc')
    verifyEmail.mockResolvedValue({ message: 'Email verified successfully' })
    renderPage()
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    expect(window.location.hash).toBe('')
    expect(window.location.search).toBe('')
    expect(verifyEmail).not.toHaveBeenCalled()
    await userEvent.setup().click(verifyButton())
    expect(verifyEmail).toHaveBeenCalledTimes(1)
    expect(verifyEmail).toHaveBeenCalledWith('abc')
    expect(await screen.findByRole('heading', { level: 1, name: 'Email verified' })).toBeInTheDocument()
  })

  it('with no token: the failure state at once, no button, nothing posted', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Verification failed' })).toBeInTheDocument()
    expect(screen.getByText('No verification token found. Please use the link from your email.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Get a new link' })).toHaveAttribute('href', '/check-email')
    expect(screen.getByRole('link', { name: 'back to login' })).toHaveAttribute('href', '/login')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(verifyEmail).not.toHaveBeenCalled()
  })
})

describe('a press posts the token once', () => {
  it('under StrictMode, through a double click and a further click, while the button stays focusable and busy', async () => {
    openAt('/verify-email?token=abc')
    const answer = deferred<unknown>()
    verifyEmail.mockReturnValue(answer.promise)
    renderPage({ strict: true })
    // StrictMode reads the address twice; the second read finds it cleared and keeps the first.
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    expect(verifyEmail).not.toHaveBeenCalled()
    const user = userEvent.setup()
    const button = verifyButton()
    await user.dblClick(button)
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).not.toBeDisabled()
    expect(button).toHaveFocus()
    expect(button).toHaveAccessibleName('Verifying…')
    await user.click(button)
    expect(verifyEmail).toHaveBeenCalledTimes(1)
    expect(verifyEmail).toHaveBeenCalledWith('abc')
    await act(async () => answer.resolve({ message: 'Email verified successfully' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Email verified' })).toBeInTheDocument()
    expect(verifyEmail).toHaveBeenCalledTimes(1)
  })

  it('two clicks in one tick, before the busy render, still send one post', async () => {
    openAt('/verify-email?token=abc')
    verifyEmail.mockReturnValue(new Promise(() => {}))
    renderPage({ strict: true })
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    const button = verifyButton()
    act(() => {
      button.click()
      button.click()
    })
    expect(verifyEmail).toHaveBeenCalledTimes(1)
  })
})

describe('the answer replaces the button and takes focus', () => {
  it('verified: says so, refreshes the identity once, and goes home after 3 s', async () => {
    vi.useFakeTimers()
    openAt('/verify-email?token=abc')
    verifyEmail.mockResolvedValue({ message: 'Email verified successfully' })
    const { invalidate } = renderPage()
    // The mount effect has run inside render's act: the token is read and the button is live.
    expect(verifyButton()).not.toHaveAttribute('aria-disabled')
    verifyButton().focus()
    fireEvent.click(verifyButton())
    await act(async () => {})
    const heading = screen.getByRole('heading', { level: 1, name: 'Email verified' })
    expect(screen.getByText('Your email address is confirmed. Taking you to the home page…')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Continue to EarningsNerd' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: 'Verify email' })).not.toBeInTheDocument()
    expect(heading.parentElement).toHaveFocus()
    expect(heading.parentElement).toHaveAttribute('tabindex', '-1')
    expect(invalidate).toHaveBeenCalledTimes(1)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.currentUser() })
    act(() => vi.advanceTimersByTime(2999))
    expect(push).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(push).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith('/')
  })

  it('failed: the failure state with the mapped message, and focus on it', async () => {
    openAt('/verify-email?token=abc')
    // A 400 whose detail is none of the endpoint's reasons reads as the link fallback.
    verifyEmail.mockRejectedValue(new ApiError(400, 'Request failed with status code 400'))
    renderPage()
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    await userEvent.setup().click(verifyButton())
    const heading = await screen.findByRole('heading', { level: 1, name: 'Verification failed' })
    expect(screen.getByText(VERIFY_LINK_FALLBACK)).toBeInTheDocument()
    // No press went unanswered before this refusal, so nothing suggests the address may be verified already.
    expect(screen.queryByText(VERIFY_FIRST_TRY_HINT, { exact: false })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Get a new link' })).toHaveAttribute('href', '/check-email')
    expect(screen.queryByRole('button', { name: 'Verify email' })).not.toBeInTheDocument()
    expect(heading.parentElement).toHaveFocus()
    expect(push).not.toHaveBeenCalled()
  })

  it.each([
    ['under StrictMode', true],
    ['without it', false],
  ])('verified, then the reader leaves within 3 s (%s): the move to the home page is cancelled', async (_name, strict) => {
    vi.useFakeTimers()
    openAt('/verify-email?token=abc')
    verifyEmail.mockResolvedValue({ message: 'Email verified successfully' })
    const { unmount } = renderPage({ strict })
    fireEvent.click(verifyButton())
    await act(async () => {})
    expect(screen.getByRole('heading', { level: 1, name: 'Email verified' })).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(1500))
    unmount()
    act(() => vi.advanceTimersByTime(10000))
    expect(push).not.toHaveBeenCalled()
  })
})

describe('a press with no answer about the link keeps the button for another press', () => {
  it.each([
    ['no connection (status 0)', new ApiError(0, 'Unable to connect to the server.')],
    ['a 503', new ApiError(503, 'Service unavailable')],
    ['a 429', new ApiError(429, 'Too many requests. Try again later.')],
  ])('%s: the notice above the focused button, nothing more posted until the next press, which posts the same token and can succeed', async (_case, rejection) => {
    openAt('/verify-email?token=abc')
    verifyEmail.mockRejectedValueOnce(rejection)
    renderPage({ strict: true })
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    const user = userEvent.setup()
    const button = verifyButton()
    await user.click(button)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(VERIFY_UNANSWERED_TITLE)
    expect(alert).toHaveTextContent(VERIFY_UNANSWERED_DESCRIPTION)
    expect(VERIFY_UNANSWERED_TITLE).toBe("We couldn't check the link just now")
    expect(VERIFY_UNANSWERED_DESCRIPTION).toBe('Try again in a minute.')
    // Still the idle state: the same button, live and focused, and no failure heading.
    expect(screen.getByRole('heading', { level: 1, name: 'Verify your email address' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Verification failed' })).not.toBeInTheDocument()
    expect(verifyButton()).toBe(button)
    expect(button).not.toHaveAttribute('aria-disabled')
    expect(button).toHaveFocus()
    expect(screen.queryByText(rejection.detail)).not.toBeInTheDocument()
    // Nothing more is posted until the reader presses again.
    await act(async () => {})
    expect(verifyEmail).toHaveBeenCalledTimes(1)
    // The next press posts once more with the same token, a double click still once.
    const answer = deferred<unknown>()
    verifyEmail.mockReturnValueOnce(answer.promise)
    await user.dblClick(button)
    expect(verifyEmail).toHaveBeenCalledTimes(2)
    expect(verifyEmail).toHaveBeenLastCalledWith('abc')
    // The press takes the old notice away while it is out.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await act(async () => answer.resolve({ message: 'Email verified successfully' }))
    const heading = await screen.findByRole('heading', { level: 1, name: 'Email verified' })
    expect(heading.parentElement).toHaveFocus()
    expect(verifyEmail).toHaveBeenCalledTimes(2)
  })

  it('a 400 on the next press: the failure state with its reason and that the first try may have gone through, no button', async () => {
    openAt('/verify-email#token=abc')
    verifyEmail
      .mockRejectedValueOnce(new ApiError(0, 'The request timed out. Please try again.'))
      .mockRejectedValueOnce(new ApiError(400, 'Invalid or expired verification link.'))
    renderPage()
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    const user = userEvent.setup()
    await user.click(verifyButton())
    expect(await screen.findByRole('alert')).toHaveTextContent(VERIFY_UNANSWERED_TITLE)
    await user.click(verifyButton())
    const heading = await screen.findByRole('heading', { level: 1, name: 'Verification failed' })
    // The first press may have verified the address before its answer was lost, which spends the token: the
    // refusal then describes the second press, so the page says the reader can log in to check.
    expect(VERIFY_FIRST_TRY_HINT).toBe('Your first try may have gone through. Log in to check whether your email is verified.')
    expect(screen.getByText(`Invalid or expired verification link. ${VERIFY_FIRST_TRY_HINT}`)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'back to login' })).toHaveAttribute('href', '/login')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByText(VERIFY_UNANSWERED_TITLE)).not.toBeInTheDocument()
    expect(heading.parentElement).toHaveFocus()
    expect(verifyEmail).toHaveBeenCalledTimes(2)
    expect(verifyEmail).toHaveBeenNthCalledWith(2, 'abc')
  })

  it.each([
    // "Expired" is said only of a token the server still holds: the first press cannot have verified with it.
    ['a lost answer, then the link has expired', new ApiError(0, 'The request timed out. Please try again.'), 'Verification link has expired. Request a new one.'],
    // A rate limit answered before the route ran, so the first press verified nothing.
    ['a rate limit, then a refused link', new ApiError(429, 'Too many requests. Try again later.'), 'Invalid or expired verification link.'],
  ])('%s: the reason alone, with no word that the first try may have gone through', async (_case, first, reason) => {
    openAt('/verify-email?token=abc')
    verifyEmail.mockRejectedValueOnce(first).mockRejectedValueOnce(new ApiError(400, reason))
    renderPage()
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    const user = userEvent.setup()
    await user.click(verifyButton())
    expect(await screen.findByRole('alert')).toHaveTextContent(VERIFY_UNANSWERED_TITLE)
    await user.click(verifyButton())
    await screen.findByRole('heading', { level: 1, name: 'Verification failed' })
    expect(screen.getByText(reason)).toBeInTheDocument()
    expect(screen.queryByText(VERIFY_FIRST_TRY_HINT, { exact: false })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Get a new link' })).toHaveAttribute('href', '/check-email')
  })

  it('a server error, then a refused link: the first try may have gone through', async () => {
    openAt('/verify-email?token=abc')
    verifyEmail
      .mockRejectedValueOnce(new ApiError(503, 'Service unavailable'))
      .mockRejectedValueOnce(new ApiError(400, 'Request failed with status code 400'))
    renderPage()
    await waitFor(() => expect(verifyButton()).not.toHaveAttribute('aria-disabled'))
    const user = userEvent.setup()
    await user.click(verifyButton())
    await screen.findByRole('alert')
    await user.click(verifyButton())
    await screen.findByRole('heading', { level: 1, name: 'Verification failed' })
    expect(screen.getByText(`${VERIFY_LINK_FALLBACK} ${VERIFY_FIRST_TRY_HINT}`)).toBeInTheDocument()
  })
})
