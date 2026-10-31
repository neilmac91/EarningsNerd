import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BulkResultSummary from '@/features/admin/components/BulkResultSummary'

/**
 * A bulk summary row's share options open in a dialog shaped like the resend dialog (E242, chief design on #1784):
 * under 200% text they cannot be narrower than their WhatsApp button and frame, 197px at 320px, and the row there is
 * 110px. The dialog names the address at its top, arrives with the options showing, and Done closes it, focus back on
 * the row's opener; where the browser has its own share sheet, that button stays in the row. The row's address shows
 * whole, breaking after its @ (AddressText), where truncate cut it. tests/e2e/admin-invite-chip-reflow.spec.ts holds
 * the dialog and the row under 200% text.
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const LINK = 'https://earningsnerd.io/register?invite=abc123'
const ADDRESS = 'ann@example.com'
const CREATED = { email: ADDRESS, ok: true, link: LINK, emailed: false }

afterEach(() => {
  Reflect.deleteProperty(navigator, 'share')
  Reflect.deleteProperty(navigator, 'canShare')
})

describe("a bulk summary row's share options open in a dialog (E242)", () => {
  it('names the address at its top, arrives with the options showing, and Done returns focus to the opener', async () => {
    const user = userEvent.setup()
    render(<BulkResultSummary outcomes={[CREATED]} skipped={[]} emailRequested />)
    const row = screen.getByRole('listitem')
    const opener = within(row).getByRole('button', { name: 'Share invite', expanded: false })
    expect(opener).toHaveAttribute('aria-haspopup', 'dialog')
    expect(screen.queryByRole('textbox', { name: 'Message' }), 'the options open in the row').toBeNull()

    await user.click(opener)
    const dialog = screen.getByRole('dialog', { name: 'Share invite' })
    expect(opener).toHaveAttribute('aria-expanded', 'true')
    expect(dialog).toHaveTextContent(`The invite link for ${ADDRESS} works once, and only for that address.`)
    expect((within(dialog).getByRole('textbox', { name: 'Message' }) as HTMLTextAreaElement).value).toContain(LINK)
    for (const name of ['WhatsApp', 'Messages', 'Email']) expect(within(dialog).getByRole('link', { name })).toBeInTheDocument()
    for (const name of ['Copy for DM/LinkedIn', 'Copy message']) expect(within(dialog).getByRole('button', { name })).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Share invite' }), 'the options arrive open, with no toggle').toBeNull()

    await user.click(within(dialog).getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(opener).toHaveFocus()
    expect(opener).toHaveAttribute('aria-expanded', 'false')
  })

  it("keeps the browser's own share button in the row, and More opens the dialog without it", async () => {
    Object.defineProperty(navigator, 'share', { value: vi.fn(), configurable: true })
    Object.defineProperty(navigator, 'canShare', { value: vi.fn(() => true), configurable: true })
    render(<BulkResultSummary outcomes={[CREATED]} skipped={[]} emailRequested />)
    const row = screen.getByRole('listitem')
    const more = await within(row).findByRole('button', { name: 'More share options', expanded: false })
    expect(more).toHaveAttribute('aria-haspopup', 'dialog')
    expect(within(row).getByRole('button', { name: 'Share invite' })).not.toHaveAttribute('aria-haspopup')

    await userEvent.setup().click(more)
    const dialog = screen.getByRole('dialog', { name: 'Share invite' })
    expect(within(dialog).queryByRole('button', { name: 'Share invite' }), 'the share sheet button moved into the dialog').toBeNull()
    expect(within(dialog).getByRole('textbox', { name: 'Message' })).toBeInTheDocument()
  })

  it("shows the row's address whole, with a break after its @", () => {
    render(<BulkResultSummary outcomes={[CREATED]} skipped={[]} emailRequested />)
    const address = within(screen.getByRole('listitem')).getByText(
      (_, element) => element?.tagName === 'SPAN' && element.textContent === ADDRESS,
    )
    expect(address).not.toHaveClass('truncate')
    expect(address).toHaveClass('min-w-0', 'break-words')
    expect(address.innerHTML).toBe('ann@<wbr>example.com')
  })
})
