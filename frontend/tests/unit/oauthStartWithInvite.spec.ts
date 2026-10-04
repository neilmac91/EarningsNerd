import { describe, expect, it, vi } from 'vitest'

/**
 * The invite is a live single-use credential: an invited social sign-up sends it in the body of
 * the POST start and follows the URL the backend returns. Nothing about the token reaches a URL.
 */
const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('@/lib/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client')
  return { ...actual, default: { post } }
})

import { startOAuthWithInvite } from '@/features/auth/api/auth-api'
import { oauthStartHref } from '@/features/auth/lib/oauthStart'

describe('invited OAuth start keeps the invite out of URLs', () => {
  it('POSTs the invite in the body and returns the provider URL', async () => {
    post.mockResolvedValueOnce({ data: { url: 'https://accounts.example/consent?state=abc' } })
    const url = await startOAuthWithInvite('google', 'tok en+/=1')
    expect(post).toHaveBeenCalledWith('/api/auth/google/start', { invite: 'tok en+/=1' })
    expect(url).toBe('https://accounts.example/consent?state=abc')
  })

  it('the plain start href takes no invite', () => {
    expect(oauthStartHref('', 'apple')).toBe('/api/auth/apple')
    // The signature itself is the gate: a second argument does not type-check.
    expect((oauthStartHref as unknown as (...args: unknown[]) => string).length).toBe(2)
  })
})
