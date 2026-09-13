import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import semver from 'semver'
import { describe, expect, it } from 'vitest'

/**
 * Structural gate for stale npm overrides (CLAUDE.md rule 12: rules become gates).
 *
 * An `overrides` entry constrains a package this repo does not itself depend on directly, so its
 * meaning is set by the packages that DO depend on it — and those move without the override line
 * changing. #852 hit this: `overrides.jsdom` forced `undici` to `^7.28.0`. Under jsdom 29, which
 * declared `undici ^7.25.0`, that raised a floor. jsdom 30 declares `undici ^8.9.0`, so the same
 * unchanged line silently became a ceiling and held undici at 7.29.1 — below what jsdom asks for.
 *
 * The invariant is DIRECTIONAL, and that distinction is the whole gate. Overrides exist to push a
 * package FORWARD past what a dependent declares: six of this repo's overrides do exactly that
 * (the `@lhci/cli` security bumps, and `postcss`, which `next` pins to an exact older patch). A
 * gate that flagged every unsatisfied range would flag all six and be useless. Holding a package
 * BACK below a dependent's declared floor is never intentional — that is the stale-ceiling bug.
 *
 * So: for every package named as an override target, the version each dependent actually resolves
 * must not be lower than the floor that dependent declares.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

interface LockNode {
  version?: string
  link?: boolean
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  peerDependenciesMeta?: Record<string, { optional?: boolean }>
}
type LockPackages = Record<string, LockNode>

interface Backward {
  dependent: string
  name: string
  declared: string
  floor: string
  resolved: string
}

/**
 * An override key may carry a version qualifier — npm documents `"undici@^8": "7.29.1"` as valid —
 * and the dependency edges it has to be matched against are named by the bare package. Recording
 * the literal key would mean `targets.has('undici')` never matches and the override is silently
 * never scanned, which is the exact "gate narrower than its rule" failure this file exists to
 * avoid. The last `@` at a non-zero index starts the qualifier; at index 0 it is a scope.
 */
const packageNameOf = (key: string): string => {
  const at = key.lastIndexOf('@')
  return at > 0 ? key.slice(0, at) : key
}

/** Every package name used as an override target, at any nesting depth. */
const overrideTargets = (overrides: unknown): Set<string> => {
  const names = new Set<string>()
  const walk = (node: unknown): void => {
    if (!node || typeof node !== 'object') return
    for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
      // npm's nested form allows a "." key meaning "the parent itself"; it names no new package.
      if (key !== '.') names.add(packageNameOf(key))
      walk(value)
    }
  }
  walk(overrides)
  return names
}

/**
 * Every field that declares a real dependency edge. `devDependencies` appears only on the root
 * node (npm strips it from installed packages) and carrying it matters: `@lhci/cli` is an override
 * target reachable through nothing else, so omitting the field left it entirely unexamined.
 * `optionalDependencies` are genuine edges too — an absent platform-specific package is already
 * tolerated below, where an unresolved or unparseable version is skipped.
 */
const DEPENDENCY_FIELDS = ['dependencies', 'devDependencies', 'optionalDependencies'] as const

/**
 * Node resolution: from `dependent`, look in ./node_modules/<name>, then walk up the nesting
 * chain. Resolving properly matters — a nested copy (js-yaml under @lhci/utils, in this tree) is a
 * different version from the hoisted one, and reading only the hoisted entry would judge the wrong
 * package.
 */
const resolveFrom = (nodes: LockPackages, dependent: string, name: string): LockNode | null => {
  let prefix = dependent
  for (;;) {
    const candidate = prefix ? `${prefix}/node_modules/${name}` : `node_modules/${name}`
    if (nodes[candidate]) return nodes[candidate]
    if (!prefix) return null
    const cut = prefix.lastIndexOf('/node_modules/')
    prefix = cut === -1 ? '' : prefix.slice(0, cut)
  }
}

