import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'

/**
 * The production build the e2e job tests, read on disk (E251): CI's job runs `npm run build` in frontend/, serves that
 * .next with `npm run start`, and runs Playwright from frontend/, as no-recharts-in-build.spec.ts reads it. The company
 * page's Sector peers checks read two things from it: the company route's first load (company-first-load.spec.ts) and
 * which of the build's scripts hold the Sector peers card (company-sector-peers.spec.ts).
 */
export const BUILD = path.resolve(__dirname, '../../../.next')

/** A string only one module's code holds, which the minifier keeps whole, for each part the company page's first load
 *  must not carry: the engine's (features/analysis/lib/charts/barChart.ts, BROKEN_BARS), the plot's
 *  (features/analysis/components/TrendChartPlot.tsx, its scroll region's name) and the Sector peers card's
 *  (features/peers/components/SectorPeersCard.tsx, a picked metric's loading status). */
export const MARKERS = {
  engine: 'Bars beyond the axis are broken',
  plot: 'Scroll horizontally to view all',
  card: 'Loading sector peers',
} as const

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
