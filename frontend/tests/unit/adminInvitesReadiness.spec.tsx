import React from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { subDays } from 'date-fns'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * /admin/invites reads what holds new invite links and invitation email (GET /api/admin/invites/readiness) and turns
 * off what is held, failing closed while the read loads or after it fails; the list and Revoke never wait on it.
 * Email is off by default, and an emailed send carries the recipient's recorded request (how and when they asked).
 * Resend always says whether to email, on the first email's terms. Each row says what is known of its email, and
 * never that it was received, read or opened (EN-BETA PB-01).
 */

vi.mock('@/features/admin/api/admin-api', async (original) => ({
  ...(await original<typeof import('@/features/admin/api/admin-api')>()),
  getInviteReadiness: vi.fn(),
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  resendInvite: vi.fn(),
  revokeInvite: vi.fn(),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import AdminInvitesPage from '@/app/admin/invites/page'
import {
  DELIVERY_STATUSES,
  createInvite,
  getInviteReadiness,
  listInvites,
  resendInvite,
  revokeInvite,
  type CreateInviteInput,
  type InviteReadiness,
  type InviteRecord,
  type MintResult,
} from '@/features/admin/api/admin-api'
import { localDay } from '@/features/admin/lib/invitePermission'
import {
  COHORT_EXCEPTION_HELD, COHORT_ONLY, COLLECTION_HELD, EMAIL_HELD, READY, delivery, pendingInvite,
} from './fixtures/inviteReadiness'

const mint = (email: string, emailed: boolean): MintResult => ({
  id: email.length,
  email,
  invite_link: `https://earningsnerd.io/register?invite=${email.split('@')[0]}`,
  expires_at: '2026-11-09T00:00:00Z',
  emailed,
  cohort: null,
  delivery_status: emailed ? 'accepted' : null,
})

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AdminInvitesPage />
    </QueryClientProvider>,
  )
}

function answer(readiness: InviteReadiness | Error | 'pending', invites: InviteRecord[] = []) {
  if (readiness === 'pending') vi.mocked(getInviteReadiness).mockReturnValue(new Promise<InviteReadiness>(() => {}))
  else if (readiness instanceof Error) vi.mocked(getInviteReadiness).mockRejectedValue(readiness)
  else vi.mocked(getInviteReadiness).mockResolvedValue(readiness)
  vi.mocked(listInvites).mockResolvedValue(invites)
}

/** Enter addresses into the chips field, and wait for the counter to take them. */
async function stage(addresses: string) {
  const field = screen.getByLabelText('Email addresses')
  fireEvent.change(field, { target: { value: addresses } })
  fireEvent.blur(field)
  await waitFor(() => expect(screen.getByText(/to invite/).textContent).toMatch(/^[1-9]\d* to invite/))
}

const emailBox = () => screen.getByRole('checkbox', { name: /Email invites/ })
const sendButton = () => screen.getByRole('button', { name: 'Send invites' })
/** A banner notice by its title: the Notice root that holds it. */
const notice = (title: string) => screen.getByText(title).closest('[role="status"], [role="alert"]') as HTMLElement
/** The "Invitation email" cell of the row for `email`. */
const emailCell = (email: string) => within(screen.getByText(email).closest('tr') as HTMLElement).getAllByRole('cell')[3]

beforeEach(() => {
  for (const fn of [getInviteReadiness, listInvites, createInvite, resendInvite, revokeInvite]) vi.mocked(fn).mockReset()
})

describe('Email invites is off by default', () => {
  it('a send with nothing ticked asks for no email and records no request', async () => {
    answer(READY)
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, false))
    renderPage()
    await screen.findByText(/No invites yet/)
    await waitFor(() => expect(emailBox()).not.toHaveAttribute('aria-disabled'))
    expect(emailBox()).not.toBeChecked()
    expect(screen.queryByLabelText('How they asked')).not.toBeInTheDocument()

    await stage('ann@example.com')
    await userEvent.setup().click(sendButton())
    await waitFor(() => expect(createInvite).toHaveBeenCalledTimes(1))
    const [input] = vi.mocked(createInvite).mock.calls[0]
    expect(input.sendEmail).toBe(false)
    expect(input.permission).toBeUndefined()
    expect(await screen.findByText('1 invite link created')).toBeInTheDocument()
  })
})

