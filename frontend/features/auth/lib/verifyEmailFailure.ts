import { ApiError } from '@/lib/api/client'

/**
 * The reasons POST /api/auth/verify-email gives for a refused link, word for word
 * (`backend/app/routers/auth.py::verify_email`, both 400s). `tests/unit/authPagesCopy.spec.tsx` holds
 * this list to that file.
 */
const LINK_UNKNOWN_OR_USED = 'Invalid or expired verification link.'
/** Said only of a token the server still holds, past its expiry: no earlier press can have verified with it. */
const LINK_EXPIRED = 'Verification link has expired. Request a new one.'
export const VERIFY_EMAIL_REASONS: readonly string[] = [LINK_UNKNOWN_OR_USED, LINK_EXPIRED]

/** A refused link whose answer carries none of the server's reasons. */
export const VERIFY_LINK_FALLBACK = 'The link has expired, or a newer one replaced it.'
/**
 * No answer about the link at all (a lost connection, a timeout, a server error, a rate limit): the notice /verify-email
 * shows above its button, which the reader can press again, since the token is unspent and still in the page's state.
 */
export const VERIFY_UNANSWERED_TITLE = "We couldn't check the link just now"
export const VERIFY_UNANSWERED_DESCRIPTION = 'Try again in a minute.'
/**
 * Added to a refusal that follows a press with no answer in the same visit, where that press may have verified the
 * address before its answer was lost. Verifying spends the token, so the refusal then describes the second press,
 * not the account, and a new link would not come (only an unverified account is sent one). Logging in shows which it
 * is. It is added only where both halves can be true: the unanswered press may have reached the route (no answer at
 * all, or a server error; a rate limit or another refusal never ran it), and the refusal is one a spent token gets
 * (an "expired" answer is given only for a token the server still holds).
 */
export const VERIFY_FIRST_TRY_HINT = 'Your first try may have gone through. Log in to check whether your email is verified.'

/**
 * What a failed press of Verify email means for the page. Only a 400 is about the link: the server refused it, so its
 * token is spent or bad and the page says why, with no second press (`retryable: false`; `spentTokenAnswer` says
 * whether a token an earlier press spent would get this same answer). Anything else told the page nothing about the
 * link, so the button stays (`retryable: true`; `mayHaveVerified` says whether the press may still have run the
 * route and verified the address).
 *
 * The API client turns every failure into an `ApiError` whose detail may be its own developer fallback (a lost
 * connection names the API host) or axios's bodiless "Request failed with status code 400", so a refusal shows its
 * detail only when it is one of the endpoint's own reasons, and the page's own sentence otherwise.
 */
export type VerifyEmailFailure =
  | { retryable: false; message: string; spentTokenAnswer: boolean }
  | { retryable: true; mayHaveVerified: boolean }

export function readVerifyEmailFailure(err: unknown): VerifyEmailFailure {
  if (err instanceof ApiError && err.status === 400) {
    return {
      retryable: false,
      message: VERIFY_EMAIL_REASONS.includes(err.detail) ? err.detail : VERIFY_LINK_FALLBACK,
      spentTokenAnswer: err.detail !== LINK_EXPIRED,
    }
  }
  // No answer at all (the client's status 0) or a server error can follow a verification that committed; a rate
  // limit or any other refusal answered before the route verified anything.
  const status = err instanceof ApiError ? err.status : 0
  return { retryable: true, mayHaveVerified: status === 0 || status >= 500 }
}
