// Next waits for each cache write before it answers, and a write to R2 took about 350 ms: on a page rendered for the
// first time, the reader waited for two of them. This wraps the R2 bucket the cache uses (the three methods OpenNext's
// R2 cache calls: get, put, delete) so that a write is answered at once and finishes after the response. Until it
// lands, a read of the same key in this instance gets the value being written, so a render still reads its own
// writes. Another instance sees the old state until the write lands, as it did while a write was in flight before.
// A write that fails is logged and dropped: the page is rendered again on its next request.
// cloudflare-server.mjs applies it; tests/unit/cloudflareCacheWrites.spec.ts runs it.
const inFlight = new Map()

export function deferCacheWrites(bucket, waitUntil, pending = inFlight) {
  return {
    async get(key) {
      const waiting = pending.get(key)
      if (!waiting) return bucket.get(key)
      return { json: async () => JSON.parse(waiting.body), text: async () => waiting.body, uploaded: waiting.at }
    },
    async put(key, body) {
      // OpenNext writes JSON text. Anything else is not held in memory, and is written as before.
      if (typeof body !== 'string') return bucket.put(key, body)
      const entry = { body, at: new Date() }
      entry.write = Promise.resolve()
        .then(() => bucket.put(key, body))
        .catch((error) => console.error(`cache write failed for ${key}: ${error}`))
        .finally(() => {
          // A later write of the same key has replaced this entry; leave that one in place.
          if (pending.get(key) === entry) pending.delete(key)
        })
      pending.set(key, entry)
      waitUntil(entry.write)
      return null
    },
    async delete(key) {
      // Let a write in flight land first, or it would bring the key back after the delete.
      const waiting = pending.get(key)
      pending.delete(key)
      if (waiting) await waiting.write
      return bucket.delete(key)
    },
  }
}
