import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import DashboardError from '@/app/dashboard/error'

/**
 * app/dashboard/error.tsx is the only error boundary under app/dashboard, so it also catches a render error on
 * /dashboard/settings and /dashboard/watchlist: whatever its words, its generic state names no route (audit DSW-12,
 * UA-51). The words are copy, free to change (brandVoiceRules.spec.ts holds their case); the signed-out state's words
 * take D-046's verb ("Log in to see your dashboard"), which brandVoiceRules.spec.ts also holds, and are not read here.
 * Server markup, so no effect runs (no Sentry call, no redirect).
 */

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const text = (markup: string) => markup.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()

describe('the dashboard route boundary', () => {
  it('names no route in its generic state, since it catches every route under /dashboard', () => {
    const shown = text(renderToStaticMarkup(<DashboardError error={new Error('render failed')} reset={() => {}} />))
    expect(shown).not.toBe('')
    expect(shown).not.toMatch(/dashboard|settings|watchlist/i)
  })
})
