import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * A company's mark beside its ticker is drawn one way: `components/CompanyLogo.tsx` (DESIGN_SYSTEM.md
 * §4 "Company mark", §9). A surface that built its own `<img src="https://img.logo.dev/…">` would miss
 * the tile, the exact-size candidates, the 404 fallback and the dashed class-share key, and nothing
 * else in the tree would notice: `next.config.js` no longer names the host (nothing renders through
 * next/image), and ESLint reads no URL. So this reads every string under the app's source for the
 * CDN's mark path and holds it to the one file. A preconnect to the host (`<link rel="preconnect"
 * href="https://img.logo.dev">`) names the origin only, never a mark, so it is not read.
 *
 * Planted forms, scored on every run: a ticker URL and a name URL are read; a URL assembled from a
 * variable (`img.logo.dev/${domain}`) is not, since the host is followed by no literal path, and stays
 * review-checked; a preconnect is not read.
 */
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED = ['app', 'components', 'features', 'hooks', 'lib']
const OWNER = 'components/CompanyLogo.tsx'
const MARK_URL = /img\.logo\.dev\/(ticker|name|crypto|isin)\b|img\.logo\.dev\/[a-z0-9.-]+\.[a-z]{2,}/i

function sourceFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) out.push(...sourceFiles(full))
    else if (/\.(ts|tsx|js|jsx|mjs|css)$/.test(entry)) out.push(full)
  }
  return out
}

function offenders(files: Array<{ rel: string; text: string }>): string[] {
  return files
    .filter(({ rel, text }) => rel !== OWNER && MARK_URL.test(text))
    .map(({ rel }) => rel)
}

describe('company marks are drawn by CompanyLogo alone', () => {
  it('reads the planted forms', () => {
    expect(
      offenders([
        { rel: 'features/x/A.tsx', text: '<img src="https://img.logo.dev/ticker/AAPL?token=pk" />' },
        { rel: 'features/x/B.tsx', text: 'const u = `https://img.logo.dev/${domain}?token=${t}`' },
        { rel: 'features/x/C.tsx', text: "fetch('https://img.logo.dev/name/apple')" },
        { rel: 'app/page.tsx', text: '<link rel="preconnect" href="https://img.logo.dev" />' },
        { rel: OWNER, text: 'https://img.logo.dev/ticker/' },
      ]),
    ).toEqual(['features/x/A.tsx', 'features/x/C.tsx'])
  })

  it('finds no mark URL outside components/CompanyLogo.tsx', () => {
    const files = SCANNED.flatMap((dir) => sourceFiles(path.join(frontendRoot, dir))).map((full) => ({
      rel: path.relative(frontendRoot, full).split(path.sep).join('/'),
      text: readFileSync(full, 'utf8'),
    }))
    expect(files.some((f) => f.rel === OWNER), 'the owner is scanned').toBe(true)
    expect(offenders(files)).toEqual([])
  })
})
