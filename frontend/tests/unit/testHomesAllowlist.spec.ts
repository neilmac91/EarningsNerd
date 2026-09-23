import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
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

const PYTHON_TEST = /^(test_.*\.py|.*_test\.py)$/
const JS_TEST = /\.(spec|test)\.(ts|tsx|js|jsx|mts|cts|mjs|cjs)$/

/**
 * The one sanctioned exemption: a hash-sealed evidence fixture. The Fable judging packages under
 * `tasks/` carry the sealed add-on's `tests/test_e8_addon.py` byte-identical, because the
 * package's `code-sha256.json` pins that exact path and the adapter refuses to run if the file
 * set changes. It is an offline proof the operator runs from the package (see its
 * verification.md), not a repo test, and it cannot be moved into backend/tests without breaking
 * the seal. The exemption is mechanical, not a name list: the file must be listed, at its
 * package-relative path, in a `code-sha256.json` in an ancestor directory, and the recorded hash
 * must match the bytes on disk. An orphan test that merely sits beside such a manifest still fails.
 */
const SEALED_MANIFEST = 'code-sha256.json'
const isSealedFixture = (file: string): boolean => {
  let dir = path.dirname(file)
  while (dir && dir !== '.') {
    const manifestPath = path.join(repoRoot, dir, SEALED_MANIFEST)
    if (existsSync(manifestPath)) {
      const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as Record<string, string>
      const rel = path.relative(dir, file).split(path.sep).join('/')
      const pinned = manifest[rel]
      if (typeof pinned !== 'string') return false
      const actual = createHash('sha256').update(readFileSync(path.join(repoRoot, file))).digest('hex')
      return actual === pinned
    }
    dir = path.dirname(dir)
  }
  return false
}

/** The repo's TRACKED files, straight from git, rather than a filesystem walk past a hand-written
 *  skip list. The skip list was itself the narrowing defect this gate exists to catch: it excluded
 *  every directory named `build`, which is NOT gitignored here, so a committed
 *  `frontend/build/orphan.spec.mjs` was invisible while `node_modules` and `.next` were only
 *  skipped by coincidence of also being gitignored. Git knows exactly which files are in the repo;
 *  guessing at that list is how the orphan gets back in. */
const allFiles = execFileSync('git', ['ls-files', '-z'], {
  cwd: repoRoot,
  encoding: 'utf8',
  maxBuffer: 64 * 1024 * 1024,
})
  .split('\0')
  .filter(Boolean)
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
    const strays = pythonTests.filter((f) => !under(f, BACKEND_TEST_HOMES) && !isSealedFixture(f))
    expect(strays, strays.map((f) => `${f} — ${under(f, COLLECTED_ROOTS)
      ? 'inside backend/tests but not one of the four documented homes'
      : 'outside backend/tests: pytest testpaths never collects it'}`).join('\n')).toEqual([])
  })

  it('exempts a sealed fixture only when its manifest hash matches the file', () => {
    const sealed = pythonTests.filter((f) => !under(f, BACKEND_TEST_HOMES) && isSealedFixture(f))
    // Anchor the exemption to the one package that uses it, so a new sealed fixture is a
    // deliberate edit here rather than a silent widening.
    expect(sealed).toEqual(['tasks/fable-e8-repin-2026-09-22/tests/test_e8_addon.py'])
    // A file the manifest does not list is not exempt, even beside the manifest.
    expect(isSealedFixture('tasks/fable-e8-repin-2026-09-22/tests/test_not_pinned.py')).toBe(false)
    // A listed file whose bytes differ from the pinned hash is not exempt either.
    const manifest = JSON.parse(readFileSync(path.join(repoRoot, 'tasks/fable-e8-repin-2026-09-22/code-sha256.json'), 'utf8')) as Record<string, string>
    const onDisk = createHash('sha256').update(readFileSync(path.join(repoRoot, 'tasks/fable-e8-repin-2026-09-22/tests/test_e8_addon.py'))).digest('hex')
    expect(manifest['tests/test_e8_addon.py']).toBe(onDisk)
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
