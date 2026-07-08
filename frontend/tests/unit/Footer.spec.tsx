import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'

// Mutable holders the hoisted mocks can read (vi.mock factories are hoisted above imports). Footer
// builds its FOOTER_LINKS at module-eval time, so each test sets the flags then re-imports Footer
// via vi.resetModules() to re-evaluate the Product column.
const h = vi.hoisted(() => ({
  enableAnalysis: false,
  enableCalendar: false,
}))

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
vi.mock('@/lib/featureFlags', () => ({
  get ENABLE_ANALYSIS() {
    return h.enableAnalysis
  },
  get ENABLE_CALENDAR() {
    return h.enableCalendar
  },
}))

async function renderFooter() {
  vi.resetModules()
  const { default: Footer } = await import('@/components/Footer')
  return render(<Footer />)
}

describe('Footer product links', () => {
  beforeEach(() => {
    h.enableAnalysis = false
    h.enableCalendar = false
  })

  it('never links to the hidden full-text search product', async () => {
    // Even with both flags on, the footer must not resurrect the /search product.
    h.enableAnalysis = true
    h.enableCalendar = true
    const { container } = await renderFooter()

    expect(container.querySelector('a[href="/search"]')).toBeNull()
    expect(container.textContent).not.toContain('Search Filings')
  })

  it('drops the dead Hot Filings / Trending anchors', async () => {
    const { container } = await renderFooter()

    expect(container.querySelector('a[href="/#hot-filings"]')).toBeNull()
    expect(container.querySelector('a[href="/#trending"]')).toBeNull()
  })

  it('shows only live products when Analysis/Calendar are off (Pricing only)', async () => {
    const { container } = await renderFooter()

    expect(container.querySelector('a[href="/pricing"]')).not.toBeNull()
    expect(container.querySelector('a[href="/analysis"]')).toBeNull()
    expect(container.querySelector('a[href="/calendar"]')).toBeNull()
  })

  it('surfaces Analysis and Calendar when their flags are on (mirrors the nav)', async () => {
    h.enableAnalysis = true
    h.enableCalendar = true
    const { container } = await renderFooter()

    expect(container.querySelector('a[href="/analysis"]')).not.toBeNull()
    expect(container.querySelector('a[href="/calendar"]')).not.toBeNull()
    expect(container.querySelector('a[href="/pricing"]')).not.toBeNull()
  })
})