const scanOverrides = (
  pkg: { overrides?: unknown },
  lock: { packages: LockPackages },
): { backward: Backward[]; forward: Backward[]; unmatched: string[] } => {
  const targets = overrideTargets(pkg.overrides)
  const backward: Backward[] = []
  const forward: Backward[] = []
  const matched = new Set<string>()

  for (const [dependent, node] of Object.entries(lock.packages)) {
    if (node.link) continue
    const declared: Array<[string, string]> = [
      ...DEPENDENCY_FIELDS.flatMap((field) => Object.entries(node[field] ?? {})),
      // Optional peers are allowed to be absent or mismatched; they are not a promise.
      ...Object.entries(node.peerDependencies ?? {}).filter(
        ([name]) => !node.peerDependenciesMeta?.[name]?.optional,
      ),
    ]

    for (const [name, range] of declared) {
      if (!targets.has(name)) continue
      matched.add(name)
      const hit = resolveFrom(lock.packages, dependent, name)
      const resolved = hit?.version
      if (!resolved || !semver.valid(resolved) || !semver.validRange(range)) continue
      const min = semver.minVersion(range)
      if (!min) continue
      if (semver.satisfies(resolved, range)) continue
      const row = {
        dependent: dependent || '(root)',
        name,
        declared: range,
        floor: min.version,
        resolved,
      }
      ;(semver.lt(resolved, min.version) ? backward : forward).push(row)
    }
  }

  return { backward, forward, unmatched: [...targets].filter((t) => !matched.has(t)).sort() }
}

const describeRows = (rows: Backward[]): string =>
  rows
    .map((r) => `  ${r.dependent} declares ${r.name}@${r.declared} but resolves ${r.resolved}`)
    .join('\n')

describe('no override holds a package below what its dependents declare', () => {
  const pkg = JSON.parse(readFileSync(path.join(frontendDir, 'package.json'), 'utf8')) as {
    overrides?: unknown
  }
  const lock = JSON.parse(readFileSync(path.join(frontendDir, 'package-lock.json'), 'utf8')) as {
    packages: LockPackages
  }
  const { backward, unmatched } = scanOverrides(pkg, lock)

  it('has no backward override in the committed lockfile', () => {
    expect(
      backward,
      'An override is holding a package BELOW a floor one of its dependents declares:\n' +
        `${describeRows(backward)}\n\n` +
        'This is the stale-ceiling bug from #852: the override line did not change, the package ' +
        'that constrains it did. Re-read why the override exists — if the reason is gone, delete ' +
        'it rather than bumping it.',
    ).toEqual([])
  })

  it('matches every override target against a real dependency edge', () => {
    // The control this file needs is NOT "at least one forward override survives" — dependency
    // upgrades can legitimately retire every one of them, and a tree with no overrides cannot hold
    // a stale ceiling, so failing there would block correct cleanup (Codex, #853).
    //
    // The failure actually worth catching is an override that EXISTS while the scan silently fails
    // to match it: a version-qualified key, a renamed package, a lockfile shape change. That is
    // vacuous success with real risk behind it, and it is what this asserts.
    expect(
      unmatched,
      'These override targets matched no dependency edge anywhere in the lockfile, so the ' +
        'backward-override assertion never examined them and passes vacuously for each. Either ' +
        'the override is dead and should be deleted, or the scan is failing to match it.',
    ).toEqual([])
  })

  it('catches the #852 stale ceiling it was written for', () => {
    // The historical tree, reduced to the three nodes that carried the bug.
    const historical = {
      packages: {
        '': { dependencies: { jsdom: '^30.0.1' } },
        'node_modules/jsdom': { version: '30.0.1', dependencies: { undici: '^8.9.0' } },
        'node_modules/undici': { version: '7.29.1' },
      } as LockPackages,
    }
    const found = scanOverrides({ overrides: { jsdom: { undici: '^7.28.0' } } }, historical)

    expect(found.backward).toEqual([
      {
        dependent: 'node_modules/jsdom',
        name: 'undici',
        declared: '^8.9.0',
        floor: '8.9.0',
        resolved: '7.29.1',
      },
    ])
  })

  it('still sees the override when its key carries a version qualifier', () => {
    // npm accepts `"undici@^8": "7.29.1"` as an override key. Recording the literal key would put
    // `undici@^8` in the target set while every dependency edge is named `undici`, so the scan
    // would skip the override entirely and report a clean tree (Codex, #853).
    const historical = {
      packages: {
        '': { dependencies: { jsdom: '^30.0.1' } },
        'node_modules/jsdom': { version: '30.0.1', dependencies: { undici: '^8.9.0' } },
        'node_modules/jsdom/node_modules/undici': { version: '7.29.1' },
      } as LockPackages,
    }
    const found = scanOverrides({ overrides: { 'undici@^8': '7.29.1' } }, historical)

    expect(found.backward.map((r) => `${r.name} ${r.floor} -> ${r.resolved}`)).toEqual([
      'undici 8.9.0 -> 7.29.1',
    ])
    expect(found.unmatched, 'a normalised key must count as matched').toEqual([])
  })
})
