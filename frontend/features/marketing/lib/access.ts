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

/** The account action while readiness is checking, closed or unconfirmed: the live example. */
const EXAMPLE_ACCOUNT = { cta: 'See a live example', ctaShort: 'Live example' } as const

const CHECKING_LINE = 'Checking registration availability. You can explore a live example.'

/** Registration policy does not imply collection readiness. Never use this display state as authorization. */
export function publicAccessCopy(mode: AccessMode, readiness: LegalReadiness | null, loading: boolean): AccessCopy {
  if (!loading && readiness?.collection_available === true) return ACCESS_COPY[mode]
  return {
    ...EXAMPLE_ACCOUNT,
    href: exampleFilingHref('access_example'),
    line: loading
      ? CHECKING_LINE
      : readiness
        ? 'New registrations are currently closed. Existing members can log in.'
        : 'Registration availability could not be confirmed. You can explore a live example or log in.',
  }
}

/** Every account label the full bar can print in `mode`: the mode's own, and the live example's while readiness checks
 *  or once it answers closed or unconfirmed. The header's hidden copy holds them all, so the nav keeps its place as
 *  readiness lands (E220). */
export const accountLabels = (mode: AccessMode): readonly string[] => [ACCESS_COPY[mode].cta, EXAMPLE_ACCOUNT.cta]

/** Every label the compact bar's account link can print in `mode` (`ctaShort`): the mode's own, and the live example's
 *  while readiness checks or once it answers closed or unconfirmed. The link holds them in one cell, so the bar keeps
 *  its height as readiness lands: under 200% text at 370 and 450px, "Live example" took one line and "Request invite"
 *  two, and the bar grew 14px (E223; chief design on #1686, comment 6436319684). */
export const accountShortLabels = (mode: AccessMode): readonly string[] => [ACCESS_COPY[mode].ctaShort, EXAMPLE_ACCOUNT.ctaShort]

/** The access lines the hero's line keeps the height of: the checking line it opens on and the mode's own, so the page
 *  under it holds still as readiness answers open. A closed or unconfirmed answer joins the cell when shown and can
 *  grow it: the closed line takes a row more than the checking line at some widths, and holding it would put a closed
 *  notice in every visit's server HTML (E220; chief design on #1686). */
export const heldAccessLines = (mode: AccessMode): readonly string[] => [CHECKING_LINE, ACCESS_COPY[mode].line]
