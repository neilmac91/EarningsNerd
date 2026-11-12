/**
 * Backend OAuth start URL for a plain social sign-in (no invite): a top-level navigation to the
 * redirecting GET. An invited sign-up never puts the token in a URL (request logs record query
 * strings): it goes through `startOAuthWithInvite` in `features/auth/api/auth-api`, which POSTs the
 * invite in the request body and returns the provider URL to navigate to.
 *
 * `handoff=1` asks the API to hand the sign-in to this frontend's landing page (app/auth/complete/page.tsx, E29 (5)):
 * the callback then sets no session cookie on its redirect and passes a one-time code the page exchanges under the
 * session cookies' lock. The API hands every sign-in off, ask or no ask, and records the ask for an API rolled back to
 * a revision that reads it; one that predates the handoff ignores it and sets the cookies on the redirect, as before,
 * so the API can roll back alone at any time (startOAuthWithInvite sends the same ask). The frontend cannot: every
 * Google or Apple sign-in lands on that page, so it is the frontend's rollback floor (docs/DEPLOYMENT.md).
 */
export const oauthStartHref = (apiBase: string, provider: 'google' | 'apple'): string =>
  `${apiBase}/api/auth/${provider}?handoff=1`
