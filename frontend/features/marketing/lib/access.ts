import type { SignupConfig } from '@/lib/serverApi'
import { FREE_SUMMARY_LIMIT } from '@/lib/planLimits'

/**
 * The landing page's ONE access decision (the design's `access` tweak). Every account CTA, the
 * access line under the hero and final CTA, the header CTA and the Free pricing card read from
 * here. The truthful state is the backend's REGISTRATION_MODE (read via fetchSignupConfig): in
 * `invite_only` mode /api/auth/register rejects any email signup without an invite, so advertising
 * "Create a free account" would be a lie.
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
  /** Full account CTA (header desktop, hero-adjacent cards, final CTA, Free plan). */
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
