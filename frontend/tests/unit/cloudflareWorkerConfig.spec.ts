// @vitest-environment node
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { markNoindex } from '../../cloudflare-robots.mjs'

/**
 * The Cloudflare Workers build is two Workers wired across files that nothing compiles together: open-next.config.ts
 * picks the cache and the queue, wrangler.jsonc (the front Worker) and wrangler.server.jsonc (the server Worker) bind
 * what they read and name each other, cloudflare-front.mjs and cloudflare-server.mjs are their entry points, and
 * public/_headers sets the static files' caching. CI's worker-build job builds them and requests one page through
 * both, which exercises neither the R2 cache nor the Durable Object, so a binding renamed in one file would first
 * fail on staging, at request time. This spec holds them to each other, and holds the properties a deployed copy of
 * the site needs (docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (staging)").
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (file: string) => readFileSync(path.join(FRONTEND, file), 'utf8')

type Route = string | { pattern: string }
interface WranglerConfig {
  name: string
  main: string
  workers_dev?: boolean
  preview_urls?: boolean
  route?: Route
  routes?: Route[]
  placement?: { region?: string; mode?: string }
  assets?: { directory?: string }
  services?: { binding: string; service: string }[]
  r2_buckets?: { binding: string; bucket_name: string }[]
  durable_objects?: { bindings: { name: string; class_name: string; script_name?: string }[] }
  migrations?: { new_sqlite_classes?: string[] }[]
  vars?: Record<string, string>
}

// The wrangler files keep each comment on a line of its own, so dropping those lines leaves JSON. A comment after a
// value fails the parse here, which is the reminder to move it. scripts/cf-deploy.mjs reads them the same way.
const wranglerFile = (file: string) =>
  JSON.parse(
    read(file)
      .split('\n')
      .filter((line) => !line.trim().startsWith('//'))
      .join('\n'),
  ) as WranglerConfig

const front = wranglerFile('wrangler.jsonc')
const server = wranglerFile('wrangler.server.jsonc')
const hostsOf = (config: WranglerConfig) =>
  [config.route, ...(config.routes ?? [])]
    .filter((route) => route !== undefined)
    .map((route) => (typeof route === 'string' ? route : route.pattern).split('/')[0])

describe('the Cloudflare Workers build', () => {
  it('binds what open-next.config.ts reads, in both Workers, and each Worker names the other', () => {
    const openNext = read('open-next.config.ts')

    // The R2 page cache reads this binding, in the front Worker (cached pages) and in the server Worker (renders),
    // and both must read one bucket. The names are OpenNext's, fixed by the overrides the config imports.
    expect(openNext).toContain('overrides/incremental-cache/r2-incremental-cache')
    for (const config of [front, server]) {
      expect(config.r2_buckets?.map((bucket) => bucket.binding), config.name).toEqual(['NEXT_INC_CACHE_R2_BUCKET'])
    }
    expect(server.r2_buckets?.[0].bucket_name).toBe(front.r2_buckets?.[0].bucket_name)

    // The Durable Object queue lives in the front Worker: it holds the class, its migration and the export. The
    // server Worker binds to it there by name, and a re-render is requested through the front Worker.
    expect(openNext).toContain('overrides/queue/do-queue')
    expect(front.durable_objects?.bindings).toEqual([{ name: 'NEXT_CACHE_DO_QUEUE', class_name: 'DOQueueHandler' }])
    expect(front.migrations?.flatMap((migration) => migration.new_sqlite_classes ?? [])).toContain('DOQueueHandler')
    expect(read(front.main)).toMatch(/^export \{ DOQueueHandler \} from '\.\/\.open-next\/\.build\/durable-objects\/queue\.js'$/m)
    expect(server.durable_objects?.bindings).toEqual([
      { name: 'NEXT_CACHE_DO_QUEUE', class_name: 'DOQueueHandler', script_name: front.name },
    ])
    expect(server.migrations, 'the class is the front Worker\'s; a migration here would create a second one').toBeUndefined()
    for (const config of [front, server]) {
      expect(config.services, config.name).toContainEqual({ binding: 'WORKER_SELF_REFERENCE', service: front.name })
    }

    // The front Worker reaches the server Worker through SERVER, held to its own build's version by the header.
    expect(front.services).toContainEqual({ binding: 'SERVER', service: server.name })
    const frontEntry = read(front.main)
    expect(frontEntry).toContain('return env.SERVER.fetch(routed, ')
    expect(frontEntry).toContain("routed.headers.set('Cloudflare-Workers-Version-Overrides', env.SERVER_VERSION_OVERRIDE)")
    expect(front.vars, 'scripts/cf-deploy.mjs fills it in; the file states that it exists').toHaveProperty('SERVER_VERSION_OVERRIDE', '')
    expect(read('scripts/cf-deploy.mjs')).toContain('const override = `SERVER_VERSION_OVERRIDE:${serverName}="${newServer}"`')

    for (const config of [front, server]) expect(existsSync(path.join(FRONTEND, config.main)), config.main).toBe(true)
    expect(front.assets?.directory).toBe('.open-next/assets')
    expect(read('public/_headers')).toMatch(/^\/_next\/static\/\*\n {2}Cache-Control: public,max-age=31536000,immutable$/m)
  })

  it('keeps the Next server out of the front Worker, and loads it in the server Worker only once its globals are set', () => {
    // The front Worker is small so that a fresh instance answers a cached page quickly: importing the Next server
    // into it, in any form, puts the whole server back into its script.
    expect(read(front.main)).not.toContain('server-functions')
    expect(read(front.main)).not.toContain('.open-next/worker.js')

    // The server Worker imports the Next server inside the request, after runWithCloudflareRequestContext has set the
    // globals its instrumentation hook reads. Imported at the top, the hook fails and Sentry never starts.
    const serverEntry = read(server.main)
    expect(serverEntry).not.toMatch(/^import .*server-functions/m)
    expect(serverEntry).toMatch(
      /runWithCloudflareRequestContext\(request, serverEnv, ctx, async \(\) => \{[^}]*const \{ handler \} = await import\('\.\/\.open-next\/server-functions\/default\/handler\.mjs'\)/s,
    )
    expect(serverEntry).toContain('NEXT_INC_CACHE_R2_BUCKET: deferCacheWrites(env.NEXT_INC_CACHE_R2_BUCKET, ')

    // Only the front Worker is reachable; the server Worker renders beside the API.
    expect(hostsOf(server)).toEqual([])
    expect([server.workers_dev, server.preview_urls]).toEqual([false, false])
    expect(server.placement).toEqual({ region: 'gcp:us-west1' })
    expect(front.placement, 'the front Worker answers cached pages where the reader is').toBeUndefined()
  })

  it('states the waitlist gate, and marks a copy of the site noindex and production never', () => {
    // middleware.ts redirects every page to /waitlist unless WAITLIST_MODE is exactly "false". It runs in the front
    // Worker. Vercel takes the value from vercel.json; a Worker without it would serve nothing but the waitlist.
    expect(['true', 'false'], 'WAITLIST_MODE is stated in wrangler.jsonc `vars`').toContain(front.vars?.WAITLIST_MODE)

    // The front Worker passes every response, its own and the server Worker's, through markNoindex, which is run
    // here as the Worker runs it.
    expect(read(front.main)).toMatch(/^ {4}return markNoindex\(response, env\)$/m)
    const rendered = () => new Response('page', { status: 404, headers: { 'X-Frame-Options': 'DENY' } })
    const marked = markNoindex(rendered(), { ROBOTS_NOINDEX: 'true' })
    expect(marked.headers.get('X-Robots-Tag')).toBe('noindex, nofollow')
    expect([marked.status, marked.headers.get('X-Frame-Options')], 'the response is otherwise the one rendered').toEqual([404, 'DENY'])
    for (const env of [{}, { ROBOTS_NOINDEX: 'false' }]) {
      expect(markNoindex(rendered(), env).headers.has('X-Robots-Tag'), 'production, with the variable unset, stays indexable').toBe(false)
    }

    // Either the Worker is a copy (staging, or a workers.dev address) and every response is noindex, or it serves
    // the production hostnames and none is: a noindex production site leaves search, and an indexable copy competes
    // with it. Each hostname must be one this spec knows, written exactly: a wildcard or another spelling could
    // cover production while reading as a copy, so it fails here until it is listed. wrangler takes a route as
    // `route` or `routes`, a string or an object, and both are read.
    const PRODUCTION_HOSTS = ['earningsnerd.io', 'www.earningsnerd.io']
    const COPY_HOSTS = ['staging.earningsnerd.io']
    const hosts = hostsOf(front)
    for (const host of hosts) {
      expect([...PRODUCTION_HOSTS, ...COPY_HOSTS], 'a route names a production hostname or a known copy, exactly').toContain(host)
    }
    const servesProduction = hosts.some((host) => PRODUCTION_HOSTS.includes(host))
    const servesACopy = front.workers_dev !== false || hosts.some((host) => COPY_HOSTS.includes(host))
    expect(servesProduction && servesACopy, 'one Worker serves production or a copy of it, never both').toBe(false)
    expect(front.vars?.ROBOTS_NOINDEX === 'true', `ROBOTS_NOINDEX for a Worker on ${hosts.join(', ') || 'workers.dev'}`).toBe(!servesProduction)
  })
})
