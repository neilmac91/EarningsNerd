import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Section headings in settings and on the dashboard carry no icon (DESIGN.md › Icons; the "Settings and
 * subscription" line in docs/brand/08-applications.md §3; D-033). An icon element (a `…Icon` component from
 * lib/icons) fails here when it renders inside an <h2>/<h3>, or as the child directly before one among the same
 * parent's children, the flex-row shape the eight removed heading icons had (DSW-13, DSW-19). A child is read
 * for what it can render: an element, either branch of a `&&`, `||`, `??` or ternary, a fragment's children,
 * or a const in the same file that holds an element (`{icon}`), and an empty expression (a `{/* comment *\/}`)
 * between the two is skipped. A fragment's children are siblings as an element's are. Each side is read one
 * wrapper deep: an element holding only icons before the heading (a chip `<span>` around one), or an element
 * holding the heading after the icon (a `<div>` with the heading and its description). A heading that titles
 * a notice or an empty state, not a section, keeps the icon that carries its state (NOT_SECTION_HEADINGS):
 * each entry is pinned to its file, its heading's words and its site (the icon and where it sits), and takes
 * one find, so an icon put inside that heading, another icon beside it, or a second heading with the same words
 * fails.
 *
 * Limits: a wrapper two deep on either side, an icon passed as a prop or built in another file, a heading
 * written as a component rather than an <h2>/<h3>, and an icon after the heading (`<h3>Notifications</h3><BellIcon />`,
 * though D-033 says "beside it") are not read; review reads them.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app/dashboard', 'features/settings', 'features/subscriptions', 'features/dashboard']
const HEADINGS = new Set(['h2', 'h3'])

type JsxNode = ts.JsxElement | ts.JsxSelfClosingElement
const isJsxNode = (node: ts.Node): node is JsxNode => ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)

/** One icon on a heading: the site as `file:line <Icon> where <hN>`, its place (the site without its line), and the heading's words. */
type HeadingIcon = { site: string; place: string; heading: string }

