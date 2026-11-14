// The server Worker on Cloudflare (wrangler.server.jsonc `main`): the Next server, which `npm run cf:build` writes
// to .open-next/server-functions. Only the front Worker (cloudflare-front.mjs) calls it, for a request the cache
// could not answer, and it has no address of its own. wrangler.server.jsonc places it beside the API, which every
// page it renders reads. Vercel's build does not read this file.
import { runWithCloudflareRequestContext } from './.open-next/cloudflare/init.js'
import { deferCacheWrites } from './cloudflare-cache-writes.mjs'

const worker = {
  async fetch(request, env, ctx) {
    const serverEnv = {
      ...env,
      NEXT_INC_CACHE_R2_BUCKET: deferCacheWrites(env.NEXT_INC_CACHE_R2_BUCKET, (write) => ctx.waitUntil(write)),
    }
    return runWithCloudflareRequestContext(request, serverEnv, ctx, async () => {
      // Imported here, not at the top: runWithCloudflareRequestContext first sets the globals the Next server and
      // its instrumentation hook (instrumentation.ts, which starts Sentry) read while they load. Loaded before
      // them, the hook fails with "__filename is not defined" and the server runs without error reporting.
      const { handler } = await import('./.open-next/server-functions/default/handler.mjs')
      return handler(request, serverEnv, ctx, request.signal)
    })
  },
}

export default worker
