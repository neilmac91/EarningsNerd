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

/** Every package name used as an override target, at any nesting depth. */
const overrideTargets = (overrides: unknown): Set<string> => {
  const names = new Set<string>()
  const walk = (node: unknown): void => {
    if (!node || typeof node !== 'object') return
    for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
      // npm's nested form allows a "." key meaning "the parent itself"; it names no new package.
      if (key !== '.') names.add(key)
      walk(value)
    }
  }
  walk(overrides)
  return names
}

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
): { backward: Backward[]; forward: Backward[] } => {
  const targets = overrideTargets(pkg.overrides)
  const backward: Backward[] = []
  const forward: Backward[] = []

  for (const [dependent, node] of Object.entries(lock.packages)) {
    if (node.link) continue
    const declared: Array<[string, string]> = [
      ...Object.entries(node.dependencies ?? {}),
      // Optional peers are allowed to be absent or mismatched; they are not a promise.
      ...Object.entries(node.peerDependencies ?? {}).filter(
        ([name]) => !node.peerDependenciesMeta?.[name]?.optional,
      ),
    ]

    for (const [name, range] of declared) {
      if (!targets.has(name)) continue
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

  return { backward, forward }
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
  const { backward, forward } = scanOverrides(pkg, lock)

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

  it('is actually scanning a tree that contains overrides', () => {
    // Without this the first assertion passes vacuously the moment the overrides block is emptied
    // or a rename makes every target name miss. Forward overrides are the deliberate kind, and
    // this repo has several, so their presence proves the scan reached real data.
    expect(
      forward.length,
      'No forward override found at all. Either the overrides block is empty or the scan is no ' +
        'longer matching the lockfile — in both cases the backward assertion above proves nothing.',
    ).toBeGreaterThan(0)
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
})
