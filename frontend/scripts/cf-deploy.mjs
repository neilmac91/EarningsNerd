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
//   6. move the server to its new version.
// A Worker that does not exist yet is created by a plain deploy, which is also what applies the front's Durable
// Object migration; such a first deploy has no earlier version to protect.
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

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

/** The version serving 100% of a Worker's traffic, or null when the Worker has never been deployed. */
function currentVersion(config) {
  let status
  try {
    status = JSON.parse(run(['wrangler', 'deployments', 'status', '--json', '-c', config], { quiet: true }))
  } catch {
    return null
  }
  const versions = status.versions ?? []
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

const serverName = readConfig(serverConfig).name
const servingServer = currentVersion(serverConfig)
const servingFront = currentVersion(frontConfig)

run(['opennextjs-cloudflare', 'build'])

const newServer = servingServer
  ? versionIn(run(['wrangler', 'versions', 'upload', '-c', serverConfig]), 'Worker Version ID')
  : versionIn(run(['wrangler', 'deploy', '-c', serverConfig]), 'Current Version ID')

const override = `SERVER_VERSION_OVERRIDE:${serverName}="${newServer}"`
const newFront = servingFront
  ? versionIn(run(['wrangler', 'versions', 'upload', '-c', frontConfig, '--var', override]), 'Worker Version ID')
  : null

run(['opennextjs-cloudflare', 'populateCache', 'remote', '-c', frontConfig])

if (servingServer) {
  run(['wrangler', 'versions', 'deploy', `${servingServer}@100%`, `${newServer}@0%`, '-y', '-c', serverConfig])
}
if (newFront) {
  run(['wrangler', 'versions', 'deploy', `${newFront}@100%`, '-y', '-c', frontConfig])
} else {
  run(['wrangler', 'deploy', '-c', frontConfig, '--var', override])
}
if (servingServer) {
  run(['wrangler', 'versions', 'deploy', `${newServer}@100%`, '-y', '-c', serverConfig])
}

console.log(`\nDeployed ${readConfig(frontConfig).name} with ${serverName} version ${newServer}.`)
