// Build a checkout's frontend and stamp the build with its source tree, its build-time inputs and its output, for
// measure-current.mjs.
// Usage (from anywhere): node tasks/analysis-redesign-2026-10/harness/build-stamped.mjs [<checkout>]
//   <checkout> defaults to this harness's own repository. A build depends on more than its tree, so the script
//   pins or records the rest:
//   - it refuses uncommitted files under frontend/, and the untracked env files `next build` loads (.env,
//     .env.local, .env.production, .env.production.local; git ignores all four, so `git status` never shows them);
//   - it runs the package's build script, `next build`, itself, on the Node running this script, rather than through
//     npm, whose own configuration (npmrc files, npm_config_* variables) can add Node options or a script shell to
//     everything it runs; it refuses a package whose build script is anything else;
//   - it runs the build with an allowlisted environment: what the toolchain needs to run and reach the network
//     (PATH, HOME, temp and locale, proxy and CA settings), NEXT_TELEMETRY_DISABLED=1, the caller's NEXT_PUBLIC_*
//     variables, which Next inlines into the bundles, and NODE_OPTIONS only while it holds nothing but heap sizes
//     (--max-old-space-size=N, --max-semi-space-size=N). Its other flags change what every build process runs
//     (--require and --import preload code, --conditions changes which files imports resolve to), so any other flag
//     is refused; every other variable (Sentry, Vercel, credentials, a stray NODE_ENV) is dropped;
//   - it writes frontend/.next/SOURCE_TREE.json = { format, commit, frontendTree, buildId, builtAt, node, nodeOptions,
//     env, media, output, stampedBy } right after the build: format is build-hash.mjs's STAMP_FORMAT, node the version
//     that ran the build, nodeOptions the heap sizes it ran with (null for none), env the NEXT_PUBLIC_* set the build
//     saw (public by design, since it ships in the client bundles), media the content hash of .next/static/media,
//     where the build puts the fonts next/font downloads from Google and the assets it copies, and output the content
//     hash of everything the build wrote under .next but Next's caches (build-hash.mjs names them), so a file edited,
//     added or removed there later no longer matches the stamp.
//   .next is ignored by git, so the stamp is the only link between a build and its inputs; measure-current.mjs
//   checks it against the served build on every run and, for the baseline, requires this format and pins its env
//   and media.
import { execFileSync, execSync } from 'node:child_process'
import { existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { STAMP_FORMAT, hashMedia, hashOutput } from './build-hash.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const CHECKOUT = path.resolve(process.argv[2] || path.join(HERE, '..', '..', '..'))
const frontend = path.join(CHECKOUT, 'frontend')
if (!existsSync(path.join(frontend, 'package.json'))) throw new Error(`${CHECKOUT} has no frontend/package.json: pass the checkout whose frontend to build`)
const git = (cmd) => execSync(`git ${cmd}`, { cwd: CHECKOUT, stdio: ['ignore', 'pipe', 'pipe'] }).toString().trim()
const dirty = git('status --porcelain -- frontend').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, ''))
if (dirty.length) throw new Error(`uncommitted files under ${frontend} (${dirty.join(', ')}): commit or stash them; the stamp names a committed tree`)
const envFiles = ['.env', '.env.local', '.env.production', '.env.production.local'].filter((f) => existsSync(path.join(frontend, f)) && !git(`ls-files -- frontend/${f}`))
if (envFiles.length) throw new Error(`untracked env files in ${frontend} (${envFiles.join(', ')}) would feed the build values its tree does not hold: move them aside, or build a fresh worktree`)
const script = (JSON.parse(readFileSync(path.join(frontend, 'package.json'), 'utf8')).scripts || {}).build
if (script !== 'next build') throw new Error(`${frontend}/package.json's build script is ${JSON.stringify(script)}, but this script runs \`next build\` itself rather than through npm, whose configuration can add Node options: teach it the new build script first`)
const nextBin = path.join(frontend, 'node_modules', 'next', 'dist', 'bin', 'next')
if (!existsSync(nextBin)) throw new Error(`${nextBin} is missing: run \`npm ci\` in ${frontend} first`)
const nodeOptions = (process.env.NODE_OPTIONS || '').split(/\s+/).filter(Boolean)
const foreign = nodeOptions.filter((o) => !/^--max[-_](old|semi)[-_]space[-_]size=\d+$/.test(o))
if (foreign.length) throw new Error(`NODE_OPTIONS holds ${foreign.join(' ')}, which every build process would run with while the stamp names a build of its tree alone: unset it (heap sizes, --max-old-space-size=N and --max-semi-space-size=N, may stay)`)
const commit = git('rev-parse HEAD')
const frontendTree = git('rev-parse HEAD:frontend')

const PASS = /^(PATH|HOME|USER|LOGNAME|TMPDIR|TMP|TEMP|LANG|LC_[A-Z]+|TZ|NODE_EXTRA_CA_CERTS|SSL_CERT_FILE|SSL_CERT_DIR|(HTTPS?|NO|ALL)_PROXY|(https?|no|all)_proxy|GLOBAL_AGENT_[A-Z_]+)$/
const env = Object.fromEntries(Object.keys(process.env).filter((k) => k.startsWith('NEXT_PUBLIC_')).sort().map((k) => [k, process.env[k]]))
const buildEnv = { ...Object.fromEntries(Object.entries(process.env).filter(([k]) => PASS.test(k))), ...(nodeOptions.length ? { NODE_OPTIONS: nodeOptions.join(' ') } : {}), NEXT_TELEMETRY_DISABLED: '1', ...env }
execFileSync(process.execPath, [nextBin, 'build'], { cwd: frontend, stdio: 'inherit', env: buildEnv })

const nextDir = path.join(frontend, '.next')
const buildIdFile = path.join(nextDir, 'BUILD_ID')
if (!existsSync(buildIdFile)) throw new Error(`${buildIdFile} is missing after the build`)
const stamp = {
  format: STAMP_FORMAT,
  commit,
  frontendTree,
  buildId: readFileSync(buildIdFile, 'utf8').trim(),
  builtAt: statSync(buildIdFile).mtime.toISOString(),
  node: process.version,
  nodeOptions: nodeOptions.join(' ') || null,
  env,
  media: hashMedia(nextDir),
  output: hashOutput(nextDir),
  stampedBy: 'tasks/analysis-redesign-2026-10/harness/build-stamped.mjs',
}
const stampFile = path.join(nextDir, 'SOURCE_TREE.json')
writeFileSync(stampFile, `${JSON.stringify(stamp, null, 2)}\n`)
console.log(`stamped ${stampFile}: build ${stamp.buildId} from ${commit.slice(0, 7)} (frontend tree ${frontendTree.slice(0, 7)}), Node ${stamp.node} with ${stamp.nodeOptions || 'no NODE_OPTIONS'}, public env ${JSON.stringify(env)}, media ${stamp.media.files} files ${stamp.media.hash.slice(0, 12)}…, output ${stamp.output.files} files ${stamp.output.hash.slice(0, 12)}…`)
