import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
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
 * or vercel.json, and no basePath. The origin mail addresses them on is review-checked.
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
type Rewrites = Route[] | { beforeFiles?: Route[]; afterFiles?: Route[]; fallback?: Route[] }

/**
 * Every rule that can redirect or rewrite a path before it is served: next.config.js evaluated as
 * `next build` loads it (Sentry's wrapper included), and vercel.json read as Vercel applies it.
 */
async function routing(): Promise<{ basePath: string; rules: [string, Route][] }> {
  const loaded = createRequire(import.meta.url)(path.join(FRONTEND, 'next.config.js'))
  const config = typeof loaded === 'function' ? await loaded('phase-production-server', { defaultConfig: {} }) : loaded
  const redirects: Route[] = (await config.redirects?.()) ?? []
  const rewrites: Rewrites = (await config.rewrites?.()) ?? []
  const rewritten = Array.isArray(rewrites)
    ? rewrites
    : [...(rewrites.beforeFiles ?? []), ...(rewrites.afterFiles ?? []), ...(rewrites.fallback ?? [])]
  const vercel = JSON.parse(readFileSync(path.join(FRONTEND, 'vercel.json'), 'utf8'))
  const named = (where: string, list: Route[] | undefined) => (list ?? []).map((r): [string, Route] => [where, r])
  return {
    basePath: config.basePath ?? '',
    rules: [
      ...named('next.config.js redirect', redirects),
      ...named('next.config.js rewrite', rewritten),
      ...named('vercel.json redirect', vercel.redirects),
      ...named('vercel.json rewrite', vercel.rewrites),
      ...named('vercel.json route', vercel.routes),
    ],
  }
}

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

    it(`${url} is reached by no redirect or rewrite in next.config.js or vercel.json`, async () => {
      const { basePath, rules } = await routing()
      expect(basePath, `${url} ${KEPT}: a basePath moves it`).toBe('')
      const hits = rules.filter(([, rule]) => reaches(rule, url)).map(([where, rule]) => `${where} ${rule.source ?? rule.src}`)
      expect(hits, `${url} ${KEPT}: never redirect or rewrite it`).toEqual([])
    })
  }
})
