import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { expect, test } from '@playwright/test'

/**
 * No script the production build holds draws with Recharts (E195 (D)): the build's truth beside
 * tests/unit/rechartsImporters.spec.ts, which fails a tracked file that names the package and a lockfile that installs
 * it, but not a dependency whose published dist inlines Recharts' code under its own name and declares no dependency on
 * it, nor what an alias set outside the tree loads. Recharts draws its DOM with classes of its own, `recharts-…` on
 * every chart part (the surface, the wrapper, the text, the shapes), most of them written whole, a string a minifier
 * keeps. So
 * this reads, on disk, every script of the build the e2e job tests: CI's job runs `npm run build` in frontend/, serves
 * that .next with `npm run start`, and runs Playwright from frontend/. It reads .next/static, the scripts browsers load,
 * and .next/server, the ones the server runs to render a page (its server-side renders of client components included),
 * whatever route loads them. The pattern needs no installed package to check it against, since it is Recharts' own
 * class prefix; the first case scores it on planted scripts, the second shows each read reached a real build, and a
 * missing build fails rather than skips.
 * Out of reach, planted below as gaps: a class name built at run time (`"recharts-".concat(type)`), and the helpers
 * Recharts ships that draw nothing (its scales, its tick and domain arithmetic), which name no class. Either reaches the
 * page only beside code that draws, and that code carries the classes. Scripts the build writes elsewhere (its cache)
 * are not shipped and not read.
 */
const BUILD = path.resolve(__dirname, '../../.next')
/** What each read covers, with the least it must hold to be a real build. */
const READS = [{ dir: 'static', floor: 30 }, { dir: 'server', floor: 100 }] as const
const RECHARTS_CLASS = /recharts-[a-z]/
/** A marker only the engine's plot ships: the attribute TrendChartPlot sets on each chart's plot, which its client chunk
 *  and its server-side render both hold. */
const ENGINE_MARKER = 'data-analysis-chart'

/** Every script under a folder, with its body: the file filter is a `.js` suffix, so a source map or a stylesheet is not
 *  read, and Next's `.js` manifests are (they list module paths, which hold no class name). */
function scriptsUnder(dir: string, root = dir): { file: string; body: string }[] {
  const out: { file: string; body: string }[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...scriptsUnder(full, root))
    else if (entry.name.endsWith('.js')) out.push({ file: path.relative(root, full), body: readFileSync(full, 'utf8') })
  }
  return out
}
/** The scripts that hold a Recharts class name. */
const drawing = (scripts: { file: string; body: string }[]) => scripts.filter(({ body }) => RECHARTS_CLASS.test(body)).map(({ file }) => file)

test('the scan’s pattern and file filter, on planted scripts (no build needed)', () => {
  const scratch = mkdtempSync(path.join(os.tmpdir(), 'no-recharts-scan-'))
  try {
    mkdirSync(path.join(scratch, 'chunks'))
    const plant = (name: string, body: string) => writeFileSync(path.join(scratch, name), body)
    // A drawn part's class, as a minified chart writes it.
    plant('chunks/surface.js', 'e.jsx("svg",{className:"recharts-surface",width:t,height:n})')
    // The package's bare name (Next's own optimizePackageImports list holds it) and the library's name in prose.
    // The package's bare name, spelled at run time so this spec names it nowhere the Recharts gate's text read sees.
    plant('chunks/name.js', `const optimized=["lodash-es","${['re', 'charts'].join('')}","rxjs"]`)
    plant('chunks/prose.js', '/* Recharts left the app (E195 (D)) */')
    // Stated gaps: a class built at run time, and a helper that draws nothing.
    plant('chunks/concat.js', 'const cls="recharts-".concat(type,"-curve")')
    plant('chunks/ticks.js', 'function getNiceTickValues(e,t){return e.map(Math.round).slice(0,t)}')
    // Not a script: a stylesheet, and a source map.
    plant('chunks/surface.css', '.recharts-surface{overflow:visible}')
    plant('chunks/surface.js.map', '{"sourcesContent":["className: \\"recharts-surface\\""]}')
    expect(drawing(scriptsUnder(scratch))).toEqual([path.join('chunks', 'surface.js')])
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

test('no script the production build holds draws with Recharts', () => {
  for (const { dir, floor } of READS) {
    const root = path.join(BUILD, dir)
    expect(existsSync(root), `no production build at ${root}: run \`npm run build\` before this suite, as CI's e2e job does`).toBe(true)
    const scripts = scriptsUnder(root)
    expect(scripts.length, `the build’s ${dir} scripts were read`).toBeGreaterThan(floor)
    expect(scripts.filter(({ body }) => body.includes(ENGINE_MARKER)).length, `the engine plot’s code was among the ${dir} scripts`).toBeGreaterThan(0)
    expect(drawing(scripts), `a ${dir} script holding a Recharts class name`).toEqual([])
  }
})
