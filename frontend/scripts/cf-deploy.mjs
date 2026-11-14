#!/usr/bin/env node
// Deploys the Cloudflare Workers copy of the frontend: `npm run cf:deploy`, or
// `node scripts/cf-deploy.mjs <front config> <server config>` for another pair of wrangler files.
// docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (staging)".
//
// The app is two Workers built from one `next build` (cloudflare-front.mjs, cloudflare-server.mjs), and a front
// version must only ever call the server version of its own build: another build's server renders pages whose
// scripts the front does not hold. So this follows OpenNext's order for a deploy with no such moment:
//   1. upload the new server version, serving nothing yet;
//   2. upload the new front version, told that server version (SERVER_VERSION_OVERRIDE);
//   3. fill the cache with the build's prerendered pages;
//   4. add the new server version to the server's deployment at 0%, so that the front may name it;
//   5. move the front to its new version, which calls its own server version by name;
//   6. move the server to its new version;
//   7. apply the front's triggers (its hostname and its schedule), which a version deploy does not carry.
// The first deploy of a pair has one more problem: each Worker names the other (the front binds the server; the
// server binds the front and its Durable Object), and Cloudflare creates neither while the other is missing. So a
// front Worker that does not exist is first created without its binding to the server, and with no hostname,
// address or schedule, which is also what applies its Durable Object migration; then the server is created; then
// the steps above run as for any deploy, and step 7 is what first makes the front reachable.
//
// Step 7 can move a hostname: wrangler replaces a hostname's existing DNS records without asking when it is not
// run at a terminal, which is how this script runs it. So a pair the repository holds is deployed only from a
// checkout with nothing changed whose frontend/ is main's as fetched now, and the script refuses anything else
// before it builds. frontend/ is everything the build reads (scripts/vercel-ignore-build.sh), so a checkout
// that main has passed with a commit elsewhere still deploys what main holds.
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const [frontConfig = 'wrangler.jsonc', serverConfig = 'wrangler.server.jsonc'] = process.argv.slice(2)

// The wrangler files keep each comment on a line of its own (tests/unit/cloudflareWorkerConfig.spec.ts).
const readConfig = (file) =>
  JSON.parse(
    readFileSync(file, 'utf8')
      .split('\n')
      .filter((line) => !line.trim().startsWith('//'))
      .join('\n'),
  )

function run(args, { quiet = false } = {}) {
  console.log(`\n$ npx ${args.join(' ')}`)
  const output = execFileSync('npx', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] })
  if (!quiet) process.stdout.write(output)
  return output
}

/**
 * The version serving 100% of a Worker's traffic, or null when the Worker has never been deployed. Only wrangler
 * saying so counts as "never deployed": any other failure (the API unreachable, a rate limit) stops the deploy here,
 * before anything is built or uploaded, since a Worker wrongly taken for new would be deployed outright, past the
 * steps that keep the two Workers on one build.
 */
