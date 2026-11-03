import { describe, expect, it, vi } from 'vitest'

/**
 * The invite is a live single-use credential: an invited social sign-up sends it in the body of
 * the POST start and follows the URL the backend returns. Nothing about the token reaches a URL.
 * Both starts ask for the OAuth session handoff (E29 (5)), the compatibility gate between this frontend and the API:
 * the plain GET start with `handoff=1`, the POST start with `handoff: true` in its body. An API that predates the
 * handoff ignores both and sets the session cookies on the callback's redirect, as before.
 */
const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('@/lib/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client')
  return { ...actual, default: { post } }
})

import { register, startOAuthWithInvite } from '@/features/auth/api/auth-api'
import { oauthStartHref } from '@/features/auth/lib/oauthStart'

describe('invited OAuth start keeps the invite out of URLs', () => {
  const agreement = { adult_eligible: true, terms_accepted: true, terms_version: '2026-10-24', eligibility_version: '2026-10-24' } as const

  it('sends the same complete, flat assent on public OAuth signup and email signup', async () => {
    post.mockResolvedValue({ data: { url: 'https://accounts.example/consent?state=abc' } })
    await startOAuthWithInvite('google', undefined, agreement)
    expect(post).toHaveBeenLastCalledWith('/api/auth/google/start', { ...agreement, handoff: true })
    await register('reader@example.test', 'long-password', 'Reader', 'captcha-token', undefined, agreement)
    expect(post).toHaveBeenLastCalledWith('/api/auth/register', {
      email: 'reader@example.test', password: 'long-password', full_name: 'Reader', invite_code: undefined, ...agreement,
    }, { headers: { 'cf-turnstile-response': 'captcha-token' } })
  })

  it('POSTs the invite in the body and returns the provider URL', async () => {
    post.mockResolvedValueOnce({ data: { url: 'https://accounts.example/consent?state=abc' } })
    const url = await startOAuthWithInvite('google', 'tok en+/=1')
    expect(post).toHaveBeenCalledWith('/api/auth/google/start', { invite: 'tok en+/=1', handoff: true })
    expect(url).toBe('https://accounts.example/consent?state=abc')
  })

  it('the plain start href takes no invite, and asks for the handoff with exactly handoff=1', () => {
    expect(oauthStartHref('', 'apple')).toBe('/api/auth/apple?handoff=1')
    expect(oauthStartHref('https://api.example', 'google')).toBe('https://api.example/api/auth/google?handoff=1')
    expect(new URL(oauthStartHref('https://api.example', 'google')).searchParams.getAll('handoff')).toEqual(['1'])
    // The signature itself is the gate: a second argument does not type-check.
    expect((oauthStartHref as unknown as (...args: unknown[]) => string).length).toBe(2)
  })
})
