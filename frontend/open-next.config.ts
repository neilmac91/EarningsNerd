import { defineCloudflareConfig } from '@opennextjs/cloudflare'
import r2IncrementalCache from '@opennextjs/cloudflare/overrides/incremental-cache/r2-incremental-cache'
import { withRegionalCache } from '@opennextjs/cloudflare/overrides/incremental-cache/regional-cache'
import doQueue from '@opennextjs/cloudflare/overrides/queue/do-queue'

// How the app runs when it is built for Cloudflare Workers (`npm run cf:build`). Vercel's build does not read this
// file. docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (staging)", has the measurements behind each choice.
const cloudflare = defineCloudflareConfig({
  // Rendered pages (the ISR cache: /company/[ticker], /filing/[id], the static routes) are stored in R2, with a
  // copy in the edge cache of each Cloudflare location that serves them, kept for at most the page's `revalidate`
  // and refreshed from R2 in the background on each hit. Measured on staging: it took the median first byte from
  // 50 to 75 ms behind Vercel to 10 to 17 ms behind. A location's copy can trail R2 by one request. The edge cache
  // works on a custom domain only, not on a workers.dev address.
  incrementalCache: withRegionalCache(r2IncrementalCache, { mode: 'long-lived' }),
  // A page past its `revalidate` is served stale once and re-rendered through a Durable Object, which also
  // de-duplicates concurrent re-renders of one page.
  queue: doQueue,
  // A cached page is answered from R2 before the Next server is loaded. Measured on the preview: this took the
  // median first byte of /pricing and /company/AAPL from about 500 ms to about 270 ms.
  enableCacheInterception: true,
})

// The Workers build leaves Vercel Web Analytics out of the app: only Vercel serves the script it loads
// (lib/featureFlags.ts ENABLE_VERCEL_ANALYTICS). `npm run cf:build` and scripts/cf-deploy.mjs both build through
// this command.
const config = { ...cloudflare, buildCommand: 'NEXT_PUBLIC_VERCEL_ANALYTICS=false npm run build' }

export default config
