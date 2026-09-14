import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import semver from 'semver'

/**
 * Structural gate for the Node runtime pin (CLAUDE.md rule 12: rules become gates).
 *
 * The Node version lives in four places that must move together — docs/DEPLOYMENT.md "Node.js version
 * moves in lockstep": (1) frontend/.nvmrc, (2) frontend/package.json engines.node, (3) every
 * `node-version:` in .github/workflows/*.yml or *.yaml, (4) the Vercel project setting (Settings → General →
 * Node.js Version — console-only, so it cannot be checked here; the founder switches it in the same
 * change). A Node bump is a deliberate PR that touches all of them AND this constant.
 */
const EXPECTED_NODE_MAJOR = 22

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (rel: string) => readFileSync(path.join(frontendDir, rel), 'utf8')

const nvmrc = read('.nvmrc').trim()
const pkg = JSON.parse(read('package.json')) as {
  engines: { node: string }
  dependencies: Record<string, string>
  devDependencies: Record<string, string>
}
const engines = pkg.engines.node
const lock = JSON.parse(read('package-lock.json')) as {
  packages: Record<string, { engines?: { node?: string } }>
}
const workflowDir = path.resolve(frontendDir, '../.github/workflows')
const workflowVersions = readdirSync(workflowDir)
  .filter((file) => /\.ya?ml$/.test(file))
  .sort()
  .flatMap((file) =>
    [...readFileSync(path.join(workflowDir, file), 'utf8').matchAll(/^\s*node-version:\s*(.*?)\s*$/gm)].map(
      (match) => ({ file, version: match[1].replace(/^['"]|['"]$/g, '') }),
    ),
  )

const SITES =
  'frontend/.nvmrc, frontend/package.json engines.node, every node-version: in .github/workflows/*.yml or *.yaml, ' +
  'and the Vercel project Node.js Version setting (founder, console) must all move together.'

describe('Node runtime is pinned in lockstep (nvmrc / engines / CI / Vercel)', () => {
  it(`.nvmrc pins an exact ${EXPECTED_NODE_MAJOR}.x.y release`, () => {
    expect(nvmrc, `frontend/.nvmrc must be an exact x.y.z version — ${SITES}`).toMatch(/^\d+\.\d+\.\d+$/)
    expect(Number(nvmrc.split('.')[0]), `frontend/.nvmrc is on Node ${nvmrc} — ${SITES}`).toBe(EXPECTED_NODE_MAJOR)
  })

  it('declares only Node releases supported by the pinned direct dependencies', () => {
    expect(semver.validRange(engines), 'engines.node must be a valid semver range').not.toBeNull()
    expect(semver.subset(engines, `${EXPECTED_NODE_MAJOR}.x`), SITES).toBe(true)
    expect(semver.satisfies(nvmrc, engines), '.nvmrc must satisfy engines.node').toBe(true)
    expect(lock.packages[''].engines?.node, 'lockfile root engine must match package.json').toBe(engines)

    // A major-only pin admitted Node 22.10 even after jsdom 30 required 22.22.2.
    // Read installed package requirements so the gate follows future dependency floors.
    const requirements = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies })
      .map((name) => ({ name, range: lock.packages[`node_modules/${name}`]?.engines?.node }))
      .filter((entry): entry is { name: string; range: string } => Boolean(entry.range))
    expect(requirements.length, 'No direct dependency Node requirements were found').toBeGreaterThan(0)
    for (const { name, range } of requirements) {
      expect(
        semver.subset(engines, range),
        `engines.node ${engines} admits releases unsupported by ${name} (${range})`,
      ).toBe(true)
    }
  })

  it('every workflow node-version equals .nvmrc exactly', () => {
    expect(workflowVersions.length, 'Workflows have no node-version: sites — did the setup-node steps move?').toBeGreaterThan(0)
    expect(workflowVersions.some(({ file }) => file === 'ci.yml'), 'ci.yml has no node-version: sites — did the setup-node steps move?').toBe(true)
    for (const { file, version } of workflowVersions) {
      expect(version, `.github/workflows/${file} pins node-version ${version} but frontend/.nvmrc says ${nvmrc} — ${SITES}`).toBe(nvmrc)
    }
  })
})
