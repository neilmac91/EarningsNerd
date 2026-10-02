/**
 * Backend OAuth start URL for the social sign-in buttons. `invite` is the closed-beta token from
 * the register magic link; the backend stores its hash against the OAuth state and redeems it when
 * the callback creates the account (REGISTRATION_MODE=invite_only refuses creation without one).
 */
export const oauthStartHref = (
  apiBase: string,
  provider: 'google' | 'apple',
  invite?: string,
): string => `${apiBase}/api/auth/${provider}${invite ? `?invite=${encodeURIComponent(invite)}` : ''}`