describe('the readiness banner says what holds what, and the page turns it off', () => {
  it('with invitation email held, says so with its reason and keeps the box focusable but unavailable', async () => {
    answer(EMAIL_HELD)
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, false))
    renderPage()
    await screen.findByText('Invitation email is on hold')
    const held = notice('Invitation email is on hold')
    expect(held).toHaveAttribute('role', 'status')
    expect(held).toHaveTextContent('Invitation email is switched off (LEGAL_INVITATION_EMAIL_ENABLED is off).')
    expect(held).toHaveTextContent('You can still create invite links with Email invites off and share them yourself.')
    expect(screen.queryByText('Registration is on hold')).not.toBeInTheDocument()

    const box = emailBox()
    expect(box).toHaveAttribute('aria-disabled', 'true')
    expect(box).not.toBeDisabled()
    expect(box).toHaveAccessibleDescription('Invitation email is on hold (see above), so these invites are links you share yourself.')
    const user = userEvent.setup()
    await user.click(box)
    expect(box).not.toBeChecked()
    expect(box).toHaveFocus()
    expect(screen.queryByLabelText('How they asked')).not.toBeInTheDocument()

    // New links still go out, to share by hand.
    await stage('ann@example.com')
    expect(sendButton()).not.toHaveAttribute('aria-disabled')
    await user.click(sendButton())
    await waitFor(() => expect(createInvite).toHaveBeenCalledTimes(1))
    expect(vi.mocked(createInvite).mock.calls[0][0].sendEmail).toBe(false)
  })

  it('with registration held, holds new links and Resend apart from email, and keeps the list and Revoke', async () => {
    answer(COLLECTION_HELD, [pendingInvite({ delivery: delivery() })])
    vi.mocked(revokeInvite).mockResolvedValue({ message: 'Invite revoked', invite_id: 1, status: 'revoked' })
    renderPage()
    await screen.findByText('Registration is on hold')
    const registration = notice('Registration is on hold')
    expect(registration).toHaveTextContent('New registrations are switched off (LEGAL_COLLECTION_ENABLED is off). The operator turns it on in the server settings.')
    expect(registration).toHaveTextContent("The operator details aren't published (LEGAL_OPERATOR_PUBLISHED is off).")
    expect(registration).toHaveTextContent("Until registration opens, you can't create invite links or resend one. The list and Revoke still work.")
    const email = notice('Invitation email is on hold')
    expect(email).toHaveTextContent('It waits for registration to open.')
    expect(email).not.toHaveTextContent('share them yourself')
    expect(emailBox()).toHaveAccessibleDescription('Invitation email is on hold while registration is (see above).')

    const user = userEvent.setup()
    await stage('ann@example.com')
    const send = sendButton()
    expect(send).toHaveAttribute('aria-disabled', 'true')
    expect(send).not.toBeDisabled()
    expect(send).toHaveAccessibleDescription('New invite links are off while registration is on hold (see above).')
    await user.click(send)
    expect(createInvite).not.toHaveBeenCalled()

    const resend = await screen.findByRole('button', { name: 'Resend invite to alice@example.com' })
    expect(resend).toHaveAttribute('aria-disabled', 'true')
    expect(resend).toHaveAccessibleDescription('New invite links are off while registration is on hold (see above).')
    await user.click(resend)
    expect(resendInvite).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Revoke invite to alice@example.com' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Revoke invite' }))
    await waitFor(() => expect(revokeInvite).toHaveBeenCalledWith(1))
  })

  it('with only the invited cohort open, says so, needs the cohort and sends links for it', async () => {
    answer(COHORT_ONLY)
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, false))
    renderPage()
    await screen.findByText('Registration is open to the invited cohort only')
    const registration = notice('Registration is open to the invited cohort only')
    expect(registration).toHaveAttribute('role', 'status')
    expect(registration).toHaveTextContent('New registrations are switched off (LEGAL_COLLECTION_ENABLED is off).')
    expect(registration).toHaveTextContent(
      'Until registration opens, a new invite link must be bound to an address and carry the cohort set in LEGAL_INVITED_COHORT, exactly, and only such a link can be resent.',
    )
    expect(screen.queryByText('Registration is on hold')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Cohort (required)')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Cohort (required)'), 'cohort-synthetic-7f3a9c')
    await stage('ann@example.com')
    expect(sendButton()).not.toHaveAttribute('aria-disabled')
    await user.click(sendButton())
    await waitFor(() => expect(createInvite).toHaveBeenCalledTimes(1))
    expect(vi.mocked(createInvite).mock.calls[0][0]).toMatchObject({ email: 'ann@example.com', cohort: 'cohort-synthetic-7f3a9c', sendEmail: false })
  })

  it('keeps the cohort optional while registration is open', async () => {
    answer(READY)
    renderPage()
    await screen.findByText(/No invites yet/)
    expect(screen.getByLabelText('Cohort (optional)')).toBeInTheDocument()
  })

  it('says something it does not recognize holds a capability, rather than nothing', async () => {
    answer({
      collection: { available: true, reasons: [] }, invited_cohort: COHORT_EXCEPTION_HELD,
      invitation_email: { available: false, reasons: ['a_new_condition'] },
    })
    renderPage()
    await screen.findByText('Invitation email is on hold')
    expect(notice('Invitation email is on hold')).toHaveTextContent(
      "Something this page doesn't recognize holds it. The server settings say what.",
    )
  })

  it('holds new links and invitation email while the check is in flight, saying so in words, never a notice', async () => {
    answer('pending')
    renderPage()
    const checking = screen.getByText('Checking whether invite links and invitation email are available…')
    expect(checking.tagName).toBe('P')
    expect(checking).toHaveAttribute('role', 'status')
    await screen.findByText(/No invites yet/)
    await stage('ann@example.com')
    expect(sendButton()).toHaveAttribute('aria-disabled', 'true')
    expect(sendButton()).toHaveAccessibleDescription('New invite links wait for the availability check above.')
    expect(emailBox()).toHaveAttribute('aria-disabled', 'true')
  })

  it('fails closed when the check fails: says so with Try again, holds links and email, keeps the list and Revoke', async () => {
    answer(new Error('network'), [pendingInvite()])
    vi.mocked(getInviteReadiness).mockRejectedValueOnce(new Error('network')).mockResolvedValue(READY)
    renderPage()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Could not check what is available.')
    expect(alert).toHaveTextContent('Until the check answers, new invite links, Resend and invitation email stay off. The list and Revoke still work.')
    expect(await screen.findByText('alice@example.com')).toBeInTheDocument()

    await stage('ann@example.com')
    expect(sendButton()).toHaveAttribute('aria-disabled', 'true')
    expect(sendButton()).toHaveAccessibleDescription('New invite links are off until the availability check above answers.')
    expect(emailBox()).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByRole('button', { name: 'Resend invite to alice@example.com' })).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByRole('button', { name: 'Revoke invite to alice@example.com' })).not.toHaveAttribute('aria-disabled')

    const retry = within(alert).getByRole('button', { name: 'Try again' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(getInviteReadiness).toHaveBeenCalledTimes(2)
    await waitFor(() => expect(sendButton()).not.toHaveAttribute('aria-disabled'))
    expect(emailBox()).not.toHaveAttribute('aria-disabled')
    // The Retry left while it held focus: focus goes to the top of the form it unblocked.
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Invite people', level: 2 })).toHaveFocus())
  })
})

