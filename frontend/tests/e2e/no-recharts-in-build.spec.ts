import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

/**
 * No script the production build ships holds a Recharts class name (E195 (D)): the build's truth beside
 * tests/unit/rechartsImporters.spec.ts, which fails a tracked file that names the package and a lockfile that installs
 * it, but not a dependency whose published dist inlines Recharts' code under its own name and declares no dependency on
 * it, nor what an alias set outside the tree loads. Code that arrives those ways ships Recharts' DOM, and every chart
 * part Recharts draws carries a `recharts-…` class (the surface, the wrapper, the text, the shapes), a string a minifier
 * keeps. So this reads, on disk, every script of the build the e2e job tests, whatever route loads it: CI's e2e job
 * runs `npm run build` in frontend/, serves that .next with `npm run start`, and runs Playwright from frontend/. The
 * pattern needs no installed package to check it against, since it is Recharts' own class prefix; the positive controls
 * show the read reached a real build, and a missing build fails rather than skips.
 */
const BUILD = path.resolve(__dirname, '../../.next/static')
const RECHARTS_CLASS = /recharts-[a-z]/
/** A marker only the engine's plot ships: the attribute TrendChartPlot sets on each chart's plot. */
const ENGINE_MARKER = 'data-analysis-chart'

function scriptsUnder(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...scriptsUnder(full))
    else if (entry.name.endsWith('.js')) out.push(full)
  }
  return out
}

test('no script the production build ships holds a Recharts class name', () => {
  expect(existsSync(BUILD), `no production build at ${BUILD}: run \`npm run build\` before this suite, as CI's e2e job does`).toBe(true)
  const shipped = scriptsUnder(BUILD).map((file) => ({ file: path.relative(BUILD, file), body: readFileSync(file, 'utf8') }))
  expect(shipped.length, 'the build’s scripts were read').toBeGreaterThan(30)
  expect(shipped.filter(({ body }) => body.includes(ENGINE_MARKER)).length, 'the engine plot’s chunk was among them').toBeGreaterThan(0)
  expect(shipped.filter(({ body }) => RECHARTS_CLASS.test(body)).map(({ file }) => file), 'a shipped script holding a Recharts class name').toEqual([])
})
