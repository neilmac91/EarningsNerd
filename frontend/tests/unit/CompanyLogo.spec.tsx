import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import CompanyLogo from '@/components/CompanyLogo'

/** The component reads the publishable token once, at import, so a token case re-imports it. */
async function withToken() {
  vi.stubEnv('NEXT_PUBLIC_LOGO_DEV_TOKEN', 'pk_test')
  vi.resetModules()
  return (await import('@/components/CompanyLogo')).default
}

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

  it('shows the monogram alone when no token is configured', () => {
    const { container } = render(<CompanyLogo decorative ticker="AAPL" />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('AA')
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

  it('sends a dotted class share dashed, the form Logo.dev reads as a US class', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="brk.b" />)
    expect(container.querySelector('img')!.getAttribute('src')).toContain('/ticker/BRK-B?')
  })

  it('keeps the monogram when the image fails', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="AEHL" />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('AE')
  })

  it('shows the mark once it loads', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="AAPL" />)
    const img = container.querySelector('img')!
    expect(img.className).toContain('opacity-0')
    fireEvent.load(img)
    expect(img.className).toContain('opacity-100')
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
    // company's monogram, a stale "failed" would never show the next company's mark.
    const Logo = await withToken()
    const { container, rerender } = render(<Logo decorative ticker="AAPL" />)
    fireEvent.load(container.querySelector('img')!)
    expect(container.querySelector('img')!.className).toContain('opacity-100')
    rerender(<Logo decorative ticker="AEHL" />)
    const next = container.querySelector('img')!
    expect(next.getAttribute('src')).toContain('/ticker/AEHL?')
    expect(next.className).toContain('opacity-0')
    expect(container.textContent).toBe('AE')
    fireEvent.error(next)
    expect(container.querySelector('img')).toBeNull()
    rerender(<Logo decorative ticker="AAPL" />)
    expect(container.querySelector('img')!.getAttribute('src')).toContain('/ticker/AAPL?')
  })

  it('loads the one above-the-fold mark eagerly', async () => {
    const Logo = await withToken()
    const { container } = render(<Logo decorative ticker="AAPL" priority />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('loading')).toBe('eager')
    expect(img.getAttribute('fetchpriority')).toBe('high')
  })
})
