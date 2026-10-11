// Build a checkout's frontend and stamp the build with its source tree and its build-time inputs, for
// measure-current.mjs.
// Usage (from anywhere): node tasks/analysis-redesign-2026-10/harness/build-stamped.mjs [<checkout>]
//   <checkout> defaults to this harness's own repository. A build depends on more than its tree, so the script
//   pins or records the rest:
//   - it refuses uncommitted files under frontend/, and the untracked env files `next build` loads (.env,
//     .env.local, .env.production, .env.production.local; git ignores all four, so `git status` never shows them);
//   - it runs `npm run build` with an allowlisted environment: what the toolchain needs to run and reach the
//     network (PATH, HOME, temp and locale, NODE_OPTIONS, proxy, CA and npm settings), NEXT_TELEMETRY_DISABLED=1,
//     and the caller's NEXT_PUBLIC_* variables, which Next inlines into the bundles; every other variable (Sentry,
//     Vercel, credentials, a stray NODE_ENV) is dropped;
//   - it writes frontend/.next/SOURCE_TREE.json = { commit, frontendTree, buildId, builtAt, node, env, media,
//     stampedBy } right after the build: env is the NEXT_PUBLIC_* set the build saw (public by design, since it ships
//     in the client bundles), media the content hash of .next/static/media, where the build puts the fonts next/font
//     downloads from Google and the assets it copies.
//   .next is ignored by git, so the stamp is the only link between a build and its inputs; measure-current.mjs
//   checks it against the served build and pins it for the baseline.
import { execSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const CHECKOUT = path.resolve(process.argv[2] || path.join(HERE, '..', '..', '..'))
const frontend = path.join(CHECKOUT, 'frontend')
if (!existsSync(path.join(frontend, 'package.json'))) throw new Error(`${CHECKOUT} has no frontend/package.json: pass the checkout whose frontend to build`)
const git = (cmd) => execSync(`git ${cmd}`, { cwd: CHECKOUT, stdio: ['ignore', 'pipe', 'pipe'] }).toString().trim()
const dirty = git('status --porcelain -- frontend').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, ''))
if (dirty.length) throw new Error(`uncommitted files under ${frontend} (${dirty.join(', ')}): commit or stash them; the stamp names a committed tree`)
const envFiles = ['.env', '.env.local', '.env.production', '.env.production.local'].filter((f) => existsSync(path.join(frontend, f)) && !git(`ls-files -- frontend/${f}`))
if (envFiles.length) throw new Error(`untracked env files in ${frontend} (${envFiles.join(', ')}) would feed the build values its tree does not hold: move them aside, or build a fresh worktree`)
const commit = git('rev-parse HEAD')
const frontendTree = git('rev-parse HEAD:frontend')

const PASS = /^(PATH|HOME|USER|LOGNAME|TMPDIR|TMP|TEMP|LANG|LC_[A-Z]+|TZ|NODE_OPTIONS|NODE_EXTRA_CA_CERTS|SSL_CERT_FILE|SSL_CERT_DIR|(HTTPS?|NO|ALL)_PROXY|(https?|no|all)_proxy|GLOBAL_AGENT_[A-Z_]+|npm_config_[a-z_]+|NPM_CONFIG_[A-Z_]+)$/
const env = Object.fromEntries(Object.keys(process.env).filter((k) => k.startsWith('NEXT_PUBLIC_')).sort().map((k) => [k, process.env[k]]))
const buildEnv = { ...Object.fromEntries(Object.entries(process.env).filter(([k]) => PASS.test(k))), NEXT_TELEMETRY_DISABLED: '1', ...env }
execSync('npm run build', { cwd: frontend, stdio: 'inherit', env: buildEnv })

// A directory's files, recursively, by relative path and bytes (measure-current.mjs hashes the same way).
const hashDir = (dir) => {
  const files = []
  const walk = (d) => { for (const e of readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); if (e.isDirectory()) walk(p); else if (e.isFile()) files.push(p) } }
  if (existsSync(dir)) walk(dir)
  files.sort()
  const h = createHash('sha256')
  for (const f of files) { h.update(`${path.relative(dir, f)}\0`); h.update(readFileSync(f)); h.update('\0') }
  return { files: files.length, hash: h.digest('hex') }
}
const buildIdFile = path.join(frontend, '.next', 'BUILD_ID')
if (!existsSync(buildIdFile)) throw new Error(`${buildIdFile} is missing after the build`)
const stamp = {
  commit,
  frontendTree,
  buildId: readFileSync(buildIdFile, 'utf8').trim(),
  builtAt: statSync(buildIdFile).mtime.toISOString(),
  node: process.version,
  env,
  media: hashDir(path.join(frontend, '.next', 'static', 'media')),
  stampedBy: 'tasks/analysis-redesign-2026-10/harness/build-stamped.mjs',
}
const stampFile = path.join(frontend, '.next', 'SOURCE_TREE.json')
writeFileSync(stampFile, `${JSON.stringify(stamp, null, 2)}\n`)
console.log(`stamped ${stampFile}: build ${stamp.buildId} from ${commit.slice(0, 7)} (frontend tree ${frontendTree.slice(0, 7)}), public env ${JSON.stringify(env)}, media ${stamp.media.files} files ${stamp.media.hash.slice(0, 12)}…`)
