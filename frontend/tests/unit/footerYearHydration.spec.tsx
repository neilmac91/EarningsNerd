import { act } from 'react'
import { renderToString } from 'react-dom/server'
import { hydrateRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Footer from '@/components/Footer'

vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))

/**
 * The footer is a client component (SiteChrome renders it, and its Cookie settings control is a button), so its
 * copyright year is read on the server and again in the browser. The two disagree for a few hours around New Year,
 * or on a page built last year, and the footer is on every route but the auth pages: hydration takes the browser's
 * year with no mismatch, rather than throwing away the server's markup.
 *
 * The footer reads the year in local time, so the two renders' clocks are set in local time too (the Date
 * constructor's own fields): the case crosses New Year in whatever zone the run is in, east or west of UTC.
 */

describe("the footer's year never breaks hydration", () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it("hydrates server markup from one year in a browser already in the next, and shows the browser's year", async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 11, 31, 23, 30))
    const container = document.createElement('div')
    container.innerHTML = renderToString(<Footer />)
    document.body.appendChild(container)
    expect(container.textContent).toContain('© 2026 EarningsNerd. All rights reserved.')

    vi.setSystemTime(new Date(2027, 0, 1, 0, 30))
    const consoleErrors = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const recoverable: unknown[] = []
    await act(async () => {
      hydrateRoot(container, <Footer />, { onRecoverableError: (error) => recoverable.push(error) })
    })

    expect(recoverable).toEqual([])
    expect(consoleErrors).not.toHaveBeenCalled()
    expect(container.textContent).toContain('© 2027 EarningsNerd. All rights reserved.')
  })
})
