// @vitest-environment node
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { markNoindex } from '../../cloudflare-robots.mjs'

/**
 * The Cloudflare Workers build is wired across files that nothing compiles together: open-next.config.ts picks
 * the cache and the queue, wrangler.jsonc binds what they read, cloudflare-worker.mjs is the entry point, and
 * public/_headers sets the static files' caching. CI builds the app for Vercel only, so a name changed in one of
 * them is not seen until a deploy, where it fails at request time. This spec holds them to each other, and holds the
 * two properties a deployed copy of the site needs (docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (preview)").
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (file: string) => readFileSync(path.join(FRONTEND, file), 'utf8')

interface WranglerConfig {
  name: string
  main: string
  workers_dev?: boolean
  route?: unknown
  routes?: unknown
  assets?: { directory?: string }
  services?: { binding: string; service: string }[]
  r2_buckets?: { binding: string }[]
  durable_objects?: { bindings: { name: string; class_name: string }[] }
  migrations?: { new_sqlite_classes?: string[] }[]
  vars?: Record<string, string>
}

// wrangler.jsonc keeps each comment on a line of its own, so dropping those lines leaves JSON. A comment after a
// value fails the parse here, which is the reminder to move it.
const wrangler = JSON.parse(
  read('wrangler.jsonc')
    .split('\n')
    .filter((line) => !line.trim().startsWith('//'))
    .join('\n'),
) as WranglerConfig

describe('the Cloudflare Workers build', () => {
  it('binds what open-next.config.ts reads, and exports its Durable Object from the entry point', () => {
    const openNext = read('open-next.config.ts')
    const entry = read(wrangler.main)

    // The R2 page cache reads this binding; the Durable Object queue reads its namespace and calls the Worker back
    // through the self-reference. The names are OpenNext's, fixed by the overrides the config imports.
    expect(openNext).toContain('overrides/incremental-cache/r2-incremental-cache')
    expect(wrangler.r2_buckets?.map((bucket) => bucket.binding)).toContain('NEXT_INC_CACHE_R2_BUCKET')
    expect(openNext).toContain('overrides/queue/do-queue')
    expect(wrangler.durable_objects?.bindings).toContainEqual({ name: 'NEXT_CACHE_DO_QUEUE', class_name: 'DOQueueHandler' })
    expect(wrangler.migrations?.flatMap((migration) => migration.new_sqlite_classes ?? [])).toContain('DOQueueHandler')
    expect(wrangler.services).toContainEqual({ binding: 'WORKER_SELF_REFERENCE', service: wrangler.name })

    // Cloudflare instantiates a Durable Object class only when the entry point exports it.
    expect(existsSync(path.join(FRONTEND, wrangler.main)), `${wrangler.main} exists`).toBe(true)
    expect(entry).toMatch(/^export \{ DOQueueHandler \} from '\.\/\.open-next\/worker\.js'$/m)

    expect(wrangler.assets?.directory).toBe('.open-next/assets')
    expect(read('public/_headers')).toMatch(/^\/_next\/static\/\*\n {2}Cache-Control: public,max-age=31536000,immutable$/m)
  })

  it('states the waitlist gate, and a copy on workers.dev is never indexed or given a route', () => {
    // middleware.ts redirects every page to /waitlist unless WAITLIST_MODE is exactly "false". Vercel takes it from
    // vercel.json; a Worker without it would serve nothing but the waitlist.
    expect(['true', 'false'], 'WAITLIST_MODE is stated in wrangler.jsonc `vars`').toContain(wrangler.vars?.WAITLIST_MODE)

    // The entry point passes every response through markNoindex, which is run here as the Worker runs it.
    expect(read(wrangler.main)).toMatch(/^ {4}return markNoindex\(await openNextWorker\.fetch\(request, env, ctx\), env\)$/m)
    const rendered = () => new Response('page', { status: 404, headers: { 'X-Frame-Options': 'DENY' } })
    const marked = markNoindex(rendered(), { ROBOTS_NOINDEX: 'true' })
    expect(marked.headers.get('X-Robots-Tag')).toBe('noindex, nofollow')
    expect([marked.status, marked.headers.get('X-Frame-Options')], 'the response is otherwise the one rendered').toEqual([404, 'DENY'])
    for (const env of [{}, { ROBOTS_NOINDEX: 'false' }]) {
      expect(markNoindex(rendered(), env).headers.has('X-Robots-Tag'), 'production, with the variable unset, stays indexable').toBe(false)
    }
    if (wrangler.workers_dev !== false) {
      expect(wrangler.vars?.ROBOTS_NOINDEX, 'a workers.dev deployment is a copy of the site: keep it out of search').toBe('true')
    }
    if (wrangler.vars?.ROBOTS_NOINDEX === 'true') {
      expect(wrangler.route ?? wrangler.routes, 'a noindex deployment must not take a production route').toBeUndefined()
    }
  })
})
