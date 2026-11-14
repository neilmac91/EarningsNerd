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

// What the scheduled handler below asks the server Worker for each minute: one page of each kind the Next server
// renders on demand. Answering one loads that route's code into the server Worker's instance, which is most of what
// a reader waits for when theirs is the first such page the instance serves (docs/DEPLOYMENT.md).
const KEEP_WARM_PATHS = ['/company/AAPL', '/filing/3']
// OpenNext's cache layer in this Worker answers a cached page itself, and then nothing reaches the server Worker.
// It passes on a request that carries Next's draft-mode cookie. The Next server finds the value is not its own and
// answers as it would any reader: the cached page, re-rendered in the background once it is stale. The hostname is
// never resolved: the request goes over the SERVER binding.
const KEEP_WARM_REQUEST = { headers: { cookie: '__prerender_bypass=keep-warm' } }
const KEEP_WARM_ORIGIN = 'https://keep-warm.invalid'

// Sends a request the cache could not answer to the server Worker. The two Workers are built together and must run
// together: scripts/cf-deploy.mjs gives each front version the server version of its own build, and this header
// holds the request to it while a deploy rolls out.
function askServer(routed, env) {
  if (env.SERVER_VERSION_OVERRIDE) {
    routed.headers.set('Cloudflare-Workers-Version-Overrides', env.SERVER_VERSION_OVERRIDE)
  }
  return env.SERVER.fetch(routed, { redirect: 'manual', cf: { cacheEverything: false } })
}

export default class FrontWorker extends WorkerEntrypoint {
  async fetch(request) {
    const { env, ctx } = this
    const response = await runWithCloudflareRequestContext(request, env, ctx, async () => {
      const routed = await routeRequest(request, env, ctx)
      // A Response is the answer already: a redirect, a refusal, or a page from the cache.
      return routed instanceof Response ? routed : askServer(routed, env)
    })
    return markNoindex(response, env)
  }

  // Cloudflare calls this once a minute (wrangler.jsonc `triggers`). A run whose request stops in this Worker, or
  // that the server Worker fails, throws, which Cloudflare records as a failed run of the schedule.
  async scheduled() {
    const { env, ctx } = this
    for (const path of KEEP_WARM_PATHS) {
      const request = new Request(KEEP_WARM_ORIGIN + path, KEEP_WARM_REQUEST)
      await runWithCloudflareRequestContext(request, env, ctx, async () => {
        const routed = await routeRequest(request, env, ctx)
        if (routed instanceof Response) {
          throw new Error(`keep-warm ${path}: the front Worker answered ${routed.status} itself, so nothing reached the server Worker`)
        }
        const response = await askServer(routed, env)
        await response.arrayBuffer()
        if (response.status >= 500) throw new Error(`keep-warm ${path}: the server Worker answered ${response.status}`)
      })
    }
  }
}