describe("an emailed invite records the recipient's request", () => {
  async function openEmailing() {
    answer(READY)
    vi.mocked(createInvite).mockImplementation(async (input: CreateInviteInput) => mint(input.email as string, true))
    renderPage()
    await screen.findByText(/No invites yet/)
    await waitFor(() => expect(emailBox()).not.toHaveAttribute('aria-disabled'))
    const user = userEvent.setup()
    await user.click(emailBox())
    expect(emailBox()).toBeChecked()
    return user
  }

  it('asks how and when they asked, both starting empty, and sends nothing until both are given', async () => {
    const user = await openEmailing()
    const group = screen.getByRole('group', { name: 'Their request for an invitation' })
    expect(group).toHaveTextContent(
      'Only email people who asked you for an invitation. Record how and when they asked: it covers every address in this send.',
    )
    const via = screen.getByLabelText('How they asked') as HTMLSelectElement
    const on = screen.getByLabelText('When they asked') as HTMLInputElement
    expect(via.value).toBe('')
    expect([...via.options].map((option) => option.text)).toEqual(['Choose one', 'Email', 'Message', 'Call', 'In person', 'Other'])
    expect(on).toHaveAttribute('type', 'date')
    // Empty, not today: both halves of the record are the admin's deliberate entries (chief design on #1965).
    expect(on.value).toBe('')
    expect(on).toHaveAttribute('max', localDay())
    expect(on).toHaveAttribute('min')
    // The recipient's request, never an admin's tick.
    expect(screen.getAllByRole('checkbox')).toEqual([emailBox()])

    await stage('ann@example.com, bob@example.com')
    await user.click(sendButton())
    expect(createInvite).not.toHaveBeenCalled()
    expect(via).toHaveAttribute('aria-invalid', 'true')
    expect(on).toHaveAttribute('aria-invalid', 'true')
    expect(via).toHaveFocus()
    expect(screen.getAllByRole('alert').map((alert) => alert.textContent)).toEqual([
      'Choose how they asked for an invitation.',
      'Enter the day they asked, within the last year.',
    ])

    await user.selectOptions(via, 'message')
    expect(screen.getByRole('alert')).toHaveTextContent('Enter the day they asked, within the last year.')
    await user.click(sendButton())
    expect(createInvite).not.toHaveBeenCalled()
    expect(on).toHaveFocus()
    const day = localDay(subDays(new Date(), 2))
    fireEvent.change(on, { target: { value: day } })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await user.click(sendButton())
    await waitFor(() => expect(createInvite).toHaveBeenCalledTimes(2))
    for (const [input] of vi.mocked(createInvite).mock.calls) {
      expect(input.sendEmail).toBe(true)
      expect(input.permission).toEqual({ requested_via: 'message', requested_on: day })
    }
    // The provider's acceptance, said as that, never as a send that arrived.
    expect(await screen.findByText('2 created · 2 accepted by the email provider')).toBeInTheDocument()
    expect(screen.getByText(/Accepted means the email provider took it, not that it was delivered\./)).toBeInTheDocument()
  })

  it('refuses a day outside the last year, or none, and says which field', async () => {
    const user = await openEmailing()
    await user.selectOptions(screen.getByLabelText('How they asked'), 'call')
    const on = screen.getByLabelText('When they asked')
    await stage('ann@example.com')
    for (const day of ['', localDay(subDays(new Date(), 400))]) {
      fireEvent.change(on, { target: { value: day } })
      await user.click(sendButton())
      expect(createInvite).not.toHaveBeenCalled()
      expect(on).toHaveAttribute('aria-invalid', 'true')
      expect(on).toHaveFocus()
      expect(screen.getByRole('alert')).toHaveTextContent('Enter the day they asked, within the last year.')
    }
  })
})

