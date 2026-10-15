import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * An allowlist or residue cap is an equality, never a ceiling (lessons/test-allowlist-caps-are-equalities.md;
 * CLAUDE.md rule 12). `expect(entries).toBeLessThanOrEqual(MAX)` lets a shrink leave the cap where it was, after
 * which a later entry fits under it with no change to the cap line and the gate never refuses the growth;
 * `toBe(MAX)` makes every shrink lower the cap in the same commit and every addition raise it, in review.
 *
 * The scan reads every unit spec git tracks (no suffix allow-list) through the TypeScript AST and reports each
 * `toBeLessThanOrEqual(...)` whose one argument is a named constant: an identifier in CONSTANT_CASE, or one
 * property of one (`MAX_PINNED.files`). A literal (a pixel budget, a count of calls) and an expression are not
 * read as a cap, and neither is `toBeLessThan`, a strict bound that is not the cap idiom; this header says so
 * rather than claiming more. CEILINGS lists the sites still written as ceilings, by file with the count and why:
 * E59 converts each list cap to an equality after the brand series lands (every file below is edited by one of
 * its PRs), and a value ceiling that is not a list cap (a z-index) keeps its line with that reason. Shrink-only:
 * the totals equal CEILINGS_MAX, lowered in the same commit as a line, and a line whose sites left fails.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const CONSTANT = /^[A-Z][A-Z0-9_]*$/

const CEILINGS: Record<string, { count: number; why: string }> = {
  'tests/unit/bottomChromeLadder.spec.ts': {
    count: 6,
    why: 'PINNED_LIMITS.files and .sites, STICKY_LIMITS.files and INLINE_FIXED_TOTAL are list caps (E59); PINNED_LIMITS.maxZ and STICKY_LIMITS.maxZ bound a z-index, a value ceiling that keeps its form',
  },
  'tests/unit/busyControlsStayFocusable.spec.ts': {
    count: 8,
    why: "the four allowlists' file and site caps (E59); #1301 and #1295 lower the retry-label pair and make them equalities",
  },
  'tests/unit/dialogAllowlist.spec.ts': { count: 1, why: 'MAX_ALLOWLIST_SIZE, a list cap (E59)' },
  'tests/unit/fullPageSpinnerGate.spec.ts': { count: 1, why: 'MAX_ALLOWLIST_SIZE, a list cap (E59)' },
  'tests/unit/inputClassesNoOverrides.spec.tsx': { count: 2, why: 'MAX_PINNED.files and .findings, list caps (E59)' },
  'tests/unit/rawFetchAllowlist.spec.ts': { count: 1, why: 'MAX_ALLOWLIST_SIZE, a list cap (E59)' },
  'tests/unit/spinnerGateHoldsFailure.spec.ts': { count: 2, why: 'MAX_ALLOWLIST_SIZE and MAX_PINNED_SITES, list caps (E59)' },
}
/** Equal to the list, never above it: lower both with the list in the same commit. */
const CEILINGS_MAX = { files: 7, sites: 21 }

/** The named constant a cap argument reads, or null when the argument is a literal or an expression. */
function namedConstant(arg: ts.Expression): string | null {
  if (ts.isIdentifier(arg)) return CONSTANT.test(arg.text) ? arg.text : null
  if (ts.isPropertyAccessExpression(arg) && ts.isIdentifier(arg.expression) && CONSTANT.test(arg.expression.text)) {
    return `${arg.expression.text}.${arg.name.text}`
  }
  return null
}

/** Every `toBeLessThanOrEqual(NAMED_CONSTANT)` in one source, as `file:line toBeLessThanOrEqual(NAME)`. */
export function ceilingSites(source: string, file = 'probe.spec.ts'): string[] {
  const kind = file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
  const out: string[] = []
  const visit = (node: ts.Node): void => {
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === 'toBeLessThanOrEqual' &&
      node.arguments.length === 1
    ) {
      const cap = namedConstant(node.arguments[0])
      if (cap) out.push(`${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} toBeLessThanOrEqual(${cap})`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

const SPECS = execFileSync('git', ['ls-files', 'tests/unit'], { cwd: FRONTEND, encoding: 'utf8' })
  .split('\n')
  .filter((rel) => /\.spec\.tsx?$/.test(rel))

describe('allowlist caps are equalities (lessons/test-allowlist-caps-are-equalities.md)', () => {
  const found = new Map<string, string[]>()
  for (const rel of SPECS) {
    const sites = ceilingSites(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel)
    if (sites.length) found.set(rel, sites)
  }

  it('reads every tracked unit spec, the listed ones among them', () => {
    expect(SPECS.length).toBeGreaterThan(100)
    for (const rel of Object.keys(CEILINGS)) expect(SPECS, rel).toContain(rel)
  })

  it('no unit spec caps a list with toBeLessThanOrEqual outside CEILINGS, and every listed count is current', () => {
    const offenders: string[] = []
    for (const [rel, sites] of found) {
      const listed = CEILINGS[rel]
      if (!listed) offenders.push(...sites)
      else if (sites.length !== listed.count) {
        offenders.push(`${rel}: ${sites.length} ceilings, CEILINGS lists ${listed.count}: ${sites.join(' | ')}`)
      }
    }
    expect(offenders, 'a cap on a list is an equality: expect(count).toBe(MAX), and the shrink lowers MAX in the same commit').toEqual([])
  })

  it('CEILINGS is shrink-only: no stale line, the totals equal CEILINGS_MAX, and every line says why', () => {
    const stale = Object.keys(CEILINGS).filter((rel) => !found.has(rel))
    expect(stale, 'a listed file with no ceiling left: delete its line and lower CEILINGS_MAX').toEqual([])
    expect(Object.keys(CEILINGS).length, 'CEILINGS_MAX.files equals the files in CEILINGS: lower it with the list, never raise it').toBe(
      CEILINGS_MAX.files,
    )
    const sites = Object.values(CEILINGS).reduce((n, { count }) => n + count, 0)
    expect(sites, 'CEILINGS_MAX.sites equals the sites in CEILINGS: lower it with the list, never raise it').toBe(CEILINGS_MAX.sites)
    for (const [rel, { why }] of Object.entries(CEILINGS)) expect(why.length, rel).toBeGreaterThan(20)
  })

  it('self-check: the reader flags a named cap and leaves a literal, an expression, a strict bound and an equality alone', () => {
    const flagged = [
      'expect(Object.keys(ALLOW).length).toBeLessThanOrEqual(MAX_ALLOWLIST_SIZE)',
      'expect(pinned).toBeLessThanOrEqual(MAX_PINNED.sites)',
      "expect(n, 'why').toBeLessThanOrEqual(CAP)",
    ]
    for (const source of flagged) expect(ceilingSites(source), source).toHaveLength(1)
    const clean = [
      'expect(box.right).toBeLessThanOrEqual(300)',
      'expect(headline.length).toBeLessThanOrEqual(MAX_CHARS + ELLIPSIS.length)',
      'expect(z).toBeLessThan(WORKSPACE_Z)',
      'expect(Object.keys(ALLOW).length).toBe(MAX_ALLOWLIST_SIZE)',
      'expect(calls).toBeLessThanOrEqual(limits.max)',
    ]
    for (const source of clean) expect(ceilingSites(source), source).toEqual([])
    expect(ceilingSites('const a = 1\nexpect(a).toBeLessThanOrEqual(MAX)\n', 'p.spec.ts')).toEqual(['p.spec.ts:2 toBeLessThanOrEqual(MAX)'])
  })
})
