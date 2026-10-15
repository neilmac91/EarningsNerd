import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import { REFERRAL_BONUS } from '@/features/waitlist/lib/referral'

/**
 * The waitlist success card (audit pub/F02, BG-10): the heading is the backend's join message, with a
 * fallback that renders as text (an HTML entity in a JS string is not decoded); the referral sentence is
 * stated once, from REFERRAL_BONUS, beside the link the backend now points at /waitlist?ref=. The form
 * submits the ?ref= it was opened with, which is how a referral is counted.
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
})
