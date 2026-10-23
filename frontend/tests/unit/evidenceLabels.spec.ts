import { describe, it, expect } from 'vitest'
import {
  FIGURE_LINKED_NOTE,
  TAKEAWAY_WITHHELD_NOTE,
  figureNote,
  sourceLinkLabel,
} from '@/features/filings/lib/evidenceLabels'

// The figure panel's status line says only what the server checked (lib/evidenceLabels.ts): a figure it did not check
// is linked, a matched one names the filed amounts it matched, and a replaced one names both the filed amount shown
// and the summary's own figure it replaced (provenance_service._swap_in_filed_figures).
describe('figureNote', () => {
  const filed = { current_period: '$416,161 million', prior_period: '$391,035 million' }

  it('says a figure the server did not check is linked, whatever amounts came with it', () => {
    expect(figureNote({ verified: false })).toBe(FIGURE_LINKED_NOTE)
    expect(figureNote({ verified: false, filed })).toBe(FIGURE_LINKED_NOTE)
  })

  it('names each filed amount a matched figure was compared with', () => {
    expect(figureNote({ verified: true, filed })).toBe(
      'Matches the figures the company filed: $416,161 million and $391,035 million.',
    )
    expect(figureNote({ verified: true, filed: { current_period: '$416,161 million' } })).toBe(
      'Matches the figure the company filed: $416,161 million.',
    )
    expect(figureNote({ verified: true })).toBe('Matches the figure the company filed.')
  })

  it('names the filed amount shown and the summary’s figure it replaced', () => {
    expect(figureNote({ verified: true, filed, replaced: { current_period: '$123.1B' } })).toBe(
      'Shown as the company filed it: $416,161 million. The summary’s figure, $123.1B, was replaced.',
    )
    expect(
      figureNote({ verified: true, filed, replaced: { current_period: '$123.1B', prior_period: '$99.0B' }, takeawayWithheld: true }),
    ).toBe(
      'Shown as the company filed it: $416,161 million and $391,035 million. The summary’s figures, $123.1B and $99.0B, ' +
        `were replaced. ${TAKEAWAY_WITHHELD_NOTE}`,
    )
  })

  it('reads a period the server did not replace as matched', () => {
    expect(figureNote({ verified: true, filed, replaced: { current_period: null } })).toBe(
      'Matches the figures the company filed: $416,161 million and $391,035 million.',
    )
  })
})

describe('sourceLinkLabel', () => {
  it('names the passage for a text-fragment link and the filing for any other', () => {
    expect(sourceLinkLabel('https://www.sec.gov/Archives/edgar/data/320193/x.htm#:~:text=Services%20net%20sales')).toBe(
      'Open the passage on SEC.gov',
    )
    expect(sourceLinkLabel('https://www.sec.gov/Archives/edgar/data/320193/x.htm')).toBe('Open the filing on SEC.gov')
  })
})
