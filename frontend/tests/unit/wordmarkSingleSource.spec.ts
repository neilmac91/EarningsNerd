/* =============================================================================
   wordmarkSingleSource.spec.ts — guardrail (v3, Q1)
   -----------------------------------------------------------------------------
   components/EarningsNerdLogo.tsx is the ONE source of the two-tone wordmark
   (variant="full" | "wordmark"). Header and AuthShell hand-composed
   `Earnings<em>Nerd</em>` before v3 and drifted in size and tracking; this spec
   fails if any other file renders the italic "Nerd" half by hand.
============================================================================= */

import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const SOURCE = 'components/EarningsNerdLogo.tsx'
const HAND_ROLLED = /<em\b[^>]*>\s*Nerd\s*<\/em>/

function walk(dir: string, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name)) out.push(p)
  }
  return out
}

describe('the wordmark has one source: EarningsNerdLogo', () => {
  it('no other file hand-composes the italic "Nerd"', () => {
    const offenders: string[] = []
    for (const dir of SCAN_DIRS) {
      for (const file of walk(path.join(ROOT, dir))) {
        const rel = path.relative(ROOT, file).split(path.sep).join('/')
        if (rel !== SOURCE && HAND_ROLLED.test(fs.readFileSync(file, 'utf8'))) offenders.push(rel)
      }
    }
    expect(offenders, 'render <EarningsNerdLogo variant="wordmark" | "full"> instead').toEqual([])
  })

  it('the source still renders it (the pattern above stays meaningful)', () => {
    expect(fs.readFileSync(path.join(ROOT, SOURCE), 'utf8')).toMatch(HAND_ROLLED)
  })
})