/** Every icon rendered inside, or directly before, a heading. */
function headingIcons(file: string, text: string): HeadingIcon[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const found: HeadingIcon[] = []
  const add = (at: ts.Node, place: string, heading: JsxNode) => found.push({ site: `${file}:${line(at)} ${place}`, place, heading: words(heading) })
  const line = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1
  const tagOf = (node: JsxNode) => (ts.isJsxElement(node) ? node.openingElement.tagName : node.tagName).getText(source)
  const isIcon = (node: JsxNode) => /Icon$/.test(tagOf(node))
  const isHeading = (node: JsxNode) => HEADINGS.has(tagOf(node))
  const words = (node: JsxNode): string => {
    const parts: string[] = []
    const read = (child: ts.Node): void => {
      if (ts.isJsxText(child)) parts.push(child.text)
      ts.forEachChild(child, read)
    }
    read(node)
    return parts.join(' ').replace(/\s+/g, ' ').trim()
  }

  /** The const initializers in this file, by name: `const icon = <BellIcon />`. */
  const consts = new Map<string, ts.Expression>()
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) consts.set(node.name.text, node.initializer)
    ts.forEachChild(node, collect)
  }
  collect(source)

  /** The elements an expression can render, through conditionals, fragments and a same-file const. */
  const fromExpression = (expression: ts.Expression, seen: Set<string> = new Set()): JsxNode[] => {
    if (ts.isParenthesizedExpression(expression)) return fromExpression(expression.expression, seen)
    if (isJsxNode(expression)) return [expression]
    if (ts.isJsxFragment(expression)) return expression.children.flatMap((child) => rendered(child, seen))
    if (ts.isConditionalExpression(expression)) return [...fromExpression(expression.whenTrue, seen), ...fromExpression(expression.whenFalse, seen)]
    if (ts.isBinaryExpression(expression)) {
      const op = expression.operatorToken.kind
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return fromExpression(expression.right, seen)
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) {
        return [...fromExpression(expression.left, seen), ...fromExpression(expression.right, seen)]
      }
    }
    if (ts.isIdentifier(expression) && consts.has(expression.text) && !seen.has(expression.text)) {
      return fromExpression(consts.get(expression.text)!, new Set([...seen, expression.text]))
    }
    return []
  }
  /** The elements one JSX child can render; whitespace and an empty expression (a comment) render none. */
  const rendered = (child: ts.Node, seen: Set<string> = new Set()): JsxNode[] => {
    if (isJsxNode(child)) return [child]
    if (ts.isJsxFragment(child)) return child.children.flatMap((inner) => rendered(inner, seen))
    if (ts.isJsxExpression(child) && child.expression) return fromExpression(child.expression, seen)
    return []
  }
  /** Whether a child renders nothing at all: whitespace-only text or an empty expression (a comment). */
  const blank = (child: ts.JsxChild) =>
    (ts.isJsxText(child) && child.containsOnlyTriviaWhiteSpaces) || (ts.isJsxExpression(child) && !child.expression)
  const childrenOf = (node: JsxNode): readonly ts.JsxChild[] => (ts.isJsxElement(node) ? node.children : [])

  /** The icons a child before a heading puts beside it: the icons it renders, and those of a wrapper holding only icons. */
  const iconsBefore = (child: ts.JsxChild): JsxNode[] =>
    rendered(child).flatMap((element) => {
      if (isIcon(element)) return [element]
      const inner = childrenOf(element).filter((c) => !blank(c))
      const held = inner.flatMap((c) => rendered(c))
      return inner.length > 0 && held.length === inner.length && held.every(isIcon) ? held : []
    })
  /** The headings a child after an icon holds: the headings it renders, and those directly inside a wrapper it renders. */
  const headingsAfter = (child: ts.JsxChild): JsxNode[] =>
    rendered(child).flatMap((element) =>
      isHeading(element) ? [element] : childrenOf(element).flatMap((c) => rendered(c)).filter(isHeading),
    )

  const visit = (node: ts.Node): void => {
    if (isJsxNode(node) && isHeading(node)) {
      const heading = node
      const outside = (element: JsxNode) => element.getStart() < heading.getStart() || element.getEnd() > heading.getEnd()
      const inside = (child: ts.Node): void => {
        if (isJsxNode(child) && isIcon(child)) add(child, `<${tagOf(child)}> inside <${tagOf(heading)}>`, heading)
        // An icon a const holds (`{icon}`) is written elsewhere: report it where the heading renders it.
        if (ts.isJsxExpression(child)) {
          for (const element of rendered(child).filter(outside)) {
            if (isIcon(element)) add(child, `<${tagOf(element)}> inside <${tagOf(heading)}>`, heading)
          }
        }
        ts.forEachChild(child, inside)
      }
      childrenOf(heading).forEach(inside)
    }
    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
      const siblings = node.children.filter((child) => !blank(child))
      siblings.forEach((child, i) => {
        if (i === 0) return
        const headings = headingsAfter(child)
        if (!headings.length) return
        const before = siblings[i - 1]
        for (const icon of iconsBefore(before)) {
          for (const heading of headings) add(before, `<${tagOf(icon)}> before <${tagOf(heading)}>`, heading)
        }
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

/**
 * Headings that title a notice or an empty state rather than a section, so the icon beside them carries the
 * state, as the design system's Notice and GuidanceCard do. Each entry is ONE icon on ONE heading, pinned by
 * its file, the heading's whole text and the icon's place (`<Icon> before <hN>`), and takes one find
 * (exempted, below); shrink-only, so an entry no find takes any more fails.
 */
type Exemption = { file: string; place: string; heading: string; why: string }
const NOT_SECTION_HEADINGS: Exemption[] = [
  {
    file: 'app/dashboard/settings/page.tsx',
    place: '<WarningCircleIcon> before <h3>',
    heading: 'Warning: This action is permanent',
    why: "the delete confirmation's warning callout: its icon is the status icon a Notice carries beside its title (DESIGN_SYSTEM.md, Inline notice)",
  },
  {
    file: 'features/dashboard/components/FeedOnboarding.tsx',
    place: '<NewspaperIcon> before <h3>',
    heading: 'Follow your first company',
    why: "the empty feed's panel in GuidanceCard's look: the brand-tint icon above its title (DESIGN_SYSTEM.md, GuidanceCard)",
  },
]

/** The finds no entry takes, each entry taking the first find at its file, place and heading, and the entries no find takes. */
function exempted(finds: Array<HeadingIcon & { file: string }>, entries: Exemption[]) {
  const taken = new Set<Exemption>()
  const left = finds.filter((find) => {
    const entry = entries.find((e) => !taken.has(e) && e.file === find.file && e.place === find.place && e.heading === find.heading)
    if (entry) taken.add(entry)
    return !entry
  })
  return { left: left.map(({ site }) => site), stale: entries.filter((entry) => !taken.has(entry)).map(({ file, heading }) => `${file}: ${heading}`) }
}

const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name)
    if (statSync(full).isDirectory()) return walk(full)
    return name.endsWith('.tsx') ? [full] : []
  })

