/* =============================================================================
   designTokenParity.spec.ts — guardrail (v3, DS-15)
   -----------------------------------------------------------------------------
   The sanctioned JS color mirrors (ui/Chart.tsx, lib/financialTone.directionHex,
   features/analysis/lib/chartExport.ts) and the motion mirror (lib/motion.ts)
   must stay value-identical to the token sources (tailwind.config.js +
   globals.css :root). Nothing fails visibly when one drifts — this spec does.
============================================================================= */

import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { MOTION } from '../../lib/motion'
const config = require('../../tailwind.config.js')

const ROOT = path.join(__dirname, '../..')
const HEX = /#[0-9a-fA-F]{6}\b/g
const read = (p: string) => fs.readFileSync(path.join(ROOT, p), 'utf8')

/** Every 6-digit hex reachable in the config's color + shadow token trees. */
function collect(value: unknown, out: Set<string>): Set<string> {
  if (typeof value === 'string') for (const h of value.match(HEX) ?? []) out.add(h.toLowerCase())
  else if (value && typeof value === 'object') for (const v of Object.values(value)) collect(v, out)
  return out
}

/** Strip comments so documented-but-unused values (e.g. "was #D99E4A") don't count. */
function stripComments(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '')
}

const MIRRORS = [
  'components/ui/Chart.tsx',
  'lib/financialTone.ts',
  'features/analysis/lib/chartExport.ts',
  // OS-facing theme colors (PWA manifest, <meta theme-color>): hex-exempt in eslint, so checked here.
  'app/manifest.ts',
  'app/layout.tsx',
]

describe('JS color mirrors stay token-true', () => {
  const tokens = collect(config.theme.extend.boxShadow, collect(config.theme.extend.colors, new Set<string>()))
  // Plain white/black are legal literals (export canvas ground, on-fill ink).
  tokens.add('#ffffff')
  tokens.add('#000000')

  for (const file of MIRRORS) {
    it(`${file} uses only config token hexes`, () => {
      const hexes = [...new Set((stripComments(read(file)).match(HEX) ?? []).map((h) => h.toLowerCase()))]
      expect(hexes.filter((h) => !tokens.has(h))).toEqual([])
    })
  }
})

describe('lib/motion.ts mirrors the globals.css motion tokens', () => {
  it('MOTION equals the --duration-* values', () => {
    const css = read('app/globals.css')
    const ms = Object.fromEntries(
      [...css.matchAll(/--duration-(\w+):\s*(\d+)ms/g)].map((m) => [m[1], Number(m[2])]),
    )
    expect(MOTION).toEqual({ fast: ms.fast, base: ms.base, slow: ms.slow, ambient: ms.ambient })
  })
})
