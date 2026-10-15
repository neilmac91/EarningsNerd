import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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
 */

const api = vi.hoisted(() => ({ joinWaitlist: vi.fn() }))
vi.mock('@/features/waitlist/api/waitlist-api', () => ({ joinWaitlist: api.joinWaitlist }))
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams('ref=ABC12345') }))
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
  it('routes an unknown referral code by its error code to its own sentence', async () => {
    // The router's 400 (routers/watchlist.py, join_waitlist): its code and its own words, no `detail`. The
    // real joinWaitlist sends the join through the shared client, whose adapter answers here.
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
      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent("We can't find this referral code on the waitlist. Check the link with whoever shared it.")
      expect(alert).not.toHaveTextContent(/status code|not recognized/i)
    } finally {
      client.defaults.adapter = adapter
    }
  })
})
