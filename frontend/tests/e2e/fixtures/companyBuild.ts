import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'

/**
 * The production build the e2e job tests, read on disk (E251): CI's job runs `npm run build` in frontend/, serves that
 * .next with `npm run start`, and runs Playwright from frontend/, as no-recharts-in-build.spec.ts reads it. The company
 * page's Sector peers checks read two things from it: the company route's first load (company-first-load.spec.ts) and
 * which of the build's scripts hold the Sector peers card (company-sector-peers.spec.ts).
 */
export const BUILD = path.resolve(__dirname, '../../../.next')

/** For each module of the trend charts' engine the Sector peers card pulls in, and for the card, what only that module's
 *  code holds and the minifier keeps whole (a string, a call or a prop as the minifier writes it), each chosen on
 *  2026-10-31 as held by no other source file under app, components, features, lib or hooks: the company page's first
 *  load must carry none of them. A module of the engine imported into the page by any path (a constant from layout.ts,
 *  say) brings its marker with it. */
export const MARKERS = {
  // features/analysis/lib/charts/
  barChart: 'Bars beyond the axis are broken', // BROKEN_BARS
  layout: 'Values don’t fit at this width.', // VALUES_DONT_FIT_HERE
  scale: 'toPrecision(12)', // clean(), a tick's float noise cleared
  model: 'Oldest period.', // PERIOD_READING
  readout: 'No prior-year period in this window', // a growth gap's tooltip words
  theme: 'rgba(62,142,132,.08)', // the light column wash, `cursor`
  // features/analysis/components/
  svg: 'geometricPrecision', // TrendChartSvg's text rendering
  plot: 'Scroll horizontally to view all', // TrendChartPlot's scroll region's name
  frame: '[^a-zA-Z0-9_-]', // ChartPlotFrame's plot id, from useId
  marks: 'paintOrder:"stroke"', // chartMarks' marker ring, as the minifier writes the prop
  // features/peers/components/SectorPeersCard.tsx, a picked metric's loading status
  card: 'Loading sector peers',
} as const

/** What only the company page's own first-load chunk holds: the peers client's path (features/peers/api/peers-api.ts),
 *  which the Sector peers gate reads on every company page. Found among the scripts a first load reads, it shows the
 *  reader took the page's own entry, not only the root's and the layout's, which alone clear the floor. */
export const PAGE_MARKER = '/peers'

/** Every script the browser can load from a build: `static/chunks`, by the path the build's manifests name it
 *  ("static/chunks/…js"), with its body. */
export function staticScripts(build = BUILD): { file: string; body: string }[] {
  const root = path.join(build, 'static', 'chunks')
  if (!existsSync(root)) throw new Error(`no production build at ${build}: run \`npm run build\` before this suite, as CI's e2e job does`)
  const out: { file: string; body: string }[] = []
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (entry.name.endsWith('.js')) out.push({ file: path.relative(build, full).split(path.sep).join('/'), body: readFileSync(full, 'utf8') })
    }
  }
  walk(root)
  return out
}

/** The scripts holding a part's string, by the path the browser asks for ("/_next/static/chunks/…js"). */
export const servedHolding = (marker: string, build = BUILD) =>
  staticScripts(build).filter(({ body }) => body.includes(marker)).map(({ file }) => `/_next/${file}`)

/** A route's first load: every script its client reference manifest names for the route's entries (the root layout, the
 *  page, and the boundaries it renders under), with the root main files and the polyfills `build-manifest.json` names,
 *  each by the path the manifests give ("static/chunks/…js"). `route` is the app route ("/company/[ticker]/page"). */
export function firstLoadOf(route: string, build = BUILD): string[] {
  const manifestFile = path.join(build, 'server', 'app', ...route.slice(1).split('/').slice(0, -1), 'page_client-reference-manifest.js')
  if (!existsSync(manifestFile)) throw new Error(`no client reference manifest at ${manifestFile}: run \`npm run build\` before this suite, as CI's e2e job does`)
  const source = readFileSync(manifestFile, 'utf8')
  const escaped = route.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')
  const assignment = new RegExp(`^globalThis\\.__RSC_MANIFEST\\["${escaped}"\\] = (\\{.*\\});?$`, 'm').exec(source)
  if (!assignment) throw new Error(`${manifestFile} assigns no manifest to ${route}`)
  const manifest = JSON.parse(assignment[1]) as { entryJSFiles: Record<string, string[]> }
  const entries = Object.keys(manifest.entryJSFiles)
  const page = route.replace(/^\//, 'app/')
  if (!entries.some((entry) => entry.endsWith(page))) throw new Error(`${route}'s manifest names no entry for ${page}: ${entries.join(', ')}`)
  const roots = JSON.parse(readFileSync(path.join(build, 'build-manifest.json'), 'utf8')) as { polyfillFiles?: string[]; rootMainFiles?: string[] }
  return [...new Set([...(roots.polyfillFiles ?? []), ...(roots.rootMainFiles ?? []), ...Object.values(manifest.entryJSFiles).flat()])]
}