describe('Resend says whether to email, on the first email\'s terms', () => {
  const rows = [
    pendingInvite({ id: 1, email: 'emailed@example.com', delivery: delivery() }),
    pendingInvite({ id: 2, email: 'manual@example.com' }),
    pendingInvite({ id: 3, email: 'unsubscribed@example.com', delivery: delivery({ status: 'delivered' }), email_suppression: 'unsubscribed' }),
  ]

  it.each([
    ['with invitation email available, only the link emailed before and not suppressed', READY, [true, false, false]],
    ['with invitation email held, none', EMAIL_HELD, [false, false, false]],
  ] as const)('%s', async (_name, readiness, emails) => {
    answer(readiness, rows)
    vi.mocked(resendInvite).mockImplementation(async (id, input) => ({
      ...mint(rows[id - 1].email as string, input.sendEmail),
      id: 10 + id,
      revoked_invite_id: id,
    }))
    renderPage()
    const user = userEvent.setup()
    for (const row of rows) {
      const resend = await screen.findByRole('button', { name: `Resend invite to ${row.email}` })
      await waitFor(() => expect(resend).not.toHaveAttribute('aria-disabled'))
      await user.click(resend)
      await screen.findByRole('dialog')
      await user.keyboard('{Escape}')
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    }
    // Always explicit: left out, the backend would email any bound invite's replacement.
    expect(vi.mocked(resendInvite).mock.calls).toEqual(rows.map((row, i) => [row.id, { sendEmail: emails[i] }]))
  })
})

