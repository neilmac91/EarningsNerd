import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { noticeTint, type NoticeVariant } from '@/components/ui'
import { bindingResolver } from './astBindings'

/**
 * Words inside Notice's tint rest in the ink, and words in another ink there clear 4.5:1 on the panel and on the page,
 * in both themes (E283; CLAUDE.md rule 11). Notice sets its words in the primary and secondary inks and only its glyph
 * in the variant's (a graphic, 3:1), and so do the borrowers of noticeTint() that keep a Notice's words, the dashboard's
 * limit banner and the verification banner (DESIGN_SYSTEM.md §4 › Inline notice). A borrower that sets words in another
 * ink inside the tint is listed in INKED with the inks it writes, and measured: the one today is the Copilot's error
 * bubble, its one sentence in the error ink (4.62:1 in dark). The settings page's delete warning set its words in the
 * error ink on the loss tint, 4.32:1 in dark, until E283; since D-076 it is a warning Notice, its list the Notice's
 * children.
 *
 * Every <Notice> is read the same way (D-076): the words a caller writes into it, in its title, its description or its
 * children (a JSX value of any prop included), and the Notice's own className, rest in the ink, so a status ink on a
 * list inside a Notice fails. A link (an <a>, a <Link>, a component named for one) may take the accent ink every link
 * takes (`text-brand-strong`, its hover `text-brand-emphasis`, their dark twins) at full strength; the accent ink on
 * anything else, or faded, fails. A <Notice> is one imported from components/ui/Notice or the components/ui barrel,
 * by alias path or relative to the file, under any name, as a namespace member or through a same-file const alias.
 * Out of reach there: words a component inside the Notice inks itself, and a class held in a variable. A title that
 * opens on its state's name is noticeTitlesAreOnePhrase.spec.ts's, which reads every piece of a title.
 *
 * What it reads, through the TypeScript AST: every source under app, components, features, hooks and lib but
 * components/ui that names the helper. Each call must sit in the className of the element it tints, its variant
 * written, under the helper's own name or a namespace import's member, so every tint has an element to read; an
 * alias, a call anywhere else, a variable variant and the helper read as a value fail. Inside each tint's element (the
 * element and everything inside it, an element in a JSX prop included), the text colours of every className's strings
 * and template chunks are read, under any variant, on each element but a glyph: an icon (a self-closing element whose tag ends in `Icon`,
 * or an <svg>) or an element that holds nothing but glyphs and blank text. Any other child, a component's included,
 * counts as words. A colour outside the ink family (`text-text-…`, or `text-current` and `text-inherit`, which take
 * the ink above) is a word in another ink: its source must be listed in INKED for that tint's variant, and a listed
 * source must write there exactly the inks INKED gives it, each of them, so words moved to another ink, or a faded
 * one (`dark:text-error-dark/80`), fail rather than pass unmeasured. The tint and the inks resolve through
 * tailwind.config.js: light reads the bare `bg-` class, dark the `dark:bg-` one, each with its opacity modifier
 * (`/[0.06]`, or `/10` on Tailwind's opacity scale), composited on the ground and rounded to 8-bit channels, as the
 * browser paints it. A tint or ink it cannot read fails. Out of reach: a class held in a variable or passed from
 * another file, an ink set inside a component the element renders, and the ink family's own contrast in a tint (a
 * faded or tertiary ink there is the e2e text-floors census's, on the routes it checks).
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const THEME = resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme
const COLORS = flattenColorPalette(THEME.colors)
const OPACITY_SCALE = THEME.opacity as Record<string, string>
const FLOOR = 4.5
/** Where the helper's borrowers live, as statusTintResidue.spec.ts's TINT_BORROWED reads them; the primitives own it. */
const DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const PRIMITIVES = 'components/ui/'
const HELPER = 'noticeTint'

type Rgb = [number, number, number]
type Theme = 'light' | 'dark'
type Tinted = ts.JsxElement | ts.JsxSelfClosingElement

/** The borrowers whose words take another ink inside the tint, with the inks they write. */
const INKED: { file: string; variant: NoticeVariant; ink: Record<Theme, string> }[] = [
  // The error bubble: the answer card's shape, its one sentence in the error ink (E196 (3)).
  { file: 'features/filings/components/copilot/CopilotMessage.tsx', variant: 'error', ink: { light: 'text-error-light', dark: 'dark:text-error-dark' } },
]

