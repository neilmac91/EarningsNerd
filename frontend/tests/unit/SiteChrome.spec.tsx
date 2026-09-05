import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const { usePathname } = vi.hoisted(() => ({ usePathname: vi.fn<() => string>() }))
vi.mock('next/navigation', () => ({ usePathname }))
// Isolate the chrome wrapper from the real Header (auth queries, theme, logo).
vi.mock('@/components/Header', () => ({ default: () => <header data-testid="site-header" /> }))
vi.mock('@/components/Footer', () => ({ default: () => <footer data-testid="site-footer" /> }))

import { SiteHeader, SkipToContent } from '@/components/SiteChrome'

// WCAG 2.4.1 (Bypass Blocks): a skip link is the first focusable element on every chromed page and
// targets the #main content wrapper rendered by app/layout.tsx.
describe('SiteChrome skip link', () => {
  it('renders the skip link before the header, targeting #main', () => {
    usePathname.mockReturnValue('/filing/3')
    const { container } = render(<SiteHeader />)
    const link = screen.getByRole('link', { name: 'Skip to main content' })
    expect(link).toHaveAttribute('href', '#main')
    // First in DOM order so it is the first Tab stop.
    expect(container.firstElementChild).toBe(link)
    expect(link.compareDocumentPosition(screen.getByTestId('site-header')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('is visually hidden until focused (sr-only with a focus reveal)', () => {
    render(<SkipToContent />)
    const link = screen.getByRole('link', { name: 'Skip to main content' })
    expect(link.className).toContain('sr-only')
    expect(link.className).toContain('focus:not-sr-only')
  })

  it('is suppressed with the header on immersive auth routes', () => {
    usePathname.mockReturnValue('/login')
    const { container } = render(<SiteHeader />)
    expect(container).toBeEmptyDOMElement()
  })
})
