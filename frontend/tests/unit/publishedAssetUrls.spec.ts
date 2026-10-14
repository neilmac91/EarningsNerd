import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getPathMatch } from 'next/dist/shared/lib/router/utils/path-match'
import { NextRequest } from 'next/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { middleware } from '@/middleware'

/**
 * A published asset URL stays where it was published (CLAUDE.md rule 12;
 * frontend/public/assets/LOGO_README.md › Rules). Transactional email shows its images by
 * address, a sent message keeps those addresses for as long as it is kept, and nobody can edit it
 * after sending, so renaming, moving, removing or replacing one of these files, or redirecting or
 * rewriting its path, changes the image in every message already delivered and on any page that
 * links it. This list is the register of published paths: a change that puts a new asset path in
 * mail adds it here in the same PR. Each path must be its published file in frontend/public, byte
 * for byte (a new rendition takes a new name, so a changed file fails here until it does); pass
 * middleware.ts in both waitlist modes; and be reached by no redirect or rewrite in next.config.js
 * or vercel.json, and no basePath, read in a production build's environment. The origin mail
 * addresses them on is review-checked, and so are the response headers a route or a headers rule sets
 * on them (a Content-Type that stops a mail client showing the image) and anything set only in the
 * Vercel dashboard (a variable a rule reads, or a redirect).
 */
const PUBLISHED = [
  // The app tile in the transactional mail header (docs/brand/templates/email-header.html) once
  // its port into backend/app/services/email_service.py ships.
  { url: '/assets/earningsnerd-appicon.png', sha256: '8b4018f64120e085a8267aa65b91d9862f044a65e19a884760872f522d695761' },
  // The bare sage mark's raster, the Excel export's bytes: first offered as the mail header's mark,
  // kept at its URL since the header took the tile (D-035), though no mail references it.
  { url: '/assets/earningsnerd-mark-sage.png', sha256: '0556990f3e0484b4690891d39c1d9565a3a5513d1593a4df17327ab302d4691d' },
]

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const PUBLIC = path.join(FRONTEND, 'public')
// The origin mail addresses the published paths on (LOGO_README.md › Rules).
const MAIL_HOST = 'www.earningsnerd.io'
// The Vercel project's production domains (docs/LAUNCH_CHECKLIST.md › DNS / redirect config): the apex,
// which redirects to www, and www.
const PRODUCTION_HOSTS = ['earningsnerd.io', MAIL_HOST]
// middleware.ts gates every path outside its allow-lists unless WAITLIST_MODE is 'false'.
const WAITLIST_MODES = ['true', 'false']
const KEPT = 'is a published URL'

type Route = { source?: string; src?: string; has?: { type: string; value?: unknown }[] }
/** A vercel.json legacy route: its regex, the response headers it may set, and whatever else it carries. */
type LegacyRoute = Route & { headers?: Record<string, string> } & Record<string, unknown>
type NextRoutes = { basePath?: string; redirects: Route[]; rewrites: Route[] | { beforeFiles?: Route[]; afterFiles?: Route[]; fallback?: Route[] } }
type VercelJson = { build?: { env?: Record<string, string> }; bulkRedirectsPath?: string; redirects?: Route[]; rewrites?: Route[]; routes?: LegacyRoute[] }

// The system variables Vercel copies under `NEXT_PUBLIC_` for a Next.js build
// (vercel.com/docs/environment-variables/framework-environment-variables).
const NEXT_PUBLIC_COPIES = [
  'VERCEL_ENV', 'VERCEL_TARGET_ENV', 'VERCEL_URL', 'VERCEL_BRANCH_URL', 'VERCEL_PROJECT_PRODUCTION_URL',
  'VERCEL_HASH_SALT', 'VERCEL_GIT_PROVIDER', 'VERCEL_GIT_REPO_SLUG', 'VERCEL_GIT_REPO_OWNER', 'VERCEL_GIT_REPO_ID',
  'VERCEL_GIT_COMMIT_REF', 'VERCEL_GIT_COMMIT_SHA', 'VERCEL_GIT_COMMIT_MESSAGE', 'VERCEL_GIT_COMMIT_AUTHOR_LOGIN',
  'VERCEL_GIT_COMMIT_AUTHOR_NAME', 'VERCEL_GIT_PULL_REQUEST_ID',
]

