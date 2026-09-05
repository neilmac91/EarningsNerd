import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Structural gate for the Node runtime pin (CLAUDE.md rule 12: rules become gates).
 *
 * The Node version lives in four places that must move together — docs/DEPLOYMENT.md "Node.js version
 * moves in lockstep": (1) frontend/.nvmrc, (2) frontend/package.json engines.node, (3) every
 * `node-version:` in .github/workflows/ci.yml, (4) the Vercel project setting (Settings → General →
 * Node.js Version — console-only, so it cannot be checked here; the founder switches it in the same
 * change). A Node bump is a deliberate PR that touches all of them AND this constant.
 */
const EXPECTED_NODE_MAJOR = 22

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (rel: string) => readFileSync(path.join(frontendDir, rel), 'utf8')

const nvmrc = read('.nvmrc').trim()
const engines = (JSON.parse(read('package.json')) as { engines?: { node?: string } }).engines?.node
const ciVersions = [...read('../.github/workflows/ci.yml').matchAll(/^\s*node-version:\s*['"]?([^'"\s]+)['"]?\s*$/gm)].map(
  (m) => m[1],
)

const SITES =
  'frontend/.nvmrc, frontend/package.json engines.node, every node-version: in .github/workflows/ci.yml, ' +
  'and the Vercel project Node.js Version setting (founder, console) must all move together.'

describe('Node runtime is pinned in lockstep (nvmrc / engines / CI / Vercel)', () => {
  it(`.nvmrc pins an exact ${EXPECTED_NODE_MAJOR}.x.y release`, () => {
    expect(nvmrc, `frontend/.nvmrc must be an exact x.y.z version — ${SITES}`).toMatch(/^\d+\.\d+\.\d+$/)
    expect(Number(nvmrc.split('.')[0]), `frontend/.nvmrc is on Node ${nvmrc} — ${SITES}`).toBe(EXPECTED_NODE_MAJOR)
  })

  it(`package.json engines.node is "${EXPECTED_NODE_MAJOR}.x"`, () => {
    expect(engines, `frontend/package.json engines.node is ${JSON.stringify(engines)} — ${SITES}`).toBe(
      `${EXPECTED_NODE_MAJOR}.x`,
    )
  })

  it('every ci.yml node-version equals .nvmrc exactly', () => {
    expect(ciVersions.length, 'ci.yml has no node-version: sites — did the setup-node steps move?').toBeGreaterThan(0)
    for (const v of ciVersions) {
      expect(v, `.github/workflows/ci.yml pins node-version ${v} but frontend/.nvmrc says ${nvmrc} — ${SITES}`).toBe(nvmrc)
    }
  })
})
