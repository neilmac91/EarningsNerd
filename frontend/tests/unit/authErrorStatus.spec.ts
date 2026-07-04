import { describe, it, expect, beforeEach, vi } from 'vitest'

// Keep the REAL ApiError class (the shape under test) but stub the axios instance so no
// network request is made. getCurrentUser only calls `api.get('/api/auth/me')`.
// `vi.hoisted` so the mock fn exists before the hoisted vi.mock factory runs.
const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/lib/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client')
  return { ...actual, default: { get } }
})

// Session helpers touch localStorage — stub them so we can assert calls without a DOM store.
vi.mock('@/lib/api/session', () => ({
  markSessionActive: vi.fn(),
  clearSessionActive: vi.fn(),
}))

import { ApiError } from '@/lib/api/client'
import { getErrorStatus } from '@/lib/api/types'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { clearSessionActive } from '@/lib/api/session'

describe('getErrorStatus', () => {
  // Regression: the axios interceptor throws a custom ApiError whose status lives at the top
  // level (`error.status`), NOT under `error.response.status`. Reading only the nested shape
  // returned `undefined` and broke the logged-out (401) detection behind the account avatar.
  it('reads the top-level status of the custom ApiError', () => {
    expect(getErrorStatus(new ApiError(401, 'Not authenticated'))).toBe(401)
    expect(getErrorStatus(new ApiError(404, 'Not found'))).toBe(404)
    expect(getErrorStatus(new ApiError(503, 'Unavailable'))).toBe(503)
  })

  it('still reads the nested status of a raw axios-shaped error', () => {
    expect(getErrorStatus({ response: { status: 401 } })).toBe(401)
  })

  it('returns undefined when there is no status to read', () => {
    expect(getErrorStatus(new Error('boom'))).toBeUndefined()
    expect(getErrorStatus(null)).toBeUndefined()
    expect(getErrorStatus('nope')).toBeUndefined()
    expect(getErrorStatus({})).toBeUndefined()
  })

  it('ignores non-integer statuses (NaN / Infinity) rather than treating them as valid codes', () => {
    expect(getErrorStatus({ status: NaN })).toBeUndefined()
    expect(getErrorStatus({ status: Infinity })).toBeUndefined()
    expect(getErrorStatus({ response: { status: NaN } })).toBeUndefined()
  })
})

describe('getCurrentUserSafe', () => {
  beforeEach(() => {
    get.mockReset()
    vi.mocked(clearSessionActive).mockClear()
  })

  it('resolves to null on a 401 (logged out) instead of throwing', async () => {
    get.mockRejectedValue(new ApiError(401, 'Not authenticated'))
    await expect(getCurrentUserSafe()).resolves.toBeNull()
    // Stale session marker is cleared so we stop attempting pointless refreshes.
    expect(clearSessionActive).toHaveBeenCalled()
  })

  it('re-throws non-401 failures (cold-start 5xx, network) so the query can retry', async () => {
    get.mockRejectedValue(new ApiError(503, 'Service temporarily unavailable'))
    await expect(getCurrentUserSafe()).rejects.toBeInstanceOf(ApiError)
    expect(clearSessionActive).not.toHaveBeenCalled()
  })

  it('resolves to the user on success', async () => {
    const user = {
      id: 1,
      email: 'neil@earningsnerd.io',
      full_name: 'Neil Mac',
      is_pro: true,
      is_beta: false,
      is_admin: true,
      email_verified: true,
    }
    get.mockResolvedValue({ data: user })
    await expect(getCurrentUserSafe()).resolves.toEqual(user)
  })
})
