import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Structural gate for the one-test-home rule (CLAUDE.md rule 12: rules become gates).
 *
 * CLAUDE.md: "`backend/tests/{unit,integration,smoke,performance}` … and `frontend/tests/{unit,e2e}`.
 * NO other test roots — a test outside these does not run in CI." That was prose only until now.
 * lessons/test-one-test-home.md records the cost: Wave 0 found an orphaned repo-root `/tests/`
 * holding the ONLY coverage of security headers and the Stripe price allowlist. CI never ran it, so
 * "tests exist" meant nothing and nobody noticed — a green suite cannot tell you about a file it
 * never collected. lessons/arch-structural-gates-over-prose-rules.md names exactly this shape as
 * the fix: "a tiny spec asserting a directory listing … equals a checked-in allowlist".
 *
 * This lives in the frontend suite because the invariant is repo-level, not stack-level, and the
 * frontend suite already hosts cross-cutting scanners (nodeVersionLockstep.spec.ts reads
 * ../.github/workflows). Keeping it here also means a repo-hygiene gate never drags the backend
 * deploy along with it.
 *
 * Two distinct failures are caught, and the message says which:
 *   1. A test file outside `backend/tests/` or `frontend/tests/` — never collected by anything.
 *      `backend/pytest.ini` sets `testpaths = tests`; `vitest.config.mts` includes
 *      `tests/unit/**​/*.spec.ts?(x)`; `playwright.config` sets `testDir: ./tests/e2e`.
 *   2. A test file inside one of those trees but outside the six documented homes — it may still
 *      run (pytest collects all of `backend/tests/`, helper dirs included) but it is not where
 *      CLAUDE.md says tests live, which is how the orphan above started.
 *
 * Naming counts too: vitest's include matches `.spec.` ONLY, so a `.test.ts` under
 * frontend/tests/unit is collected by nothing at all despite sitting in the right folder.
 */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')

const BACKEND_TEST_HOMES = [
  'backend/tests/unit',
  'backend/tests/integration',
  'backend/tests/smoke',
  'backend/tests/performance',
] as const
const FRONTEND_TEST_HOMES = ['frontend/tests/unit', 'frontend/tests/e2e'] as const

/** Collected-by-nothing boundaries: the roots the runners are actually pointed at. */
const COLLECTED_ROOTS = ['backend/tests', 'frontend/tests'] as const

const SKIP_DIRS = new Set([
  'node_modules', '.git', '.next', '.venv', 'venv', '__pycache__', 'dist', 'build',
  'coverage', 'playwright-report', 'test-results', '.turbo', '.vercel', '.pytest_cache',
])

const PYTHON_TEST = /^(test_.*\.py|.*_test\.py)$/
const JS_TEST = /\.(spec|test)\.(ts|tsx|js|jsx|mts|cts|mjs|cjs)$/

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) walk(full, acc)
    else acc.push(path.relative(repoRoot, full).split(path.sep).join('/'))
  }
  return acc
}

const allFiles = walk(repoRoot)
const under = (file: string, roots: readonly string[]) => roots.some((r) => file.startsWith(`${r}/`))

describe('tests live in exactly one home per stack', () => {
  const pythonTests = allFiles.filter((f) => PYTHON_TEST.test(path.basename(f)))
  const jsTests = allFiles.filter((f) => JS_TEST.test(path.basename(f)))

  it('finds the test files it is meant to be scanning', () => {
    // A scanner that silently matches nothing passes forever. Anchor it to reality so a broken
    // walk or over-eager skip list fails here rather than going quietly green.
    expect(pythonTests.length).toBeGreaterThan(100)
    expect(jsTests.length).toBeGreaterThan(50)
  })

  it('has no Python test file outside the documented backend homes', () => {
    const strays = pythonTests.filter((f) => !under(f, BACKEND_TEST_HOMES))
    expect(strays, strays.map((f) => `${f} — ${under(f, COLLECTED_ROOTS)
      ? 'inside backend/tests but not one of the four documented homes'
      : 'outside backend/tests: pytest testpaths never collects it'}`).join('\n')).toEqual([])
  })

  it('has no JS/TS test file outside the documented frontend homes', () => {
    const strays = jsTests.filter((f) => !under(f, FRONTEND_TEST_HOMES))
    expect(strays, strays.map((f) => `${f} — ${under(f, COLLECTED_ROOTS)
      ? 'inside frontend/tests but not tests/unit or tests/e2e'
      : 'outside frontend/tests: neither vitest nor playwright collects it'}`).join('\n')).toEqual([])
  })

  it('names every frontend unit test .spec, which is all vitest collects', () => {
    const unitDir = 'frontend/tests/unit/'
    const uncollected = jsTests.filter((f) => f.startsWith(unitDir) && !/\.spec\.(ts|tsx)$/.test(f))
    expect(uncollected, `vitest.config.mts includes tests/unit/**/*.spec.ts?(x) only, so these are in the right folder but run nowhere:\n${uncollected.join('\n')}`).toEqual([])
  })

  it('still matches the homes CLAUDE.md documents', () => {
    // Lockstep: moving a home in the doc without moving it here (or vice versa) fails.
    const claude = readFileSync(path.join(repoRoot, 'CLAUDE.md'), 'utf8')
    expect(claude).toContain('backend/tests/{unit,integration,smoke,performance}')
    expect(claude).toContain('frontend/tests/{unit,e2e}')
    expect(claude).toContain('NO other test roots')
  })
})
