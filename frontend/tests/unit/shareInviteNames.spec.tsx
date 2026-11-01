import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ShareInvite from '@/features/admin/components/ShareInvite'

/**
 * Every control in the invite share panel is named by the words it shows (WCAG 2.5.3, Label in Name; E243, chief
 * design on #1784): a reader who sees "Copy message" can say it to a voice control, and a screen reader says what the
 * page shows. The controls took aria-labels that replaced their words ("Copy invite message and link for a DM or
 * LinkedIn" on "Copy for DM/LinkedIn", "Show share options" on "Share invite"), so a spoken label found nothing. Now no
 * control here takes an aria-label: each keeps its words, the toggle's state is its aria-expanded, and "More", beside
 * the platform's own share button, extends its name with a hidden tail
 * (lessons/frontend-hidden-name-tails-bring-their-own-space.md). For each control the case reads the words it shows
 * (its text, less what is hidden from assistive tech and the hidden tail) and holds its whole name to begin with them.
 * In a dialog of their own (a bulk summary row's, E242) the options and Done are held the same way; the dialog's ✕,
 * ui/Modal's, shows no words, so its name ("Close") is its label.
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const LINK = 'https://earningsnerd.io/invite/abc123'

/** The words a sighted reader sees on a control: its text, less what assistive tech never reads and the sr-only tail. */
function shownWords(control: HTMLElement): string {
  const copy = control.cloneNode(true) as HTMLElement
  for (const hidden of copy.querySelectorAll('[aria-hidden="true"], .sr-only')) hidden.remove()
  return (copy.textContent ?? '').replace(/\s+/g, ' ').trim()
}

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** The share panel's controls, each with the name it is read by and the words it shows. */
function controls(container: HTMLElement) {
  return [...within(container).queryAllByRole('button'), ...within(container).queryAllByRole('link')].map((control) => ({
    control,
    words: shownWords(control),
  }))
}

/** `except` holds a control that shows no words, a dialog's ✕, which its aria-label names. */
function expectEachNameBeginsWithItsWords(container: HTMLElement, except: HTMLElement[] = []) {
  const all = controls(container).filter(({ control }) => !except.includes(control))
  expect(all.length).toBeGreaterThan(0)
  for (const { control, words } of all) {
    expect(words, 'every share control shows words').not.toBe('')
    expect(control, `"${words}" begins its control's name`).toHaveAccessibleName(new RegExp(`^${escape(words)}`))
  }
  const labelled = [...container.querySelectorAll('[aria-label]')].filter((element) => !except.includes(element as HTMLElement))
  expect(labelled, 'no control replaces its words with an aria-label').toHaveLength(0)
}

afterEach(() => {
  Reflect.deleteProperty(navigator, 'share')
  Reflect.deleteProperty(navigator, 'canShare')
})

describe("the invite share panel's controls are named by the words they show (E243)", () => {
  it('without the platform share sheet: the toggle is "Share invite", and each option its own words', async () => {
    const { container } = render(<ShareInvite link={LINK} email={null} />)
    const toggle = screen.getByRole('button', { name: 'Share invite', expanded: false })
    expectEachNameBeginsWithItsWords(container)
    await userEvent.setup().click(toggle)
    expect(toggle).toHaveAccessibleName('Share invite')
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    // WhatsApp opens a new tab and says so after its words (E281); Messages and Email open in place.
    expect(screen.getAllByRole('link').map((link) => link.textContent!.trim())).toEqual(['WhatsApp (opens in a new tab)', 'Messages', 'Email'])
    for (const name of [/^WhatsApp ?\(opens in a new tab\)$/, 'Messages', 'Email']) expect(screen.getByRole('link', { name })).toBeInTheDocument()
    for (const name of ['Copy for DM/LinkedIn', 'Copy message']) expect(screen.getByRole('button', { name })).toBeInTheDocument()
    expectEachNameBeginsWithItsWords(container)
  })

  it('with the platform share sheet: "Share invite" opens it, and "More" is read "More share options"', async () => {
    Object.defineProperty(navigator, 'share', { value: vi.fn(), configurable: true })
    Object.defineProperty(navigator, 'canShare', { value: vi.fn(() => true), configurable: true })
    const { container } = render(<ShareInvite link={LINK} email="ann@example.com" />)
    const more = await screen.findByRole('button', { name: 'More share options', expanded: false })
    expect(shownWords(more)).toBe('More')
    expect(screen.getByRole('button', { name: 'Share invite' })).not.toHaveAttribute('aria-expanded')
    await userEvent.setup().click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expectEachNameBeginsWithItsWords(container)
  })

  it('in a dialog of their own: the opener, the options and Done are named by their words', async () => {
    const { container } = render(<ShareInvite link={LINK} email="ann@example.com" optionsIn="dialog" />)
    expectEachNameBeginsWithItsWords(container)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Share invite', expanded: false }))
    const dialog = screen.getByRole('dialog', { name: 'Share invite' })
    for (const name of [/^WhatsApp ?\(opens in a new tab\)$/, 'Messages', 'Email']) expect(within(dialog).getByRole('link', { name })).toBeInTheDocument()
    for (const name of ['Copy for DM/LinkedIn', 'Copy message', 'Done']) expect(within(dialog).getByRole('button', { name })).toBeInTheDocument()
    expectEachNameBeginsWithItsWords(dialog, [within(dialog).getByRole('button', { name: 'Close' })])
  })
})