/**
 * The environment a production build on Vercel runs in, as far as the repository can say:
 * - every system variable Vercel documents as set at build time
 *   (vercel.com/docs/environment-variables/system-environment-variables), with the `NEXT_PUBLIC_` copies it
 *   adds for a Next.js project. One takes the value the repository holds (the production branch, the Git
 *   provider, the repository's owner and name) or, where it holds none (the deployment's URLs and IDs, the
 *   project's and the repository's IDs, the commit), a representative one, so a rule that asks whether one
 *   is set is read as Vercel's build reads it. The ones Vercel sets only while a dashboard setting is on
 *   (Skew Protection, the automation bypass secret, OIDC federation, an Ignored Build Step's
 *   VERCEL_GIT_PREVIOUS_SHA) are set as if it were, and all of them as if the project's access to system
 *   variables were on, so a rule that asks whether one is unset is review-checked. VERCEL_REGION is set at
 *   run time only. VERCEL_PROJECT_PRODUCTION_URL is the project's shortest production custom domain, which
 *   the dashboard's domains decide, so the routes are read once for each production host;
 * - vercel.json's `build.env` (its `env` goes to functions at run time, not to the build);
 * - what vercel.json's buildCommand, `npm run build`, and its script, `next build`, set before the config is
 *   read: npm's lifecycle variables, Next's NODE_ENV, NEXT_RUNTIME and TURBOPACK, and the command's
 *   arguments. The build phase itself goes to the loader.
 * Of the shell's environment it keeps only PATH and HOME. Next's loader still reads frontend/.env* files, as
 * `next build` does; the repository ignores them, so CI and Vercel have none, and a developer's own copy
 * changes the reading on that machine alone. A rule that depends on a value the repository cannot know is
 * review-checked: a variable set only in the Vercel dashboard, one Vercel's builder sets that its reference
 * does not list, a production build deployed from the CLI (`npm run deploy`), or the exact URL or commit of
 * a deployment. next.config.js and vercel.json are high-tier files.
 */
function productionBuildEnv(vercel: VercelJson, productionHost: string): NodeJS.ProcessEnv {
  const system: Record<string, string> = {
    VERCEL: '1',
    CI: '1',
    VERCEL_ENV: 'production',
    VERCEL_TARGET_ENV: 'production',
    VERCEL_URL: 'earnings-nerd-production.vercel.app',
    VERCEL_BRANCH_URL: 'earnings-nerd-git-main.vercel.app',
    VERCEL_PROJECT_PRODUCTION_URL: productionHost,
    VERCEL_DEPLOYMENT_ID: 'dpl_production',
    VERCEL_PROJECT_ID: 'prj_production',
    VERCEL_SKEW_PROTECTION_ENABLED: '1',
    VERCEL_AUTOMATION_BYPASS_SECRET: 'bypass',
    VERCEL_OIDC_TOKEN: 'oidc',
    VERCEL_HASH_SALT: '1',
    VERCEL_GIT_PROVIDER: 'github',
    VERCEL_GIT_REPO_SLUG: 'EarningsNerd',
    VERCEL_GIT_REPO_OWNER: 'neilmac91',
    VERCEL_GIT_REPO_ID: '1',
    VERCEL_GIT_COMMIT_REF: 'main',
    VERCEL_GIT_COMMIT_SHA: '0'.repeat(40),
    VERCEL_GIT_PREVIOUS_SHA: 'f'.repeat(40),
    VERCEL_GIT_COMMIT_MESSAGE: 'A production build',
    VERCEL_GIT_COMMIT_AUTHOR_LOGIN: 'author',
    VERCEL_GIT_COMMIT_AUTHOR_NAME: 'Author',
    // A production build runs on a push to the production branch, which no pull request triggers.
    VERCEL_GIT_PULL_REQUEST_ID: '',
  }
  const copies = NEXT_PUBLIC_COPIES.map((name) => {
    // The child drops an undefined value without a word, so a misspelled name would copy nothing.
    if (!(name in system)) throw new Error(`NEXT_PUBLIC_COPIES names ${name}, which the system variables lack`)
    return [`NEXT_PUBLIC_${name}`, system[name]]
  })
  return {
    PATH: process.env.PATH,
    HOME: process.env.HOME,
    ...system,
    ...Object.fromEntries(copies),
    ...vercel.build?.env,
    npm_lifecycle_event: 'build',
    npm_lifecycle_script: 'next build',
    NODE_ENV: 'production',
    NEXT_RUNTIME: 'nodejs',
    TURBOPACK: 'auto',
  }
}

