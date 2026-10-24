import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import CompanyLogo from '@/components/CompanyLogo'

/** The component reads the publishable token once, at import, so a token case re-imports it. */
async function withToken(token: string | null = 'pk_test') {
  // `null` removes the variable, whatever the shell running the suite exports (a default parameter
  // would swallow `undefined`).
  vi.stubEnv('NEXT_PUBLIC_LOGO_DEV_TOKEN', token === null ? undefined : token)
  vi.resetModules()
  return (await import('@/components/CompanyLogo')).default
}

const slot = (container: HTMLElement) => container.querySelector('[data-company-mark]')!
const monogram = (container: HTMLElement) => slot(container).querySelector('span')!

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  vi.resetModules()
})

describe('CompanyLogo', () => {
  it('labels a standalone logo so assistive tech can name the company', () => {
    render(<CompanyLogo decorative={false} ticker="AAPL" name="Apple Inc." />)
    expect(screen.getByRole('img', { name: 'Apple Inc. logo' })).toBeInTheDocument()
  })

  it('falls back to the ticker for a standalone logo without a name', () => {
    render(<CompanyLogo decorative={false} ticker="AAPL" />)
    expect(screen.getByRole('img', { name: 'AAPL logo' })).toBeInTheDocument()
  })

  it('hides a decorative logo, so a name rendered beside it is announced once', () => {
    // The same accessible-name computation as a link or the search listbox's option buttons.
    render(
      <button type="button">
        <CompanyLogo decorative ticker="AAPL" name="Apple Inc." />
        <span>Apple Inc.</span>
      </button>,
    )
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByLabelText(/logo/)).toBeNull()
    expect(screen.getByRole('button')).toHaveAccessibleName('Apple Inc.')
  })

  it('shows the monogram alone when no token is configured', async () => {
    const Logo = await withToken(null)
    const { container } = render(<Logo decorative ticker="AAPL" />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('AA')
    expect(monogram(container).className).toContain('opacity-100')
  })

  it('shows a visible "?" monogram for a company without a ticker', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative={false} ticker={null} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('?')
    expect(monogram(container).className).toContain('opacity-100')
    expect(screen.getByRole('img', { name: 'Company logo' })).toBeInTheDocument()
  })

  it('is a white tile on the radius scale in both themes, never a circle and never the brand tint', () => {
    // The two rules the 2026-10 company-mark review set (DESIGN_SYSTEM.md §9): a circle cut Logo.dev's
    // square tiles, and a black mark on the dark theme's tint measured 1.4:1.
    const small = render(<CompanyLogo decorative ticker="AAPL" size={24} />)
    const large = render(<CompanyLogo decorative ticker="MSFT" size={28} />)
    for (const [container, radius] of [
      [small.container, 'rounded-sm'],
      [large.container, 'rounded'],
    ] as const) {
      const classes = slot(container).className.split(/\s+/)
      expect(classes).toContain('bg-white')
      expect(classes).toContain('ring-border-light')
      expect(classes).toContain('dark:ring-white/10')
      expect(classes).toContain(radius)
      expect(classes).not.toContain('rounded-full')
      expect(classes.filter((c) => /(^|:)bg-brand/.test(c))).toEqual([])
    }
  })

  it('asks the CDN at the exact size for 1x, 2x and 3x screens, with a 404 for a missing logo', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="AAPL" size={24} />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('srcset')).toBe(
      [24, 48, 72]
        .map((px, i) => `https://img.logo.dev/ticker/AAPL?token=pk_test&size=${px}&format=png&fallback=404 ${i + 1}x`)
        .join(', '),
    )
    expect(img.getAttribute('src')).toContain('size=48&')
    expect(img.getAttribute('loading')).toBe('lazy')
    expect(img.hasAttribute('fetchpriority')).toBe(false)
  })

  it('sends a dotted class share dashed, the form Logo.dev reads as a US class, and names the slot by it', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="brk.b" />)
    expect(container.querySelector('img')!.getAttribute('src')).toContain('/ticker/BRK-B?')
    // The hook scripts/capture-company-marks.mjs finds and labels every mark by.
    expect(slot(container).getAttribute('data-company-mark')).toBe('BRK-B')
  })

  it('keeps the monogram when the image fails', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="AEHL" />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('AE')
    expect(monogram(container).className).toContain('opacity-100')
  })

  it('shows the mark once it loads', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="AAPL" />)
    const img = container.querySelector('img')!
    expect(img.className).toContain('opacity-0')
    fireEvent.load(img)
    expect(img.className).toContain('opacity-100')
    expect(monogram(container).className).toContain('opacity-0')
  })

  it('shows a mark that finished loading before React attached its listeners', async () => {
    // Server-rendered above the fold, the landing's chips load before hydration: `load` has fired
    // with nobody listening, so the component reads the element's state on mount instead.
    const Logo = await withToken()
    vi.spyOn(HTMLImageElement.prototype, 'complete', 'get').mockReturnValue(true)
    vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockReturnValue(48)
    const { container } = render(<Logo decorative ticker="AAPL" size={24} />)
    expect(container.querySelector('img')!.className).toContain('opacity-100')
  })

  it('removes a mark that failed before React attached its listeners', async () => {
    const Logo = await withToken()
    vi.spyOn(HTMLImageElement.prototype, 'complete', 'get').mockReturnValue(true)
    vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockReturnValue(0)
    const { container } = render(<Logo decorative ticker="AEHL" />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('AE')
  })

  it('starts over when a mounted instance changes ticker', async () => {
    // The analysis page's picker changes the ticker in place: a stale "loaded" would hide the next
    // company's monogram, a stale "failed" would never show the next company's mark, and a return to
    // an earlier company must not reuse its old state either.
    const Logo = await withToken()
    const { container, rerender } = render(<Logo decorative ticker="AAPL" />)
    fireEvent.load(container.querySelector('img')!)
    expect(container.querySelector('img')!.className).toContain('opacity-100')
    rerender(<Logo decorative ticker="AEHL" />)
    const next = container.querySelector('img')!
    expect(next.getAttribute('src')).toContain('/ticker/AEHL?')
    expect(next.className).toContain('opacity-0')
    expect(container.textContent).toBe('AE')
    expect(monogram(container).className).toContain('opacity-100')
    fireEvent.error(next)
    expect(container.querySelector('img')).toBeNull()
    rerender(<Logo decorative ticker="AAPL" />)
    const back = container.querySelector('img')!
    expect(back.getAttribute('src')).toContain('/ticker/AAPL?')
    expect(back.className).toContain('opacity-0')
    expect(monogram(container).className).toContain('opacity-100')
  })

  it('loads the one above-the-fold mark eagerly', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="AAPL" priority />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('loading')).toBe('eager')
    expect(img.getAttribute('fetchpriority')).toBe('high')
  })
})
