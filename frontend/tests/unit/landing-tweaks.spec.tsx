import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ACCESS_COPY,
  betaPricingActive,
  DEFAULT_ACCESS_MODE,
  resolveAccessMode,
} from '@/features/marketing/lib/access'
import {
  CONTROL_HEADLINE,
  DEFAULT_HEADLINE,
  HEADLINES,
  pageTitleFor,
  resolveHeadlineVariant,
} from '@/features/marketing/lib/headline'
import HeroHeadline from '@/features/marketing/components/HeroHeadline'
import { FREE_SUMMARY_LIMIT } from '@/lib/planLimits'

/**
 * The landing page's "tweaks" (design/landing-redesign/RATIONALE.md) each have ONE deciding source
 * in the repo. This pins the decision functions and the headline swap so every instance on the page
 * flips together: access line + account CTAs follow the backend registration gate; the beta pricing
 * line follows the closed beta + promo config; the H1 follows the PostHog experiment arm.
 */

const mockVariant = vi.hoisted(() => ({ value: undefined as unknown }))
vi.mock('posthog-js/react', () => ({ useFeatureFlagVariantKey: () => mockVariant.value }))

describe('access decision (design tweak `access`)', () => {
  it('fails closed to the invite copy when the backend cannot be read', () => {
    expect(resolveAccessMode(null)).toBe('invite')
    expect(DEFAULT_ACCESS_MODE).toBe('invite')
  })

  it('advertises open registration only when REGISTRATION_MODE is public', () => {
    expect(resolveAccessMode({ mode: 'public', beta_promo_enabled: false })).toBe('public')
    expect(resolveAccessMode({ mode: 'invite_only', beta_promo_enabled: true })).toBe('invite')
  })

  it('routes each variant to its real flow and states the free cap from the plan mirror', () => {
    expect(ACCESS_COPY.public.href).toBe('/register')
    expect(ACCESS_COPY.public.line).toContain(`${FREE_SUMMARY_LIMIT} AI summaries a month`)
    expect(ACCESS_COPY.invite.href).toBe('/waitlist')
    expect(ACCESS_COPY.invite.line).toBe('Private beta · request an invite')
  })
})

describe('beta pricing line (design tweak `showBeta`)', () => {
  it('shows only while the closed beta runs AND the 100%-off promo is configured', () => {
    expect(betaPricingActive({ mode: 'invite_only', beta_promo_enabled: true })).toBe(true)
    expect(betaPricingActive({ mode: 'invite_only', beta_promo_enabled: false })).toBe(false)
    expect(betaPricingActive({ mode: 'public', beta_promo_enabled: true })).toBe(false)
    expect(betaPricingActive(null)).toBe(false)
  })
})

describe('headline experiment (design tweak `headline`)', () => {
  const originalTitle = document.title

  beforeEach(() => {
    mockVariant.value = undefined
    document.title = originalTitle
  })
  afterEach(() => {
    document.title = originalTitle
  })

  it('resolves A by default, C for the control arm, and ignores unknown arms', () => {
    expect(resolveHeadlineVariant(undefined)).toBe(DEFAULT_HEADLINE)
    expect(resolveHeadlineVariant(false)).toBe('A')
    expect(resolveHeadlineVariant('B')).toBe('B')
    expect(resolveHeadlineVariant('control')).toBe(CONTROL_HEADLINE)
    expect(resolveHeadlineVariant('garbage')).toBe('A')
    expect(pageTitleFor('A')).toBe('EarningsNerd | Every number in the filing, traced to the filing')
  })

  it('renders variant A in server HTML and leaves the document title alone', () => {
    render(<HeroHeadline />)
    const h1 = screen.getByRole('heading', { level: 1 })
    expect(h1).toHaveTextContent(`${HEADLINES.A.pre}${HEADLINES.A.accent}${HEADLINES.A.post}`)
    expect(h1).toHaveAttribute('data-headline-variant', 'A')
    expect(document.title).toBe(originalTitle)
  })

  it('swaps to the flagged arm and retitles the document to match', () => {
    mockVariant.value = 'C'
    render(<HeroHeadline />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Understand any SEC filing in minutes')
    expect(document.title).toBe(pageTitleFor('C'))
  })
})
