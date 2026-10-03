import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import CompanyLogo from '@/components/CompanyLogo'

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
})
