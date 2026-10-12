import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

/**
 * The founder slot (docs/brand/08-applications.md §6): the landing page's one first-person line.
 * It renders nothing until the founder supplies the words, so no placeholder ever ships, and once
 * filled it renders the sentence and the signature exactly. The shipped value is the founder's to
 * set; this spec only guards the rules the sentence must keep when it arrives.
 */
const slot = vi.hoisted(() => ({ note: null as null | { sentence: string; name: string } }))
vi.mock('@/features/marketing/lib/founderNote', () => ({
  get FOUNDER_NOTE() {
    return slot.note
  },
}))

import FounderNote from '@/features/marketing/components/FounderNote'

afterEach(() => {
  slot.note = null
})

describe('FounderNote', () => {
  it('renders nothing while the slot is empty: no placeholder, no empty figure', () => {
    const { container } = render(<FounderNote />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the sentence and its signature once the founder supplies them', () => {
    slot.note = { sentence: 'I wanted every number I read to point at the filing it came from.', name: 'Alex' }
    render(<FounderNote />)
    expect(screen.getByRole('figure')).toBeInTheDocument()
    expect(screen.getByText(slot.note.sentence).tagName).toBe('BLOCKQUOTE')
    expect(screen.getByText('Alex · EarningsNerd').tagName).toBe('FIGCAPTION')
  })
})

describe('the shipped founder sentence', () => {
  it('when set, keeps the voice rules: no exclamation mark, no em-dash, a name to sign it', async () => {
    const { FOUNDER_NOTE } = await vi.importActual<typeof import('@/features/marketing/lib/founderNote')>('@/features/marketing/lib/founderNote')
    if (FOUNDER_NOTE === null) return
    expect(FOUNDER_NOTE.sentence).not.toMatch(/[!—]/)
    expect(FOUNDER_NOTE.sentence.trim().length).toBeGreaterThan(0)
    expect(FOUNDER_NOTE.name.trim().length).toBeGreaterThan(0)
  })
})
