import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ContactForm from '@/features/contact/components/ContactForm'
import { ApiError } from '@/lib/api/client'

/**
 * What a failed contact send tells the reader (audit UA-24, UA-25) and the success panel's outline
 * (UA-21). The rate limit is mapped from the status, never from the words of the message: the
 * backend's 429 sentence ("Too many requests. Please try again in 1 hour(s).") holds no "429", so a
 * match on the text never fired. A string detail is the backend's own sentence and is shown; a
 * non-string or empty detail (FastAPI's validation list, a bare error) shows the fallback. The failure
 * is a Notice: role="alert", title "Message not sent". The success heading is an h2 under the page's h1.
 */

const api = vi.hoisted(() => ({ submitContactForm: vi.fn() }))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: api.submitContactForm }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  TURNSTILE_ENABLED: false,
}))

const RATE_LIMITED = 'Too many messages from this connection. Try again in an hour.'
const SEND_FAILED = "We couldn't send your message. Try again in a minute."

afterEach(() => {
  cleanup()
  api.submitContactForm.mockReset()
})

function fillAndSend() {
  render(<ContactForm />)
  fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
  fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.test' } })
  fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: 'A message long enough.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
}

/** The failure Notice: its title, then the sentence under it. */
async function failure(): Promise<string> {
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(/^Message not sent/)
  return alert.textContent!.replace(/^Message not sent/, '')
}

describe('ContactForm send errors', () => {
  it('a 429 shows the hour sentence, whatever its detail says', async () => {
    api.submitContactForm.mockRejectedValue(new ApiError(429, 'Too many requests. Please try again in 1 hour(s).'))
    fillAndSend()
    expect(await failure()).toBe(RATE_LIMITED)
  })

  it('a "429" in the words of another status is not the rate limit', async () => {
    api.submitContactForm.mockRejectedValue(new ApiError(400, 'Request 429 was refused.'))
    fillAndSend()
    expect(await failure()).toBe('Request 429 was refused.')
  })

  it("the backend's string detail is shown as it came", async () => {
    api.submitContactForm.mockRejectedValue(new ApiError(503, 'Service temporarily unavailable. Please try again in a moment.'))
    fillAndSend()
    expect(await failure()).toBe('Service temporarily unavailable. Please try again in a moment.')
  })

  it.each([
    ['a validation list', new ApiError(422, [{ loc: ['body', 'name'], msg: 'too short', type: 'value_error' }] as unknown as string)],
    ['an empty detail', new ApiError(500, '  ')],
    ['an error that is not the API client', new TypeError('Failed to fetch')],
    ['a thrown string', 'boom'],
  ])('%s shows the fallback', async (_label, err) => {
    api.submitContactForm.mockRejectedValue(err)
    fillAndSend()
    expect(await failure()).toBe(SEND_FAILED)
  })
})

describe('ContactForm success panel', () => {
  it('"Message sent" is an h2 with the reply sentence', async () => {
    api.submitContactForm.mockResolvedValue({})
    fillAndSend()
    const heading = await screen.findByRole('heading', { name: 'Message sent' })
    expect(heading.tagName).toBe('H2')
    expect(screen.getByText('We have your message and will reply within 1–2 business days.')).toBeInTheDocument()
  })
})
