import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

/**
 * The reader-quote slot (docs/brand/01-interview.md §2, "What must stay honest"; audit BG-28): it
 * renders nothing until a real reader supplies their words, so no placeholder testimonial ever ships,
 * and once filled it renders the quote and the attribution exactly. The shipped value is a reader's to
 * give; this spec guards the rules the quote must keep when it arrives. Mirrors founderNote.spec.tsx.
 */
const slot = vi.hoisted(() => ({ quote: null as null | { quote: string; attribution: string } }))
vi.mock('@/features/marketing/lib/readerQuote', () => ({
  get READER_QUOTE() {
    return slot.quote
  },
}))
vi.mock('@/lib/analytics', () => ({ default: { homepageSectionViewed: vi.fn() } }))

import ReaderQuoteSlot from '@/features/marketing/components/ReaderQuoteSlot'

afterEach(() => {
  slot.quote = null
})

describe('ReaderQuoteSlot', () => {
  it('renders nothing while the slot is empty: no placeholder, no reserved figure', () => {
    const { container } = render(<ReaderQuoteSlot />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the quote and its attribution once a reader supplies them', () => {
    slot.quote = { quote: 'I check the figure against the filing before I trust it.', attribution: 'Sam · reads 10-Ks of the companies they hold' }
    render(<ReaderQuoteSlot />)
    expect(screen.getByRole('region', { name: 'Reader quote' })).toBeInTheDocument()
    expect(screen.getByText(slot.quote.quote).tagName).toBe('BLOCKQUOTE')
    expect(screen.getByText(slot.quote.attribution).tagName).toBe('FIGCAPTION')
  })
})

describe('the shipped reader quote', () => {
  it('when set, keeps the voice rules: no exclamation mark, no em-dash, an attribution', async () => {
    const { READER_QUOTE } = await vi.importActual<typeof import('@/features/marketing/lib/readerQuote')>('@/features/marketing/lib/readerQuote')
    if (READER_QUOTE === null) return
    expect(READER_QUOTE.quote).not.toMatch(/[!—]/)
    expect(READER_QUOTE.attribution).not.toMatch(/[!—]/)
    expect(READER_QUOTE.quote.trim().length).toBeGreaterThan(0)
    expect(READER_QUOTE.attribution.trim().length).toBeGreaterThan(0)
  })
})
