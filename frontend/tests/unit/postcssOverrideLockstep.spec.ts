import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Structural gate for the postcss override pin (CLAUDE.md rule 12: rules become gates).
 *
 * `overrides.postcss` used to be the literal string "$postcss" — npm's self-referencing form, which
 * means "force every transitive postcss to whatever the direct dependency resolves to", and which
 * therefore could not drift by construction. The vitest 5 upgrade had to replace it with a real
 * range: npm 10.9.7 fails to resolve a `$name` reference while walking vitest 5's expanded peer set
 * and aborts the whole install with `Unable to resolve reference $postcss`. Measured — vitest 5
 * alone reproduces it on an otherwise untouched tree, and substituting the literal is what clears it.
 *
 * That substitution traded a guarantee for a duplicate. The two values must now be kept equal by
 * hand, which is exactly the kind of pairing that rots, so this asserts them equal instead. If npm
 * fixes the `$name` resolution, restoring "$postcss" is the better end state and this gate should be
 * deleted in the same change.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const pkg = JSON.parse(readFileSync(path.join(frontendDir, 'package.json'), 'utf8')) as {
  dependencies: Record<string, string>
  overrides: Record<string, unknown>
}

describe('postcss override stays in lockstep with the direct dependency', () => {
  it('pins the same range in both places', () => {
    expect(
      pkg.overrides.postcss,
      'overrides.postcss must equal dependencies.postcss — they are two copies of one decision, ' +
        'and a transitive postcss forced to a different version than the one the app builds with ' +
        'is precisely what the override exists to prevent.',
    ).toBe(pkg.dependencies.postcss)
  })

  it('is a real range, not the $postcss reference npm cannot resolve here', () => {
    // If someone restores "$postcss" without also proving `npm install` resolves, the install
    // breaks for everyone rather than for them. Fail here, where the message explains why.
    expect(
      String(pkg.overrides.postcss).startsWith('$'),
      'overrides.postcss is back to a $name reference; npm 10.9.7 cannot resolve one through ' +
        "vitest 5's peer set. Verify `npm install` from a clean node_modules before restoring it.",
    ).toBe(false)
  })
})
