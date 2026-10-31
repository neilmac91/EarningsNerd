/**
 * The contact form's field limits, the same numbers as the backend's
 * `ContactSubmissionCreate` (backend/app/schemas/contact.py), and a client email rule that refuses
 * the typo shapes its `EmailStr` refuses: a name, subject or message the form accepts is one the
 * server accepts, and so is an email that passes `isPlausibleEmail`, except for the rarer forms
 * `EmailStr` also refuses (a reserved domain such as `.test`, a period just before the @-sign). A 422
 * the client could not foresee asks the reader to check the fields. Lengths count the trimmed value
 * in code points, as Python's `len` does. `tests/unit/contactValidationParity.spec.ts` holds the two
 * sides together.
 */
export const CONTACT_LIMITS = {
  nameMin: 2,
  nameMax: 100,
  subjectMax: 200,
  messageMin: 10,
  messageMax: 2000,
} as const

/** The trimmed value's length in code points (an emoji counts once, as on the server). */
export function trimmedLength(value: string): number {
  return Array.from(value.trim()).length
}

/** One @-sign, no whitespace, something before it, and a domain of two or more non-empty labels. */
export function isPlausibleEmail(value: string): boolean {
  if (/\s/.test(value)) return false
  const parts = value.split('@')
  if (parts.length !== 2 || !parts[0]) return false
  const labels = parts[1].split('.')
  return labels.length >= 2 && labels.every((label) => label.length > 0)
}
