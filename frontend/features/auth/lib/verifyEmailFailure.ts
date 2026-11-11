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
/**
 * No answer about the link at all (a lost connection, a timeout, a server error, a rate limit): the notice /verify-email
 * shows above its button, which the reader can press again, since the token is unspent and still in the page's state.
 */
export const VERIFY_UNANSWERED_TITLE = "We couldn't check the link just now"
export const VERIFY_UNANSWERED_DESCRIPTION = 'Try again in a minute.'

/**
 * What a failed press of Verify email means for the page. Only a 400 is about the link: the server refused it, so its
 * token is spent or bad and the page says why, with no second press (`retryable: false`). Anything else told the page
 * nothing about the link, so the token is unspent and the button stays (`retryable: true`).
 *
 * The API client turns every failure into an `ApiError` whose detail may be its own developer fallback (a lost
 * connection names the API host) or axios's bodiless "Request failed with status code 400", so a refusal shows its
 * detail only when it is one of the endpoint's own reasons, and the page's own sentence otherwise.
 */
export type VerifyEmailFailure = { retryable: false; message: string } | { retryable: true }

export function readVerifyEmailFailure(err: unknown): VerifyEmailFailure {
  if (err instanceof ApiError && err.status === 400) {
    return { retryable: false, message: VERIFY_EMAIL_REASONS.includes(err.detail) ? err.detail : VERIFY_LINK_FALLBACK }
  }
  return { retryable: true }
}
