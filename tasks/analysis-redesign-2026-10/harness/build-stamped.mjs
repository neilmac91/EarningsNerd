// Build a checkout's frontend and stamp the build with its source tree, its build-time inputs and its output, for
// measure-current.mjs.
// Usage (from anywhere): node tasks/analysis-redesign-2026-10/harness/build-stamped.mjs [<checkout>]
//   <checkout> defaults to this harness's own repository. A build depends on more than its tree, so the script
//   pins or records the rest:
//   - it refuses uncommitted files under frontend/, and the untracked env files Next loads (build-hash.mjs's
//     ENV_FILES; git ignores all four, so `git status` never shows them);
//   - it reinstalls frontend/node_modules with `npm ci` from the lockfile right before the build, so the packages the
//     build runs are the lockfile's tarballs (npm checks each against the lockfile's integrity hash), not an install
//     made for another revision or edited since: node_modules is ignored by git. npm keeps its network settings
//     (registry, proxy, CA), but its node-options and script-shell settings, which would run code in every install
//     script, are set back to npm's defaults on the command line. It then refuses an install that is not the one the
//     lockfile describes (a package missing or at another version, or a top-level package the lockfile does not
//     list; an optional platform package may be absent). Run it on a worktree whose node_modules may be replaced;
//   - it runs the package's build script, `next build`, itself, on the Node running this script, rather than through
//     npm, whose own configuration (npmrc files, npm_config_* variables) can add Node options or a script shell to
//     everything it runs; it refuses a package whose build script is anything else;
//   - it runs the install and the build in build-hash.mjs's controlled environment (what the toolchain needs to run
//     and reach the network, NEXT_TELEMETRY_DISABLED=1, and NODE_OPTIONS only while it holds nothing but heap sizes;
//     any other Node flag is refused, since --require and --import would preload code into every process), plus the
//     caller's NEXT_PUBLIC_* variables for the build, which Next inlines into the bundles; every other variable is
//     dropped;
//   - it writes frontend/.next/SOURCE_TREE.json = { format, commit, frontendTree, buildId, builtAt, node, nodeOptions,
//     install, env, media, output, stampedBy } right after the build: format is build-hash.mjs's STAMP_FORMAT, node the
//     version that ran the build, nodeOptions the heap sizes it ran with (null for none), install the npm version that
//     ran `npm ci` with how many of the lockfile's packages were installed and checked and how many optional ones were
//     absent and the content hash of node_modules after the build (files and hash; measure-current.mjs checks it
//     before and after it serves the build), env the NEXT_PUBLIC_* set the build saw (public by design, since it ships in the client bundles), media
//     the content hash of .next/static/media, where the build puts the fonts next/font downloads from Google and the
//     assets it copies, and output the content hash of everything the build wrote under .next but Next's caches
//     (build-hash.mjs names them), so a file edited, added or removed there later no longer matches the stamp.
//   .next is ignored by git, so the stamp is the only link between a build and its inputs; measure-current.mjs
//   checks it against the served build on every run and, for the baseline, requires this format and pins its env
//   and media.
import { execFileSync, execSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ENV_FILES, STAMP_FORMAT, controlledEnv, hashInstall, hashMedia, hashOutput, heapOptions } from './build-hash.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const CHECKOUT = path.resolve(process.argv[2] || path.join(HERE, '..', '..', '..'))
const frontend = path.join(CHECKOUT, 'frontend')
if (!existsSync(path.join(frontend, 'package.json'))) throw new Error(`${CHECKOUT} has no frontend/package.json: pass the checkout whose frontend to build`)
const git = (cmd) => execSync(`git ${cmd}`, { cwd: CHECKOUT, stdio: ['ignore', 'pipe', 'pipe'] }).toString().trim()
const dirty = git('status --porcelain -- frontend').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, ''))
if (dirty.length) throw new Error(`uncommitted files under ${frontend} (${dirty.join(', ')}): commit or stash them; the stamp names a committed tree`)
const envFiles = ENV_FILES.filter((f) => existsSync(path.join(frontend, f)) && !git(`ls-files -- frontend/${f}`))
if (envFiles.length) throw new Error(`untracked env files in ${frontend} (${envFiles.join(', ')}) would feed the build values its tree does not hold: move them aside, or build a fresh worktree`)
const script = (JSON.parse(readFileSync(path.join(frontend, 'package.json'), 'utf8')).scripts || {}).build
if (script !== 'next build') throw new Error(`${frontend}/package.json's build script is ${JSON.stringify(script)}, but this script runs \`next build\` itself rather than through npm, whose configuration can add Node options: teach it the new build script first`)
const lockFile = path.join(frontend, 'package-lock.json')
if (!existsSync(lockFile)) throw new Error(`${lockFile} is missing: \`npm ci\` installs from the lockfile`)
const nodeOptions = heapOptions()
const commit = git('rev-parse HEAD')
const frontendTree = git('rev-parse HEAD:frontend')