/**
 * The redirects and rewrites `next build` writes into the deployment, read the way it reads them:
 * Next's own config loader and custom-route loader (next/dist/server/config,
 * next/dist/lib/load-custom-routes), in the build phase and in a production build's environment, so a
 * rule that only a production build enables is read too. They run in a child process, which keeps the
 * test's environment its own; the routes come back as one marked JSON line.
 */
const LOAD_NEXT_ROUTES = `
const loadConfig = require('next/dist/server/config').default
const loadCustomRoutes = require('next/dist/lib/load-custom-routes').default
const { PHASE_PRODUCTION_BUILD } = require('next/constants')
;(async () => {
  const config = await loadConfig(PHASE_PRODUCTION_BUILD, process.cwd(), { silent: true })
  const { redirects, rewrites } = await loadCustomRoutes(config)
  process.stdout.write('\\n__ROUTES__' + JSON.stringify({ basePath: config.basePath, redirects, rewrites }) + '\\n')
})().catch((error) => { console.error(error); process.exit(1) })
`

function nextRoutes(vercel: VercelJson, productionHost: string): NextRoutes {
  // `node -e code a b` gives the code an argv of [node, a, b], as `next build` sees [node, next, build].
  const out = execFileSync(process.execPath, ['-e', LOAD_NEXT_ROUTES, path.join(FRONTEND, 'node_modules/.bin/next'), 'build'], {
    cwd: FRONTEND,
    env: productionBuildEnv(vercel, productionHost),
    encoding: 'utf8',
  })
  const line = out.split('\n').find((l) => l.startsWith('__ROUTES__'))
  if (!line) throw new Error(`next.config.js's routes did not load:\n${out}`)
  return JSON.parse(line.slice('__ROUTES__'.length))
}

/**
 * Every rule that can redirect, rewrite or refuse a path before it is served: Next's, and vercel.json's as
 * Vercel applies them. A legacy route's regex may be spelled `src` or `source`; it is kept as `src`, the
 * spelling reaches() reads as a regex. A legacy route that does nothing but set response headers on the
 * way, as Vercel's cache-control example does (`"headers": { … }, "continue": true`), serves the same file
 * at the same path and passes: its keys are among those in INERT_ROUTE_KEYS, none of its headers is a
 * Location, and it sets `continue: true`. One without it stops Vercel's matching at itself, skipping the
 * routes after it in its phase, and whether the file is then served depends on those routes, so the
 * register refuses it rather than model them: a refusal on the safe side. It reads `routes` as one list,
 * not by Vercel's phases, so a route after `{ "handle": "filesystem" }`, which a served file never reaches,
 * is read as one before it, on the same side. Any other key counts, whatever it does: `dest` or
 * `destination`, `status` or `statusCode`, `mitigate`, `locale`, `transforms`, `middlewarePath`, and any key
 * Vercel adds. The bulk redirects vercel.json can import from a file (`bulkRedirectsPath`) are not read
 * here, so the register refuses them until it reads them.
 */
const INERT_ROUTE_KEYS = new Set(['src', 'source', 'headers', 'continue', 'has', 'missing', 'methods', 'caseSensitive'])
function routing(): { basePaths: [string, string][]; bulkRedirectsPath?: string; rules: [string, Route][] } {
  const vercel: VercelJson = JSON.parse(readFileSync(path.join(FRONTEND, 'vercel.json'), 'utf8'))
  const builds = PRODUCTION_HOSTS.map((host) => ({ read: `read with VERCEL_PROJECT_PRODUCTION_URL=${host}`, next: nextRoutes(vercel, host) }))
  const rewritten = ({ rewrites }: NextRoutes) => Array.isArray(rewrites)
    ? rewrites
    : [...(rewrites.beforeFiles ?? []), ...(rewrites.afterFiles ?? []), ...(rewrites.fallback ?? [])]
  const moves = (r: LegacyRoute) =>
    r.continue !== true
    || Object.keys(r).some((k) => !INERT_ROUTE_KEYS.has(k))
    || Object.keys(r.headers ?? {}).some((h) => h.toLowerCase() === 'location')
  const legacy = (vercel.routes ?? []).filter(moves).map(({ src, source, has }): Route => ({ src: src ?? source, has }))
  const named = (where: string, list: Route[] | undefined) => (list ?? []).map((r): [string, Route] => [where, r])
  return {
    basePaths: builds.map(({ read, next }): [string, string] => [read, next.basePath ?? '']),
    bulkRedirectsPath: vercel.bulkRedirectsPath,
    rules: [
      ...builds.flatMap(({ read, next }) => [
        ...named(`next.config.js redirect (${read})`, next.redirects),
        ...named(`next.config.js rewrite (${read})`, rewritten(next)),
      ]),
      ...named('vercel.json redirect', vercel.redirects),
      ...named('vercel.json rewrite', vercel.rewrites),
      ...named('vercel.json route', legacy),
    ],
  }
}

