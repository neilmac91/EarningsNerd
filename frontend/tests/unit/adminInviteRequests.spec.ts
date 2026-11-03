import { afterEach, describe, expect, it, vi } from 'vitest'

/**
 * What the admin invites page posts (EN-BETA PB-01; review of #1965). The page's specs replace createInvite and
 * resendInvite at the module boundary, so this one holds the mapping itself, against the real functions: a mint sends
 * the recipient's recorded request with its addresses, and a Resend always names whether to email. The route reads a
 * re-send that names no choice as "email the bound invite's replacement", so a body that left send_email out of a
 * manual Resend would email the address the admin meant to hand a link to.
 */
const posted = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('@/lib/api/client', async (original) => ({
  ...(await original<typeof import('@/lib/api/client')>()),
  default: { post: posted.post, get: vi.fn() },
}))

import { createInvite, resendInvite } from '@/features/admin/api/admin-api'
import { localDay, permissionDayRange } from '@/features/admin/lib/invitePermission'

const PERMISSION = { requested_via: 'message' as const, requested_on: '2026-10-30' }

afterEach(() => {
  posted.post.mockReset()
})

describe('the bodies the admin invites page posts', () => {
  it('a mint that emails sends the address, the choice and the recorded request', async () => {
    posted.post.mockResolvedValue({ data: {} })
    await createInvite({ email: 'tester@example.com', sendEmail: true, permission: PERMISSION })
    expect(posted.post).toHaveBeenCalledWith('/api/admin/invites', {
      email: 'tester@example.com', send_email: true, permission: PERMISSION,
    })
  })

  it('a mint for a link to share sends no request and says it emails nothing', async () => {
    posted.post.mockResolvedValue({ data: {} })
    await createInvite({ email: 'tester@example.com', sendEmail: false })
    expect(posted.post).toHaveBeenCalledWith('/api/admin/invites', { email: 'tester@example.com', send_email: false })
  })

  it.each([
    ['a manual Resend', { sendEmail: false }, { send_email: false }],
    ['an emailed Resend', { sendEmail: true }, { send_email: true }],
    ['an emailed Resend of a link never emailed', { sendEmail: true, permission: PERMISSION }, { send_email: true, permission: PERMISSION }],
  ] as const)('%s names whether to email, always', async (_label, input, body) => {
    posted.post.mockResolvedValue({ data: {} })
    await resendInvite(7, input)
    expect(posted.post).toHaveBeenCalledWith('/api/admin/invites/7/resend', body)
  })
})

describe("the request day's range (invitePermission.ts), against the server's day check", () => {
  it('offers 364 days back to the admin\'s own today, so every day passes a server a day ahead or behind', () => {
    // The server (routers/admin.py InvitePermission.plausible_day) takes UTC's day + 1 back to UTC's day − 365. The
    // admin's calendar day is at most one day off UTC's, so [local − 364, local] sits inside it in every zone; its
    // edges are pinned server-side in test_the_request_day_holds_every_day_the_form_offers.
    const at = new Date(2026, 10, 2, 12, 0, 0)
    expect(permissionDayRange(at)).toEqual({ min: '2025-11-03', max: '2026-11-02' })
    expect(localDay(at)).toBe('2026-11-02')
  })
})
