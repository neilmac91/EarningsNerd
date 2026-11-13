// The Worker's entry point on Cloudflare (wrangler.jsonc `main`). It wraps the handler OpenNext generates
// (`npm run cf:build` writes .open-next/worker.js) with one behaviour of ours: a deployment whose ROBOTS_NOINDEX
// variable is "true" marks every response it renders noindex, so a preview or staging copy of the site is never
// indexed beside production. The variable is read per request, so one build can serve a copy and, unset,
// production. Vercel's build does not read this file.
import openNextWorker from './.open-next/worker.js'

// The Durable Object that re-renders stale pages (open-next.config.ts `queue`) must be exported by the entry point.
export { DOQueueHandler } from './.open-next/worker.js'

const worker = {
  async fetch(request, env, ctx) {
    const response = await openNextWorker.fetch(request, env, ctx)
    if (env.ROBOTS_NOINDEX !== 'true') return response
    const marked = new Response(response.body, response)
    marked.headers.set('X-Robots-Tag', 'noindex, nofollow')
    return marked
  },
}

export default worker
