/**
 * The contact form's field limits, the same numbers as the backend's
 * `ContactSubmissionCreate` (backend/app/schemas/contact.py): a value the form accepts is one the
 * server accepts, so a send never fails on a 422 the reader could not see coming. Lengths count the
 * trimmed value, as both sides do. `tests/unit/contactValidationParity.spec.ts` holds the two
 * together.
 */
export const CONTACT_LIMITS = {
  nameMin: 2,
  nameMax: 100,
  subjectMax: 200,
  messageMin: 10,
  messageMax: 2000,
} as const
