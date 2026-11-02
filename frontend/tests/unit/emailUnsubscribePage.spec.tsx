import React, { StrictMode } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * The page an invitation email's unsubscribe link opens, {FRONTEND_URL}/email/unsubscribe#token=<token>
 * (backend invite_delivery_service.build_unsubscribe_link). It is safe for a link scanner: opening it sends nothing,
 * the token leaves the address bar at once, and only a press posts it (POST /api/email/unsubscribe). Each answer says
 * what happened: done (and what still arrives), a link it does not know (and how to reach support), too many tries,
 * or no answer; with no token it says the email's link is needed and keeps the button unavailable.
 */

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/lib/api/client', async (original) => ({
  ...(await original<typeof import('@/lib/api/client')>()),
  default: { get: mocks.get, post: mocks.post },
}))

import UnsubscribePage from '@/app/email/unsubscribe/page'
import { ApiError } from '@/lib/api/client'
import { CONTACT_ADDRESSES } from '@/lib/contactAddresses'

/**
 * A minted token's shape: 43 URL-safe characters (secrets.token_urlsafe(32)), with its `-` and `_`, which a fragment
 * keeps as they are. Built from a short repeat so it reads as no credential (CI's secret scan, `.gitleaksignore`).
 */
const TOKEN = 'a-b_'.repeat(10) + 'c-d'

const openAt = (url: string) => window.history.replaceState(null, '', url)
const unsubscribeButton = () => screen.getByRole('button', { name: 'Unsubscribe' })

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => {
    resolve = yes
  })
  return { promise, resolve }
}

beforeEach(() => {
  mocks.get.mockReset()
  mocks.post.mockReset()
  openAt('/email/unsubscribe')
})

