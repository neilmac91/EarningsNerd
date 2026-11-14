// The front Worker on Cloudflare (wrangler.jsonc `main`): the one a reader's request reaches. It holds OpenNext's
// routing layer only (middleware.ts, redirects, and pages answered from the cache), which `npm run cf:build` writes
// to .open-next/middleware, and it serves the static files. A request the cache cannot answer goes to the server
// Worker (cloudflare-server.mjs), which holds the Next server.
//
// Two Workers, because a Worker's script is loaded whole on a fresh instance: with the Next server in it (17 MB),
// a cached page took about 0.85 s on a fresh instance, and with this script alone (under 1 MB) about 0.2 s
// (docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (staging)"). Vercel's build does not read this file.
import { WorkerEntrypoint } from 'cloudflare:workers'
import { runWithCloudflareRequestContext } from './.open-next/cloudflare/init.js'
import { handler as routeRequest } from './.open-next/middleware/handler.mjs'
import { markNoindex } from './cloudflare-robots.mjs'

// The Durable Object that re-renders stale pages (open-next.config.ts `queue`) lives in this Worker; the server
// Worker binds to it by this Worker's name.
export { DOQueueHandler } from './.open-next/.build/durable-objects/queue.js'

export default class FrontWorker extends WorkerEntrypoint {
  async fetch(request) {
    const { env, ctx } = this
    const response = await runWithCloudflareRequestContext(request, env, ctx, async () => {
      const routed = await routeRequest(request, env, ctx)
      // A Response is the answer already: a redirect, a refusal, or a page from the cache.
      if (routed instanceof Response) return routed
      // The two Workers are built together and must run together. scripts/cf-deploy.mjs gives each front version
      // the server version of its own build, and this header holds the request to it while a deploy rolls out.
      if (env.SERVER_VERSION_OVERRIDE) {
        routed.headers.set('Cloudflare-Workers-Version-Overrides', env.SERVER_VERSION_OVERRIDE)
      }
      return env.SERVER.fetch(routed, { redirect: 'manual', cf: { cacheEverything: false } })
    })
    return markNoindex(response, env)
  }
}
