// @vitest-environment node
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { markNoindex } from '../../cloudflare-robots.mjs'

/**
 * The Cloudflare Workers build is two Workers wired across files that nothing compiles together: open-next.config.ts
 * picks the cache and the queue, wrangler.jsonc (the front Worker) and wrangler.server.jsonc (the server Worker) bind
 * what they read and name each other, cloudflare-front.mjs and cloudflare-server.mjs are their entry points, and
 * public/_headers sets the static files' caching. There are two such pairs, staging's and production's
 * (wrangler.production.jsonc, wrangler.production.server.jsonc), on the same entry points, and every test below
 * runs on each. CI's worker-build job builds them and requests one page through
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
  compatibility_date?: string
  compatibility_flags?: string[]
  workers_dev?: boolean
  preview_urls?: boolean
  route?: Route
  routes?: Route[]
  placement?: { region?: string; mode?: string }
  triggers?: { crons?: string[] }
  dev?: { upstream_protocol?: string }
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

const PAIRS = [
  { pair: 'staging', front: wranglerFile('wrangler.jsonc'), server: wranglerFile('wrangler.server.jsonc') },
  { pair: 'production', front: wranglerFile('wrangler.production.jsonc'), server: wranglerFile('wrangler.production.server.jsonc') },
]
// The hostnames a Worker may serve, written exactly: a wildcard or another spelling could cover production while
// reading as a copy, so it fails until it is listed here.
const PRODUCTION_HOSTS = ['earningsnerd.io', 'www.earningsnerd.io']
const PRODUCTION_CANONICAL_HOST = 'www.earningsnerd.io'
const COPY_HOSTS = ['staging.earningsnerd.io']
const hostsOf = (config: WranglerConfig) =>
  [config.route, ...(config.routes ?? [])]
    .filter((route) => route !== undefined)
    .map((route) => (typeof route === 'string' ? route : route.pattern).split('/')[0])

describe.each(PAIRS)('the Cloudflare Workers build, $pair', ({ front, server }) => {
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
    // A static file does not pass through the Worker, so the HSTS header cloudflare-browser.mjs sets is repeated here.
    expect(read('public/_headers')).toMatch(/^\/\*\n {2}Strict-Transport-Security: max-age=63072000$/m)
    expect(read('cloudflare-browser.mjs')).toContain("sent.headers.set('Strict-Transport-Security', 'max-age=63072000')")
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

  it('keeps each on-demand page route loaded in the server Worker: every minute the front Worker asks it for one page of each', () => {
    // An instance of the server Worker that has not yet served a company page loads that route's code on a reader's
    // first one, which was most of the wait (docs/DEPLOYMENT.md). The schedule is the front Worker's; the server
    // Worker has no trigger of its own and is reached over SERVER.
    expect(front.triggers?.crons).toEqual(['* * * * *'])
    expect(server.triggers, 'the server Worker is called by the front Worker only').toBeUndefined()
    // A version deploy does not carry a Worker's triggers, so the deploy applies them, last: the schedule must
    // not start on a front version that has no handler for it.
    const deploy = read('scripts/cf-deploy.mjs')
    const applied = deploy.indexOf("run(['wrangler', 'triggers', 'deploy', '-c', frontConfig])")
    expect(applied).toBeGreaterThan(deploy.lastIndexOf("run(['wrangler', 'versions', 'deploy', "))

    const frontEntry = read(front.main)
    expect(frontEntry).toMatch(/^ {2}async scheduled\(\) \{$/m)
    const listed = frontEntry.match(/^const KEEP_WARM_PATHS = \[([^\]]+)\]$/m)?.[1] ?? ''
    const paths = [...listed.matchAll(/'([^']+)'/g)].map((match) => match[1])

    // The on-demand pages are the routes with a parameter anywhere in their path: the build prerenders none of
    // their pages, so each is first rendered for a reader. Every such route has exactly one page in the list, and
    // the list holds nothing else: a route added later is warmed from its first deploy, or this fails. A route
    // group's folder, `(name)`, is not part of the address.
    const onDemandRoutes = readdirSync(path.join(FRONTEND, 'app'), { recursive: true, encoding: 'utf8' })
      .map((file) => file.split(path.sep))
      .filter((parts) => /^page\.[jt]sx?$/.test(parts[parts.length - 1]) && parts.some((part) => /^\[.+\]$/.test(part)))
      .map((parts) => `/${parts.slice(0, -1).filter((part) => !/^\(.+\)$/.test(part)).join('/')}`)
    expect(onDemandRoutes.length).toBeGreaterThan(0)
    const routeOf = (warmed: string) => onDemandRoutes.filter((route) => new RegExp(`^${route.replace(/\[[^/]+\]/g, '[^/]+')}$`).test(warmed))
    expect(paths.map((warmed) => routeOf(warmed).join()).sort()).toEqual([...onDemandRoutes].sort())
    // middleware.ts lets each through with the waitlist gate up or down, so the request is never redirected.
    const allowedPrefixes = read('middleware.ts').match(/^const ALLOWED_PREFIXES = \[(.+)\]$/m)?.[1] ?? ''
    for (const warmed of paths) expect(allowedPrefixes).toContain(`'/${warmed.split('/')[1]}'`)

    // The request must pass the front Worker's cache, which would answer a cached page itself. OpenNext's cache
    // layer passes on a request carrying Next's draft-mode cookie, by this test in the installed version; when an
    // upgrade rewords it, check that the schedule still reaches the server Worker before changing this line.
    expect(frontEntry).toContain("const KEEP_WARM_COOKIE = '__prerender_bypass=keep-warm'")
    // Its hostname is the site's own where the Worker has one: a stale page's re-render is requested at the host
    // the request named, through `fetch`, which redirects every hostname but that one.
    expect(frontEntry).toContain('const host = env.CANONICAL_HOST || KEEP_WARM_HOST_WITHOUT_A_SITE')
    expect(frontEntry).toContain('const request = new Request(`https://${host}${path}`, { headers: { cookie: KEEP_WARM_COOKIE, host } })')
    expect(read('node_modules/@opennextjs/aws/dist/core/routing/cacheInterceptor.js')).toContain('cookies.includes("__prerender_bypass")')
    // A run that stops in the front Worker, or that the server Worker fails, throws once every page has been asked
    // for: Cloudflare records the run as failed. CI's worker-build job runs the schedule against a page the cache
    // already holds, where a request that did not pass the cache fails the job.
    expect(frontEntry).toContain('if (routed instanceof Response) {\n            throw new Error(`the front Worker answered ')
    expect(frontEntry).toContain('if (response.status >= 500) throw new Error(`the server Worker answered ')
    expect(frontEntry).toContain("if (failures.length > 0) throw new Error(`keep-warm: ${failures.join('; ')}`)")
    // Its requests reach the server Worker the way a reader's do, through the one call that holds a front version
    // to its own build's server version while a deploy rolls out.
    expect(frontEntry.match(/env\.SERVER\.fetch\(/g)).toHaveLength(1)
    expect(frontEntry).toContain('          const response = await askServer(routed, env)\n')
    expect(read('../.github/workflows/ci.yml')).toContain(`-D cached.txt http://127.0.0.1:8788${paths[0]}\n`)
  })

  it('states the waitlist gate, and marks a copy of the site noindex and production never', () => {
    // middleware.ts redirects every page to /waitlist unless WAITLIST_MODE is exactly "false". It runs in the front
    // Worker. Vercel takes the value from vercel.json; a Worker without it would serve nothing but the waitlist.
    expect(['true', 'false'], 'WAITLIST_MODE is stated in wrangler.jsonc `vars`').toContain(front.vars?.WAITLIST_MODE)

    // The front Worker passes every response, its own and the server Worker's, through markNoindex, which is run
    // here as the Worker runs it.
    expect(read(front.main)).toMatch(/^ {4}return markNoindex\(forBrowser\(response\), env\)$/m)
    const rendered = () => new Response('page', { status: 404, headers: { 'X-Frame-Options': 'DENY' } })
    const marked = markNoindex(rendered(), { ROBOTS_NOINDEX: 'true' })
    expect(marked.headers.get('X-Robots-Tag')).toBe('noindex, nofollow')
    expect([marked.status, marked.headers.get('X-Frame-Options')], 'the response is otherwise the one rendered').toEqual([404, 'DENY'])
    for (const env of [{}, { ROBOTS_NOINDEX: 'false' }]) {
      expect(markNoindex(rendered(), env).headers.has('X-Robots-Tag'), 'production, with the variable unset, stays indexable').toBe(false)
    }

    // Either the Worker is a copy (staging, or a workers.dev address) and every response is noindex, or it serves
    // the production hostnames and none is: a noindex production site leaves search, and an indexable copy competes
    // with it. wrangler takes a route as `route` or `routes`, a string or an object, and both are read.
    const hosts = hostsOf(front)
    for (const host of hosts) {
      expect([...PRODUCTION_HOSTS, ...COPY_HOSTS], 'a route names a production hostname or a known copy, exactly').toContain(host)
    }
    const servesProduction = hosts.some((host) => PRODUCTION_HOSTS.includes(host))
    const servesACopy = front.workers_dev !== false || hosts.some((host) => COPY_HOSTS.includes(host))
    expect(servesProduction && servesACopy, 'one Worker serves production or a copy of it, never both').toBe(false)
    expect(front.vars?.ROBOTS_NOINDEX === 'true', `ROBOTS_NOINDEX for a Worker on ${hosts.join(', ') || 'workers.dev'}`).toBe(!servesProduction)

    // A Worker with hostnames serves its pages at one of them, and cloudflare-browser.mjs redirects the rest there.
    // Production's is `www`, as on Vercel, and it takes both hostnames together: the bare domain alone would have
    // nowhere to redirect to, and `www` alone would leave the bare domain on the old host. A Worker on a workers.dev
    // address names none, or every request to it would be sent to a site it does not serve.
    if (hosts.length === 0) {
      expect(front.vars?.CANONICAL_HOST, 'no hostname, so no canonical one').toBeUndefined()
    } else {
      expect(hosts).toContain(front.vars?.CANONICAL_HOST)
    }
    if (servesProduction) {
      expect([...hosts].sort()).toEqual([...PRODUCTION_HOSTS].sort())
      expect(front.vars?.CANONICAL_HOST).toBe(PRODUCTION_CANONICAL_HOST)
    }
    expect(read(front.main)).toMatch(/^ {6}canonicalRedirect\(request, env\) \?\?$/m)
    // `wrangler dev` hands a Worker with a hostname its local requests at that hostname over HTTP, which the
    // redirect would send to the deployed site: CI's worker-build job and `npm run cf:preview` would test nothing.
    expect(front.dev).toEqual({ upstream_protocol: 'https' })
  })
})

describe('the two pairs of Workers', () => {
  const [staging, production] = PAIRS

  it('share the code and nothing that holds state', () => {
    // One build serves both, so each pair has the same entry points, runtime settings, schedule and placement.
    const shape = ({ front, server }: (typeof PAIRS)[number]) => ({
      mains: [front.main, server.main],
      runtime: [front.compatibility_date, front.compatibility_flags, server.compatibility_date, server.compatibility_flags],
      assets: front.assets,
      triggers: front.triggers,
      placement: server.placement,
      waitlist: front.vars?.WAITLIST_MODE,
    })
    expect(shape(production)).toEqual(shape(staging))
    // Each hostname belongs to one pair: staging's serves copies only, so no edit to its files, which the bare
    // `npm run cf:deploy` deploys, can take a production hostname.
    for (const host of hostsOf(staging.front)) expect(COPY_HOSTS, 'staging serves a copy, never production').toContain(host)
    for (const host of hostsOf(production.front)) expect(PRODUCTION_HOSTS, 'production serves production, never a copy').toContain(host)
    // And nothing one pair writes is read by the other: its Workers, and so its Durable Object, and its page cache.
    const owned = ({ front, server }: (typeof PAIRS)[number]) => [front.name, server.name, front.r2_buckets?.[0].bucket_name]
    for (const name of owned(production)) expect(owned(staging)).not.toContain(name)
    expect(new Set([...owned(staging), ...owned(production)]).size).toBe(6)
  })

  it('are each deployed by their own script, and staging is the pair the bare commands mean', () => {
    const scripts = JSON.parse(read('package.json')).scripts as Record<string, string>
    expect(scripts['cf:deploy']).toBe('node scripts/cf-deploy.mjs')
    expect(read('scripts/cf-deploy.mjs')).toContain("const [frontConfig = 'wrangler.jsonc', serverConfig = 'wrangler.server.jsonc'] = process.argv.slice(2)")
    expect(scripts['cf:deploy:production']).toBe('node scripts/cf-deploy.mjs wrangler.production.jsonc wrangler.production.server.jsonc')
  })

  it('are deployed from main only: the script refuses a changed or unmerged checkout before it builds', () => {
    // The deploy's last step attaches the front Worker's hostnames, and wrangler replaces a hostname's existing DNS
    // records without asking when it is not run at a terminal. A deploy from the branch that holds the cutover
    // change would move production before the change was merged. Only a pair of files git does not track, with no
    // hostname, passes: an experiment's.
    const deploy = read('scripts/cf-deploy.mjs')
    expect(deploy).toContain("if (git('status', '--porcelain') !== '') {\n    throw new Error(")
    expect(deploy).toContain("git('fetch', '--quiet', 'origin', 'main')\n  const [head, main] = [git('rev-parse', 'HEAD'), git('rev-parse', 'FETCH_HEAD')]\n  if (head !== main) {\n    throw new Error(")
    expect(deploy).toContain('if (!tracked(frontConfig) && !tracked(serverConfig)) {\n    if (!namesAHostname) return\n    throw new Error(')
    expect(deploy).toContain('const namesAHostname = front.route !== undefined || (front.routes ?? []).length > 0')
    const refused = deploy.indexOf('\nrequireMain()\n')
    expect(refused).toBeGreaterThan(-1)
    for (const later of ['currentVersion(serverConfig)\n', "run(['opennextjs-cloudflare', 'build'])"]) {
      expect(deploy.indexOf(later, refused), later).toBeGreaterThan(refused)
      expect(deploy.slice(0, refused)).not.toContain(`= ${later}`)
    }
  })

  it('can each be created from nothing: the front Worker first, without the binding Cloudflare would refuse', () => {
    // Each Worker names the other, and Cloudflare creates neither while the other is missing (codes 10061 and
    // 10143). scripts/cf-deploy.mjs creates a missing front Worker without its SERVER binding and with nothing that
    // sends it a request, then the server, then deploys as usual.
    const deploy = read('scripts/cf-deploy.mjs')
    expect(deploy).toContain("services: front.services.filter((service) => service.binding !== 'SERVER'),")
    expect(deploy).toContain('const { route: _route, routes: _routes, triggers: _triggers, $schema: _schema, ...front } = readConfig(config)')
    expect(deploy).toMatch(/workers_dev: false,\n {4}preview_urls: false,\n {2}\}/)
    const created = deploy.indexOf('const servingFront = servedFront ?? createFront(frontConfig)')
    expect(created).toBeGreaterThan(-1)
    expect(deploy.indexOf("const servingServer = servedServer ?? versionIn(run(['wrangler', 'deploy', '-c', serverConfig])")).toBeGreaterThan(created)
  })
})
