import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const requireNode = createRequire(import.meta.url)

/**
 * The frontend build reads frontend/ and nothing else. Vercel's build filter compares that directory alone
 * (scripts/vercel-ignore-build.sh), and Next nests its standalone output under any wider root, where an adapter that
 * builds a Worker from it does not look.
 *
 * Turbopack refuses a module outside its root, so with the root at frontend/ an outside import fails the build
 * itself. backend/tests/unit/test_frontend_build_filter.py scans shipped files for such a read, but it reads path
 * literals only: a path joined from segments, or a tsconfig alias, is out of its reach. This spec holds the root, so
 * the build's own refusal stays behind that scan.
 *
 * Next takes the root from the nearest lockfile when the config names none, and frontend/package-lock.json is the
 * only one. A lockfile added above frontend/ would move the root with no change here: that is review-checked.
 */
describe("the frontend build's root", () => {
  it('stays at frontend/: next.config.js widens neither root it can set', () => {
    const config = requireNode(path.join(FRONTEND, 'next.config.js')) as {
      turbopack?: { root?: string }
      outputFileTracingRoot?: string
    }
    expect(typeof config, 'next.config.js exports an object, so its roots are the ones Next reads').toBe('object')
    const roots = { 'turbopack.root': config.turbopack?.root, outputFileTracingRoot: config.outputFileTracingRoot }
    for (const [name, root] of Object.entries(roots)) {
      const resolved = root === undefined ? FRONTEND : path.resolve(FRONTEND, root)
      expect(resolved, `${name} is ${root}: copy a file the build needs under frontend/ and hold it to its source with a spec, as lib/publicEmailAddresses.json is`).toBe(FRONTEND)
    }
  })
})
