// How build-stamped.mjs and measure-current.mjs hash a frontend build, which stamp format they share, and the
// environment both run Next in, so the stamp's writer and its checker agree.
import { createHash } from 'node:crypto'
import { existsSync, lstatSync, readdirSync, readFileSync, readlinkSync } from 'node:fs'
import path from 'node:path'

// The stamp's format: build-stamped.mjs writes it, and measure-current.mjs writes the baseline only from a stamp of
// this format, so a stamp from an older script is refused. Raise it whenever what a stamp guarantees changes.
// 2: the build ran `next build` itself, not through npm, with no Node flags but heap sizes (recorded), and the stamp
// records the build's whole output. (Stamps without a format predate it.)
// 3: and node_modules was the install package-lock.json describes (every listed package at its version, an optional
// platform package possibly absent, no unlisted top-level package).
// 4: and that install was made by `npm ci` from the lockfile right before the build, so the packages' contents are the
// lockfile's tarballs (npm checks each against the lockfile's integrity hash), not an earlier or edited install.
export const STAMP_FORMAT = 4

// The env files Next loads, at `next build` and at `next start` alike; git ignores all four, so `git status` never
// shows them.
export const ENV_FILES = ['.env', '.env.local', '.env.production', '.env.production.local']

// NODE_OPTIONS reaches every Node process it is set for, and most of its flags change what runs (--require and
// --import preload code, --conditions changes which files imports resolve to), so only heap sizes pass.
export const heapOptions = () => {
  const flags = (process.env.NODE_OPTIONS || '').split(/\s+/).filter(Boolean)
  const foreign = flags.filter((o) => !/^--max[-_](old|semi)[-_]space[-_]size=\d+$/.test(o))
  if (foreign.length) throw new Error(`NODE_OPTIONS holds ${foreign.join(' ')}, which every Next process would run with, unrecorded: unset it (heap sizes, --max-old-space-size=N and --max-semi-space-size=N, may stay)`)
  return flags.join(' ')
}

// The environment Next builds and serves in: what the toolchain needs to run and reach the network (PATH, HOME, temp
// and locale, proxy and CA settings), NEXT_TELEMETRY_DISABLED=1, NODE_OPTIONS while it holds heap sizes only, and
// the caller's additions; every other variable (Sentry, Vercel, credentials, a stray NODE_ENV) is dropped.
const PASS = /^(PATH|HOME|USER|LOGNAME|TMPDIR|TMP|TEMP|LANG|LC_[A-Z]+|TZ|NODE_EXTRA_CA_CERTS|SSL_CERT_FILE|SSL_CERT_DIR|(HTTPS?|NO|ALL)_PROXY|(https?|no|all)_proxy|GLOBAL_AGENT_[A-Z_]+)$/
export const controlledEnv = (extra = {}) => {
  const nodeOptions = heapOptions()
  return { ...Object.fromEntries(Object.entries(process.env).filter(([k]) => PASS.test(k))), ...(nodeOptions ? { NODE_OPTIONS: nodeOptions } : {}), NEXT_TELEMETRY_DISABLED: '1', ...extra }
}

// A directory's regular files and symbolic links, recursively, by relative path and by bytes (a link by its target),
// leaving out the entries `skip` names relative to `dir` (a directory with everything under it).
export const hashDir = (dir, skip = []) => {
  const entries = []
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name)
      if (skip.includes(path.relative(dir, p))) continue
      if (e.isDirectory()) walk(p)
      else if (e.isFile() || e.isSymbolicLink()) entries.push(p)
    }
  }
  if (existsSync(dir)) walk(dir)
  entries.sort()
  const h = createHash('sha256')
  for (const f of entries) { h.update(`${path.relative(dir, f)}\0`); h.update(lstatSync(f).isSymbolicLink() ? `-> ${readlinkSync(f)}` : readFileSync(f)); h.update('\0') }
  return { files: entries.length, hash: h.digest('hex') }
}

// What Next writes under .next after the build, and the stamp: its build and fetch caches (cache/), `next dev`'s
// output (dev/), the pages `next start` renders and caches while it serves (server/route-cache/), and
// SOURCE_TREE.json. Everything else under .next is what the build wrote (bundles, server code, prerendered pages,
// manifests, the build id), and no later `next start` or `next dev` touches it (checked on Next 16.3.8).
export const OUTPUT_SKIP = ['cache', 'dev', 'server/route-cache', 'SOURCE_TREE.json']
// The build's whole output: tamper evidence for one build, since the build id and the prerendered pages differ
// between two builds of the same tree.
export const hashOutput = (nextDir) => hashDir(nextDir, OUTPUT_SKIP)
// The fonts next/font downloads from Google at build time and the assets the build copies: reproducible across
// builds of one tree, so the baseline pins it.
export const hashMedia = (nextDir) => hashDir(path.join(nextDir, 'static', 'media'))
