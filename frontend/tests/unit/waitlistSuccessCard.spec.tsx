import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MouseEvent, ReactNode } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
// axios's own settle (its xhr, http and fetch adapters end with it): the stub adapter below applies the
// request's validateStatus exactly as a real response would.
import settle from 'axios/unsafe/core/settle.js'
import client, { ApiError } from '@/lib/api/client'
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
 * A Ctrl or Cmd click opens the link in a new tab and leaves this one as it was. A Turnstile token verifies
 * once, so a join that does not land renews the widget, and the next submit carries a new token.
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
type LinkStandInProps = {
  href: string
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void
  onNavigate?: (event: { preventDefault: () => void }) => void
  scroll?: boolean
  children: ReactNode
  [key: string]: unknown
}
// next/link 16 as it handles a click (client/app-dir/link.js): onClick runs on every click. A modified click (Ctrl,
// Cmd, Shift or Alt: a new tab or window) is the browser's, and only a plain one calls onNavigate and then navigates,
// here by changing the URL. The scroll prop shows as data-scroll.
vi.mock('next/link', () => ({
  default: ({ href, onClick, onNavigate, scroll, children, ...props }: LinkStandInProps) => (
    <a
      href={href}
      data-scroll={scroll === undefined ? undefined : String(scroll)}
      {...props}
      onClick={(event) => {
        onClick?.(event)
        if (event.defaultPrevented) return
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {
          // The browser opens the link in a new tab and this one stays as it was; jsdom cannot open one.
          event.preventDefault()
          return
        }
        event.preventDefault()
        let navigationPrevented = false
        onNavigate?.({ preventDefault: () => (navigationPrevented = true) })
        if (!navigationPrevented) url.go(href)
      }}
    >
      {children}
    </a>
  ),
}))
// Turnstile, off as CI builds it unless a case turns it on. On, each mount of the widget yields a new token, as a
// new Cloudflare widget does.
const turnstile = vi.hoisted(() => ({ on: false, mounts: 0 }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  get TURNSTILE_ENABLED() {
    return turnstile.on
  },
}))
vi.mock('@/features/auth/components/TurnstileWidget', async () => {
  const { useEffect } = await import('react')
  return {
    default: function TurnstileWidget({ onToken }: { onToken: (token: string) => void }) {
      useEffect(() => {
        if (turnstile.on) onToken(`token-${++turnstile.mounts}`)
      }, [onToken])
      return null
    },
  }
})
afterEach(() => {
  url.reset()
  turnstile.on = false
  turnstile.mounts = 0
})

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

  // The waitlist page centres this column below lg (`app/waitlist/page.tsx`). A Notice's title and description would
  // inherit it while its action row stays at the start, so each Notice in the form sets its own text to the start.
  it('sets the refusal to the start, inside a column the page centres below lg', async () => {
    expect(await joinRefused()).toHaveClass('text-left')
  })

  it('sets the error Notice to the start too', async () => {
    api.joinWaitlist.mockRejectedValueOnce(new ApiError(0, 'Network Error'))
    render(<WaitlistForm source="waitlist" />)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'ada@example.test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
    expect(await screen.findByRole('alert')).toHaveClass('text-left')
  })

  it('offers "Join without the code" under the message, a link to /waitlist with no ?ref= (F47, D-046)', async () => {
    const alert = await joinRefused()
    const joinWithout = within(alert).getByRole('link', { name: 'Join without the code' })
    expect(joinWithout).toHaveAttribute('href', '/waitlist')
    // scroll={false}: the reader stays at the form, where focus goes.
    expect(joinWithout).toHaveAttribute('data-scroll', 'false')
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

  it('keeps the refusal on a Ctrl or Cmd click, which opens the link in a new tab and leaves this one on its ?ref=', async () => {
    const alert = await joinRefused()
    for (const modifier of ['ctrlKey', 'metaKey']) {
      fireEvent.click(within(alert).getByRole('link', { name: 'Join without the code' }), { [modifier]: true })
      expect(screen.queryByRole('alert'), modifier).toBe(alert)
    }
    expect(screen.getByLabelText('Email address')).not.toHaveFocus()
  })

  // The router verifies the Turnstile token before it reads the code, and Cloudflare verifies a token once (siteverify
  // answers timeout-or-duplicate after), so a join that does not land renews the widget for the next submit.
  describe('with Turnstile on', () => {
    const joined = { success: true, message: "You're on the waitlist.", position: 43, referral_code: 'new00002', referral_link: link }
    beforeEach(() => {
      turnstile.on = true
      // Its calls and any answer a failed case left queued.
      api.joinWaitlist.mockReset()
    })

    it('sends a new token on the join without the code', async () => {
      const alert = await joinRefused()
      fireEvent.click(within(alert).getByRole('link', { name: 'Join without the code' }))
      api.joinWaitlist.mockResolvedValueOnce(joined)
      fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
      expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent("You're on the waitlist.")
      expect(api.joinWaitlist.mock.calls.map(([join, token]) => [join.referral_code, token])).toEqual([
        ['abc12345', 'token-1'],
        [null, 'token-2'],
      ])
    })

    it.each([
      ['a rate limit', new ApiError(429, 'Too many waitlist requests. Please try again later.')],
      ['a network error', new ApiError(0, 'Network Error')],
    ])('sends a new token on the retry after %s', async (_, failure) => {
      api.joinWaitlist.mockRejectedValueOnce(failure)
      render(<WaitlistForm source="waitlist" />)
      fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'ada@example.test' } })
      fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
      await screen.findByRole('alert')
      api.joinWaitlist.mockResolvedValueOnce(joined)
      fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
      expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent("You're on the waitlist.")
      expect(api.joinWaitlist.mock.calls.map(([, token]) => token)).toEqual(['token-1', 'token-2'])
    })
  })
})
