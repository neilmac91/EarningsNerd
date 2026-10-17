import type { ReactElement } from 'react'
import { render, screen } from '@testing-library/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { GuidanceCard } from '@/components/ui/GuidanceCard'
import RouteError from '@/app/error'
import DashboardError from '@/app/dashboard/error'
import GlobalError from '@/app/global-error'
import { GlobalErrorBoundary } from '@/components/GlobalErrorBoundary'

/**
 * Two actions wrap rather than overflow (#1380; the reserve's condition, D-032). At 200% text on a phone, a card's
 * two actions side by side are wider than the card: the dashboard's account card put its Retry's left edge off the
 * screen at 320px, and the route error boundaries pushed Try again past the card. GuidanceCard's action row wraps and
 * centres its actions, so the second goes under the first when they do not fit, and global-error's own row does the
 * same; GuidanceCard's description breaks a long word (a backend message can hold a token). Rendered in Chromium for
 * the account card and both route boundaries in tests/e2e/reflow-200.spec.ts; global-error replaces the root layout,
 * which no e2e request can make throw, and GlobalErrorBoundary catches only what the route boundaries do not, so
 * these markup checks are their gate.
 */

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('next/font/google', () => ({ Inter: () => ({ className: 'font-inter' }) }))

const reset = () => {}
const failure = Object.assign(new Error('render failed'), { digest: undefined })

class Throws extends GlobalErrorBoundary {
  constructor(props: ConstructorParameters<typeof GlobalErrorBoundary>[0]) {
    super(props)
    this.state = { hasError: true, error: failure }
  }
}

describe('two actions wrap rather than overflow (#1380)', () => {
  it("GuidanceCard lays its actions in one wrapping, centred row, and breaks a long word in its description", () => {
    render(
      <GuidanceCard
        variant="error"
        title="Unable to load your dashboard"
        description="The account service failed: ACCOUNT_SERVICE_UPSTREAM_TIMEOUT"
        action={
          <>
            <button type="button">Try again</button>
            <a href="/login">Go to login</a>
          </>
        }
      />,
    )
    const row = screen.getByRole('button', { name: 'Try again' }).parentElement as HTMLElement
    expect(row).toHaveClass('flex', 'flex-wrap', 'items-center', 'justify-center')
    expect(screen.getByRole('link', { name: 'Go to login' }).parentElement).toBe(row)
    expect(screen.getByText(/ACCOUNT_SERVICE_UPSTREAM_TIMEOUT/)).toHaveClass('break-words')
  })

  it.each([
    ['app/error.tsx', <RouteError key="route" error={failure} reset={reset} />],
    ['app/dashboard/error.tsx', <DashboardError key="dash" error={failure} reset={reset} />],
    ['app/global-error.tsx', <GlobalError key="global" error={failure} reset={reset} />],
    ['components/GlobalErrorBoundary.tsx', <Throws key="boundary">{null}</Throws>],
  ])('%s: Try again and its second action share one row, and it wraps', (_file, ui: ReactElement) => {
    const doc = new DOMParser().parseFromString(renderToStaticMarkup(ui), 'text/html')
    const retry = [...doc.querySelectorAll('button')].find((button) => button.textContent?.trim() === 'Try again')
    expect(retry).toBeDefined()
    const row = retry!.parentElement as HTMLElement
    expect(row.children).toHaveLength(2)
    expect(row.classList.contains('flex')).toBe(true)
    expect(row.classList.contains('flex-wrap')).toBe(true)
  })
})
