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
 * show the limits are the ones it applies: a name or message one character short, a name, subject or
 * message one character long (in code points, as Python's `len` counts: no field carries a native
 * maxLength, which counts UTF-16 units and would cut a message of 2,000 emoji the server accepts) and
 * an email `EmailStr` refuses, each refused before any request; the maximum in emoji is sent whole.
 */

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const schema = readFileSync(path.resolve(frontendDir, '../backend/app/schemas/contact.py'), 'utf8')
const createModel = schema.match(/class ContactSubmissionCreate\(BaseModel\):([\s\S]*?)\nclass /)?.[1] ?? ''
const requirements = readFileSync(path.resolve(frontendDir, '../backend/requirements.txt'), 'utf8')

/** The `package==version` pin of one package in a pip-compiled requirements text, or undefined. */
function pinOf(text: string, pkg: string): string | undefined {
  return text.match(new RegExp(`^${pkg}==([^\\s;#\\\\]+)`, 'm'))?.[1]
}

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
 * from email-validator 2.3.0 under pydantic 2.14.0, the pins in backend/requirements.txt (VERDICT_PINS,
 * asserted below, so a bump of either re-derives the table in the same PR), produced in the backend's
 * venv as pydantic runs it: `TypeAdapter(EmailStr).validate_python(address)`, which calls
 * `validate_email(address, check_deliverability=False)`, each address checked with the refusal caught. The table samples the typo shapes;
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

const VERDICT_PINS = { 'email-validator': '2.3.0', pydantic: '2.14.0' } as const

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

  it('the email table was derived under the email-validator and pydantic that backend/requirements.txt pins', () => {
    expect({
      'email-validator': pinOf(requirements, 'email-validator'),
      pydantic: pinOf(requirements, 'pydantic'),
    }).toEqual(VERDICT_PINS)
  })

  it('self-check: the pin reader takes the package line, never a neighbour that shares its prefix', () => {
    const sample = 'pydantic-core==2.50.0\n    # via\n    #   email-validator\npydantic==2.14.0\npydantic-settings==2.15.0\n'
    expect(pinOf(sample, 'pydantic')).toBe('2.14.0')
    expect(pinOf('pydantic-core==2.50.0\npydantic-settings==2.15.0\n', 'pydantic')).toBeUndefined()
    expect(pinOf('    # via email-validator\nemail-validator==2.3.0 \\\n', 'email-validator')).toBe('2.3.0')
  })

  it('the client email rule refuses every address EmailStr refuses in the table, and takes the plain ones', () => {
    const verdicts = Object.fromEntries(EMAIL_SAMPLES.map(([address]) => [address, isPlausibleEmail(address)]))
    expect(verdicts).toEqual(Object.fromEntries(EMAIL_SAMPLES))
  })

  it('the form applies those limits in code points: no native maxLength, and a value one short, one long or an email EmailStr refuses is refused before any request', () => {
    render(createElement(ContactForm))
    const name = screen.getByLabelText(/^Name/)
    const subject = screen.getByLabelText('Subject')
    const message = screen.getByLabelText(/^Message/)
    // A native maxLength counts UTF-16 units and would cut an emoji-heavy value the server accepts.
    expect(name).not.toHaveAttribute('maxLength')
    expect(subject).not.toHaveAttribute('maxLength')
    expect(message).not.toHaveAttribute('maxLength')

    const send = screen.getByRole('button', { name: 'Send message' })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.com' } })

    fireEvent.change(name, { target: { value: ` ${'A'.repeat(CONTACT_LIMITS.nameMin - 1)} ` } })
    fireEvent.change(message, { target: { value: 'A message long enough.' } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Your name needs at least ${CONTACT_LIMITS.nameMin} characters.`,
    )

    fireEvent.change(name, { target: { value: 'A'.repeat(CONTACT_LIMITS.nameMin) } })
    fireEvent.change(message, { target: { value: ` ${'m'.repeat(CONTACT_LIMITS.messageMin - 1)} ` } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Your message needs at least ${CONTACT_LIMITS.messageMin} characters.`,
    )

    // Five emoji are ten UTF-16 units but five code points, and the server's len() counts five.
    fireEvent.change(message, { target: { value: '\u{1F600}'.repeat(Math.ceil(CONTACT_LIMITS.messageMin / 2)) } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Your message needs at least ${CONTACT_LIMITS.messageMin} characters.`,
    )

    // One over each maximum, in code points, is refused with the sentence that names the bound: the
    // message case is astral, so its UTF-16 length is twice the count the server would refuse it on.
    fireEvent.change(message, { target: { value: 'A message long enough.' } })
    fireEvent.change(name, { target: { value: 'A'.repeat(CONTACT_LIMITS.nameMax + 1) } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(`Your name can be at most ${CONTACT_LIMITS.nameMax} characters.`)

    fireEvent.change(name, { target: { value: 'A'.repeat(CONTACT_LIMITS.nameMin) } })
    fireEvent.change(subject, { target: { value: 'S'.repeat(CONTACT_LIMITS.subjectMax + 1) } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(`Your subject can be at most ${CONTACT_LIMITS.subjectMax} characters.`)

    fireEvent.change(subject, { target: { value: '' } })
    fireEvent.change(message, { target: { value: '\u{1F600}'.repeat(CONTACT_LIMITS.messageMax + 1) } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Your message can be at most ${CONTACT_LIMITS.messageMax.toLocaleString('en-US')} characters.`,
    )

    fireEvent.change(message, { target: { value: 'A message long enough.' } })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@gmail' } })
    fireEvent.click(send)
    expect(screen.getByRole('alert')).toHaveTextContent('Please enter a valid email address.')
    expect(api.submitContactForm).not.toHaveBeenCalled()
  })

  it('a message of the maximum in emoji, twice that in UTF-16 units, is sent whole', async () => {
    api.submitContactForm.mockResolvedValue({})
    render(createElement(ContactForm))
    const message = '\u{1F600}'.repeat(CONTACT_LIMITS.messageMax)
    expect(message.length).toBe(CONTACT_LIMITS.messageMax * 2)
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.com' } })
    fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: message } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await screen.findByRole('heading', { name: 'Message sent' })
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)
    expect(api.submitContactForm.mock.calls[0][0].message).toBe(message)
  })
})
