/**
 * Backend OAuth start URL for a plain social sign-in (no invite): a top-level navigation to the
 * redirecting GET. An invited sign-up never puts the token in a URL (request logs record query
 * strings): it goes through `startOAuthWithInvite` in `features/auth/api/auth-api`, which POSTs the
 * invite in the request body and returns the provider URL to navigate to.
 */
export const oauthStartHref = (apiBase: string, provider: 'google' | 'apple'): string =>
  `${apiBase}/api/auth/${provider}`
