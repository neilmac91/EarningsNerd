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
 * addresses them on is review-checked, and so is anything set only in the Vercel dashboard (a
 * variable a rule reads, or a redirect).
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
// middleware.ts gates every path outside its allow-lists unless WAITLIST_MODE is 'false'.
const WAITLIST_MODES = ['true', 'false']
const KEPT = 'is a published URL'

type Route = { source?: string; src?: string; has?: { type: string; value?: string }[] }
type NextRoutes = { basePath?: string; redirects: Route[]; rewrites: Route[] | { beforeFiles?: Route[]; afterFiles?: Route[]; fallback?: Route[] } }
type VercelJson = { build?: { env?: Record<string, string> }; redirects?: Route[]; rewrites?: Route[]; routes?: Route[] }

/**
 * The environment a production build on Vercel runs in, as far as the repository can say: Next's own
 * NODE_ENV (the phase goes to the loader), the system variables Vercel sets on a production build and
 * the `NEXT_PUBLIC_` copies it adds for a Next.js project, and vercel.json's `build.env` (its `env` goes
 * to functions at run time, not to the build). Of the shell's environment it keeps only PATH and HOME.
 * Next's loader still reads frontend/.env* files, as `next build` does; the repository ignores them, so
 * CI and Vercel have none, and a developer's own copy changes the reading on that machine alone. A rule
 * that depends on a value the repository cannot know (a variable set only in the Vercel dashboard, or a
 * deployment's own URL or commit) is review-checked; next.config.js and vercel.json are high-tier files.
 */
function productionBuildEnv(vercel: VercelJson): NodeJS.ProcessEnv {
  return {
    PATH: process.env.PATH,
    HOME: process.env.HOME,
    VERCEL: '1',
    CI: '1',
    VERCEL_ENV: 'production',
    VERCEL_TARGET_ENV: 'production',
    VERCEL_GIT_COMMIT_REF: 'main',
    NEXT_PUBLIC_VERCEL_ENV: 'production',
    NEXT_PUBLIC_VERCEL_TARGET_ENV: 'production',
    NEXT_PUBLIC_VERCEL_GIT_COMMIT_REF: 'main',
    ...vercel.build?.env,
    NODE_ENV: 'production',
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

function nextRoutes(vercel: VercelJson): NextRoutes {
  const out = execFileSync(process.execPath, ['-e', LOAD_NEXT_ROUTES], {
    cwd: FRONTEND,
    env: productionBuildEnv(vercel),
    encoding: 'utf8',
  })
  const line = out.split('\n').find((l) => l.startsWith('__ROUTES__'))
  if (!line) throw new Error(`next.config.js's routes did not load:\n${out}`)
  return JSON.parse(line.slice('__ROUTES__'.length))
}

/** Every rule that can redirect or rewrite a path before it is served: Next's, and vercel.json's as Vercel applies them. */
function routing(): { basePath: string; rules: [string, Route][] } {
  const vercel: VercelJson = JSON.parse(readFileSync(path.join(FRONTEND, 'vercel.json'), 'utf8'))
  const next = nextRoutes(vercel)
  const rewritten = Array.isArray(next.rewrites)
    ? next.rewrites
    : [...(next.rewrites.beforeFiles ?? []), ...(next.rewrites.afterFiles ?? []), ...(next.rewrites.fallback ?? [])]
  const named = (where: string, list: Route[] | undefined) => (list ?? []).map((r): [string, Route] => [where, r])
  return {
    basePath: next.basePath ?? '',
    rules: [
      ...named('next.config.js redirect', next.redirects),
      ...named('next.config.js rewrite', rewritten),
      ...named('vercel.json redirect', vercel.redirects),
      ...named('vercel.json rewrite', vercel.rewrites),
      ...named('vercel.json route', vercel.routes),
    ],
  }
}

let routes: ReturnType<typeof routing> | undefined

/**
 * Whether a rule can reach a path on the mail origin. A `source` goes through Next's own matcher, with
 * the options `next build` compiles custom routes with (server/lib/router-utils/filesystem.js);
 * vercel.json's redirects and rewrites take the same syntax, and a legacy route's `src` is a regex
 * over the whole path. A rule held to another host by a `has` host condition cannot reach the mail
 * origin; any other condition is taken to hold.
 */
function reaches(rule: Route, url: string): boolean {
  const otherHost = rule.has?.some((h) => h.type === 'host' && h.value !== undefined && !new RegExp(`^(?:${h.value})$`).test(MAIL_HOST))
  if (otherHost) return false
  if (rule.source !== undefined) return getPathMatch(rule.source, { strict: true, removeUnnamedParams: true })(url) !== false
  if (rule.src !== undefined) return new RegExp(`^(?:${rule.src})$`).test(url)
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
      const { basePath, rules } = (routes ??= routing())
      expect(basePath, `${url} ${KEPT}: a basePath moves it`).toBe('')
      const hits = rules.filter(([, rule]) => reaches(rule, url)).map(([where, rule]) => `${where} ${rule.source ?? rule.src}`)
      expect(hits, `${url} ${KEPT}: never redirect or rewrite it`).toEqual([])
    })
  }
})
