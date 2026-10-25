import type { SignupConfig } from '@/lib/serverApi'
import { FREE_SUMMARY_LIMIT } from '@/lib/planLimits'
import { exampleFilingHref } from '@/lib/featureFlags'
import type { LegalReadiness } from '@/features/legal/api/legal-api'

/**
 * Registration policy (the design's `access` tweak). In invite_only mode the backend rejects an
 * email signup without an invite. Public entry points also need current collection readiness;
 * publicAccessCopy combines it with this policy without changing the registration gate itself.
 */
export type AccessMode = 'public' | 'invite'

/** Fail closed: with no answer from the backend, never advertise a signup that /register rejects. */
export const DEFAULT_ACCESS_MODE: AccessMode = 'invite'

export const resolveAccessMode = (config: SignupConfig | null): AccessMode =>
  config?.mode === 'public' ? 'public' : DEFAULT_ACCESS_MODE

/**
 * "Free for beta members" is true only while the closed beta is running (invites are the only
 * way in) AND the 100%-off promo that makes Pro $0 for beta members is configured server-side.
 */
export const betaPricingActive = (config: SignupConfig | null): boolean =>
  config?.mode === 'invite_only' && config.beta_promo_enabled

export interface AccessCopy {
  /** Full account CTA (header desktop, hero-adjacent cards, the closing line, Free plan). */
  cta: string
  /** Short CTA for the mobile header bar. */
  ctaShort: string
  /** The one-line access statement under the primary CTAs. */
  line: string
  /** Where the account CTA goes: open registration, or the invite/waitlist flow. */
  href: string
}

export const ACCESS_COPY: Record<AccessMode, AccessCopy> = {
  public: {
    cta: 'Create a free account',
    ctaShort: 'Sign up',
    line: `Free account · ${FREE_SUMMARY_LIMIT} AI summaries a month · no credit card`,
    href: '/register',
  },
  invite: {
    cta: 'Request an invite',
    ctaShort: 'Request invite',
    line: 'Private beta · request an invite',
    href: '/waitlist',
  },
}

/** Registration policy does not imply collection readiness. Never use this display state as authorization. */
export function publicAccessCopy(mode: AccessMode, readiness: LegalReadiness | null, loading: boolean): AccessCopy {
  if (!loading && readiness?.collection_available === true) return ACCESS_COPY[mode]
  return {
    cta: 'See a live example',
    ctaShort: 'Live example',
    href: exampleFilingHref('access_example'),
    line: loading
      ? 'Checking registration availability. You can explore a live example.'
      : readiness
        ? 'New registrations are currently closed. Existing members can log in.'
        : 'Registration availability could not be confirmed. You can explore a live example or log in.',
  }
}
