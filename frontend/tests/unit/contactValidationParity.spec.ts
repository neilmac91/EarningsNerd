import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ContactForm from '@/features/contact/components/ContactForm'
import { CONTACT_LIMITS, isPlausibleEmail } from '@/features/contact/lib/limits'

/**
 * The contact form accepts what the server accepts for the name, subject and message, and refuses
 * the email typos the server refuses (CLAUDE.md rule 12; audit UA-24). The backend's
 * `ContactSubmissionCreate` (backend/app/schemas/contact.py) bounds each field with
 * `Field(min_length, max_length)`, re-checks the trimmed name and message in its validators, and
 * types the email `EmailStr`; a value the form let through and the server refused came back as a 422
 * the reader could not act on (a one-letter name did, before this gate, and so did `ada@gmail`). This
 * spec reads the Python and holds `features/contact/lib/limits.ts` to it, then renders the form to
 * show the limits are the ones it applies: each field's maxLength, a name or message one character
 * short (in code points, as Python's `len` counts) and an email `EmailStr` refuses, each refused
 * before any request.
 */

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const schema = readFileSync(path.resolve(frontendDir, '../backend/app/schemas/contact.py'), 'utf8')
const createModel = schema.match(/class ContactSubmissionCreate\(BaseModel\):([\s\S]*?)\nclass /)?.[1] ?? ''

/** `min_length` or `max_length` of one field's `Field(...)` declaration. */
function fieldBound(field: string, bound: 'min_length' | 'max_length'): number {
  const decl = createModel.match(new RegExp(`^\\s+${field}: [^\\n]*?= Field\\(([^\\n]*)\\)\\s*$`, 'm'))?.[1]
  if (!decl) throw new Error(`${field} has no Field(...) in ContactSubmissionCreate`)
  const value = decl.match(new RegExp(`\\b${bound}=(\\d+)`))?.[1]
  if (!value) throw new Error(`${field}'s Field(...) has no ${bound}`)
  return Number(value)
}

/** The `len(v) < N` floor a field's validator applies to the trimmed value. */
function validatorFloor(field: string): number {
  const body = createModel.match(new RegExp(`@field_validator\\("${field}"\\)([\\s\\S]*?)(?=\\n    @field_validator|$)`))?.[1]
  if (!body) throw new Error(`${field} has no field_validator in ContactSubmissionCreate`)
  const value = body.match(/if len\(v\) < (\d+):/)?.[1]
  if (!value) throw new Error(`${field}'s validator has no len(v) floor`)
  return Number(value)
}

/**
 * Addresses and the verdict the backend's `EmailStr` gives each (true = accepted). The verdicts come
 * from email-validator 2.3.0 under pydantic 2.13.5, the pins in backend/requirements.txt, produced in
 * the backend's venv as pydantic runs it: `validate_email(address, check_deliverability=False)`, each
 * address checked with `EmailNotValidError` caught as the refusal. The table samples the typo shapes;
 * `EmailStr` also refuses rarer forms the client rule does not check (a reserved domain such as
 * `.test`, a period just before the @-sign, a label opening with a hyphen), and such an address comes
 * back as a 422 that asks the reader to check the fields. The client may be stricter than `EmailStr`
 * (it refuses `Ada <ada@example.com>`, which pydantic takes), never looser on this table.
 */
const EMAIL_SAMPLES: ReadonlyArray<readonly [string, boolean]> = [
  ['ada@example.com', true],
  ['ada.lovelace@mail.example.co.uk', true],
  ['ada+notes@example.org', true],
  ['ADA@EXAMPLE.COM', true],
  ['ada@gmail', false],
  ['ada@localhost', false],
  ['ada', false],
  ['ada@', false],
  ['@example.com', false],
  ['ada@@example.com', false],
  ['ada@ex@ample.com', false],
  ['ada lovelace@example.com', false],
  ['ada@exam ple.com', false],
  ['ada@.example.com', false],
  ['ada@example..com', false],
  ['ada@example.com.', false],
  ['ada@example.', false],
]

const api = vi.hoisted(() => ({ submitContactForm: vi.fn() }))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: api.submitContactForm }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  TURNSTILE_ENABLED: false,
}))

afterEach(() => {
  cleanup()
  api.submitContactForm.mockReset()
})

describe('contact form limits equal the backend schema', () => {
  it('reads the backend model', () => {
    expect(createModel, 'ContactSubmissionCreate not found in backend/app/schemas/contact.py').not.toBe('')
  })

  it('the name, subject and message bounds match Field(...) and the validators', () => {
    expect({
      nameMin: fieldBound('name', 'min_length'),
      nameMax: fieldBound('name', 'max_length'),
      subjectMax: fieldBound('subject', 'max_length'),
      messageMin: fieldBound('message', 'min_length'),
      messageMax: fieldBound('message', 'max_length'),
    }).toEqual(CONTACT_LIMITS)
    // The validators re-check the trimmed value; the form trims before it checks and sends.
    expect(validatorFloor('name')).toBe(CONTACT_LIMITS.nameMin)
    expect(validatorFloor('message')).toBe(CONTACT_LIMITS.messageMin)
  })

  it('the schema still types the email EmailStr', () => {
    expect(createModel).toMatch(/^\s+email: EmailStr = Field\(/m)
  })

  it('the client email rule refuses every address EmailStr refuses in the table, and takes the plain ones', () => {
    const verdicts = Object.fromEntries(EMAIL_SAMPLES.map(([address]) => [address, isPlausibleEmail(address)]))
    expect(verdicts).toEqual(Object.fromEntries(EMAIL_SAMPLES))
  })

  it('the form applies those limits: maxLength on each field, and a value one short or an email EmailStr refuses is refused before any request', () => {
    render(createElement(ContactForm))
    const name = screen.getByLabelText(/^Name/)
    const subject = screen.getByLabelText('Subject')
    const message = screen.getByLabelText(/^Message/)
    expect(name).toHaveAttribute('maxLength', String(CONTACT_LIMITS.nameMax))
    expect(subject).toHaveAttribute('maxLength', String(CONTACT_LIMITS.subjectMax))
    expect(message).toHaveAttribute('maxLength', String(CONTACT_LIMITS.messageMax))

    const send = screen.getByRole('button', { name: 'Send message' })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.com' } })

    fireEvent.change(name, { target: { value: ` ${'A'.repeat(CONTACT_LIMITS.nameMin - 1)} ` } })
    fireEvent.change(message, { target: { value: 'A message long enough.' } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Please enter at least ${CONTACT_LIMITS.nameMin} characters for your name.`,
    )

    fireEvent.change(name, { target: { value: 'A'.repeat(CONTACT_LIMITS.nameMin) } })
    fireEvent.change(message, { target: { value: ` ${'m'.repeat(CONTACT_LIMITS.messageMin - 1)} ` } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Message must be at least ${CONTACT_LIMITS.messageMin} characters long.`,
    )

    // Five emoji are ten UTF-16 units but five code points, and the server's len() counts five.
    fireEvent.change(message, { target: { value: '\u{1F600}'.repeat(Math.ceil(CONTACT_LIMITS.messageMin / 2)) } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Message must be at least ${CONTACT_LIMITS.messageMin} characters long.`,
    )

    fireEvent.change(message, { target: { value: 'A message long enough.' } })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@gmail' } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent('Please enter a valid email address.')
    expect(api.submitContactForm).not.toHaveBeenCalled()
  })
})
