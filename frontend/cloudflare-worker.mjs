// The Worker's entry point on Cloudflare (wrangler.jsonc `main`). It wraps the handler OpenNext generates
// (`npm run cf:build` writes .open-next/worker.js) with one behaviour of ours, markNoindex. ROBOTS_NOINDEX is read
// per request, so one build can serve a copy and, with the variable unset, production. Vercel's build does not read
// this file.
import openNextWorker from './.open-next/worker.js'
import { markNoindex } from './cloudflare-robots.mjs'

// The Durable Object that re-renders stale pages (open-next.config.ts `queue`) must be exported by the entry point.
export { DOQueueHandler } from './.open-next/worker.js'

const worker = {
  async fetch(request, env, ctx) {
    return markNoindex(await openNextWorker.fetch(request, env, ctx), env)
  },
}

export default worker
