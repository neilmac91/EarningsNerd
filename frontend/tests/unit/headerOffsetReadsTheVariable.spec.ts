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
 * class token, behind any variants:
 *   1. a `top-` at the header's scale that does not read the variable: a spacing step of 16 or more
 *      (`top-16`, `top-24`) or an arbitrary value with a length of 4rem or 64px or more (`top-[4rem]`,
 *      `top-[calc(64px_+_1rem)]`). `top-0`, small steps, fractions, `top-full` and a negative `-top-` are
 *      left alone there (they are not a header offset), as is anything that reads the variable
 *      (`var(--site-header-h…)`, or Tailwind's `[--site-header-h]` shorthand);
 *   2. a top scroll margin (`scroll-mt-`, `scroll-my-`, `scroll-m-`) that reads the variable. The document's
 *      `scroll-padding-top` (app/globals.css, held here too) applies the header's height once to every
 *      focus, anchor jump and scrollIntoView, and a scroll margin adds to it, so a margin that reads the
 *      variable again lands every jump one bar lower. A margin holds only a section's own room
 *      beyond the header (`scroll-mt-16`). The padding steps aside while focus is inside the site header
 *      (`html:has([data-site-header]:focus-within)`, held here with the header's attribute): the header
 *      is stuck in view, and the padding, which counts its open mobile menu, would scroll the page behind
 *      the menu at every Tab through it. Below lg the filing page's section nav, a second bar stuck under the
 *      header, publishes its height as `--section-nav-h` and the padding adds it, so a margin that reads the
 *      nav's height gives it back (`scroll-mt-[calc(4rem_-_var(--section-nav-h,0px))]`) and never adds it
 *      again; a focus inside the nav drops the nav's share (`html:has([data-section-nav]:focus-within)`,
 *      held here with the nav's attribute);
 *   3. a `sticky` class list whose `top-` (or `inset-`, `inset-y-`) does not read the variable: `sticky
 *      top-0`, a small step, `top-px` or an arbitrary length, which sticks the element under the site header
 *      (the page header did, its title showing through the bar and its back link unclickable beneath it).
 *      Two files stick at the top by design and are pinned to their sites: the site header itself,
 *      and a table's header cells, which stick inside the table's own scroll box. Fractions, `top-full`,
 *      `top-auto`, a percentage and a negative `-top-` are left alone. A list is one string, a whole
 *      template literal, a call of a class-name helper (`cn`, `cx`, `clsx`, `twMerge`, `twJoin`) or every
 *      string in one JSX attribute (`cn('sticky', open && 'top-0')`), a JSX attribute nested in another
 *      being a list of its own; a class list assembled from strings held apart (a const handed to `cn`) or
 *      an inline `position: sticky` style is not read.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
/** Whether a class value reads the header's height: `var(--site-header-h…)` or Tailwind 3.4's `[--site-header-h]`. */
const readsHeader = (value: string) => /(?:var\(|\[)--site-header-h\b/.test(value)
/** The class-name helpers whose arguments are one class list. */
const CLASS_CALLS = new Set(['cn', 'cx', 'clsx', 'twMerge', 'twJoin'])

/** The files that stick at the top of the viewport (or of their own scroll box) by design, each pinned to its
    count of sticky sites with a top that does not read the variable. */
const STICKS_AT_THE_TOP: Record<string, { sites: number; reason: string }> = {
  'components/Header.tsx': { sites: 1, reason: 'the site header itself, the one bar that sticks at the top of the viewport' },
  'components/ui/DataTable.tsx': { sites: 1, reason: "a table's header cells, which stick inside the table's own scroll box" },
}

/** A cheap first pass over a file's raw text: only a file that mentions a candidate (a top of step 16 or
    more, an arbitrary top, any top scroll margin, a sticky list) is parsed, so the tree scan stays fast under load. */
const CANDIDATE = /(?:top-(?:1[6-9]|[2-9]\d|\d{3,}|\[)|scroll-m[ty]?-|\bsticky\b)/
const TOKEN = /(?:^|[\s"'`{])((?:[a-z0-9[\]().@=/&>_!-]+:)*!?)(-?)(top|inset-y|inset|scroll-m[ty]?)-(\S+)/g

/** Rule 1: the tokens in one string that offset from the top at the header's scale without the variable. */
function headerOffsets(text: string): string[] {
  const found: string[] = []
  for (const m of text.matchAll(TOKEN)) {
    const [, variants, negative, utility, value] = m
    const token = `${variants}${negative}${utility}-${value}`
    if (utility !== 'top' || negative || readsHeader(value)) continue
    if (/^\d+(\.\d+)?$/.test(value)) {
      if (Number(value) >= 16) found.push(token)
    } else if (value.startsWith('[')) {
      const lengths = [...value.matchAll(/(\d+(?:\.\d+)?)(rem|px)/g)]
      if (lengths.some(([, n, unit]) => Number(n) >= (unit === 'rem' ? 4 : 64))) found.push(token)
    }
  }
  return found
}

/** Rule 2: the top scroll margins in one string that read the variable, which the document already applies. */
function scrollMarginsReadingTheHeader(text: string): string[] {
  const found: string[] = []
  for (const m of text.matchAll(TOKEN)) {
    const [, variants, negative, utility, value] = m
    if (utility.startsWith('scroll-m') && readsHeader(value)) found.push(`${variants}${negative}${utility}-${value}`)
  }
  return found
}

/** Rule 2, the section nav's half: the top scroll margins in one string that read `--section-nav-h` other than to
    give it back. The document's padding already adds the nav below lg, so a margin may only subtract it. */
function scrollMarginsAddingTheNav(text: string): string[] {
  const found: string[] = []
  for (const m of text.matchAll(TOKEN)) {
    const [, variants, negative, utility, value] = m
    if (!utility.startsWith('scroll-m') || !/(?:var\(|\[)--section-nav-h\b/.test(value)) continue
    const readsOnlyToSubtract = value.split(/(?:var\(|\[)--section-nav-h\b/).slice(0, -1).every((before) => /_-_$/.test(before))
    if (!readsOnlyToSubtract) found.push(`${variants}${negative}${utility}-${value}`)
  }
  return found
}

/** Whether a class list holds `sticky`, behind any variants. */
const holdsSticky = (text: string) => /(?:^|[\s"'`{])(?:[a-z0-9[\]().@=/&>_!-]+:)*!?sticky(?=$|[\s"'`}])/.test(text)

/** Rule 3: in a sticky class list, the tops (an `inset-` or `inset-y-` sets one too) that do not read the variable and
    put the element under the header. */
function stickyTopsUnderTheHeader(text: string): string[] {
  if (!holdsSticky(text)) return []
  const found: string[] = []
  for (const m of text.matchAll(TOKEN)) {
    const [, variants, negative, utility, value] = m
    if (utility.startsWith('scroll-m') || negative || readsHeader(value)) continue
    if (utility === 'inset' && value.startsWith('x-')) continue
    const length = /^\d+(\.\d+)?$/.test(value) || value === 'px' || (value.startsWith('[') && !value.includes('%'))
    if (length) found.push(`${variants}${utility}-${value}`)
  }
  return found
}

interface Finding {
  rule: 1 | 2 | 3
  site: string
}

/** Every finding in one source file, its path relative to the frontend root. */
function scanSource(rel: string, source: string): Finding[] {
  const findings: Finding[] = []
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const stringish = (node: ts.Node): node is ts.StringLiteral | ts.NoSubstitutionTemplateLiteral | ts.TemplateLiteralLikeNode =>
    ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)
  const classCall = (node: ts.Node) => ts.isCallExpression(node) && ts.isIdentifier(node.expression) && CLASS_CALLS.has(node.expression.text)
  /** The strings in a list's subtree, joined as one class list; a JSX attribute nested in it is a list of its own. */
  const listOf = (root: ts.Node): string => {
    const parts: string[] = []
    const collect = (node: ts.Node) => {
      if (node !== root && ts.isJsxAttribute(node)) return
      if (stringish(node)) parts.push(node.text)
      ts.forEachChild(node, collect)
    }
    collect(root)
    return parts.join(' ')
  }
  const push = (rule: Finding['rule'], node: ts.Node, tokens: string[]) => {
    for (const token of tokens) findings.push({ rule, site: `${rel}:${lineOf(node)} "${token}"` })
  }
  // Rules 1 and 2 read each string; rule 3 reads each class list once: a JSX attribute (a nested one too: an
  // `actions={<…/>}` prop holds elements with lists of their own), or outside any list a template literal or a
  // class-name call, whole (the strings inside are not read again on their own), or a string outside all of them.
  const visit = (node: ts.Node, inList: boolean) => {
    const owner = (ts.isJsxAttribute(node) && !!node.initializer) || (!inList && (ts.isTemplateExpression(node) || classCall(node)))
    if (owner) push(3, node, stickyTopsUnderTheHeader(listOf(node)))
    if (stringish(node)) {
      push(1, node, headerOffsets(node.text))
      push(2, node, [...scrollMarginsReadingTheHeader(node.text), ...scrollMarginsAddingTheNav(node.text)])
      if (!inList) push(3, node, stickyTopsUnderTheHeader(node.text))
    }
    ts.forEachChild(node, (child) => visit(child, inList || owner))
  }
  visit(sf, false)
  return findings
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

function scanApp(): Finding[] {
  const findings: Finding[] = []
  for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
    const source = readFileSync(file, 'utf8')
    if (CANDIDATE.test(source)) findings.push(...scanSource(path.relative(ROOT, file), source))
  }
  return findings
}

describe('every offset under the site header reads --site-header-h, and the document applies it once', () => {
  it('the rules name what they should and nothing else', () => {
    expect(headerOffsets('sticky top-16 z-sticky')).toEqual(['top-16'])
    expect(headerOffsets('hidden lg:top-16 lg:w-[420px]')).toEqual(['lg:top-16'])
    expect(headerOffsets('sticky top-24')).toEqual(['top-24'])
    expect(headerOffsets('top-[4rem] top-[64px] md:top-[calc(64px_+_1rem)]')).toEqual(['top-[4rem]', 'top-[64px]', 'md:top-[calc(64px_+_1rem)]'])
    expect(headerOffsets('sticky top-[var(--site-header-h,4rem)] lg:top-[calc(var(--site-header-h,4rem)_+_2rem)]')).toEqual([])
    expect(headerOffsets('sticky top-0 focus:top-4 top-1/2 top-full -top-20 top-[calc(100%_+_4px)]')).toEqual([])
    expect(headerOffsets('desktop-16 stop-24 notop-16 scroll-mt-32 scroll-mt-[calc(var(--site-header-h,4rem)_+_4rem)]')).toEqual([])
    // Tailwind 3.4's shorthand reads the variable too.
    expect(headerOffsets('sticky top-[--site-header-h]')).toEqual([])

    expect(scrollMarginsReadingTheHeader(
      'scroll-mt-[calc(var(--site-header-h,4rem)_+_4rem)] lg:scroll-mt-[calc(var(--site-header-h,4rem)_+_2rem)]',
    )).toEqual(['scroll-mt-[calc(var(--site-header-h,4rem)_+_4rem)]', 'lg:scroll-mt-[calc(var(--site-header-h,4rem)_+_2rem)]'])
    expect(scrollMarginsReadingTheHeader('scroll-my-[var(--site-header-h,4rem)] scroll-m-[var(--site-header-h)]')).toEqual([
      'scroll-my-[var(--site-header-h,4rem)]',
      'scroll-m-[var(--site-header-h)]',
    ])
    expect(scrollMarginsReadingTheHeader(
      'scroll-mt-16 lg:scroll-mt-8 scroll-my-4 scroll-m-2 scroll-mt-0 scroll-mb-[var(--site-header-h,4rem)] top-[var(--site-header-h,4rem)]',
    )).toEqual([])
    expect(scrollMarginsReadingTheHeader('scroll-mt-[--site-header-h]')).toEqual(['scroll-mt-[--site-header-h]'])
    // A margin may read the section nav's height only to give it back.
    expect(scrollMarginsAddingTheNav('scroll-mt-[calc(4rem_-_var(--section-nav-h,0px))] lg:scroll-mt-8 scroll-mt-16')).toEqual([])
    expect(scrollMarginsAddingTheNav(
      'scroll-mt-[calc(4rem_+_var(--section-nav-h,0px))] scroll-mt-[var(--section-nav-h)] md:scroll-my-[--section-nav-h] scroll-mt-[calc(4rem_-_var(--section-nav-h)_+_var(--section-nav-h))]',
    )).toEqual([
      'scroll-mt-[calc(4rem_+_var(--section-nav-h,0px))]',
      'scroll-mt-[var(--section-nav-h)]',
      'md:scroll-my-[--section-nav-h]',
      'scroll-mt-[calc(4rem_-_var(--section-nav-h)_+_var(--section-nav-h))]',
    ])
    expect(scrollMarginsAddingTheNav('top-[var(--section-nav-h)] scroll-mb-[var(--section-nav-h)]')).toEqual([])

    expect(stickyTopsUnderTheHeader('sticky top-0 z-40')).toEqual(['top-0'])
    expect(stickyTopsUnderTheHeader('lg:sticky lg:top-4')).toEqual(['lg:top-4'])
    expect(stickyTopsUnderTheHeader('!sticky top-px')).toEqual(['top-px'])
    expect(stickyTopsUnderTheHeader('sticky top-[2px] md:top-16')).toEqual(['top-[2px]', 'md:top-16'])
    expect(stickyTopsUnderTheHeader('sticky top-[var(--site-header-h,4rem)] lg:top-[calc(var(--site-header-h,4rem)_+_2rem)]')).toEqual([])
    expect(stickyTopsUnderTheHeader('sticky left-0 bottom-0 top-1/2 top-full top-auto top-[50%] -top-px')).toEqual([])
    expect(stickyTopsUnderTheHeader('absolute top-0')).toEqual([])
    expect(stickyTopsUnderTheHeader('nonsticky sticky-header top-0')).toEqual([])
    // An inset sets the top as well; an inline inset does not.
    expect(stickyTopsUnderTheHeader('sticky inset-0')).toEqual(['inset-0'])
    expect(stickyTopsUnderTheHeader('sticky inset-x-0 md:inset-y-0')).toEqual(['md:inset-y-0'])
    expect(stickyTopsUnderTheHeader('sticky inset-x-0 bottom-0 top-[--site-header-h]')).toEqual([])

    // A class list is a string, a whole template literal or one JSX attribute, wherever its strings sit.
    expect(scanSource('probe.tsx', "const a = <div className={cn('sticky', open && 'top-0')} />").map((f) => f.site)).toEqual(['probe.tsx:1 "top-0"'])
    expect(scanSource('probe.tsx', 'const a = <div className={`sticky ${tone} top-0`} />').map((f) => f.site)).toEqual(['probe.tsx:1 "top-0"'])
    expect(scanSource('probe.tsx', "const a = <div className={cn('relative', open && 'top-0')} />")).toEqual([])
    // A class-name call is a list outside JSX too, and a JSX attribute nested in another is a list of its own.
    expect(scanSource('probe.ts', "const cls = cn('sticky', open && 'top-0')").map((f) => f.site)).toEqual(['probe.ts:1 "top-0"'])
    expect(scanSource(
      'probe.tsx',
      'const a = <Bar actions={<><div className="sticky top-[var(--site-header-h,4rem)]" /><span className="absolute top-0" /></>} />',
    )).toEqual([])
    expect(scanSource('probe.tsx', 'const a = <Bar actions={<div className="sticky top-0" />} />').map((f) => f.site)).toEqual(['probe.tsx:1 "top-0"'])
    // The first pass lets every token the rules name through, a template head that runs into an interpolation included.
    for (const raw of ['top-16', 'lg:top-24', 'top-[4rem]', 'scroll-mt-[calc(var(--site-header-h,4rem)_+_4rem)]', 'scroll-my-4', 'scroll-m-2', '`sticky top-16${x}`', 'sticky top-0']) {
      expect(CANDIDATE.test(raw), raw).toBe(true)
    }
  })

  it("nothing under app, components, features, hooks or lib offsets from the top at the header's scale on its own", () => {
    const offenders = scanApp().filter((f) => f.rule === 1).map((f) => f.site)
    expect(offenders, "read the header's height: top-[var(--site-header-h,4rem)]").toEqual([])
  })

  it("no top scroll margin reads the header's height or adds the section nav's, and the document's scroll padding reads both", () => {
    const offenders = scanApp().filter((f) => f.rule === 2).map((f) => f.site)
    expect(
      offenders,
      "the document's scroll-padding-top already clears the header and the section nav: a section's scroll margin holds only its own room (scroll-mt-16), less the nav's share",
    ).toEqual([])
    const globalsCss = readFileSync(path.join(ROOT, 'app/globals.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
    const html = globalsCss.match(/@layer base\s*\{\s*html\s*\{([^}]*)\}/)?.[1] ?? ''
    expect(html, 'app/globals.css: html sets scroll-padding-top: calc(var(--site-header-h, 4rem) + var(--section-nav-h, 0px))').toMatch(
      /(?:^|;)\s*scroll-padding-top:\s*calc\(var\(--site-header-h,\s*4rem\)\s*\+\s*var\(--section-nav-h,\s*0px\)\);/,
    )
    expect(
      globalsCss,
      "app/globals.css: a focus inside the section nav drops the nav's share and keeps the header's, or a Tab through its chips scrolls the page",
    ).toMatch(/html:has\(\[data-section-nav\]:focus-within\)\s*\{\s*scroll-padding-top:\s*var\(--site-header-h,\s*4rem\);?\s*\}/)
    expect(
      readFileSync(path.join(ROOT, 'features/summaries/components/SummaryBlocks.tsx'), 'utf8'),
      "features/summaries/components/SummaryBlocks.tsx: the section nav carries data-section-nav",
    ).toMatch(/<nav\b[^>]*\sdata-section-nav[\s>]/)
    expect(
      globalsCss,
      'app/globals.css: the padding steps aside while focus is inside the site header, or a Tab through its open menu scrolls the page behind it',
    ).toMatch(/html:has\(\[data-site-header\]:focus-within\)\s*\{\s*scroll-padding-top:\s*0(?:px)?;?\s*\}/)
    expect(readFileSync(path.join(ROOT, 'components/Header.tsx'), 'utf8'), 'components/Header.tsx: the site header carries data-site-header').toMatch(
      /<header\b[^>]*\sdata-site-header[\s>]/,
    )
  })

  it('nothing sticks under the site header: only the pinned files stick at the top', () => {
    const sites = scanApp().filter((f) => f.rule === 3).map((f) => f.site)
    const fileOf = (site: string) => site.slice(0, site.indexOf(':'))
    expect(
      sites.filter((site) => !(fileOf(site) in STICKS_AT_THE_TOP)),
      'sticky chrome below the site header reads its height: top-[var(--site-header-h,4rem)]. A page\'s own header scrolls with the page (SecondaryHeader).',
    ).toEqual([])
    for (const [file, { sites: count, reason }] of Object.entries(STICKS_AT_THE_TOP)) {
      expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
      expect(sites.filter((site) => fileOf(site) === file).length, `${file} drifted from its pin`).toBe(count)
    }
  })
})
