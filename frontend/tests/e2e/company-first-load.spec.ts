import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import { BUILD, firstLoadOf, MARKERS, staticScripts } from './fixtures/companyBuild'

/**
 * The trend charts' engine stays out of the company page's first load (E251). The Sector peers card, and the engine with
 * it, loads in a chunk of its own, and only once the peers endpoint answers a cohort (features/peers/components/
 * SectorPeers.tsx), as Financial trends keeps the engine out of the filing page's. A static import of the card, or of the
 * engine by anything the company route loads, would put it back in every company page's first load, which no render
 * test sees, and production answers no cohort until the SIC backfill, so no page there would show it either. So this
 * reads the build the e2e job tests, on disk (fixtures/companyBuild.ts): the company route's first load, every script
 * its client reference manifest names for the route's entries (the root layout, the page and the boundaries it renders
 * under) with the root main files and the polyfills `build-manifest.json` names, and fails any of them that holds the
 * engine's, the plot's or the card's own string. The first case scores the reader on a planted build; the second reads
 * the real one, where each string must stand in some script of the build, so the check reads real code, and the first
 * load must hold at least FLOOR scripts. A missing build fails rather than skips.
 */
const ROUTE = '/company/[ticker]/page'
/** The fewest scripts a real first load of the route holds: the build of 2026-10-31 loads 19. */
const FLOOR = 10

/** The first-load scripts holding a part's string, as "file: part". */
function holding(build: string, files: string[]) {
  const scripts = new Map(staticScripts(build).map(({ file, body }) => [file, body]))
  return files.flatMap((file) => {
    const body = scripts.get(file)
    if (body == null) return [`${file}: named by the manifests, absent from the build`]
    return Object.entries(MARKERS).filter(([, marker]) => body.includes(marker)).map(([part]) => `${file}: ${part}`)
  })
}

test('the reader, on a planted build (no build needed)', () => {
  const scratch = mkdtempSync(path.join(os.tmpdir(), 'company-first-load-'))
  try {
    const plant = (file: string, body: string) => {
      mkdirSync(path.dirname(path.join(scratch, file)), { recursive: true })
      writeFileSync(path.join(scratch, file), body)
    }
    const entry = {
      '[project]/frontend/app/layout': ['static/chunks/layout.js'],
      '[project]/frontend/app/company/[ticker]/page': ['static/chunks/page.js', 'static/chunks/card.js'],
    }
    plant('server/app/company/[ticker]/page_client-reference-manifest.js', [
      'globalThis.__RSC_MANIFEST = globalThis.__RSC_MANIFEST || {};',
      `globalThis.__RSC_MANIFEST["/company/[ticker]/page"] = ${JSON.stringify({ clientModules: {}, entryJSFiles: entry })};`,
      '',
    ].join('\n'))
    plant('build-manifest.json', JSON.stringify({ polyfillFiles: ['static/chunks/polyfills.js'], rootMainFiles: ['static/chunks/main.js'] }))
    plant('static/chunks/polyfills.js', 'self.fetch||polyfill()')
    plant('static/chunks/main.js', 'hydrate(document)')
    plant('static/chunks/layout.js', 'e.jsx("html",{lang:"en"})')
    plant('static/chunks/page.js', `e.jsx("div",{role:"status","aria-label":"${MARKERS.card}"})`)
    // The card, statically imported; and the engine where it belongs, in a chunk of its own the first load never names.
    plant('static/chunks/card.js', `const t={mark:"",text:"${MARKERS.engine}; their printed value is the true value."}`)
    plant('static/chunks/engine.js', `label:\`\${e.title} chart. ${MARKERS.plot} \${r.items}.\``)
    const files = firstLoadOf(ROUTE, scratch)
    expect(files.sort()).toEqual(['card.js', 'layout.js', 'main.js', 'page.js', 'polyfills.js'].map((file) => `static/chunks/${file}`))
    expect(holding(scratch, files)).toEqual(['static/chunks/card.js: engine', 'static/chunks/page.js: card'])
    // A manifest that names no entry for the route's page is no first load of it.
    const manifest = 'server/app/company/[ticker]/page_client-reference-manifest.js'
    plant(manifest, readFileSync(path.join(scratch, manifest), 'utf8').replace('app/company/[ticker]/page":', 'app/other/page":'))
    expect(() => firstLoadOf(ROUTE, scratch)).toThrow(/names no entry for app\/company\/\[ticker\]\/page/)
  } finally {
    rmSync(scratch, { recursive: true, force: true })
  }
})

test('the company page’s first load holds none of the engine, the plot or the Sector peers card', () => {
  const files = firstLoadOf(ROUTE)
  expect(files.length, `the company route's first-load scripts were read from ${BUILD}`).toBeGreaterThanOrEqual(FLOOR)
  const scripts = staticScripts()
  for (const [part, marker] of Object.entries(MARKERS)) {
    expect(scripts.some(({ body }) => body.includes(marker)), `the ${part}'s string "${marker}" stands in a script of the build`).toBe(true)
  }
  expect(holding(BUILD, files), 'a first-load script holding the engine, the plot or the card').toEqual([])
})
