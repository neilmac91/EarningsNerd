/* =============================================================================
   designTokenParity.spec.ts — guardrail (v3, DS-15)
   -----------------------------------------------------------------------------
   The sanctioned JS color mirrors (ui/Chart.tsx, lib/financialTone.directionHex,
   features/analysis/lib/chartExport.ts, features/analysis/lib/charts/theme.ts)
   and the motion mirror (lib/motion.ts) must stay value-identical to the token
   sources (tailwind.config.js + globals.css :root). Nothing fails visibly when
   one drifts — this spec does. chart-theme.spec.ts ties each charts/theme.ts
   field to its own named token as well.
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
  'features/analysis/lib/charts/theme.ts',
  // OS-facing theme colors (PWA manifest, <meta theme-color>): hex-exempt in eslint, so checked here.
  'app/manifest.ts',
  'app/layout.tsx',
]

/** The trend-chart spec renderer's own pairs (tailwind.config.js, E194), its own until E195's token fold names them. */
const RENDERER_PAIRS = ['s1', 's2', 's3', 's4', 's5', 's6', 'tick', 'value', 'gridline', 'review']
const RENDERER_MIRROR = 'features/analysis/lib/charts/theme.ts'

describe('JS color mirrors stay token-true', () => {
  const tokens = collect(config.theme.extend.boxShadow, collect(config.theme.extend.colors, new Set<string>()))
  // Plain white/black are legal literals (export canvas ground, on-fill ink).
  tokens.add('#ffffff')
  tokens.add('#000000')
  // The hexes only the renderer's pairs hold: its new dark series and inks, which wait for the founder's F66 decision.
  const { chart, ...others } = config.theme.extend.colors
  const elsewhere = collect(config.theme.extend.boxShadow, collect({ ...others, chart: Object.fromEntries(Object.entries(chart).filter(([key]) => !RENDERER_PAIRS.includes(key))) }, new Set<string>()))
  const rendererOnly = [...collect(RENDERER_PAIRS.map((key) => chart[key]), new Set<string>())].filter((hex) => !elsewhere.has(hex))

  for (const file of MIRRORS) {
    it(`${file} uses only config token hexes`, () => {
      const hexes = [...new Set((stripComments(read(file)).match(HEX) ?? []).map((h) => h.toLowerCase()))]
      expect(hexes.filter((h) => !tokens.has(h))).toEqual([])
      // Only the renderer's own mirror takes its pairs' new values: a production mirror that did (Chart.tsx's dark
      // labels or series) would ship them before F66, and every hex would still be a token.
      if (file !== RENDERER_MIRROR) expect(hexes.filter((h) => rendererOnly.includes(h)), 'the spec renderer’s own hexes, before F66 (E195 folds them in)').toEqual([])
    })
  }

  it('reads the renderer’s own hexes', () => {
    expect(RENDERER_PAIRS.every((key) => key in chart)).toBe(true)
    expect(rendererOnly).toEqual(expect.arrayContaining(['#62b2a6', '#b8bec7', '#dcd9d0', '#525c6b', '#fbbf24']))
    expect(MIRRORS).toContain(RENDERER_MIRROR)
  })
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
