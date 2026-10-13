import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useWhatChanged } from '@/features/summaries/hooks/useWhatChanged'
import { queryKeys } from '@/lib/queryKeys'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'

/**
 * The change report is served per viewer (E17, PR B): a Pro reader gets every Item 1A wording
 * change, everyone else the teaser. The hook keys the read by the signed-in reader, installs the
 * page's anonymous server seed on the anonymous entry, and issues the read only once /me has
 * settled and is not being re-read. That order is the fix for an expired Pro token: the endpoint
 * reads the user optionally, so a stale token is served the teaser with a 200 and nothing in that
 * response would refresh it; /me refreshes it first, and the report's read carries the fresh
 * token. A fresh cached /me makes no request, so a Pro reader served the teaser has /me and the
 * report re-read once. A signed-in reader's failed read keeps the seed as the report, provisional.
 */

const api = vi.hoisted(() => ({ getWhatChanged: vi.fn(), getCurrentUserSafe: vi.fn() }))
vi.mock('@/features/summaries/api/summaries-api', () => ({ getWhatChanged: api.getWhatChanged }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))

const SEED: ChangeReport = {
  has_prior: true,
  comparison_basis: 'Year over year',
  prior_filing: null,
  metrics: null,
  reporting_currency: null,
  risks: null,
  key_changes: null,
  has_changes: false,
  section_changes: null,
}
const SERVED: ChangeReport = { ...SEED, has_changes: true }
const READER = { id: 7, email: 'reader@example.test', full_name: 'Reader', is_pro: true, is_beta: false, is_admin: false, email_verified: true }
const WORDING = {
  section: 'item_1a' as const,
  section_label: 'Risk factors',
  engine_version: 1,
  prior_filing: null,
  status: 'ok' as const,
  reason: null,
  current: { status: 'ok', extracted_at: null, reference_only: false, char_count: 10, paragraph_count: 2 },
  prior: { status: 'ok', extracted_at: null, reference_only: false, char_count: 10, paragraph_count: 2 },
  paragraphs: { prior: 2, later: 2, prior_excluded: 0, later_excluded: 0 },
  counts: { unchanged: 1, modified: 1, added: 0, removed: 0, moved: 0 },
  words: { later_total: 10, inserted: 1, deleted: 1, changed_ratio: 0.1 },
  has_changes: true,
  items: [],
  items_total: 1,
}
const TEASER: ChangeReport = { ...SERVED, section_changes: { ...WORDING, access: 'teaser', truncated: true } }
const FULL: ChangeReport = { ...SERVED, section_changes: { ...WORDING, access: 'full', truncated: false } }

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function mount(seed?: ChangeReport, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return { client, ...renderHook(() => useWhatChanged(42, seed), { wrapper }) }
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('useWhatChanged', () => {
  it('serves the anonymous seed at once and never reads again for an anonymous reader', async () => {
    const me = deferred<null>()
    api.getCurrentUserSafe.mockReturnValue(me.promise)
    const { result } = mount(SEED)
    expect(result.current.query.data).toEqual(SEED)
    expect(result.current.settled).toBe(false)
    expect(result.current.provisional).toBe(true)
    me.resolve(null)
    await waitFor(() => expect(result.current.settled).toBe(true))
    expect(result.current.viewer).toBeNull()
    expect(result.current.provisional).toBe(false)
    expect(result.current.key).toEqual(queryKeys.whatChanged.byViewer(42, null))
    expect(result.current.query.data).toEqual(SEED)
    await tick()
    expect(api.getWhatChanged).not.toHaveBeenCalled()
  })

  it('without a seed, reads once /me has settled: for an anonymous reader, and for a failed /me alike', async () => {
    api.getCurrentUserSafe.mockResolvedValue(null)
    api.getWhatChanged.mockResolvedValue(SERVED)
    const first = mount()
    expect(first.result.current.query.isPending).toBe(true)
    expect(first.result.current.query.data).toBeUndefined()
    await waitFor(() => expect(first.result.current.query.data).toEqual(SERVED))
    expect(api.getWhatChanged).toHaveBeenCalledWith(42)
    expect(first.result.current.provisional).toBe(false)
    first.unmount()

    api.getCurrentUserSafe.mockRejectedValue(new Error('down'))
    const second = mount()
    await waitFor(() => expect(second.result.current.query.data).toEqual(SERVED))
    expect(second.result.current.viewer).toBeNull()
    expect(second.result.current.key).toEqual(queryKeys.whatChanged.byViewer(42, null))
  })

  it('reads a signed-in reader’s own entry after /me, with the seed standing in, and leaves the anonymous entry as it was', async () => {
    const me = deferred<typeof READER>()
    api.getCurrentUserSafe.mockReturnValue(me.promise)
    const served = deferred<ChangeReport>()
    api.getWhatChanged.mockReturnValue(served.promise)
    const { result, client } = mount(SEED)
    expect(result.current.query.data).toEqual(SEED)
    me.resolve(READER)
    await waitFor(() => expect(api.getWhatChanged).toHaveBeenCalledTimes(1))
    expect(result.current.viewer).toBe(7)
    expect(result.current.key).toEqual(queryKeys.whatChanged.byViewer(42, 7))
    expect(result.current.query.data).toEqual(SEED)
    expect(result.current.query.isPlaceholderData).toBe(true)
    expect(result.current.provisional).toBe(true)
    served.resolve(SERVED)
    await waitFor(() => expect(result.current.query.data).toEqual(SERVED))
    expect(result.current.provisional).toBe(false)
    expect(client.getQueryData(queryKeys.whatChanged.byViewer(42, null))).toEqual(SEED)
    expect(client.getQueryData(queryKeys.whatChanged.byViewer(42, 7))).toEqual(SERVED)
  })

  it('issues the read only after /me resolved the reader, so the token /me refreshed is the one it carries', async () => {
    const me = deferred<typeof READER>()
    api.getCurrentUserSafe.mockReturnValue(me.promise)
    api.getWhatChanged.mockResolvedValue(SERVED)
    const { result } = mount()
    await tick()
    expect(api.getCurrentUserSafe).toHaveBeenCalled()
    expect(api.getWhatChanged).not.toHaveBeenCalled()
    me.resolve(READER)
    await waitFor(() => expect(result.current.query.data).toEqual(SERVED))
    expect(api.getCurrentUserSafe.mock.invocationCallOrder[0]).toBeLessThan(api.getWhatChanged.mock.invocationCallOrder[0])
  })

  it('with /me cached but being re-read on this mount, the read waits for that re-read (the request that refreshes the token)', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(queryKeys.currentUser(), READER) // cached and stale (the default staleTime 0): refetched on mount
    const me = deferred<typeof READER>()
    api.getCurrentUserSafe.mockReturnValue(me.promise)
    api.getWhatChanged.mockResolvedValue(FULL)
    const { result } = mount(SEED, client)
    expect(result.current.viewer).toBe(7)
    expect(result.current.settled).toBe(true)
    expect(result.current.provisional).toBe(true)
    await tick()
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(1)
    expect(api.getWhatChanged).not.toHaveBeenCalled()
    me.resolve(READER)
    await waitFor(() => expect(result.current.report).toEqual(FULL))
    expect(api.getWhatChanged).toHaveBeenCalledTimes(1)
    expect(api.getCurrentUserSafe.mock.invocationCallOrder[0]).toBeLessThan(api.getWhatChanged.mock.invocationCallOrder[0])
  })

  it('a Pro reader served the teaser off a fresh cached /me has /me and the report re-read once; a second teaser stands', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    client.setQueryData(queryKeys.currentUser(), READER) // fresh: no request on mount, so an expired token goes out
    api.getCurrentUserSafe.mockResolvedValue(READER) // the re-read (its 401 refreshes the token under the hood)
    api.getWhatChanged.mockResolvedValueOnce(TEASER).mockResolvedValue(FULL)
    const { result } = mount(SEED, client)
    await waitFor(() => expect(result.current.report).toEqual(FULL))
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(1)
    expect(api.getWhatChanged).toHaveBeenCalledTimes(2)
    expect(api.getCurrentUserSafe.mock.invocationCallOrder[0]).toBeLessThan(api.getWhatChanged.mock.invocationCallOrder[1])
    expect(result.current.provisional).toBe(false)
    cleanup()
    vi.clearAllMocks()

    // Still the teaser after the re-read (the plan lapsed, /me's Pro flag is the stale mirror): it stands.
    const again = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    again.setQueryData(queryKeys.currentUser(), READER)
    api.getCurrentUserSafe.mockResolvedValue(READER)
    api.getWhatChanged.mockResolvedValue(TEASER)
    const second = mount(SEED, again)
    await waitFor(() => expect(api.getWhatChanged).toHaveBeenCalledTimes(2))
    await tick()
    await tick()
    expect(api.getWhatChanged).toHaveBeenCalledTimes(2)
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(1)
    expect(second.result.current.report).toEqual(TEASER)
  })

  it('a Free reader served the teaser, and an anonymous seed standing in as the teaser, trigger no re-read', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    client.setQueryData(queryKeys.currentUser(), { ...READER, is_pro: false })
    api.getWhatChanged.mockResolvedValue(TEASER)
    const { result } = mount(TEASER, client)
    expect(result.current.query.isPlaceholderData).toBe(true) // the seed, as the teaser, for a signed-in reader
    await waitFor(() => expect(result.current.provisional).toBe(false))
    await tick()
    expect(api.getWhatChanged).toHaveBeenCalledTimes(1)
    expect(api.getCurrentUserSafe).not.toHaveBeenCalled()
  })

  it('a signed-in reader whose own read fails keeps the seed as the report, held provisional', async () => {
    api.getCurrentUserSafe.mockResolvedValue(READER)
    api.getWhatChanged.mockRejectedValue(new Error('down'))
    const { result, client } = mount(SEED)
    await waitFor(() => expect(result.current.query.isError).toBe(true))
    expect(result.current.query.data).toBeUndefined()
    expect(result.current.report).toEqual(SEED)
    expect(result.current.provisional).toBe(true)
    expect(result.current.failure.failed).toBe(true)
    expect(client.getQueryData(queryKeys.whatChanged.byViewer(42, null))).toEqual(SEED)
    cleanup()
    // Without a seed there is nothing to hold: the report is absent, as before.
    const bare = mount()
    await waitFor(() => expect(bare.result.current.query.isError).toBe(true))
    expect(bare.result.current.report).toBeUndefined()
  })

  it('is keyed by the signed-in reader, not by the Pro mirror /me carries', async () => {
    api.getCurrentUserSafe.mockResolvedValue({ ...READER, is_pro: false })
    api.getWhatChanged.mockResolvedValue(SERVED)
    const { result } = mount(SEED)
    await waitFor(() => expect(result.current.query.data).toEqual(SERVED))
    expect(result.current.key).toEqual(queryKeys.whatChanged.byViewer(42, 7))
  })

  it('names one key family, so the anonymous entry and a reader’s entry are the same filing to an invalidation', () => {
    expect(queryKeys.whatChanged.all()).toEqual(['what-changed'])
    expect(queryKeys.whatChanged.byViewer(42, null)).toEqual(['what-changed', 42, null])
    expect(queryKeys.whatChanged.byViewer(42, 7)).toEqual(['what-changed', 42, 7])
  })
})
