import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import BulkResultSummary from '@/features/admin/components/BulkResultSummary'
import CopyLinkButton from '@/features/admin/components/CopyLinkButton'
import ResendShareModal from '@/features/admin/components/ResendShareModal'

/**
 * Copy link keeps its words and confirms through the toast region, once (chief design on #1789 and #1791). It was named
 * "Copy link" by an aria-label while its words flashed to "Copied", so the name lacked the word shown (WCAG 2.5.3), and
 * a press said nothing a screen reader hears in the resend dialog (4.1.3), while in the bulk summary's live region the
 * flash was heard. Now its name is its words and stays so through a press, the press puts "Invite link copied" in the
 * toast region, as Copy message does, and no words change in the summary's live region, so the toast is the one thing
 * heard there. tests/unit/copyConfirmations.spec.ts holds every clipboard write to the rule.
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const LINK = 'https://earningsnerd.io/register?invite=abc123'

// fireEvent, not user-event: user-event's setup puts its own clipboard in place of the one installed here.
function installClipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  return writeText
}
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')

beforeEach(() => vi.clearAllMocks())
afterEach(() => {
  cleanup()
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard)
  else Reflect.deleteProperty(navigator, 'clipboard')
})

describe('Copy link is named by its words and confirms once, through the toast region', () => {
  it('keeps its words through a press, which copies the link and says so in the toast region', async () => {
    const writeText = installClipboard()
    render(<CopyLinkButton link={LINK} />)
    const button = screen.getByRole('button', { name: 'Copy link' })
    expect(button, 'an aria-label in place of its words').not.toHaveAttribute('aria-label')

    fireEvent.click(button)
    await waitFor(() => expect(toast.success).toHaveBeenCalledExactlyOnceWith('Invite link copied'))
    expect(writeText).toHaveBeenCalledExactlyOnceWith(LINK)
    expect(button).toHaveAccessibleName('Copy link')
    expect(button).toHaveTextContent(/^Copy link$/)
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('says so when the link could not be copied', async () => {
    installClipboard(vi.fn().mockRejectedValue(new Error('denied')))
    render(<CopyLinkButton link={LINK} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copy link' }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledExactlyOnceWith('Could not copy the link.'))
    expect(toast.success).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Copy link' })).toHaveTextContent(/^Copy link$/)
  })

  it("changes no words in the bulk summary's live region, so the toast is the one thing heard there", async () => {
    installClipboard()
    const { container } = render(
      <BulkResultSummary outcomes={[{ email: 'ann@example.com', ok: true, link: LINK, emailed: false }]} skipped={[]} emailRequested />,
    )
    const region = container.querySelector<HTMLElement>('[aria-live="polite"]')!
    const words = region.textContent

    fireEvent.click(within(region).getByRole('button', { name: 'Copy link' }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledExactlyOnceWith('Invite link copied'))
    expect(region.textContent, "the summary's live region would say the press again").toBe(words)
  })

  it('confirms through the toast region in the resend dialog too', async () => {
    installClipboard()
    render(<ResendShareModal link={LINK} email={null} emailed={false} onClose={() => {}} />)
    const button = within(screen.getByRole('dialog')).getByRole('button', { name: 'Copy link' })

    fireEvent.click(button)
    await waitFor(() => expect(toast.success).toHaveBeenCalledExactlyOnceWith('Invite link copied'))
    expect(button).toHaveAccessibleName('Copy link')
  })
})
