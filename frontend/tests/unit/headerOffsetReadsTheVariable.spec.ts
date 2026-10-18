import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * The site header publishes its rendered height on <html> as `--site-header-h` (components/Header.tsx),
 * and that is the one offset under it (DESIGN_SYSTEM.md §4 Stacking): under enlarged text the bar wraps
 * to two or three rows, so chrome pinned at a fixed `top-16` slides under it (the filing page's section
 * nav did, at 390 px with the text size doubled; tests/e2e/reflow-200.spec.ts holds that case in a
 * browser). This gate reads every string under app, components, features, hooks and lib, and fails on a
 * class token, behind any variants, that offsets from the top at the header's scale without reading the
 * variable:
 *   - a top scroll margin (`scroll-mt-`, `scroll-my-`, `scroll-m-`), which exists to clear the header;
 *   - a `top-` of 4rem or more: a spacing step of 16 or more (`top-16`, `top-24`) or an arbitrary value
 *     with a length of 4rem or 64px or more (`top-[4rem]`, `top-[calc(64px_+_1rem)]`).
 * `top-0`, small steps, fractions, `top-full` and a negative `-top-` are left alone (they are not a
 * header offset), as is anything that reads `var(--site-header-h`.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const VARIABLE = 'var(--site-header-h'

/** A cheap first pass over a file's raw text: only a file that mentions a candidate (a top of step 16 or
    more, an arbitrary top, any top scroll margin) is parsed, so the tree scan stays fast under load. */
const CANDIDATE = /(?:top-(?:1[6-9]|[2-9]\d|\d{3,}|\[)|scroll-m[ty]?-)/
const TOKEN = /(?:^|[\s"'`{])((?:[a-z0-9[\]().@=/&>_!-]+:)*!?)(-?)(top|scroll-m[ty]?)-(\S+)/g

/** The tokens in one string that offset from the top at the header's scale without the variable. */
function headerOffsets(text: string): string[] {
  const found: string[] = []
  for (const m of text.matchAll(TOKEN)) {
    const [, variants, negative, utility, value] = m
    const token = `${variants}${negative}${utility}-${value}`
    if (negative || value.includes(VARIABLE)) continue
    if (utility.startsWith('scroll-m')) {
      if (value !== '0' && value !== '[0]') found.push(token)
      continue
    }
    if (/^\d+(\.\d+)?$/.test(value)) {
      if (Number(value) >= 16) found.push(token)
    } else if (value.startsWith('[')) {
      const lengths = [...value.matchAll(/(\d+(?:\.\d+)?)(rem|px)/g)]
      if (lengths.some(([, n, unit]) => Number(n) >= (unit === 'rem' ? 4 : 64))) found.push(token)
    }
  }
  return found
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

describe('every offset under the site header reads --site-header-h', () => {
  it('the rule names what it should and nothing else', () => {
    expect(headerOffsets('sticky top-16 z-sticky')).toEqual(['top-16'])
    expect(headerOffsets('hidden lg:top-16 lg:w-[420px]')).toEqual(['lg:top-16'])
    expect(headerOffsets('sticky top-24')).toEqual(['top-24'])
    expect(headerOffsets('scroll-mt-32 lg:scroll-mt-24')).toEqual(['scroll-mt-32', 'lg:scroll-mt-24'])
    expect(headerOffsets('scroll-my-4 scroll-m-2')).toEqual(['scroll-my-4', 'scroll-m-2'])
    expect(headerOffsets('top-[4rem] top-[64px] md:top-[calc(64px_+_1rem)]')).toEqual(['top-[4rem]', 'top-[64px]', 'md:top-[calc(64px_+_1rem)]'])
    expect(headerOffsets(
      'sticky top-[var(--site-header-h,4rem)] scroll-mt-[calc(var(--site-header-h,4rem)_+_4rem)] lg:top-[calc(var(--site-header-h,4rem)_+_2rem)]',
    )).toEqual([])
    expect(headerOffsets('sticky top-0 focus:top-4 top-1/2 top-full -top-20 top-[calc(100%_+_4px)] scroll-mt-0 scroll-py-6')).toEqual([])
    expect(headerOffsets('desktop-16 stop-24 notop-16')).toEqual([])
    // The first pass lets every token the rule names through, a template head that runs into an interpolation included.
    for (const raw of ['top-16', 'lg:top-24', 'top-[4rem]', 'scroll-mt-32', 'scroll-my-4', 'scroll-m-2', '`sticky top-16${x}`']) expect(CANDIDATE.test(raw), raw).toBe(true)
  })

  it('nothing under app, components, features, hooks or lib offsets from the top at the header\'s scale on its own', () => {
    const offenders: string[] = []
    for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
      const source = readFileSync(file, 'utf8')
      if (!CANDIDATE.test(source)) continue
      const rel = path.relative(ROOT, file)
      const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, false, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
      const visit = (node: ts.Node) => {
        if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) {
          const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
          for (const token of headerOffsets(node.text)) offenders.push(`${rel}:${line} "${token}"`)
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
    expect(offenders, 'read the header\'s height: top-[var(--site-header-h,4rem)], scroll-mt-[calc(var(--site-header-h,4rem)_+_…)]').toEqual([])
  })
})