function hex(value: string | undefined): Rgb {
  const m = /^#([0-9a-f]{6})$/i.exec(value ?? '')
  if (!m) throw new Error(`a colour this spec cannot read: ${value}`)
  return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)) as Rgb
}
const channel = (v: number) => {
  const s = v / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const luminance = ([r, g, b]: Rgb) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
const ratio = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const over = (top: Rgb, alpha: number, ground: Rgb): Rgb => top.map((c, i) => Math.round(c * alpha + ground[i] * (1 - alpha))) as Rgb

/** A tint's colour and opacity from its `bg-` class in one theme (`dark:` for dark), or a throw. */
function tint(classes: string, theme: Theme): { colour: Rgb; alpha: number } {
  const prefix = theme === 'dark' ? 'dark:bg-' : 'bg-'
  const found = classes.split(/\s+/).filter((c) => c.startsWith(prefix) && (theme === 'dark' || !c.includes(':')))
  if (found.length !== 1) throw new Error(`${theme}: ${found.length} tints in "${classes}"`)
  const m = /^(?:dark:)?bg-([a-z-]+)\/(?:\[(\d*\.?\d+)\]|(\d+))$/.exec(found[0])
  if (!m) throw new Error(`a tint this spec cannot read: ${found[0]}`)
  const alpha = m[2] !== undefined ? Number(m[2]) : Number(OPACITY_SCALE[m[3]])
  if (!(alpha > 0 && alpha <= 1)) throw new Error(`an opacity this spec cannot read: ${found[0]}`)
  return { colour: hex(COLORS[m[1]]), alpha }
}
const inkOf = (cls: string) => hex(COLORS[cls.replace(/^(?:dark:)?text-/, '')])
/** The colour a text class names, under any variants, an arbitrary or named one included, and with any opacity
    (`dark:text-error-dark/80` names `error-dark`, `[&_li]:text-error-light` names `error-light`), or null for a size,
    an alignment or anything else that is no text colour. The utility follows the last colon outside brackets. */
const textColour = (token: string) => {
  const m = /^!?text-(.+?)(?:\/.+)?$/.exec(token.split(/:(?![^[]*\])/).pop()!)
  return m && (m[1] in COLORS || m[1].startsWith('[')) ? m[1] : null
}
/** The ink family: the ink's own tokens, and the two that take the ink above. */
const isInk = (colour: string) => colour.startsWith('text-') || colour === 'current' || colour === 'inherit'
const GROUNDS: Record<Theme, Record<string, Rgb>> = {
  light: { panel: hex(COLORS['panel-light']), page: hex(COLORS['background-light']) },
  dark: { panel: hex(COLORS['panel-dark']), page: hex(COLORS['background-dark']) },
}

const parse = (file: string, source: string) =>
  ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
const isClassAttribute = (node: ts.Node, sf: ts.SourceFile): node is ts.JsxAttribute =>
  ts.isJsxAttribute(node) && /^\w*[cC]lassName$/.test(node.name.getText(sf))

/** Each element whose className calls the helper, with the variant it writes, and each use of the helper this spec
    cannot place on such an element, as `file:line why`. */
function tints(sf: ts.SourceFile): { found: { variant: string; element: Tinted }[]; unplaced: string[] } {
  const found: { variant: string; element: Tinted }[] = []
  const unplaced: string[] = []
  const at = (node: ts.Node) => `${sf.fileName}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  /** Where one use of the helper sits: an element with the variant it writes, or why it has none (null for an import
      under the helper's own name, which is no use). */
  const place = (node: ts.Identifier): { variant: string; element: Tinted } | string | null => {
    const parent = node.parent
    if (ts.isImportSpecifier(parent)) return parent.propertyName ? 'is imported under another name' : null
    // The callee: the helper itself, or a namespace import's member (`UI.noticeTint`).
    const callee = ts.isPropertyAccessExpression(parent) && parent.name === node ? parent : node
    const call = callee.parent
    if (!ts.isCallExpression(call) || call.expression !== callee) return 'is read as a value, not called'
    const [variant, ...rest] = call.arguments
    if (variant === undefined || !ts.isStringLiteralLike(variant) || rest.length > 0) return '(…) variant is not one string literal'
    let up: ts.Node = call
    while (!ts.isJsxAttribute(up) && !ts.isSourceFile(up)) up = up.parent
    if (!isClassAttribute(up, sf)) return "(…) is called outside an element's className"
    const element = up.parent.parent
    return { variant: variant.text, element: ts.isJsxOpeningElement(element) ? element.parent : element }
  }
  const visit = (node: ts.Node): void => {
    if (ts.isIdentifier(node) && node.text === HELPER) {
      const placed = place(node)
      if (typeof placed === 'string') unplaced.push(`${at(node)} ${HELPER}${placed.startsWith('(') ? '' : ' '}${placed}`)
      else if (placed) found.push(placed)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { found, unplaced }
}

/** The text colours outside the ink family on the tint's element and every element inside it but a glyph. `allow`
    passes a colour on one element (a link's accent ink inside a Notice); `root` reads the element's own className even
    when it holds nothing but glyphs (a Notice written with empty children still has a className to read). */
function wordInks(element: Tinted, sf: ts.SourceFile, allow?: (cls: string, node: Tinted) => boolean, root = false): string[] {
  const tag = (node: Tinted) => (ts.isJsxElement(node) ? node.openingElement : node).tagName.getText(sf)
  const isIcon = (node: Tinted) => /Icon$/.test(tag(node)) || tag(node) === 'svg'
  // Blank text, an empty expression (a comment) or an icon draw no word; nor does an element of nothing else.
  const glyph = (node: ts.JsxChild): boolean => {
    if (ts.isJsxText(node)) return node.text.trim() === ''
    if (ts.isJsxExpression(node)) return node.expression === undefined
    if (ts.isJsxSelfClosingElement(node)) return isIcon(node)
    if (ts.isJsxElement(node)) return isIcon(node) || node.children.every(glyph)
    return node.children.every(glyph)
  }
  const tokens: { token: string; node: Tinted }[] = []
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) && ((root && node === element) || !glyph(node))) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node
      const strings = (n: ts.Node): void => {
        if (ts.isStringLiteralLike(n) || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)) tokens.push(...n.text.split(/\s+/).map((token) => ({ token, node })))
        ts.forEachChild(n, strings)
      }
      opening.attributes.properties.filter((p) => isClassAttribute(p, sf)).forEach(strings)
    }
    ts.forEachChild(node, visit)
  }
  visit(element)
  return tokens.filter(({ token, node }) => {
    const colour = textColour(token)
    return colour !== null && !isInk(colour) && !(allow?.(token, node) ?? false)
  }).map(({ token }) => token)
}

/** Every source under DIRS but the primitives that names the helper, from the frontend root. */
function borrowers(): string[] {
  const out: string[] = []
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name)
      const file = path.relative(ROOT, p).split(path.sep).join('/')
      if (entry.isDirectory()) walk(p)
      else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name) && !file.startsWith(PRIMITIVES)) {
        if (readFileSync(p, 'utf8').includes(HELPER)) out.push(file)
      }
    }
  }
  DIRS.forEach((dir) => walk(path.join(ROOT, dir)))
  return out.sort()
}

const read = (file: string) => parse(file, readFileSync(path.join(ROOT, file), 'utf8'))

/** Whether an import specifier in a file names the modules a <Notice> comes from: components/ui/Notice or the
    components/ui barrel, by alias path or relative to the file. */
function isNoticeModule(file: string, specifier: string): boolean {
  let key = specifier
  if (key.startsWith('@/')) key = key.slice(2)
  else if (key.startsWith('.')) key = path.posix.normalize(path.posix.join(path.posix.dirname(file), key))
  else return false
  key = key.replace(/\/+$/, '').replace(/\.(tsx?|js)$/, '').replace(/\/index$/, '')
  return key === 'components/ui' || key === 'components/ui/Notice'
}

/** Each <Notice> in a source, under its import's own name, an alias or a namespace member, unless a local shadows it. */
function noticeElements(sf: ts.SourceFile): Tinted[] {
  const names = new Set<string>()
  const namespaces = new Set<string>()
  for (const st of sf.statements) {
    if (!ts.isImportDeclaration(st) || !ts.isStringLiteral(st.moduleSpecifier) || !st.importClause) continue
    if (!isNoticeModule(sf.fileName, st.moduleSpecifier.text)) continue
    const bindings = st.importClause.namedBindings
    if (bindings && ts.isNamedImports(bindings)) {
      for (const el of bindings.elements) if ((el.propertyName ?? el.name).text === 'Notice') names.add(el.name.text)
    } else if (bindings) namespaces.add(bindings.name.text)
  }
  // `const N = Notice` (or `= UI.Notice`), followed until no new alias appears.
  const aliases: Array<[string, ts.Expression]> = []
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) aliases.push([node.name.text, node.initializer])
    ts.forEachChild(node, collect)
  }
  collect(sf)
  const isNoticeRef = (e: ts.Expression): boolean =>
    (ts.isIdentifier(e) && names.has(e.text)) ||
    (ts.isPropertyAccessExpression(e) && ts.isIdentifier(e.expression) && namespaces.has(e.expression.text) && e.name.text === 'Notice')
  for (let grew = true; grew; ) {
    grew = false
    for (const [alias, init] of aliases) {
      if (!names.has(alias) && isNoticeRef(init)) {
        names.add(alias)
        grew = true
      }
    }
  }
  const resolve = bindingResolver(sf)
  const isAlias = (id: ts.Identifier) => {
    const binding = resolve(id)
    return !!binding && ts.isVariableDeclaration(binding.decl) && !!binding.init && isNoticeRef(binding.init)
  }
  const out: Tinted[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = (ts.isJsxElement(node) ? node.openingElement : node).tagName
      const isNotice = (ts.isIdentifier(tag) && names.has(tag.text) && (!resolve(tag) || isAlias(tag))) ||
        (ts.isPropertyAccessExpression(tag) && ts.isIdentifier(tag.expression) && namespaces.has(tag.expression.text) && !resolve(tag.expression) && tag.name.text === 'Notice')
      if (isNotice) out.push(node)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** A link's ink, the accent's, which a link inside a Notice keeps (DESIGN.md › Links): brand-strong and its hover, at
    full strength, on a link (an <a>, a <Link> or a component named for one). */
const isLinkInk = (cls: string) => /^brand-(strong|emphasis)(-dark)?$/.test(textColour(cls) ?? '') && !/\/[^\]]*$/.test(cls)
const isLink = (node: Tinted, sf: ts.SourceFile) => /^(a|Link|[A-Z]\w*Link)$/.test((ts.isJsxElement(node) ? node.openingElement : node).tagName.getText(sf))
/** The words a caller writes into a Notice in another ink than the ink family, a link's accent ink aside. */
const noticeWords = (element: Tinted, sf: ts.SourceFile) => wordInks(element, sf, (cls, node) => isLink(node, sf) && isLinkInk(cls), true)

/** Every source under DIRS but the primitives, from the frontend root. */
function sources(): string[] {
  const out: string[] = []
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name)
      const file = path.relative(ROOT, p).split(path.sep).join('/')
      if (entry.isDirectory()) walk(p)
      else if (/\.tsx$/.test(entry.name) && !/\.(spec|test)\.tsx$/.test(entry.name) && !file.startsWith(PRIMITIVES)) out.push(file)
    }
  }
  DIRS.forEach((dir) => walk(path.join(ROOT, dir)))
  return out.sort()
}

describe("words inside Notice's tint (E283)", () => {
  it.each(INKED)('$file: its $variant words clear 4.5:1 in the tint on the panel and the page, in both themes', ({ file, variant, ink }) => {
    const sf = read(file)
    const lent = tints(sf).found.filter((t) => t.variant === variant)
    expect(lent.length, `${file} lends the ${variant} tint to an element`).toBeGreaterThan(0)
    const inks = lent.flatMap((t) => wordInks(t.element, sf))
    expect(inks.filter((cls) => !Object.values(ink).includes(cls)), `inside the tint, ${file} sets words only in the measured inks`).toEqual([])
    expect(Object.values(ink).filter((cls) => !inks.includes(cls)), `inside the tint, ${file} writes each measured ink`).toEqual([])
    const failing: string[] = []
    for (const theme of ['light', 'dark'] as Theme[]) {
      const { colour, alpha } = tint(noticeTint(variant), theme)
      for (const [name, ground] of Object.entries(GROUNDS[theme])) {
        const measured = ratio(inkOf(ink[theme]), over(colour, alpha, ground))
        if (measured < FLOOR) failing.push(`${theme} on the ${name}: ${measured.toFixed(2)}:1`)
      }
    }
    expect(failing).toEqual([])
  })

  it('every borrower keeps its words in the ink unless INKED lists it, and every tint has an element to read', () => {
    const files = borrowers()
    // The reader reaches the tree: the limit banner it keeps in the ink, and each listed borrower.
    expect(files).toEqual(expect.arrayContaining(['app/dashboard/page.tsx', ...INKED.map((entry) => entry.file)]))
    const unplaced: string[] = []
    const unlisted: string[] = []
    for (const file of files) {
      const sf = read(file)
      const { found, unplaced: lost } = tints(sf)
      unplaced.push(...lost)
      for (const { variant, element } of found) {
        const inks = wordInks(element, sf)
        if (inks.length > 0 && !INKED.some((entry) => entry.file === file && entry.variant === variant)) {
          unlisted.push(`${file}: ${inks.join(' ')} inside ${HELPER}('${variant}')`)
        }
      }
    }
    expect(unplaced, `call ${HELPER} by its own name, its variant written, in the className of the element it tints`).toEqual([])
    expect(
      unlisted,
      "inside Notice's tint, words rest in the ink and the variant's ink is the glyph's alone, as in a Notice (DESIGN_SYSTEM.md §4 › Inline notice); words in another ink are listed in INKED and measured",
    ).toEqual([])
  })

  it('fails what it should: the loss tint the warning wore, a tint it cannot read, words in another ink, and a tint with no element', () => {
    // The loss tint (loss-soft-dark, an rgba token) under the error ink, on the dark panel: 4.32:1, under the floor.
    const m = /^rgba\((\d+),(\d+),(\d+),(\d*\.?\d+)\)$/.exec(COLORS['loss-soft-dark'] ?? '')
    if (!m) throw new Error(`loss-soft-dark is not the rgba this case reads: ${COLORS['loss-soft-dark']}`)
    const loss: Rgb = [Number(m[1]), Number(m[2]), Number(m[3])]
    const measured = ratio(inkOf('dark:text-error-dark'), over(loss, Number(m[4]), GROUNDS.dark.panel))
    expect(measured.toFixed(2)).toBe('4.32')
    expect(measured).toBeLessThan(FLOOR)
    expect(() => tint('bg-error-light', 'light')).toThrow('a tint this spec cannot read')
    expect(() => tint('bg-error-light/[0.06] bg-error-light/10', 'light')).toThrow('2 tints')
    expect(() => tint('dark:bg-error-dark/10', 'light')).toThrow('0 tints')
    // Read: inside the tint, a colour outside the ink family on anything but a glyph. Not read: the heading outside
    // it, the icon, the ink family, a button that holds its icon alone. Unplaced: the alias, the helper as a value, a
    // call outside a className, a variable variant.
    const planted = parse(
      'planted.tsx',
      [
        "import { noticeTint as lent } from '@/components/ui'",
        'export const Page = () => (',
        '  <section>',
        '    <h2 className="text-error-light dark:text-error-dark">Delete account</h2>',
        "    <div className={cx('rounded-lg border p-4', noticeTint('error'))}>",
        '      <WarningCircleIcon className="h-5 w-5 text-error-light dark:text-error-dark" />',
        '      <h3 className="font-semibold text-text-primary-light dark:text-text-primary-dark">Warning</h3>',
        '      <p className={`text-left ${on ? "text-text-tertiary-light" : ""} dark:text-error-dark/80`}>words</p>',
        "      <ul className={cx('list-disc', 'hover:text-error-light')}><li>one</li></ul>",
        '      <button className="text-warning-light dark:text-current"><XIcon /></button>',
        '      <Button label={<span className="text-success-light">Retry</span>} />',
        '      <p className="text-current">{sentence}</p>',
        '      <p className="text-[#b91c1c]"><Message /></p>',
        '      <Note className="text-info-light" />',
        '      <ol className="[&_li]:text-warning-light *:text-error-light aria-[current]:text-success-light data-[open=true]:text-info-light group-hover/row:dark:text-error-dark [&:hover]:text-text-primary-light"><li>one</li></ol>',
        '    </div>',
        '  </section>',
        ')',
        'const value = noticeTint',
        "const call = noticeTint('error')",
        'const loose = <hr className={noticeTint(kind)} />',
        "const kept = <p>{noticeTint('warning')}</p>",
      ].join('\n'),
    )
    const { found, unplaced } = tints(planted)
    expect(found.map((t) => [t.variant, planted.getLineAndCharacterOfPosition(t.element.getStart(planted)).line + 1])).toEqual([['error', 5]])
    expect(wordInks(found[0].element, planted)).toEqual([
      'dark:text-error-dark/80', 'hover:text-error-light', 'text-success-light', 'text-[#b91c1c]', 'text-info-light',
      '[&_li]:text-warning-light', '*:text-error-light', 'aria-[current]:text-success-light', 'data-[open=true]:text-info-light', 'group-hover/row:dark:text-error-dark',
    ])
    expect(unplaced).toEqual([
      'planted.tsx:1 noticeTint is imported under another name',
      'planted.tsx:19 noticeTint is read as a value, not called',
      "planted.tsx:20 noticeTint(…) is called outside an element's className",
      'planted.tsx:21 noticeTint(…) variant is not one string literal',
      "planted.tsx:22 noticeTint(…) is called outside an element's className",
    ])
  })
})

describe('words inside a Notice (D-076)', () => {
  it('every Notice keeps the words a caller writes into it in the ink, a link in the accent ink', () => {
    const files = sources()
    let count = 0
    const inked: string[] = []
    for (const file of files) {
      const sf = read(file)
      for (const element of noticeElements(sf)) {
        count += 1
        const at = `${file}:${sf.getLineAndCharacterOfPosition(element.getStart(sf)).line + 1}`
        for (const cls of noticeWords(element, sf)) inked.push(`${at} ${cls}`)
      }
    }
    // Not vacuous: the reader reaches the Notices, the settings page's delete warning among them.
    expect(count).toBeGreaterThanOrEqual(45)
    expect(noticeElements(read('app/dashboard/settings/page.tsx'))).toHaveLength(1)
    expect(inked, "a Notice's words rest in the ink, a link in the accent ink, and its glyph alone takes the variant's (DESIGN_SYSTEM.md §4 › Inline notice)").toEqual([])
  })

  it('fails what it should: a status ink in a title, a description or the children, the accent ink off a link or faded, and a Notice root', () => {
    const planted = parse(
      'components/planted.tsx',
      [
        "import { Notice as Box } from './ui'",
        "import * as UI from '@/components/ui/Notice'",
        "import { Notice as Other } from './Notice'",
        'const N = UI.Notice',
        'export const A = () => (',
        '  <>',
        '    <Box variant="warning" title="t" description={<span className="text-warning-light">risky <a className="text-brand-strong hover:text-brand-emphasis dark:text-brand-strong-dark">more</a></span>}>',
        '      <ul className="list-disc text-text-secondary-light"><li className="dark:text-error-dark">one</li></ul>',
        '      <p className="text-brand-strong">not a link</p><Link className="text-brand-strong/70">faded</Link>',
        '    </Box>',
        '    <N variant="info" title="t" className="text-info-light"></N>',
        '    <Other variant="info" title="t" />',
        '  </>',
        ')',
        'export const B = () => { const Box = (p: object) => <div {...p} />; return <Box className="text-error-light" /> }',
      ].join('\n'),
    )
    const found = noticeElements(planted)
    // './ui' from components/ is the barrel; './Notice' from components/ is no Notice module; the shadowing local is skipped.
    expect(found.map((e) => planted.getLineAndCharacterOfPosition(e.getStart(planted)).line + 1)).toEqual([7, 11])
    expect(noticeWords(found[0], planted)).toEqual(['text-warning-light', 'dark:text-error-dark', 'text-brand-strong', 'text-brand-strong/70'])
    // A Notice written with empty children still has its own className read.
    expect(noticeWords(found[1], planted)).toEqual(['text-info-light'])
  })
})
