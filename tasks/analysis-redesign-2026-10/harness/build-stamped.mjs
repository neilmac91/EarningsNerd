// Build a checkout's frontend and stamp the build with its source tree, for measure-current.mjs.
// Usage (from anywhere): node tasks/analysis-redesign-2026-10/harness/build-stamped.mjs [<checkout>]
//   <checkout> defaults to this harness's own repository. The environment passes through to `npm run build`
//   (NEXT_PUBLIC_ENABLE_ANALYSIS, NEXT_PUBLIC_API_BASE_URL). The script refuses uncommitted files under
//   frontend/, runs the build, then writes frontend/.next/SOURCE_TREE.json = { commit, frontendTree, buildId,
//   builtAt, stampedBy } from the checkout's HEAD right after the build, so measure-current.mjs can bind the
//   served build (by its BUILD_ID) to the source tree it records; .next is ignored by git, so the stamp is the
//   only link between a build and a tree.
import { execSync } from 'node:child_process'
import { existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const CHECKOUT = path.resolve(process.argv[2] || path.join(HERE, '..', '..', '..'))
const frontend = path.join(CHECKOUT, 'frontend')
if (!existsSync(path.join(frontend, 'package.json'))) throw new Error(`${CHECKOUT} has no frontend/package.json: pass the checkout whose frontend to build`)
const git = (cmd) => execSync(`git ${cmd}`, { cwd: CHECKOUT, stdio: ['ignore', 'pipe', 'pipe'] }).toString().trim()
const dirty = git('status --porcelain -- frontend').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, ''))
if (dirty.length) throw new Error(`uncommitted files under ${frontend} (${dirty.join(', ')}): commit or stash them; the stamp names a committed tree`)
const commit = git('rev-parse HEAD')
const frontendTree = git('rev-parse HEAD:frontend')
execSync('npm run build', { cwd: frontend, stdio: 'inherit' })
const buildIdFile = path.join(frontend, '.next', 'BUILD_ID')
if (!existsSync(buildIdFile)) throw new Error(`${buildIdFile} is missing after the build`)
const stamp = {
  commit,
  frontendTree,
  buildId: readFileSync(buildIdFile, 'utf8').trim(),
  builtAt: statSync(buildIdFile).mtime.toISOString(),
  stampedBy: 'tasks/analysis-redesign-2026-10/harness/build-stamped.mjs',
}
const stampFile = path.join(frontend, '.next', 'SOURCE_TREE.json')
writeFileSync(stampFile, `${JSON.stringify(stamp, null, 2)}\n`)
console.log(`stamped ${stampFile}: build ${stamp.buildId} from ${commit.slice(0, 7)} (frontend tree ${frontendTree.slice(0, 7)})`)
