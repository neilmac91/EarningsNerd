import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { routeFiles, walkImports } from './importWalk'

/**
 * Nothing on the landing page is struck through (the founder's review, 2026-10-22; D-058). The catch card struck
 * through $391.0B, Apple's correct FY2024 total net sales, as "From memory", while the table above showed the same
 * figure as the prior period: a filed figure marked as wrong, and a mark screen readers never heard. The landing's
 * figures are filed or calculated, never wrong.
 *
 * The scan reads every module the landing route reaches (app/page.tsx with the root layout, error and not-found
 * files, through the import graph, importWalk.ts), so a shared component the landing renders, such as the Financial
 * Highlights table, is read as well as features/marketing. One module keeps its strike-through by meaning: the
 * change report's removed words (WordingChanges), which the summary renderer's imports reach and the landing does not
 * render. The pricing page's former price is on another route.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOT_FILES = ['page.tsx', 'layout.tsx', 'template.tsx', 'loading.tsx', 'error.tsx', 'not-found.tsx']
const LANDING_ROOTS = routeFiles('app', ROOT_FILES, FRONTEND).filter((file) => path.posix.dirname(file) === 'app')
const REMOVED_WORDS = 'features/filings/components/WordingChanges.tsx'
// Every way a module can draw one: the class or the CSS value (a style object's included), and the elements that strike
// through by default. "<s" alone would also match <span>, <section>, <svg> and <select>, so the tag must end there.
const STRIKE = /line-through|<(?:del|s|strike)(?=[\s>/])/
const strikesIn = (source: string) => STRIKE.test(source)
const strikes = (file: string) => strikesIn(readFileSync(path.join(FRONTEND, file), 'utf8'))

describe('the landing page strikes through no figure', () => {
  const files = walkImports(LANDING_ROOTS, FRONTEND)

  it('no module the landing reaches draws a strike-through', () => {
    expect(files, 'the scan reads the landing route and the evidence row').toEqual(
      expect.arrayContaining(['app/page.tsx', 'features/marketing/components/EvidenceSection.tsx', 'features/summaries/components/FinancialMetricsTable.tsx']),
    )
    expect(files.filter((file) => file !== REMOVED_WORDS && strikes(file))).toEqual([])
  })

  it.each([
    ['a strike-through class', `<span className="line-through">$391.0B</span>`],
    ['a style object', `<span style={{ textDecoration: 'line-through' }}>$391.0B</span>`],
    ['a deletion', `<del>$391.0B</del>`],
    ['a strike element', `<s className="x">$391.0B</s>`],
    ['an old strike element', `<strike>$391.0B</strike>`],
  ])('fails a planted %s', (_, source) => {
    expect(strikesIn(source)).toBe(true)
  })

  it.each(['<span>', '<section className="x">', '<svg viewBox="0 0 1 1">', '<select>', '<details>', '<strong>'])(
    'passes %s, which strikes nothing through',
    (source) => {
      expect(strikesIn(source)).toBe(false)
    },
  )

  it('keeps its one exemption only while the landing still reaches it', () => {
    // An exemption the landing no longer reaches is a stale entry: delete it here.
    expect(files).toContain(REMOVED_WORDS)
    expect(strikes(REMOVED_WORDS)).toBe(true)
  })
})