describe('opening the page sends nothing', () => {
  it('takes the token out of the address bar at once, keeping the rest of the address', async () => {
    openAt(`/email/unsubscribe?from=mail#token=${TOKEN}`)
    render(<UnsubscribePage />)
    expect(screen.getByRole('heading', { level: 1, name: 'Unsubscribe from invitation emails' })).toBeInTheDocument()
    await waitFor(() => expect(window.location.hash).toBe(''))
    expect(window.location.pathname).toBe('/email/unsubscribe')
    expect(window.location.search).toBe('?from=mail')
    expect(unsubscribeButton()).not.toHaveAttribute('aria-disabled')
    expect(mocks.get).not.toHaveBeenCalled()
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it('keeps the token through development StrictMode, which reads the fragment twice', async () => {
    openAt(`/email/unsubscribe#token=${TOKEN}`)
    mocks.post.mockResolvedValue({ data: { status: 'unsubscribed' } })
    render(
      <StrictMode>
        <UnsubscribePage />
      </StrictMode>,
    )
    expect(window.location.hash).toBe('')
    expect(mocks.post).not.toHaveBeenCalled()
    await userEvent.setup().click(unsubscribeButton())
    expect(mocks.post).toHaveBeenCalledWith('/api/email/unsubscribe', { token: TOKEN })
  })
})

describe('a press posts the token once and says the answer', () => {
  it('done: says invitation emails stop and account emails still arrive, and hands focus to that answer', async () => {
    openAt(`/email/unsubscribe#token=${TOKEN}`)
    mocks.post.mockResolvedValue({ data: { status: 'unsubscribed' } })
    render(<UnsubscribePage />)
    const button = unsubscribeButton()
    button.focus()
    await userEvent.setup().click(button)
    expect(mocks.post).toHaveBeenCalledTimes(1)
    expect(mocks.post).toHaveBeenCalledWith('/api/email/unsubscribe', { token: TOKEN })
    const done = (await screen.findByText("You're unsubscribed")).closest('[role="status"]') as HTMLElement
    expect(done).toHaveTextContent(
      "We won't send invitation emails to this address. Emails about an account you create, such as password resets, still arrive.",
    )
    expect(screen.queryByRole('button', { name: 'Unsubscribe' })).not.toBeInTheDocument()
    expect(done.parentElement).toHaveFocus()
    expect(mocks.get).not.toHaveBeenCalled()
  })

  it('keeps the button focused but inert while the press is answered', async () => {
    openAt(`/email/unsubscribe#token=${TOKEN}`)
    const answer = deferred<{ data: { status: string } }>()
    mocks.post.mockReturnValue(answer.promise)
    render(<UnsubscribePage />)
    const user = userEvent.setup()
    const button = unsubscribeButton()
    await user.click(button)
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).not.toBeDisabled()
    expect(button).toHaveFocus()
    await user.click(button)
    expect(mocks.post).toHaveBeenCalledTimes(1)
    answer.resolve({ data: { status: 'unsubscribed' } })
    expect(await screen.findByText("You're unsubscribed")).toBeInTheDocument()
  })

  it.each([404, 422])('a %s: says the link is not valid and how to reach support, and stops offering the button', async (status) => {
    openAt(`/email/unsubscribe#token=${TOKEN}`)
    mocks.post.mockRejectedValue(new ApiError(status, "This unsubscribe link isn't valid."))
    render(<UnsubscribePage />)
    await userEvent.setup().click(unsubscribeButton())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("This link isn't valid")
    expect(alert).toHaveTextContent("It may be cut short or out of date. Write to support@earningsnerd.io and we'll stop invitation emails to your address.")
    expect(within(alert).getByRole('link', { name: CONTACT_ADDRESSES.support })).toHaveAttribute('href', `mailto:${CONTACT_ADDRESSES.support}`)
    expect(screen.queryByRole('button', { name: 'Unsubscribe' })).not.toBeInTheDocument()
    expect(alert.parentElement).toHaveFocus()
  })

  it('a 429: asks to try again later, and keeps the button for that', async () => {
    openAt(`/email/unsubscribe#token=${TOKEN}`)
    mocks.post.mockRejectedValue(new ApiError(429, 'Too many requests. Try again later.'))
    render(<UnsubscribePage />)
    await userEvent.setup().click(unsubscribeButton())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Too many tries for now')
    expect(alert).toHaveTextContent('Wait a while, then try again.')
    expect(unsubscribeButton()).not.toHaveAttribute('aria-disabled')
  })

  it.each([
    ['no answer from the network', () => Promise.reject(new ApiError(0, 'Could not reach the server. Try again in a moment.'))],
    ['a server error', () => Promise.reject(new ApiError(500, 'A server error occurred.'))],
    ['an answer that confirms nothing', () => Promise.resolve({ data: { status: 'pending' } })],
  ])('%s: says it could not unsubscribe, never that it did, and a second press posts again', async (_name, reply) => {
    openAt(`/email/unsubscribe#token=${TOKEN}`)
    mocks.post.mockImplementation(reply)
    render(<UnsubscribePage />)
    const user = userEvent.setup()
    await user.click(unsubscribeButton())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("We couldn't unsubscribe you just now")
    expect(screen.queryByText("You're unsubscribed")).not.toBeInTheDocument()
    await user.click(unsubscribeButton())
    expect(mocks.post).toHaveBeenCalledTimes(2)
  })
})

describe('without a token, the page says the email link is needed', () => {
  it.each([
    ['no fragment', '/email/unsubscribe'],
    ['an empty token', '/email/unsubscribe#token='],
    ['a fragment without one', '/email/unsubscribe#section=2'],
  ])('%s: names the email link and support, keeps the button focusable but unavailable, and posts nothing', async (_name, url) => {
    openAt(url)
    render(<UnsubscribePage />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('This page needs the link from your email')
    expect(alert).toHaveTextContent('Open the unsubscribe link in the invitation email: it carries the code this page needs.')
    expect(within(alert).getByRole('link', { name: CONTACT_ADDRESSES.support })).toHaveAttribute('href', `mailto:${CONTACT_ADDRESSES.support}`)
    const button = unsubscribeButton()
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).not.toBeDisabled()
    expect(button).toHaveAccessibleDescription(/^This page needs the link from your email/)
    await userEvent.setup().click(button)
    expect(mocks.post).not.toHaveBeenCalled()
    expect(mocks.get).not.toHaveBeenCalled()
    expect(window.location.hash).toBe('')
  })
})