function currentVersion(config) {
  console.log(`\n$ npx wrangler deployments status --json -c ${config}`)
  let output
  try {
    output = execFileSync('npx', ['wrangler', 'deployments', 'status', '--json', '-c', config], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
  } catch (error) {
    const said = `${error.stdout ?? ''}${error.stderr ?? ''}`
    if (/This Worker does not exist on your account|has no deployments/.test(said)) return null
    throw new Error(`${config}: could not read the Worker's deployment, so nothing was deployed.\n${said}`)
  }
  const versions = JSON.parse(output).versions ?? []
  if (versions.length !== 1 || versions[0].percentage !== 100) {
    throw new Error(`${config}: a deploy is half-way (${JSON.stringify(versions)}); finish or roll it back with \`wrangler versions deploy\` first`)
  }
  return versions[0].version_id
}

function versionIn(output, label) {
  const found = output.match(new RegExp(`${label}:\\s*([0-9a-f-]{36})`))
  if (!found) throw new Error(`wrangler printed no "${label}"`)
  return found[1]
}

/**
 * Creates a front Worker that does not exist yet, and returns its version. The config is the front Worker's own
 * without the SERVER binding, which Cloudflare refuses while the server Worker is missing, and without anything
 * that would send it a request: it calls a server it does not have. It is written under .wrangler/, which git
 * ignores, so its paths are made absolute.
 */
function createFront(config) {
  const { route: _route, routes: _routes, triggers: _triggers, $schema: _schema, ...front } = readConfig(config)
  const unreachable = {
    ...front,
    main: path.resolve(front.main),
    assets: { ...front.assets, directory: path.resolve(front.assets.directory) },
    services: front.services.filter((service) => service.binding !== 'SERVER'),
    workers_dev: false,
    preview_urls: false,
  }
  mkdirSync('.wrangler', { recursive: true })
  const file = path.join('.wrangler', 'cf-deploy-first-front.json')
  writeFileSync(file, JSON.stringify(unreachable, null, 2))
  return versionIn(run(['wrangler', 'deploy', '-c', file]), 'Current Version ID')
}

/**
 * Refuses a deploy of unreviewed code or configuration to a pair the repository holds, or to any hostname. A pair
 * of files git does not track and that names no hostname, an experiment's on a workers.dev address, is let through.
 */
function requireMain() {
  const git = (...args) => execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim()
  const tracked = (file) => git('ls-files', '--', file) !== ''
  const front = readConfig(frontConfig)
  const namesAHostname = front.route !== undefined || (front.routes ?? []).length > 0
  if (!tracked(frontConfig) && !tracked(serverConfig)) {
    if (!namesAHostname) return
    throw new Error(`${frontConfig} is not in the repository and names a hostname; only a reviewed file may take one.`)
  }
  if (git('status', '--porcelain') !== '') {
    throw new Error('The checkout has changes. Deploy from a clean checkout of main: `git status` lists what differs.')
  }
  git('fetch', '--no-tags', '--quiet', 'origin', 'refs/heads/main')
  if (git('rev-parse', 'HEAD:frontend') !== git('rev-parse', 'FETCH_HEAD:frontend')) {
    const [head, main] = [git('rev-parse', '--short', 'HEAD'), git('rev-parse', '--short', 'FETCH_HEAD')]
    throw new Error(`frontend/ at ${head}, this checkout, is not frontend/ at ${main}, main as it is now. Deploy main's.`)
  }
}

requireMain()

const serverName = readConfig(serverConfig).name
const servedServer = currentVersion(serverConfig)
const servedFront = currentVersion(frontConfig)

run(['opennextjs-cloudflare', 'build'])

const servingFront = servedFront ?? createFront(frontConfig)
const servingServer = servedServer ?? versionIn(run(['wrangler', 'deploy', '-c', serverConfig]), 'Current Version ID')

const newServer = versionIn(run(['wrangler', 'versions', 'upload', '-c', serverConfig]), 'Worker Version ID')
const override = `SERVER_VERSION_OVERRIDE:${serverName}="${newServer}"`
const newFront = versionIn(run(['wrangler', 'versions', 'upload', '-c', frontConfig, '--var', override]), 'Worker Version ID')

run(['opennextjs-cloudflare', 'populateCache', 'remote', '-c', frontConfig])

run(['wrangler', 'versions', 'deploy', `${servingServer}@100%`, `${newServer}@0%`, '-y', '-c', serverConfig])
run(['wrangler', 'versions', 'deploy', `${newFront}@100%`, '-y', '-c', frontConfig])
run(['wrangler', 'versions', 'deploy', `${newServer}@100%`, '-y', '-c', serverConfig])
run(['wrangler', 'triggers', 'deploy', '-c', frontConfig])

console.log(`\nDeployed ${readConfig(frontConfig).name} (was ${servingFront}) with ${serverName} version ${newServer}.`)
