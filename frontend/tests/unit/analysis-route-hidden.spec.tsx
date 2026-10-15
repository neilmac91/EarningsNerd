import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'

// Mutable holders the hoisted mocks can read (vi.mock factories are hoisted above imports).
const h = vi.hoisted(() => ({
  enableAnalysis: false,
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

vi.mock('next/navigation', () => ({ notFound: h.notFound }))
vi.mock('@/lib/featureFlags', () => ({
  get ENABLE_ANALYSIS() {
    return h.enableAnalysis
  },
  ENABLE_PRO_TRIAL: false,
  ENABLE_FPI_FILINGS: false,
}))

import AnalysisLayout from '@/app/analysis/layout'
import ProDepth from '@/features/marketing/components/ProDepth'
import PricingSection from '@/features/marketing/components/PricingSection'

describe('Analysis route gating (NEXT_PUBLIC_ENABLE_ANALYSIS)', () => {
  beforeEach(() => {
    h.notFound.mockClear()
  })

  it('404s /analysis when the flag is off', () => {
    h.enableAnalysis = false
    expect(() => AnalysisLayout({ children: 'gated' })).toThrow('NEXT_NOT_FOUND')
    expect(h.notFound).toHaveBeenCalledTimes(1)
  })

  it('renders the route when the flag is on', () => {
    h.enableAnalysis = true
    const out = AnalysisLayout({ children: 'visible' })
    expect(h.notFound).not.toHaveBeenCalled()
    expect(out).toBeTruthy()
  })
})

/**
 * The public pages sell Multi-Period Analysis only while the flag ships it (audit pub/F06): the route
 * 404s with the flag off, so the landing's Pro section and pricing cards must not list it. The /pricing
 * page's plan list is held the same way in PricingPage.spec.tsx, which carries that page's harness.
 */
describe('The public pages follow NEXT_PUBLIC_ENABLE_ANALYSIS', () => {
  const surfaces = () => {
    const pro = render(<ProDepth />)
    const proText = pro.container.textContent ?? ''
    pro.unmount()
    const pricing = render(<PricingSection accessMode="public" showBeta={false} />)
    const pricingText = pricing.container.textContent ?? ''
    pricing.unmount()
    return { proText, pricingText }
  }

  it('names no Multi-Period feature on the landing while the flag is off', () => {
    h.enableAnalysis = false
    const { proText, pricingText } = surfaces()
    expect(proText).not.toMatch(/Multi-Period|periods side by side|Excel export|XLSX/)
    // The Excel export is the analysis workbook, so the Pro list drops it with the route.
    expect(pricingText).not.toMatch(/Multi-Period|Excel|XLSX/)
    expect(pricingText).toContain('PDF and CSV exports')
    // Anti-vacuity: both surfaces rendered their lists.
    expect(proText).toContain('Change Report')
    expect(pricingText).toContain('Unlimited summaries')
  })

  it('names it on both while the flag is on', () => {
    h.enableAnalysis = true
    const { proText, pricingText } = surfaces()
    expect(proText).toContain('Multi-Period Analysis')
    expect(proText).toContain('Excel export')
    expect(pricingText).toContain('Multi-Period Analysis demo (locked)')
    expect(pricingText).toContain('Unlimited Multi-Period Analysis')
    expect(pricingText).toContain('PDF, CSV and Excel exports')
  })
})
