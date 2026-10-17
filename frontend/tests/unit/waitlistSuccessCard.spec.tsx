import { afterEach, describe, expect, it, vi } from 'vitest'
import type { MouseEvent, ReactNode } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
// axios's own settle (its xhr, http and fetch adapters end with it): the stub adapter below applies the
// request's validateStatus exactly as a real response would.
import settle from 'axios/unsafe/core/settle.js'
import client from '@/lib/api/client'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import { REFERRAL_BONUS } from '@/features/waitlist/lib/referral'

/**
 * The waitlist success card (audit pub/F02, BG-10): the heading is the backend's join message, with a
 * fallback that renders as text (an HTML entity in a JS string is not decoded); the referral sentence is
 * stated once, from REFERRAL_BONUS, beside the link the backend now points at /waitlist?ref=. The form
 * submits the ?ref= it was opened with, which is how a referral is counted. The link is set in the data
 * face, so its code reads as typed, and the share links wrap inside the card at 200% text. A code no
 * signup holds is answered 400 with the router's code and no `detail`: the form routes on the code to its
 * own sentence, never on the router's words, and never prints axios's "Request failed with status code 400".
 * Under it, "Join without the code" links to /waitlist (F47, D-046), and the submit after it carries no code.
 */

const api = vi.hoisted(() => ({ joinWaitlist: vi.fn() }))
vi.mock('@/features/waitlist/api/waitlist-api', () => ({ joinWaitlist: api.joinWaitlist }))
// The page's URL, which the form reads its code from. A client-side navigation (the next/link stand-in below)
// changes it and re-renders the hook's readers without remounting them, as the App Router does for search params.
const url = vi.hoisted(() => {
  const opened = 'ref=ABC12345'
  let search = opened
  const listeners = new Set<() => void>()
  return {
    read: () => search,
    go(href: string) {
      search = new URL(href, 'https://earningsnerd.io').search.slice(1)
      listeners.forEach((listener) => listener())
    },
    reset: () => {
      search = opened
    },
    subscribe(listener: () => void) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
  }
})
vi.mock('next/navigation', async () => {
  const { useSyncExternalStore } = await import('react')
  return { useSearchParams: () => new URLSearchParams(useSyncExternalStore(url.subscribe, url.read, url.read)) }
})
vi.mock('next/link', () => ({
  default: ({ href, onClick, children, scroll: _scroll, ...props }: { href: string; onClick?: (event: MouseEvent<HTMLAnchorElement>) => void; children: ReactNode; scroll?: boolean; [key: string]: unknown }) => (
    <a
      href={href}
      {...props}
      onClick={(event) => {
        onClick?.(event)
        event.preventDefault()
        url.go(href)
      }}
    >
      {children}
    </a>
  ),
}))
afterEach(() => url.reset())
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  TURNSTILE_ENABLED: false,
}))

const link = 'https://earningsnerd.io/waitlist?ref=new00001'

async function join(message: string | undefined) {
  api.joinWaitlist.mockResolvedValueOnce({ success: true, message, position: 42, referral_code: 'new00001', referral_link: link })
  render(<WaitlistForm source="waitlist" />)
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'ada@example.test' } })
  fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
  return screen.findByRole('heading', { level: 2 })
}

describe('waitlist success card', () => {
  it('renders the backend message as its heading and submits the ?ref= it was opened with', async () => {
    expect(await join("You're on the waitlist.")).toHaveTextContent("You're on the waitlist.")
    expect(api.joinWaitlist).toHaveBeenCalledWith(expect.objectContaining({ referral_code: 'abc12345' }), undefined)
  })

  it('falls back to readable text, never an HTML entity', async () => {
    const heading = await join('')
    expect(heading.textContent).toBe("You're on the waitlist.")
  })

  it('states the referral bonus once, from REFERRAL_BONUS, beside the link', async () => {
    await join("You're on the waitlist.")
    expect(screen.getByText(link)).toBeInTheDocument()
    const sentence = `Each person who joins with your link moves you up ${REFERRAL_BONUS} spots.`
    expect(screen.getAllByText(sentence)).toHaveLength(1)
    expect(document.body.textContent?.match(/\bspots?\b/g)).toHaveLength(1)
  })

  it('sets the link in the data face, whose Geist Mono draws the x of a code as typed', async () => {
    await join("You're on the waitlist.")
    expect(screen.getByText(link)).toHaveClass('font-data')
  })

  it('lets the share links wrap inside the card (DESIGN_SYSTEM.md, Wrapping button)', async () => {
    await join("You're on the waitlist.")
    for (const name of ['Share on Twitter', 'Share on LinkedIn', 'Share on WhatsApp']) {
      const classes = screen.getByRole('link', { name }).className.split(/\s+/)
      expect(classes, name).toEqual(expect.arrayContaining(['whitespace-normal', 'max-w-full']))
      expect(classes, name).not.toContain('whitespace-nowrap')
    }
  })
})

describe('waitlist join refused', () => {
  // The router's 400 (routers/watchlist.py, join_waitlist): its code and its own words, no `detail`. The real
  // joinWaitlist sends the join through the shared client, whose adapter answers here. Resolves to the alert.
  async function joinRefused() {
    const body = { success: false, error: 'invalid_referral', message: 'Referral code not recognized.' }
    const actual = await vi.importActual<typeof import('@/features/waitlist/api/waitlist-api')>('@/features/waitlist/api/waitlist-api')
    const adapter = client.defaults.adapter
    client.defaults.adapter = (config: InternalAxiosRequestConfig) =>
      new Promise<AxiosResponse>((resolve, reject) =>
        settle(resolve, reject, { data: body, status: 400, statusText: 'Bad Request', headers: {}, config, request: {} }),
      )
    api.joinWaitlist.mockImplementationOnce(actual.joinWaitlist)
    try {
      render(<WaitlistForm source="waitlist" />)
      fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'ada@example.test' } })
      fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
      return await screen.findByRole('alert')
    } finally {
      client.defaults.adapter = adapter
    }
  }

  it('routes an unknown referral code by its error code to its own sentence', async () => {
    const alert = await joinRefused()
    // One phrase as the title, the second sentence the description (lessons/frontend-a-notice-title-is-one-phrase.md).
    expect(within(alert).getByText("We can't find this referral code on the waitlist")).toBeInTheDocument()
    expect(within(alert).getByText('Check the link with whoever shared it.')).toBeInTheDocument()
    expect(alert).not.toHaveTextContent(/status code|not recognized/i)
  })

  it('offers "Join without the code" under the message, a link to /waitlist with no ?ref= (F47, D-046)', async () => {
    const alert = await joinRefused()
    expect(within(alert).getByRole('link', { name: 'Join without the code' })).toHaveAttribute('href', '/waitlist')
  })

  it('sends no referral code on the submit after following it, the email still typed', async () => {
    const alert = await joinRefused()
    expect(api.joinWaitlist).toHaveBeenLastCalledWith(expect.objectContaining({ referral_code: 'abc12345' }), undefined)
    fireEvent.click(within(alert).getByRole('link', { name: 'Join without the code' }))
    // The refusal is gone with the code it was about, and focus waits in the email field it kept.
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByLabelText('Email address')).toHaveFocus()
    expect(screen.getByLabelText('Email address')).toHaveValue('ada@example.test')

    api.joinWaitlist.mockResolvedValueOnce({ success: true, message: "You're on the waitlist.", position: 43, referral_code: 'new00002', referral_link: link })
    fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
    expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent("You're on the waitlist.")
    expect(api.joinWaitlist).toHaveBeenLastCalledWith(expect.objectContaining({ referral_code: null }), undefined)
  })
})
