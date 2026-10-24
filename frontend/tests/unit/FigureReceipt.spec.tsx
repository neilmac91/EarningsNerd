import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { renderToStaticMarkup } from 'react-dom/server'
import FigureReceipt from '@/features/marketing/components/FigureReceipt'
import { SAMPLE_FILING, SAMPLE_FINANCIAL_METRICS, SAMPLE_RECEIPT } from '@/features/marketing/lib/landing-samples'
import { ArrowSquareOutIcon, BracketsCurlyIcon } from '@/lib/icons'

// The receipt's result chip wears the product chip's glyph for its state (SourceTrace): braces for a figure that
// matches the filing, the link arrow for one that is only linked, so the landing never pairs braces with "not checked".
const row = SAMPLE_FINANCIAL_METRICS.find((r) => r.metric === 'Total net sales')!
const glyph = (Icon: typeof BracketsCurlyIcon) => renderToStaticMarkup(<Icon className="h-3 w-3 shrink-0" aria-hidden="true" />)

describe('FigureReceipt', () => {
  it.each([
    [true, 'Matches filing', BracketsCurlyIcon],
    [false, 'Linked, not checked', ArrowSquareOutIcon],
  ])('a figure with source_verified %s reads "%s" with its chip glyph', (verified, label, Icon) => {
    render(
      <FigureReceipt
        row={{ ...row, source_verified: verified }}
        receipt={SAMPLE_RECEIPT}
        company="Apple"
        form={SAMPLE_FILING.filingType}
        fiscalYear={SAMPLE_FILING.fiscalYear}
      />,
    )
    const chip = screen.getByText(label)
    expect(chip.querySelector('svg')?.outerHTML).toBe(glyph(Icon))
  })
})
