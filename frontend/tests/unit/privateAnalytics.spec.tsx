import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render } from '@testing-library/react'
import { hydrateRoot } from 'react-dom/client'
import { renderToString } from 'react-dom/server'
import type { ComponentProps } from 'react'
import { beforeSendVercel, PrivateAnalytics } from '@/app/private-analytics'
import { CONSENT_VERSION, saveCookiePreferences, clearCookiePreferences } from '@/components/CookieConsent'

/**
 * Vercel Web Analytics only after consent (D-046, D4). The consent bar says analytics stay off until the visitor
 * allows them; PrivateAnalytics reads the choice PostHog obeys (CookieConsent's stored `cookie_consent` and its
 * `cookieConsentChanged`) and renders the library's <Analytics> only while analytics are allowed. The library is
 * the real one: in jsdom its mount appends its script tag (the debug build's URL, as in development; a production
 * build appends /_vercel/insights/script.js), which jsdom never fetches. A wrapper counts the component's mounts.
 */

const mounts = vi.hoisted(() => ({ live: 0, total: 0 }))
vi.mock('@vercel/analytics/next', async (importOriginal) => {
  const real = await importOriginal<typeof import('@vercel/analytics/next')>()
  const { useEffect } = await import('react')
  return {
    Analytics: (props: ComponentProps<typeof real.Analytics>) => {
      useEffect(() => {
        mounts.live += 1
        mounts.total += 1
        return () => {
          mounts.live -= 1
        }
      }, [])
      return <real.Analytics {...props} />
    },
  }
})

type VercelWindow = Window & { va?: unknown; vaq?: unknown; vam?: unknown }
const vercelScripts = () => document.head.querySelectorAll('script[data-sdkn^="@vercel/analytics"]')
const choose = (analytics: boolean) =>
  act(() => saveCookiePreferences({ essential: true, analytics, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }))
const pageview = { type: 'pageview' as const, url: 'https://example.test/pricing' }

afterEach(() => {
  // Unmount first, so the count reads 0 before the next case (Testing Library's own cleanup runs after this hook).
  cleanup()
  vercelScripts().forEach((script) => script.remove())
  const w = window as VercelWindow
  delete w.va
  delete w.vaq
  delete w.vam
  localStorage.clear()
  vi.restoreAllMocks()
  clearCookiePreferences()
  mounts.live = 0
  mounts.total = 0
})

describe('Vercel Web Analytics waits for analytics consent', () => {
  it('renders nothing before the stored choice is read: the server HTML is empty and hydrating it mounts nothing', async () => {
    const container = document.body.appendChild(document.createElement('div'))
    container.innerHTML = renderToString(<PrivateAnalytics />)
    expect(container).toBeEmptyDOMElement()
    // The hydration render must not mount the library before the choice is read: its mount appends a script
    // that nothing removes, so a render that mounts it and then reads "no choice" has already loaded it.
    const root = await act(async () => hydrateRoot(container, <PrivateAnalytics />))
    try {
      expect(mounts.total).toBe(0)
      expect(vercelScripts()).toHaveLength(0)
    } finally {
      act(() => root.unmount())
      container.remove()
    }
  })

  it.each([
    ['no choice stored yet', null],
    ['Essential only', { essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z' }],
  ])('renders nothing with %s: no Analytics component, no script', (_label, stored) => {
    if (stored) localStorage.setItem('cookie_consent', JSON.stringify(stored))
    const { container } = render(<PrivateAnalytics />)
    expect(container).toBeEmptyDOMElement()
    expect(mounts.total).toBe(0)
    expect(vercelScripts()).toHaveLength(0)
    expect((window as VercelWindow).va).toBeUndefined()
  })

  it('renders it once the visitor allows analytics on the bar', () => {
    render(<PrivateAnalytics />)
    expect(vercelScripts()).toHaveLength(0)
    choose(true)
    expect(mounts.live).toBe(1)
    expect(vercelScripts()).toHaveLength(1)
    expect(beforeSendVercel(pageview)).not.toBeNull()
  })

  it('loads at once on a page opened with analytics allowed', () => {
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z', version: CONSENT_VERSION }))
    render(<PrivateAnalytics />)
    expect(mounts.live).toBe(1)
    expect(vercelScripts()).toHaveLength(1)
  })

  it('unmounts on a withdrawal and drops every event the loaded script would send, which stays until the next load', () => {
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: true, sessionRecording: false, timestamp: '2026-10-01T00:00:00.000Z', version: CONSENT_VERSION }))
    render(<PrivateAnalytics />)
    choose(false)
    expect(mounts.live).toBe(0)
    expect(beforeSendVercel(pageview)).toBeNull()
    // The library's limit: no unload, so its script tag remains in this page.
    expect(vercelScripts()).toHaveLength(1)
  })

  it.each(['failed-write', 'cross-tab-clear'] as const)('stops the loaded SDK component and its send hook on %s', mode => {
    render(<PrivateAnalytics />)
    choose(true)
    expect(mounts.live).toBe(1)
    if (mode === 'failed-write') {
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Unavailable') })
      vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new DOMException('Unavailable') })
      choose(false)
    } else {
      localStorage.clear()
      act(() => window.dispatchEvent(new StorageEvent('storage', { key: null, storageArea: localStorage })))
    }
    expect(mounts.live).toBe(0)
    expect(beforeSendVercel(pageview)).toBeNull()
    expect(vercelScripts()).toHaveLength(1)
  })
})
