import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import RouteError from '@/app/error'
import DashboardError from '@/app/dashboard/error'
import GlobalError from '@/app/global-error'
import { GlobalErrorBoundary } from '@/components/GlobalErrorBoundary'
import AccountLoadFailure from '@/features/auth/components/AccountLoadFailure'
import type { RetainedFailure } from '@/hooks/useRetainedFailure'

/**
 * UA-50: a fallback that replaces the whole page opens the page outline with an h1 (DESIGN_SYSTEM §5).
 * The route boundary, the dashboard's two states, the root-layout fallback (global-error) and the
 * providers' boundary each render a page of their own; GuidanceCard took only 'h2' | 'h3', so they opened
 * with an h3 (global-error with a hand-written h2). GuidanceCard now takes 'h1' and each passes it. So does
 * the signed-in routes' account card, which the dashboard, the watchlist and the admin section render in
 * place of the page when their first /me read fails.
 *
 * Holds: the first heading each fallback renders is an h1 titled as the reader sees it. Server markup, so
 * no effect runs (no Sentry call, no redirect). tests/e2e/text-floors.spec.ts walks the route boundary in
 * Chromium too, with the rest of the outline beneath it.
 */

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
// The root's fonts (app/fonts.ts, which global-error.tsx imports, E147): next/font is compiled away by Next's build, so
// its three loaders are stubbed.
vi.mock('next/font/google', () => {
  const font = () => ({ className: 'font-inter', variable: '' })
  return { Inter: font, Geist_Mono: font, Newsreader: font }
})

const firstHeading = (ui: ReactElement) => {
  const match = renderToStaticMarkup(ui).match(/<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1>/)
  return match ? `h${match[1]} ${match[2].replace(/<[^>]+>/g, '').trim()}` : 'no heading'
}

const reset = () => {}
const failure = Object.assign(new Error('render failed'), { digest: undefined })
const accountFailure: RetainedFailure = { failed: true, error: new Error('Server unavailable'), busy: false, retry: () => {} }

class Throws extends GlobalErrorBoundary {
  constructor(props: ConstructorParameters<typeof GlobalErrorBoundary>[0]) {
    super(props)
    this.state = { hasError: true, error: failure }
  }
}

describe('page-replacing error fallbacks open with an h1 (UA-50)', () => {
  it.each([
    ['app/error.tsx', <RouteError key="route" error={failure} reset={reset} />, /^h1 Something went wrong$/],
    ['app/global-error.tsx', <GlobalError key="global" error={failure} reset={reset} />, /^h1 Something went wrong$/],
    // The dashboard's titles are the dashboard PR's copy (UA-51); this holds the level only.
    ['app/dashboard/error.tsx (generic)', <DashboardError key="dash" error={failure} reset={reset} />, /^h1 \S/],
    ['app/dashboard/error.tsx (signed out)', <DashboardError key="auth" error={new Error('401 Unauthorized')} reset={reset} />, /^h1 \S/],
    ['components/GlobalErrorBoundary.tsx', <Throws key="boundary">{null}</Throws>, /^h1 Something went wrong$/],
    ['features/auth/components/AccountLoadFailure.tsx', <AccountLoadFailure key="account" failure={accountFailure} focusTarget={{ current: null }} title="Unable to load your watchlist" />, /^h1 Unable to load your watchlist$/],
  ])('%s', (_file, ui, expected) => {
    expect(firstHeading(ui)).toMatch(expected)
  })
})