// The install: `npm ci` from the lockfile, right before the build. npm keeps its network settings (the npm_config_*
// variables and the npmrc files it reads carry the registry, proxy and CA), while node-options and script-shell,
// which would run code in every install script, are set back to npm's defaults on the command line, which outranks
// every npmrc file and variable.
const installEnv = controlledEnv(Object.fromEntries(Object.entries(process.env).filter(([k]) => /^npm_config_/i.test(k))))
const npmVersion = execFileSync('npm', ['--version'], { env: installEnv }).toString().trim()
execFileSync('npm', ['ci', '--no-audit', '--no-fund', '--node-options=', '--script-shell=/bin/sh'], { cwd: frontend, stdio: 'inherit', env: installEnv })
const nextBin = path.join(frontend, 'node_modules', 'next', 'dist', 'bin', 'next')
if (!existsSync(nextBin)) throw new Error(`${nextBin} is missing after \`npm ci\``)
// The install must then be the one the lockfile describes: every package it lists installed at its version (an
// optional one may be absent, as the other platforms' builds of sharp and swc are), and no top-level package installed
// that it does not list.
const listed = Object.entries(JSON.parse(readFileSync(lockFile, 'utf8')).packages || {}).filter(([p, m]) => p.startsWith('node_modules/') && !m.link)
const drift = []
let optionalAbsent = 0
for (const [p, m] of listed) {
  const manifest = path.join(frontend, p, 'package.json')
  if (!existsSync(manifest)) { if (m.optional || m.devOptional) optionalAbsent++; else drift.push(`${p} missing`); continue }
  const version = JSON.parse(readFileSync(manifest, 'utf8')).version
  if (version !== m.version) drift.push(`${p} ${version}, the lockfile ${m.version}`)
}
const names = new Set(listed.map(([p]) => p))
const scoped = (d) => (d.startsWith('@') ? readdirSync(path.join(frontend, 'node_modules', d)).map((s) => `node_modules/${d}/${s}`) : [`node_modules/${d}`])
for (const p of readdirSync(path.join(frontend, 'node_modules')).filter((d) => !d.startsWith('.')).flatMap(scoped)) if (!names.has(p)) drift.push(`${p} not in the lockfile`)
if (drift.length) throw new Error(`${frontend}/node_modules is not the install package-lock.json describes after \`npm ci\` (${drift.length}: ${drift.slice(0, 3).join('; ')}${drift.length > 3 ? '; …' : ''})`)

// The build: Next's own CLI on this Node, in the controlled environment plus the caller's NEXT_PUBLIC_* variables.
const env = Object.fromEntries(Object.keys(process.env).filter((k) => k.startsWith('NEXT_PUBLIC_')).sort().map((k) => [k, process.env[k]]))
execFileSync(process.execPath, [nextBin, 'build'], { cwd: frontend, stdio: 'inherit', env: controlledEnv(env) })

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
  nodeOptions: nodeOptions || null,
  install: { by: 'npm ci', npm: npmVersion, packages: listed.length - optionalAbsent, optionalAbsent, ...hashInstall(frontend) },
  env,
  media: hashMedia(nextDir),
  output: hashOutput(nextDir),
  stampedBy: 'tasks/analysis-redesign-2026-10/harness/build-stamped.mjs',
}
const stampFile = path.join(nextDir, 'SOURCE_TREE.json')
writeFileSync(stampFile, `${JSON.stringify(stamp, null, 2)}\n`)
console.log(`stamped ${stampFile}: build ${stamp.buildId} from ${commit.slice(0, 7)} (frontend tree ${frontendTree.slice(0, 7)}), Node ${stamp.node} with ${stamp.nodeOptions || 'no NODE_OPTIONS'}, public env ${JSON.stringify(env)}, media ${stamp.media.files} files ${stamp.media.hash.slice(0, 12)}…, output ${stamp.output.files} files ${stamp.output.hash.slice(0, 12)}…`)
