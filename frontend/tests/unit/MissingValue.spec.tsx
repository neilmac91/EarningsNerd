import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MissingValue } from '@/components/ui'

/**
 * The missing-value element's contract (DESIGN_SYSTEM.md §4, Missing value; E88): the eye sees the token, assistive
 * tech hears words in its place and never the token, and the words stay inside whatever clips the cell. Where the
 * app may render the token at all is tests/unit/missingValueToken.spec.ts's.
 */
describe('MissingValue', () => {
  it('shows the token, hidden from assistive tech, and reads "unavailable" by default', () => {
    render(
      <table>
        <tbody>
          <tr>
            <td data-testid="cell">
              <MissingValue />
            </td>
          </tr>
        </tbody>
      </table>,
    )
    const cell = screen.getByTestId('cell')
    expect(within(cell).getByText('—')).toHaveAttribute('aria-hidden', 'true')
    expect(within(cell).getByText('unavailable')).toHaveClass('sr-only')
    expect(screen.getByRole('cell')).toHaveAccessibleName('unavailable')
  })

  it('reads the words a site passes, and takes the ink a site gives it', () => {
    const { container } = render(<MissingValue label="no cohort" className="text-text-tertiary-light dark:text-text-secondary-dark" />)
    const element = container.firstElementChild as HTMLElement
    expect(element).toHaveTextContent(/^—no cohort$/)
    expect(within(element).getByText('no cohort')).toHaveClass('sr-only')
    expect(element).toHaveClass('text-text-tertiary-light', 'dark:text-text-secondary-dark')
  })

  // An sr-only box is absolutely positioned; inside a truncating cell or a table's scroll box it escapes an
  // unpositioned clip and widens the page (lessons/frontend-sr-only-needs-a-positioned-clip.md), so the element is the
  // words' containing block.
  it('positions itself, so its words stay inside a clipped cell', () => {
    const { container } = render(<MissingValue />)
    const element = container.firstElementChild as HTMLElement
    expect(element).toHaveClass('relative')
    expect(element.children).toHaveLength(2)
    expect(element.querySelector('.sr-only')!.parentElement).toBe(element)
  })
})
