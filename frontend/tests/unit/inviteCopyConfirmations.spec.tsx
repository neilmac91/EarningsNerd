import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import BulkResultSummary from '@/features/admin/components/BulkResultSummary'
import CopyLinkButton from '@/features/admin/components/CopyLinkButton'
import ResendShareModal from '@/features/admin/components/ResendShareModal'

/**
 * The admin invite surfaces' copy controls keep their words and say a press once, where a screen reader hears it
 * (chief design on #1789, #1791 and #1793). Copy link was named "Copy link" by an aria-label while its words flashed
 * to "Copied", so its name lacked the word shown (WCAG 2.5.3), and a press said nothing a screen reader hears in the
 * resend dialog (4.1.3), while in the bulk summary's live region the flash was heard. Now its name is its words through
 * a press, and the press is said once in each place:
 * - in the bulk summary, through the toast region ("Invite link copied"), with no words changing in its live region;
 * - inside a dialog, in a status line inside the dialog: the page's toast region lies outside an aria-modal dialog,
 *   which hides it from VoiceOver, so a toast from in there is never heard. The resend dialog says Copy link's press,
 *   and a share sheet that could not open, in its own line under the row; the share options, in the resend dialog or
 *   in their own (a summary row's), say Copy message and Copy for DM/LinkedIn in theirs.
 * tests/unit/copyConfirmations.spec.ts holds every clipboard write to the rule, and names this spec as these writers'.
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const LINK = 'https://earningsnerd.io/register?invite=abc123'

// fireEvent, not user-event: user-event's setup puts its own clipboard in place of the one installed here.
function installClipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  return writeText
}
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')

/** The browser's own share sheet, offered for this link, its share answered by `share`. */
function offerShareSheet(share: () => Promise<void>) {
  Object.defineProperty(navigator, 'share', { configurable: true, value: vi.fn(share) })
  Object.defineProperty(navigator, 'canShare', { configurable: true, value: () => true })
}

/** Every text a status line holds as it changes, so a second press that says the same is seen emptied in between. */
function textsOf(line: HTMLElement): string[] {
  const texts: string[] = []
  new MutationObserver(() => texts.push(line.textContent ?? '')).observe(line, { childList: true, characterData: true, subtree: true })
  return texts
}

const expectNoToast = () => {
  expect(toast.success, 'a toast from inside a dialog, which VoiceOver never hears').not.toHaveBeenCalled()
  expect(toast.error, 'a toast from inside a dialog, which VoiceOver never hears').not.toHaveBeenCalled()
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => {
  cleanup()
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard)
  else Reflect.deleteProperty(navigator, 'clipboard')
  Reflect.deleteProperty(navigator, 'share')
  Reflect.deleteProperty(navigator, 'canShare')
})

describe('outside a dialog, Copy link keeps its words and says a press through the toast region', () => {
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

  it("says a summary row's share sheet that could not open in the toast region, and a dismissed one not at all", async () => {
    offerShareSheet(() => Promise.reject(new DOMException('Denied', 'NotAllowedError')))
    render(<BulkResultSummary outcomes={[{ email: 'ann@example.com', ok: true, link: LINK, emailed: false }]} skipped={[]} emailRequested />)
    fireEvent.click(screen.getByRole('button', { name: 'Share invite' }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledExactlyOnceWith('Could not open the share sheet.'))

    vi.clearAllMocks()
    offerShareSheet(() => Promise.reject(new DOMException('Dismissed', 'AbortError')))
    fireEvent.click(screen.getByRole('button', { name: 'Share invite' }))
    await waitFor(() => expect(navigator.share).toHaveBeenCalledTimes(1))
    expect(toast.error).not.toHaveBeenCalled()
  })
})

describe('inside a dialog, a press is said in a status line inside it, never in the toast region', () => {
  const resend = () => {
    render(<ResendShareModal link={LINK} email={null} emailed={false} onClose={() => {}} />)
    return screen.getByRole('dialog')
  }

  it("says Copy link's press in the resend dialog's status line, and a second press again", async () => {
    installClipboard()
    const dialog = resend()
    const button = within(dialog).getByRole('button', { name: 'Copy link' })
    const [line] = within(dialog).getAllByRole('status')
    expect(line, 'the line is in place, empty, before a press').toHaveTextContent(/^$/)
    const texts = textsOf(line)

    fireEvent.click(button)
    await waitFor(() => expect(line).toHaveTextContent(/^Invite link copied\.$/))
    fireEvent.click(button)
    await waitFor(() => expect(texts, 'emptied before the second press says it again').toEqual(['Invite link copied.', '', 'Invite link copied.']))
    expect(dialog.contains(line), 'the line lies inside the dialog').toBe(true)
    expect(button).toHaveAccessibleName('Copy link')
    expectNoToast()
  })

  it("says a failed copy of the link in the resend dialog's status line", async () => {
    installClipboard(vi.fn().mockRejectedValue(new Error('denied')))
    const dialog = resend()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Copy link' }))
    await waitFor(() => expect(within(dialog).getByText('Could not copy the link.')).toHaveAttribute('role', 'status'))
    expectNoToast()
  })

  it("says a share sheet that could not open in the resend dialog's status line, and a dismissed one not at all", async () => {
    offerShareSheet(() => Promise.reject(new DOMException('Denied', 'NotAllowedError')))
    const dialog = resend()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Share invite' }))
    await waitFor(() => expect(within(dialog).getByText('Could not open the share sheet.')).toHaveAttribute('role', 'status'))
    expectNoToast()

    offerShareSheet(() => Promise.reject(new DOMException('Dismissed', 'AbortError')))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Share invite' }))
    await waitFor(() => expect(navigator.share).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(within(dialog).queryByText('Could not open the share sheet.')).toBeNull())
    expectNoToast()
  })

  it.each(['Copy message', 'Copy for DM/LinkedIn'])("says %s in the share options' own line, in the resend dialog", async (name) => {
    const writeText = installClipboard()
    const dialog = resend()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Share invite', expanded: false }))
    fireEvent.click(within(dialog).getByRole('button', { name }))
    await waitFor(() => expect(within(dialog).getByText('Invite message copied.')).toHaveAttribute('role', 'status'))
    expect(writeText).toHaveBeenCalledOnce()
    expect(writeText.mock.calls[0][0], 'the message carries the link').toContain(LINK)
    expectNoToast()
  })

  it('says a failed copy of the message in the share options\' own line', async () => {
    installClipboard(vi.fn().mockRejectedValue(new Error('denied')))
    const dialog = resend()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Share invite', expanded: false }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Copy message' }))
    await waitFor(() => expect(within(dialog).getByText('Could not copy the message.')).toHaveAttribute('role', 'status'))
    expectNoToast()
  })

  it("says Copy message in a summary row's share dialog, and the line starts empty each time it opens", async () => {
    installClipboard()
    render(<BulkResultSummary outcomes={[{ email: 'ann@example.com', ok: true, link: LINK, emailed: false }]} skipped={[]} emailRequested />)
    const opener = screen.getByRole('button', { name: 'Share invite' })
    fireEvent.click(opener)
    const dialog = screen.getByRole('dialog', { name: 'Share invite' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Copy message' }))
    await waitFor(() => expect(within(dialog).getByText('Invite message copied.')).toHaveAttribute('role', 'status'))
    expectNoToast()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(opener)
    const reopened = screen.getByRole('dialog', { name: 'Share invite' })
    expect(within(reopened).getByRole('status'), 'the last press is not said again').toHaveTextContent(/^$/)
  })
})