describe('Section headings in settings and on the dashboard carry no icon', () => {
  it('sees an icon inside a heading and one directly before it, and nothing else (self-check)', () => {
    const fixture = [
      'const a = <h2><BellIcon className="h-5 w-5" /> Filing alerts</h2>',
      'const b = <div className="flex items-center gap-3"><CreditCardIcon className="h-5 w-5" />',
      '  <h2>Billing</h2></div>',
      'const c = <div><h3>Plan</h3><LightningIcon /></div>',
      'const d = <div><LinkIcon /><p>Not a heading</p><h3>Accounts</h3></div>',
      'const e = <Badge icon={<LightningIcon />}>Pro</Badge>',
      "const f = <div><CreditCardIcon />{/* The panel's focus target on a retry */}<h2>Billing</h2></div>",
      'const g = <div>{show && <BellIcon />}<h2>Alerts</h2></div>',
      'const h = <div>{pro ? <LightningIcon /> : <LockIcon />}<h3>Plan</h3></div>',
      'const i = <><GearIcon /><h2>Settings</h2></>',
      'const j = <div><span className="chip"><BellIcon /></span><h2>Alerts</h2></div>',
      'const k = <div><BellIcon /><div><h2>Alerts</h2><p>Get notified.</p></div></div>',
      'const shield = <ShieldIcon />',
      'const l = <div>{shield}<h2>Security</h2></div>',
      'const m = <h3>{shield} Sessions</h3>',
      'const n = <div><Link href="/"><ArrowLeftIcon /> Back</Link><div><h2>Settings</h2></div></div>',
      'const o = <div><span><span><BellIcon /></span></span><h2>Two wrappers deep</h2></div>',
      'const p = <div><BellIcon />{ready && <h2>Ready</h2>}</div>',
    ].join('\n')
    expect(headingIcons('fixture.tsx', fixture).map(({ site }) => site)).toEqual([
      'fixture.tsx:1 <BellIcon> inside <h2>',
      'fixture.tsx:2 <CreditCardIcon> before <h2>',
      'fixture.tsx:7 <CreditCardIcon> before <h2>',
      'fixture.tsx:8 <BellIcon> before <h2>',
      'fixture.tsx:9 <LightningIcon> before <h3>',
      'fixture.tsx:9 <LockIcon> before <h3>',
      'fixture.tsx:10 <GearIcon> before <h2>',
      'fixture.tsx:11 <BellIcon> before <h2>',
      'fixture.tsx:12 <BellIcon> before <h2>',
      'fixture.tsx:14 <ShieldIcon> before <h2>',
      'fixture.tsx:15 <ShieldIcon> inside <h3>',
      'fixture.tsx:18 <BellIcon> before <h2>',
    ])
  })

  it('no settings, subscription or dashboard source puts an icon on a section heading', () => {
    const files = ROOTS.flatMap((root) => walk(path.join(frontendDir, root)))
    // Not vacuous: the settings sources this rule came from are scanned.
    const rels = files.map((file) => path.relative(frontendDir, file).split(path.sep).join('/'))
    expect(rels).toEqual(expect.arrayContaining([
      'features/settings/components/BillingPanel.tsx',
      'features/settings/components/NotificationPreferencesForm.tsx',
      'app/dashboard/settings/page.tsx',
      'features/dashboard/components/FilingFeed.tsx',
    ]))
    const finds = files.flatMap((file, i) => headingIcons(rels[i], readFileSync(file, 'utf8')).map((find) => ({ ...find, file: rels[i] })))
    const { left, stale } = exempted(finds, NOT_SECTION_HEADINGS)
    expect(left).toEqual([])
    // Shrink-only: an entry no heading with an icon takes any more goes.
    expect(stale).toEqual([])
  })

  it('an exemption takes the one icon at its site, never another icon on that heading or a second heading with its words (self-check)', () => {
    const fixture = [
      'const a = <div><span className="tint"><NewspaperIcon /></span><h3>Follow your first company</h3></div>',
      // The review of #1312's forms: another icon beside a heading with the pinned words, one inside the pinned
      // heading, and the pinned site written twice.
      'const b = <div className="flex items-center gap-2"><BellIcon className="h-5 w-5" /><h3>Follow your first company</h3></div>',
      'const c = <div><span><NewspaperIcon /></span><h3><BellIcon className="h-4 w-4" /> Follow your first company</h3></div>',
      'const d = <div><span className="tint"><NewspaperIcon /></span><h3>Follow your first company</h3></div>',
    ].join('\n')
    const entry: Exemption = { file: 'fixture.tsx', place: '<NewspaperIcon> before <h3>', heading: 'Follow your first company', why: 'planted' }
    const finds = headingIcons('fixture.tsx', fixture).map((find) => ({ ...find, file: 'fixture.tsx' }))
    expect(exempted(finds, [entry])).toEqual({
      left: ['fixture.tsx:2 <BellIcon> before <h3>', 'fixture.tsx:3 <NewspaperIcon> before <h3>', 'fixture.tsx:3 <BellIcon> inside <h3>', 'fixture.tsx:4 <NewspaperIcon> before <h3>'],
      stale: [],
    })
    expect(exempted([], [entry]).stale, 'an entry no find takes is stale').toEqual(['fixture.tsx: Follow your first company'])
    // The pinned heading with its own icon gone and another put inside it: the entry takes no other icon.
    const moved = headingIcons('fixture.tsx', 'const e = <h3><BellIcon className="h-4 w-4" /> Follow your first company</h3>').map((find) => ({ ...find, file: 'fixture.tsx' }))
    expect(exempted(moved, [entry])).toEqual({ left: ['fixture.tsx:1 <BellIcon> inside <h3>'], stale: ['fixture.tsx: Follow your first company'] })
  })
})
