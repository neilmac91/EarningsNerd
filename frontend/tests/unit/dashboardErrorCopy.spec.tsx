import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import DashboardError from '@/app/dashboard/error'

/**
 * app/dashboard/error.tsx is the only error boundary under app/dashboard, so it also catches a render
 * error on /dashboard/settings and /dashboard/watchlist: its generic line names no route (audit DSW-12,
 * UA-51). Titles and buttons are in sentence case. The signed-out state keeps its verb ("Go to login")
 * until the founder picks Log in or Sign in (tasks/todo.md F23). Server markup, so no effect runs (no
 * Sentry call, no redirect).
 */

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const text = (markup: string) => markup.replace(/<[^>]+>/g, ' ').replace(/&#x27;|&apos;/g, "'").replace(/\s+/g, ' ')
const reset = () => {}

describe('the dashboard route boundary', () => {
  it('says what happened without naming a route, in sentence case', () => {
    const shown = text(renderToStaticMarkup(<DashboardError error={new Error('render failed')} reset={reset} />))
    expect(shown).toContain('Something went wrong')
    expect(shown).toContain("This page didn't load. The error has been logged.")
    expect(shown).not.toMatch(/dashboard|settings|watchlist/i)
    expect(shown).toContain('Try again')
    expect(shown).toContain('Go home')
  })

  it('keeps the signed-out state in sentence case', () => {
    const shown = text(renderToStaticMarkup(<DashboardError error={new Error('401 Unauthorized')} reset={reset} />))
    expect(shown).toContain('Authentication required')
    expect(shown).toContain('Go to login')
  })
})
