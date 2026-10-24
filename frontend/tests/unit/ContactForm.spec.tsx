import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ContactForm from '@/features/contact/components/ContactForm'
import { ApiError } from '@/lib/api/client'

/**
 * What a failed contact send tells the reader (audit UA-24, UA-25) and the success panel's outline
 * (UA-21). The rate limit is mapped from the status, never from the words of the message: the
 * backend's 429 sentence ("Too many requests. Please try again in 1 hour(s).") holds no "429", so a
 * match on the text never fired. A 422 asks the reader to check the fields, since sending the same
 * values again fails the same way. A 5xx shows the surface's sentence: the route's own 500 detail
 * ("Failed to save contact form submission") is developer wording with no next step, and the
 * client's own 503 sentence ("Service temporarily unavailable…") stops there too. On any other
 * status the backend's own detail is shown when the body carried a non-blank one
 * (`ApiError.backendDetail`; a whitespace-only detail counts as none), and the surface's sentence when
 * it did not: lib/api/client's connection fallback ("Could not reach the
 * server…") and axios's "Request failed with status code N" sit in `detail` and never reach
 * the reader. The failure is a Notice: role="alert", title "Message not sent". The success heading
 * is an h2 under the page's h1.
 */

const api = vi.hoisted(() => ({ submitContactForm: vi.fn() }))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: api.submitContactForm }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  TURNSTILE_ENABLED: false,
}))

const RATE_LIMITED = 'Too many messages from this connection. Try again in an hour.'
const CHECK_FIELDS = 'Check the fields and send again.'
const SEND_FAILED = "We couldn't send your message. Try again in a minute."

/** An ApiError as the response interceptor builds it when the body carried a string `detail`. */
function backendError(status: number, detail: string): ApiError {
  const err = new ApiError(status, detail)
  err.backendDetail = detail
  return err
}

afterEach(() => {
  cleanup()
  api.submitContactForm.mockReset()
})

function fillAndSend() {
  render(<ContactForm />)
  fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
  fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.com' } })
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
    api.submitContactForm.mockRejectedValue(backendError(400, 'Request 429 was refused.'))
    fillAndSend()
    expect(await failure()).toBe('Request 429 was refused.')
  })

  it("a 5xx shows the surface's sentence, never the route's save-failure string", async () => {
    api.submitContactForm.mockRejectedValue(backendError(500, 'Failed to save contact form submission'))
    fillAndSend()
    expect(await failure()).toBe(SEND_FAILED)
  })

  it.each([
    ['a validation list', new ApiError(422, [{ loc: ['body', 'email'], msg: 'not valid', type: 'value_error' }] as unknown as string)],
    ['a string detail', backendError(422, 'value is not a valid email address')],
  ])('a 422 with %s asks the reader to check the fields', async (_label, err) => {
    api.submitContactForm.mockRejectedValue(err)
    fillAndSend()
    expect(await failure()).toBe(CHECK_FIELDS)
  })

  it.each([
    ['a failed connection', new ApiError(0, 'Could not reach the server. Try again in a moment.')],
    ["axios's message for a bodiless 413", new ApiError(413, 'Request failed with status code 413')],
    ["the client's own 503 sentence, through the 5xx branch", new ApiError(503, 'Service temporarily unavailable. Please try again in a moment.')],
    ['an empty backend detail on a 4xx', backendError(400, '  ')],
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
    expect(screen.getByText('Thanks for your message. The aim is to reply within 2 business days.')).toBeInTheDocument()
  })
})
