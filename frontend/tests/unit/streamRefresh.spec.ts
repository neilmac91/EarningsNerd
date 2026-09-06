import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

// postStreamWithRefresh is the ONE home for the raw-SSE 401 → /refresh → replay dance shared by
// all three sanctioned stream readers (summary, Copilot, Analysis). ensureRefreshed() (from the
// axios client) wraps refreshAccessToken, so mocking the latter controls the refresh outcome while
// the real single-flight promise is exercised.
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))

import { postStreamWithRefresh } from '@/lib/api/streamRefresh'
import { refreshAccessToken } from '@/lib/api/refresh'
import { hasActiveSession, advanceSessionGeneration, markSessionActive, subscribeSessionLoss } from '@/lib/api/session'

const res = (status: number) =>
  ({ status, ok: status >= 200 && status < 300 }) as unknown as Response

const flushMacrotask = () => new Promise((r) => setTimeout(r, 0))

describe('postStreamWithRefresh', () => {
  beforeEach(() => {
    vi.mocked(refreshAccessToken).mockReset()
    window.localStorage.setItem('en_session_active', '1') // logged-in marker
  })
  afterEach(() => {
    window.localStorage.clear()
  })

  it('returns a non-401 response unchanged, with no refresh', async () => {
    const doPost = vi.fn().mockResolvedValue(res(200))
    const out = await postStreamWithRefresh(doPost)
    expect(out.status).toBe(200)
    expect(doPost).toHaveBeenCalledTimes(1)
    expect(refreshAccessToken).not.toHaveBeenCalled()
  })

  it('on 401 with an active session: refreshes once and returns the replayed response', async () => {
    vi.mocked(refreshAccessToken).mockResolvedValue(undefined)
    const doPost = vi.fn().mockResolvedValueOnce(res(401)).mockResolvedValueOnce(res(200))
    const out = await postStreamWithRefresh(doPost)
    expect(out.status).toBe(200)
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(doPost).toHaveBeenCalledTimes(2)
  })

  // Nit #3.1: the in-between path — refresh succeeds but the replay STILL 401s (account disabled
  // mid-session / new cookie didn't take). Must be exactly one refresh + one replay, never a
  // refresh→replay→401→refresh loop.
  it('replay still 401 after a successful refresh: one refresh, one replay, no loop', async () => {
    vi.mocked(refreshAccessToken).mockResolvedValue(undefined)
    const doPost = vi.fn().mockResolvedValue(res(401))
    const out = await postStreamWithRefresh(doPost)
    expect(out.status).toBe(401)
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(doPost).toHaveBeenCalledTimes(2)
  })

  it('clears the session marker and returns the 401 (no replay) when refresh fails', async () => {
    vi.mocked(refreshAccessToken).mockRejectedValue(Object.assign(new Error('refresh rejected'), { response: { status: 401 } }))
    const doPost = vi.fn().mockResolvedValue(res(401))
    const out = await postStreamWithRefresh(doPost)
    expect(out.status).toBe(401)
    expect(doPost).toHaveBeenCalledTimes(1)
    expect(hasActiveSession()).toBe(false)
  })

  it('does not refresh a guest 401 (no active-session marker)', async () => {
    window.localStorage.clear()
    const doPost = vi.fn().mockResolvedValue(res(401))
    const out = await postStreamWithRefresh(doPost)
    expect(out.status).toBe(401)
    expect(refreshAccessToken).not.toHaveBeenCalled()
    expect(doPost).toHaveBeenCalledTimes(1)
  })

  // Nit #3.2: the load-bearing reason this reuses ensureRefreshed() rather than a local refresh —
  // two concurrent 401s must fire exactly ONE /refresh, because two calls on the single-use
  // ROTATING refresh token invalidate each other and log the user out. This fails if someone
  // "simplifies" the helper back to a bare refreshAccessToken() call.
  it('shares a single in-flight refresh across concurrent callers', async () => {
    let releaseRefresh!: () => void
    vi.mocked(refreshAccessToken).mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          releaseRefresh = resolve
        }),
    )
    const doPostA = vi.fn().mockResolvedValueOnce(res(401)).mockResolvedValueOnce(res(200))
    const doPostB = vi.fn().mockResolvedValueOnce(res(401)).mockResolvedValueOnce(res(200))

    const pA = postStreamWithRefresh(doPostA)
    const pB = postStreamWithRefresh(doPostB)
    // Let both first POSTs resolve and both callers park on the SAME in-flight refresh promise.
    await flushMacrotask()
    releaseRefresh()
    const [a, b] = await Promise.all([pA, pB])

    expect(a.status).toBe(200)
    expect(b.status).toBe(200)
    expect(refreshAccessToken).toHaveBeenCalledTimes(1) // ONE /refresh for both, not two
  })
})


describe('stream refresh session ownership', () => {
  it.each([undefined, 429, 503])('preserves response and active marker on transient refresh status %s', async (status) => {
    markSessionActive()
    const lost = vi.fn()
    const unsubscribe = subscribeSessionLoss(lost)
    vi.mocked(refreshAccessToken).mockRejectedValue(Object.assign(new Error('temporary refresh failure'), {
      response: status === undefined ? undefined : { status },
    }))
    const denied = res(401)
    const doPost = vi.fn().mockResolvedValue(denied)
    try {
      expect(await postStreamWithRefresh(doPost)).toBe(denied)
      expect(doPost).toHaveBeenCalledTimes(1)
      expect(hasActiveSession()).toBe(true)
      expect(lost).not.toHaveBeenCalled()
    } finally { unsubscribe() }
  })

  it('does not replay or notify loss when the original response belongs to A', async () => {
    markSessionActive()
    let resolve!: (response: Response) => void
    const doPost = vi.fn(() => new Promise<Response>((yes) => { resolve = yes }))
    const lost = vi.fn()
    const unsubscribe = subscribeSessionLoss(lost)
    const pending = postStreamWithRefresh(doPost)
    advanceSessionGeneration()
    markSessionActive()
    try {
      const denied = res(401)
      resolve(denied)
      expect(await pending).toBe(denied)
      expect(doPost).toHaveBeenCalledTimes(1)
      expect(hasActiveSession()).toBe(true)
      expect(lost).not.toHaveBeenCalled()
    } finally { unsubscribe() }
  })
})