let routes: ReturnType<typeof routing> | undefined

/**
 * A legacy route's `src` as Vercel compiles it (@vercel/routing-utils normalizeRoutes): a `^` and a `$`
 * are added only where missing, so `/a|/b` matches any path that starts with `/a`, and the regex
 * matches regardless of case, as Vercel matches routes.
 */
function legacyRouteRegex(src: string): RegExp {
  return new RegExp(`${src.startsWith('^') ? '' : '^'}${src}${src.endsWith('$') ? '' : '$'}`, 'i')
}

/**
 * Whether a rule can reach a path on the mail origin. A `source` goes through Next's own matcher, with
 * the options `next build` compiles custom routes with (server/lib/router-utils/filesystem.js), which
 * ignore case; vercel.json's redirects and rewrites take the same syntax and match case, so there the
 * check can only err toward failing. A legacy route's `src` is matched as Vercel compiles it. A rule
 * held to another host by a `has` host condition cannot reach the mail origin. The condition's string
 * is compiled as Next compiles one (shared/lib/router/utils/prepare-destination.js, `^value$`), and the
 * same is assumed for vercel.json's, since Vercel does not publish how it matches them. Any other
 * condition, an object-valued one included, is taken to hold.
 */
function reaches(rule: Route, url: string): boolean {
  const otherHost = rule.has?.some(
    (h) => h.type === 'host' && typeof h.value === 'string' && !new RegExp(`^${h.value}$`).test(MAIL_HOST),
  )
  if (otherHost) return false
  if (rule.source !== undefined) return getPathMatch(rule.source, { strict: true, removeUnnamedParams: true })(url) !== false
  if (rule.src !== undefined) return legacyRouteRegex(rule.src).test(url)
  return false
}

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('published asset URLs', () => {
  for (const { url, sha256 } of PUBLISHED) {
    it(`${url} is still its published file in frontend/public`, () => {
      const file = path.join(PUBLIC, url)
      expect(existsSync(file), `${url} ${KEPT}: keep the file at this path`).toBe(true)
      const digest = createHash('sha256').update(readFileSync(file)).digest('hex')
      expect(digest, `${url} ${KEPT}: keep its image, and write a new rendition under a new name`).toBe(sha256)
    })

    it.each(WAITLIST_MODES)(`${url} passes the middleware with WAITLIST_MODE=%s`, (mode) => {
      vi.stubEnv('WAITLIST_MODE', mode)
      const res = middleware(new NextRequest(new URL(url, `https://${MAIL_HOST}`)))
      expect(res.headers.get('location'), `${url} ${KEPT}: never redirect it`).toBeNull()
      expect(res.headers.get('x-middleware-next'), `${url} ${KEPT}: pass it through`).toBe('1')
    })

    it(`${url} is reached by no redirect or rewrite in next.config.js or vercel.json`, () => {
      const { basePaths, bulkRedirectsPath, rules } = (routes ??= routing())
      for (const [read, basePath] of basePaths) expect(basePath, `${url} ${KEPT}: a basePath moves it (${read})`).toBe('')
      expect(
        bulkRedirectsPath,
        `${url} ${KEPT}: vercel.json imports bulk redirects, which this register does not read; teach it to read them first`,
      ).toBeUndefined()
      const hits = rules.filter(([, rule]) => reaches(rule, url)).map(([where, rule]) => `${where} ${rule.source ?? rule.src}`)
      expect(hits, `${url} ${KEPT}: never redirect or rewrite it (a vercel.json route that only sets headers on it sets "continue": true)`).toEqual([])
    })
  }
})
