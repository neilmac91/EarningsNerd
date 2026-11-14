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
import { canonicalRedirect, forBrowser } from './cloudflare-browser.mjs'
import { markNoindex } from './cloudflare-robots.mjs'

// The Durable Object that re-renders stale pages (open-next.config.ts `queue`) lives in this Worker; the server
// Worker binds to it by this Worker's name.
export { DOQueueHandler } from './.open-next/.build/durable-objects/queue.js'

// What the scheduled handler below asks the server Worker for each minute: one page of each kind the Next server
// renders on demand. Answering one loads that route's code into the server Worker's instance, which is most of what
// a reader waits for when theirs is the first such page the instance serves (docs/DEPLOYMENT.md).
const KEEP_WARM_PATHS = ['/company/AAPL', '/company/AAPL/insiders', '/filing/3']
// OpenNext's cache layer in this Worker answers a cached page itself, and then nothing reaches the server Worker.
// It passes on a request that carries Next's draft-mode cookie. The Next server finds the value is not its own and
// answers as it would any reader: the cached page, re-rendered in the background once it is stale.
const KEEP_WARM_COOKIE = '__prerender_bypass=keep-warm'
// The request goes over the SERVER binding, so its hostname is never resolved. It is the site's own
// (CANONICAL_HOST) where the Worker has one: the server Worker names a stale page's re-render by the Host header,
// and that re-render comes back through `fetch` below, which redirects any other hostname.
const KEEP_WARM_HOST_WITHOUT_A_SITE = 'keep-warm.invalid'

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
    const response =
      canonicalRedirect(request, env) ??
      (await runWithCloudflareRequestContext(request, env, ctx, async () => {
        const routed = await routeRequest(request, env, ctx)
        // A Response is the answer already: a redirect, a refusal, or a page from the cache.
        return routed instanceof Response ? routed : askServer(routed, env)
      }))
    return markNoindex(forBrowser(response), env)
  }

  // Cloudflare calls this once a minute (wrangler.jsonc `triggers`). Every page is asked for, and then a run in
  // which a request stopped in this Worker, or the server Worker failed one, throws: Cloudflare records the run as
  // failed, with each page's reason.
  async scheduled() {
    const { env, ctx } = this
    const failures = []
    const host = env.CANONICAL_HOST || KEEP_WARM_HOST_WITHOUT_A_SITE
    for (const path of KEEP_WARM_PATHS) {
      const request = new Request(`https://${host}${path}`, { headers: { cookie: KEEP_WARM_COOKIE, host } })
      try {
        await runWithCloudflareRequestContext(request, env, ctx, async () => {
          const routed = await routeRequest(request, env, ctx)
          if (routed instanceof Response) {
            throw new Error(`the front Worker answered ${routed.status} itself, so nothing reached the server Worker`)
          }
          const response = await askServer(routed, env)
          await response.arrayBuffer()
          if (response.status >= 500) throw new Error(`the server Worker answered ${response.status}`)
        })
      } catch (error) {
        failures.push(`${path}: ${error instanceof Error ? error.message : error}`)
      }
    }
    if (failures.length > 0) throw new Error(`keep-warm: ${failures.join('; ')}`)
  }
}