describe('each row says what is known of its email', () => {
  it('shows every delivery state in words that never claim it was received, read or opened', async () => {
    answer(READY, DELIVERY_STATUSES.map((status, i) => pendingInvite({ id: i + 1, email: `${status}@example.com`, delivery: delivery({ status }) })))
    renderPage()
    await screen.findByText('accepted@example.com')
    expect(screen.getAllByRole('columnheader')[3]).toHaveTextContent('Invitation email')
    for (const status of DELIVERY_STATUSES) {
      expect(emailCell(`${status}@example.com`).textContent, status).not.toMatch(/\b(received|inbox|read|opened|seen)\b/i)
    }
    const accepted = emailCell('accepted@example.com')
    expect(within(accepted).getByText('Accepted by the email provider')).toBeInTheDocument()
    expect(within(accepted).getByText("Delivery isn't confirmed.")).toBeInTheDocument()
    expect(within(accepted).getByText('Asked by email, Oct 30, 2026')).toBeInTheDocument()
    expect(accepted.textContent).not.toMatch(/\bdelivered\b/i)
    const delivered = emailCell('delivered@example.com')
    expect(within(delivered).getByText("Delivered to the recipient's mail server")).toBeInTheDocument()
    expect(within(delivered).getByText('Not proof it reached them.')).toBeInTheDocument()
    expect(within(emailCell('unknown@example.com')).getByText('Outcome unknown')).toBeInTheDocument()
  })

  it('says a link never emailed is not emailed', async () => {
    answer(READY, [pendingInvite(), pendingInvite({ id: 2, email: null })])
    renderPage()
    await screen.findByText('alice@example.com')
    expect(emailCell('alice@example.com')).toHaveTextContent(/^Not emailed$/)
    expect(emailCell('Link only')).toHaveTextContent(/^Not emailed$/)
  })

  it("never says the state's words twice: a note whose cause the state names reads what follows instead", async () => {
    answer(READY, [
      pendingInvite({ id: 1, email: 'bounced@example.com', delivery: delivery({ status: 'bounced', bounce_type: 'permanent' }), email_suppression: 'hard_bounce' }),
      pendingInvite({ id: 2, email: 'spam@example.com', delivery: delivery({ status: 'complained' }), email_suppression: 'complaint' }),
      // A cause the state does not name keeps its own note.
      pendingInvite({ id: 3, email: 'later@example.com', delivery: delivery({ status: 'delivered' }), email_suppression: 'hard_bounce' }),
      pendingInvite({ id: 4, email: 'soft@example.com', delivery: delivery({ status: 'bounced', bounce_type: 'temporary' }), email_suppression: 'hard_bounce' }),
    ])
    renderPage()
    await screen.findByText('bounced@example.com')
    for (const [email, state, note] of [
      ['bounced@example.com', 'Bounced permanently', 'No invitation email goes to this address.'],
      ['spam@example.com', 'Reported as spam', 'No invitation email goes to this address.'],
      ['later@example.com', "Delivered to the recipient's mail server", 'Bounced permanently.'],
      ['soft@example.com', 'Bounced temporarily', 'Bounced permanently.'],
    ] as const) {
      const cell = emailCell(email)
      expect(within(cell).getByText(state), email).toBeInTheDocument()
      expect(within(cell).getByText(note), email).toHaveClass('font-medium')
      expect(cell.textContent?.split(state.replace(/\.$/, '')).length, `${email} says its state twice`).toBe(2)
    }
  })

  it('shows a suppressed address as a note of its own, and its Resend emails nothing', async () => {
    answer(READY, [pendingInvite({ delivery: delivery({ status: 'complained' }), email_suppression: 'complaint' })])
    vi.mocked(resendInvite).mockResolvedValue({ ...mint('alice@example.com', false), revoked_invite_id: 1 })
    renderPage()
    await screen.findByText('alice@example.com')
    const cell = emailCell('alice@example.com')
    expect(within(cell).getAllByText('Reported as spam')).toHaveLength(1) // the email's own state
    // The state already names the cause, so the note says what follows, never the same words again (chief design on #1965).
    expect(within(cell).getByText('No invitation email goes to this address.')).toHaveClass('font-medium') // the address's note
    expect(cell.textContent?.match(/Reported as spam/g)).toHaveLength(1)
    expect(cell).toHaveTextContent('Resend makes a new link without emailing it.')

    const resend = screen.getByRole('button', { name: 'Resend invite to alice@example.com' })
    await waitFor(() => expect(resend).not.toHaveAttribute('aria-disabled'))
    await userEvent.setup().click(resend)
    await waitFor(() => expect(resendInvite).toHaveBeenCalledWith(1, { sendEmail: false }))
  })
})
