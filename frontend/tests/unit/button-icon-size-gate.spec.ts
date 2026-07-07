import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Gate for the icon-button "crushed glyph" bug (AAPL field test): `cx` does NOT tailwind-merge,
 * so a `px-0` className override on a Button whose size already sets `px-3` resolves by
 * STYLESHEET order — px-3 won, leaving a 6px content box that squeezed 20px icons to slivers.
 * Icon-only buttons use the first-class `size="icon-sm"` (components/ui/Button.tsx) instead of
 * fighting the size's padding. This spec bans the losing pattern app-wide; if a genuinely
 * non-Button `px-0` ever appears, allowlist that file here explicitly.
 */

const ROOTS = ['app', 'components', 'features', 'lib']
const ALLOWLIST = new Set<string>([])

function* tsxFiles(dir: string): Generator<string> {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry)
    if (statSync(path).isDirectory()) {
      if (entry === 'node_modules') continue
      yield* tsxFiles(path)
    } else if (/\.tsx?$/.test(entry)) {
      yield path
    }
  }
}

describe('button icon-size gate', () => {
  it('no className carries px-0 (use size="icon-sm" for icon-only buttons)', () => {
    const offenders: string[] = []
    for (const root of ROOTS) {
      for (const file of tsxFiles(join(process.cwd(), root))) {
        const rel = file.slice(process.cwd().length + 1)
        if (ALLOWLIST.has(rel)) continue
        if (/\bpx-0\b/.test(readFileSync(file, 'utf-8'))) offenders.push(rel)
      }
    }
    expect(offenders).toEqual([])
  })
})
