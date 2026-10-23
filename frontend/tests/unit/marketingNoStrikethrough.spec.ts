import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * No landing-page sample figure is struck through (the founder's review, 2026-10-22). The catch card struck through
 * $391.0B, Apple's correct FY2024 total net sales, as "From memory", while the table above showed the same figure as
 * the prior period: a filed figure marked as wrong, and a mark screen readers never heard. The landing's figures are
 * filed or calculated, never wrong, so nothing in features/marketing draws a strike-through. Elsewhere it keeps its
 * meanings: the change report's removed words (WordingChanges) and the pricing page's former price.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const MARKETING = path.join(FRONTEND, 'features/marketing')

function sources(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) sources(full, out)
    else if (/\.(tsx?|css)$/.test(entry.name)) out.push(full)
  }
  return out
}

describe('the landing page strikes through no figure', () => {
  it('no marketing module draws a strike-through', () => {
    const files = sources(MARKETING)
    expect(files.length, 'the scan reads the marketing modules').toBeGreaterThan(10)
    const struck = files.filter((file) => /line-through|text-decoration:\s*line-through/.test(readFileSync(file, 'utf8')))
    expect(struck.map((file) => path.relative(FRONTEND, file))).toEqual([])
  })
})
