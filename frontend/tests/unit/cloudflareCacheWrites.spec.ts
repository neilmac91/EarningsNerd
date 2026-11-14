// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'
import { deferCacheWrites } from '../../cloudflare-cache-writes.mjs'

/**
 * cloudflare-cache-writes.mjs answers a cache write at once and lets it finish after the response. These hold what
 * that must not cost: a render reads its own writes, a failed write breaks nothing, and a delete is not undone by a
 * write still in flight. The bucket here is a Map behind promises the test resolves by hand.
 */
function bucketOf(stored = new Map<string, string>()) {
  const landing: Array<{ key: string; land: () => void; fail: (error: Error) => void }> = []
  const bucket = {
    get: vi.fn(async (key: string) =>
      stored.has(key) ? { json: async () => JSON.parse(stored.get(key)!), uploaded: new Date(0) } : null,
    ),
    put: vi.fn(
      (key: string, body: string) =>
        new Promise<void>((resolve, reject) => {
          landing.push({ key, land: () => (stored.set(key, body), resolve()), fail: reject })
        }),
    ),
    delete: vi.fn(async (key: string) => void stored.delete(key)),
  }
  return { bucket, stored, landing }
}

const settled = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('deferred cache writes', () => {
  it('answers a write before it lands, hands it to waitUntil, and serves it to a read meanwhile', async () => {
    const { bucket, stored, landing } = bucketOf()
    const kept: Promise<unknown>[] = []
    const cache = deferCacheWrites(bucket, (write: Promise<unknown>) => kept.push(write), new Map())

    await cache.put('page', JSON.stringify({ html: 'new' }))
    await settled()
    expect(stored.has('page'), 'the write has not landed, yet put() has returned').toBe(false)
    expect(kept, 'the write is kept alive past the response').toHaveLength(1)

    const read = await cache.get('page')
    expect(await read.json()).toEqual({ html: 'new' })
    expect(read.uploaded).toBeInstanceOf(Date)
    expect(bucket.get, 'the value being written is served from memory').not.toHaveBeenCalled()

    landing[0].land()
    await kept[0]
    expect(stored.get('page')).toBe(JSON.stringify({ html: 'new' }))
    await cache.get('page')
    expect(bucket.get, 'once landed, reads go to the bucket again').toHaveBeenCalledTimes(1)
  })

  it('lands two writes to one key in the order they were made, and reads the newer one throughout', async () => {
    const { bucket, stored, landing } = bucketOf()
    const kept: Promise<unknown>[] = []
    const cache = deferCacheWrites(bucket, (write: Promise<unknown>) => kept.push(write), new Map())

    await cache.put('page', '"first"')
    await cache.put('page', '"second"')
    await settled()
    expect(bucket.put, 'the second write waits for the first, so it cannot land before it').toHaveBeenCalledTimes(1)
    expect(await (await cache.get('page')).json()).toBe('second')

    landing[0].land()
    await kept[0]
    await settled()
    expect(bucket.put).toHaveBeenCalledTimes(2)
    expect(await (await cache.get('page')).json(), 'the first landing does not drop the second from memory').toBe('second')

    landing[1].land()
    await kept[1]
    expect(stored.get('page'), 'the newer write is what the bucket keeps').toBe('"second"')
  })

  it('drops a failed write without throwing, so the next read misses and the page is rendered again', async () => {
    const { bucket, landing } = bucketOf()
    const kept: Promise<unknown>[] = []
    const failures = vi.spyOn(console, 'error').mockImplementation(() => {})
    const cache = deferCacheWrites(bucket, (write: Promise<unknown>) => kept.push(write), new Map())

    await cache.put('page', '"lost"')
    await settled()
    landing[0].fail(new Error('R2 is away'))
    await expect(kept[0]).resolves.toBeUndefined()
    expect(failures).toHaveBeenCalledWith(expect.stringContaining('cache write failed for page'))
    expect(await cache.get('page')).toBeNull()
    failures.mockRestore()
  })

  it('lets every write in flight land before a delete of the same key, so the delete is the last word', async () => {
    const { bucket, stored, landing } = bucketOf()
    const cache = deferCacheWrites(bucket, () => {}, new Map())

    await cache.put('page', '"stale"')
    await cache.put('page', '"staler"')
    await settled()
    const deleted = cache.delete('page')
    await settled()
    landing[0].land()
    await settled()
    await settled()
    expect(bucket.delete, 'the delete waits for both writes').not.toHaveBeenCalled()
    landing[1].land()
    await deleted
    expect(stored.has('page')).toBe(false)
    expect(await cache.get('page')).toBeNull()
  })

  it('writes anything that is not text as before', async () => {
    const { bucket } = bucketOf()
    const waitUntil = vi.fn()
    const cache = deferCacheWrites(bucket, waitUntil, new Map())
    const bytes = new Uint8Array([1, 2, 3])
    void cache.put('blob', bytes)
    expect(bucket.put).toHaveBeenCalledWith('blob', bytes)
    expect(waitUntil).not.toHaveBeenCalled()
  })
})
