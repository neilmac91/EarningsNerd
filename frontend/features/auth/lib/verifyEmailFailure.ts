import { ApiError } from '@/lib/api/client'

/**
 * The reasons POST /api/auth/verify-email gives for a refused link, word for word
 * (`backend/app/routers/auth.py::verify_email`, both 400s). `tests/unit/authPagesCopy.spec.tsx` holds
 * this list to that file.
 */
export const VERIFY_EMAIL_REASONS: readonly string[] = [
  'Invalid or expired verification link.',
  'Verification link has expired. Request a new one.',
]

/** A refused link whose answer carries none of the server's reasons. */
export const VERIFY_LINK_FALLBACK = 'The link has expired, or a newer one replaced it.'
/** No answer about the link at all: a lost connection, a timeout, a server error, a rate limit. */
export const VERIFY_RETRY_FALLBACK = "We couldn't check the link just now. Reload this page to try again."

/**
 * What /verify-email says when the link is not accepted. The API client turns every failure into an
 * `ApiError` whose detail may be its own developer fallback (a lost connection names the API host) or
 * axios's bodiless "Request failed with status code 400", so the page shows the detail only when it is
 * one of the endpoint's own reasons, and its own sentence otherwise.
 */
export function verifyEmailFailureMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 400) {
    return VERIFY_EMAIL_REASONS.includes(err.detail) ? err.detail : VERIFY_LINK_FALLBACK
  }
  return VERIFY_RETRY_FALLBACK
}
