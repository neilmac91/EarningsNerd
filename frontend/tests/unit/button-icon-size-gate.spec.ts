import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Gate for the icon-button "crushed glyph" bug (AAPL field test): `cx` does NOT tailwind-merge,
 * so a `px-0` className override on a Button whose size already sets `px-3` resolves by
 * STYLESHEET order — px-3 won, leaving a 6px content box that squeezed 20px icons to slivers.
 * Icon-only buttons use the first-class `size="icon-sm"` (components/ui/Button.tsx) instead of
 * fighting the size's padding.
 *
 * DELIBERATELY a blanket app-wide ban with an explicit allowlist (the componentsAllowlist.spec
 * pattern), not a Button-scoped regex: multi-line JSX props and wrapper components that forward
 * className into Button (exactly what PanelControl was) defeat element-scoped matching, and a
 * missing ROOTS directory should fail LOUDLY (a rename must update the gate, not silently
 * shrink its coverage). If a genuinely non-Button `px-0` ever appears, allowlist its exact
 * class in that file (ALLOWLIST below), so any other `px-0` in the file still fails.
 */

// Anchored to this file, not process.cwd() — the suite must pass no matter where vitest is
// launched from (the componentsAllowlist.spec.ts anchoring recipe).
const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features', 'lib']
// File → the one non-Button px-0 class it may carry: once, as a whole class (no variant or
// modifier before it), in a file that renders no Button. An entry that stops holding fails.
const ALLOWLIST = new Map<string, string>([
  // The Trace to Source demo's claim box, a <div>, gives up its side padding below a 24rem
  // viewport (E143); the file's one button is the source chip, whose class is
  // sourceTraceChipClass(), not a sized Button.
  ['features/marketing/components/TraceToSourceDemo.tsx', '[@media(max-width:24rem)]:px-0'],
])
// The allowlisted class as a whole token of a class string; the `g` flag counts every copy.
const wholeClass = (cls: string, flags = '') =>
  new RegExp(`(?<=^|[\\s'"\`])${cls.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=$|[\\s'"\`])`, flags)

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
      for (const file of tsxFiles(join(FRONTEND_ROOT, root))) {
        const rel = file.slice(FRONTEND_ROOT.length + 1)
        const allowed = ALLOWLIST.get(rel)
        const text = readFileSync(file, 'utf-8')
        if (/\bpx-0\b/.test(allowed ? text.replace(wholeClass(allowed), '') : text)) offenders.push(rel)
      }
    }
    expect(offenders).toEqual([])
  })

  it('each allowlisted px-0 class is in its file exactly once, as a whole class, in a file with no Button', () => {
    for (const [rel, allowed] of ALLOWLIST) {
      const text = readFileSync(join(FRONTEND_ROOT, rel), 'utf-8')
      expect(text.match(wholeClass(allowed, 'g'))?.length ?? 0, rel).toBe(1)
      expect(text, rel).not.toMatch(/<Button\b/)
    }
  })
})
