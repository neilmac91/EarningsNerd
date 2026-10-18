import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver } from './astBindings'

/**
 * A Badge is a label, never a control (brand sweep filing/F27; DESIGN_SYSTEM.md: passive Card and Badge
 * primitives do not implement the control-state set). The ticker route once wrapped a brand Badge in a
 * link, so the row's one action looked like a status chip and had no hover, focus or pressed state of
 * its own. So no control has Badges and nothing else as its face, and no Badge is a control itself. A
 * Badge may sit inside a control beside the control's own words or icon ("New" beside a link's text, a
 * count on a bell).
 *
 * What it reads, in every tracked .tsx and .jsx file outside tests/ (git ls-files), one walk per file:
 *  - A Badge: the DS Badge under any binding the file gives it: `Badge`, a renamed import
 *    (`import { Badge as Chip }`), a namespace member (`UI.Badge`), and a const alias of either
 *    (`const Chip = UI.Badge`, `UI['Badge']`, `const { Badge: Chip } = UI`).
 *  - A control: `<a>`, `<button>`, `<summary>`; next/link's Link under any name; a component named `Link`,
 *    `…Link` or `…Button` (the DS Button, RetryButton), by the name it is imported under or a namespace
 *    member; and any element that takes a handler (`on…`), an `href`, a `tabIndex` of 0 or more, or a
 *    control role, written as a string, a literal in braces, or a spread of an object literal. A role,
 *    a tabIndex or a spread the scan cannot read makes the element a control (it fails closed).
 *  - Its face: what it renders that a reader sees, read through wrapper elements and fragments, the
 *    right side of `&&`, both branches of a ternary, `||` and `??`, arrays, a `.map` callback's JSX, a
 *    same-file const holding JSX, a same-file function's return, and a `children` attribute. Whitespace
 *    (`{' '}`) and a visually hidden span (`sr-only`) are not face. A component the scan does not know is
 *    face when it closes itself (an icon) and is read through when it has children (a wrapper). A control
 *    whose face is, on some path, Badges and nothing else fails.
 *  - A Badge that takes a handler, an `href`, a `tabIndex` of 0 or more, a control role, or a role, a
 *    tabIndex or a spread the scan cannot read, fails.
 *
 * Out of reach, planted below as gaps: a Badge handed in through a prop or a parameter, a Badge a function
 * from another module returns, a component of another module that wraps its children in a control, and a
 * Badge re-exported under another name by another module.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const INTRINSIC_CONTROLS = new Set(['a', 'button', 'summary'])
const CONTROL_ROLES = new Set([
  'button', 'link', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'tab', 'checkbox', 'radio', 'switch', 'option', 'treeitem',
])
/** A component named as a control: next/link's Link, the DS Button and its wrappers (RetryButton), a link component. */
const CONTROL_NAME = /^(?:Link|\w*Button|\w+Link)$/
/** Intrinsic elements that are face of their own (media, fields), whatever their children. */
const SELF_FACE = new Set(['svg', 'img', 'picture', 'video', 'audio', 'canvas', 'iframe', 'input', 'select', 'textarea', 'meter', 'progress', 'hr'])

type Element = ts.JsxElement | ts.JsxSelfClosingElement
/** A face: whether some path renders a Badge, and whether every path renders something else a reader sees. */
interface Face { badge: boolean; other: boolean }
const EMPTY: Face = { badge: false, other: false }
const OTHER: Face = { badge: false, other: true }
const BADGE: Face = { badge: true, other: false }
/** Faces rendered one after another. */
const seq = (faces: Face[]): Face => ({ badge: faces.some((f) => f.badge), other: faces.some((f) => f.other) })
/** Faces of which one renders. */
const alt = (faces: Face[]): Face => ({ badge: faces.some((f) => f.badge), other: faces.length > 0 && faces.every((f) => f.other) })

const unwrap = (e: ts.Expression): ts.Expression => {
  while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e) || ts.isSatisfiesExpression(e)) e = e.expression
  return e
}
const openingOf = (el: Element) => (ts.isJsxElement(el) ? el.openingElement : el)
const childrenOf = (el: Element): readonly ts.JsxChild[] => (ts.isJsxElement(el) ? el.children : [])
/** A static string an expression or initializer holds, or null. */
const staticText = (e: ts.Expression | ts.JsxAttributeValue | undefined): string | null => {
  if (!e) return null
  if (ts.isJsxExpression(e)) return staticText(e.expression)
  const x = unwrap(e as ts.Expression)
  return ts.isStringLiteralLike(x) ? x.text : null
}
/** A static number an expression or initializer holds (a sign allowed), or null. */
const staticNumber = (e: ts.Expression | ts.JsxAttributeValue | undefined): number | null => {
  if (!e) return null
  if (ts.isJsxExpression(e)) return staticNumber(e.expression)
  const x = unwrap(e as ts.Expression)
  if (ts.isNumericLiteral(x)) return Number(x.text)
  if (ts.isPrefixUnaryExpression(x) && ts.isNumericLiteral(x.operand)) {
    if (x.operator === ts.SyntaxKind.MinusToken) return -Number(x.operand.text)
    if (x.operator === ts.SyntaxKind.PlusToken) return Number(x.operand.text)
  }
  if (ts.isStringLiteralLike(x) && /^-?\d+$/.test(x.text.trim())) return Number(x.text)
  return null
}
/** Every static class token an element's className holds (string literals and template chunks under it). */
function classTokens(el: Element): string[] {
  const out: string[] = []
  for (const attr of openingOf(el).attributes.properties) {
    if (!ts.isJsxAttribute(attr) || attr.name.getText() !== 'className' || !attr.initializer) continue
    const visit = (node: ts.Node): void => {
      if (ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) out.push(...node.text.split(/\s+/))
      ts.forEachChild(node, visit)
    }
    visit(attr.initializer)
  }
  return out.filter(Boolean)
}

/** The control traits of an element's attributes: each handler, href, tab stop or control role, and what it cannot read. */
function controlTraits(el: Element): string[] {
  const traits: string[] = []
  const read = (name: string, value: ts.Expression | ts.JsxAttributeValue | undefined, present: boolean) => {
    if (/^on[A-Z]/.test(name)) traits.push(name)
    else if (name === 'href') traits.push('href')
    else if (name === 'tabIndex' && present) {
      const n = staticNumber(value)
      if (n === null) traits.push('tabIndex={…}')
      else if (n >= 0) traits.push(`tabIndex=${n}`)
    } else if (name === 'role' && present) {
      const role = staticText(value)
      if (role === null) traits.push('role={…}')
      else if (role.split(/\s+/).some((r) => CONTROL_ROLES.has(r))) traits.push(`role="${role}"`)
    }
  }
  for (const attr of openingOf(el).attributes.properties) {
    if (ts.isJsxAttribute(attr)) {
      read(attr.name.getText(), attr.initializer, true)
      continue
    }
    const spread = unwrap(attr.expression)
    if (!ts.isObjectLiteralExpression(spread)) {
      traits.push('{...spread}')
      continue
    }
    for (const prop of spread.properties) {
      if (ts.isPropertyAssignment(prop) && (ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name))) read(prop.name.text, prop.initializer, true)
      else if (ts.isShorthandPropertyAssignment(prop)) read(prop.name.text, undefined, true)
      else traits.push('{...spread}')
    }
  }
  return traits
}

/** The Badges in one source that are a control's whole face, or a control themselves. */
export function badgeControls(source: string, file = 'probe.tsx'): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('.jsx') ? ts.ScriptKind.JSX : ts.ScriptKind.TSX)
  const resolve = bindingResolver(sf)
  const badges = new Set(['Badge'])
  const controls = new Set<string>()
  const namespaces = new Set<string>()
  const member = (name: string, into: { badge: Set<string>; control: Set<string> }, local: string) => {
    if (name === 'Badge') into.badge.add(local)
    else if (CONTROL_NAME.test(name)) into.control.add(local)
  }
  // The file's bindings of the Badge, the controls and the namespaces holding them, to a fixed point (an alias
  // of an alias).
  for (let size = -1; size !== badges.size + controls.size + namespaces.size; ) {
    size = badges.size + controls.size + namespaces.size
    const visit = (node: ts.Node): void => {
      if (ts.isImportDeclaration(node) && node.importClause && ts.isStringLiteral(node.moduleSpecifier)) {
        const from = node.moduleSpecifier.text
        const { name, namedBindings } = node.importClause
        if (name && from === 'next/link') controls.add(name.text)
        if (namedBindings && ts.isNamespaceImport(namedBindings)) namespaces.add(namedBindings.name.text)
        if (namedBindings && ts.isNamedImports(namedBindings)) {
          for (const spec of namedBindings.elements) {
            const imported = (spec.propertyName ?? spec.name).text
            if (imported === 'default' && from === 'next/link') controls.add(spec.name.text)
            else member(imported, { badge: badges, control: controls }, spec.name.text)
          }
        }
      }
      if (ts.isImportEqualsDeclaration(node)) namespaces.add(node.name.text)
      if (ts.isVariableDeclaration(node) && node.initializer) {
        const init = unwrap(node.initializer)
        const fromNamespace = (e: ts.Expression): string | null =>
          ts.isPropertyAccessExpression(e) && ts.isIdentifier(e.expression) && namespaces.has(e.expression.text)
            ? e.name.text
            : ts.isElementAccessExpression(e) && ts.isIdentifier(e.expression) && namespaces.has(e.expression.text)
              ? staticText(e.argumentExpression)
              : null
        if (ts.isIdentifier(node.name)) {
          const local = node.name.text
          if (ts.isIdentifier(init) && badges.has(init.text)) badges.add(local)
          else if (ts.isIdentifier(init) && controls.has(init.text)) controls.add(local)
          else if (ts.isIdentifier(init) && namespaces.has(init.text)) namespaces.add(local)
          else {
            const name = fromNamespace(init)
            if (name) member(name, { badge: badges, control: controls }, local)
          }
        } else if (ts.isObjectBindingPattern(node.name) && ts.isIdentifier(init) && namespaces.has(init.text)) {
          for (const element of node.name.elements) {
            if (!ts.isIdentifier(element.name)) continue
            const key = element.propertyName ? (ts.isIdentifier(element.propertyName) || ts.isStringLiteral(element.propertyName) ? element.propertyName.text : null) : element.name.text
            if (key) member(key, { badge: badges, control: controls }, element.name.text)
          }
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
  }

  type Kind = 'badge' | 'control' | 'intrinsic' | 'component'
  const kindOf = (tag: ts.JsxTagNameExpression): Kind => {
    if (ts.isIdentifier(tag)) {
      if (badges.has(tag.text)) return 'badge'
      if (controls.has(tag.text) || CONTROL_NAME.test(tag.text)) return 'control'
      if (/^[a-z]/.test(tag.text)) return INTRINSIC_CONTROLS.has(tag.text) ? 'control' : 'intrinsic'
      return 'component'
    }
    if (ts.isPropertyAccessExpression(tag) && ts.isIdentifier(tag.expression) && namespaces.has(tag.expression.text)) {
      if (tag.name.text === 'Badge') return 'badge'
      if (CONTROL_NAME.test(tag.name.text)) return 'control'
    }
    return 'component'
  }
  const tagOf = (el: Element) => openingOf(el).tagName.getText()

  /** The JSX a same-file function returns: an arrow's expression body or each `return` in its own body. */
  const returnsOf = (fn: ts.Node): ts.Expression[] => {
    if (ts.isArrowFunction(fn) && !ts.isBlock(fn.body)) return [fn.body]
    const body = (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn) || ts.isFunctionDeclaration(fn)) ? fn.body : undefined
    const out: ts.Expression[] = []
    const visit = (node: ts.Node): void => {
      if (ts.isReturnStatement(node) && node.expression) out.push(node.expression)
      if (!ts.isFunctionLike(node)) ts.forEachChild(node, visit)
    }
    if (body) ts.forEachChild(body, visit)
    return out
  }

  const faceOfExpr = (expr: ts.Expression, seen: Set<ts.Node>): Face => {
    const e = unwrap(expr)
    if (ts.isStringLiteralLike(e)) return e.text.trim() ? OTHER : EMPTY
    if (ts.isTemplateExpression(e) || ts.isNumericLiteral(e) || ts.isBigIntLiteral(e)) return OTHER
    if (e.kind === ts.SyntaxKind.NullKeyword || e.kind === ts.SyntaxKind.TrueKeyword || e.kind === ts.SyntaxKind.FalseKeyword) return EMPTY
    if (ts.isJsxElement(e) || ts.isJsxSelfClosingElement(e) || ts.isJsxFragment(e)) return faceOfNode(e, seen)
    if (ts.isConditionalExpression(e)) return alt([faceOfExpr(e.whenTrue, seen), faceOfExpr(e.whenFalse, seen)])
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return alt([faceOfExpr(e.right, seen), EMPTY])
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return alt([faceOfExpr(e.left, seen), faceOfExpr(e.right, seen)])
      return OTHER
    }
    if (ts.isArrayLiteralExpression(e)) return seq(e.elements.map((x) => faceOfExpr(ts.isSpreadElement(x) ? x.expression : x, seen)))
    if (ts.isCallExpression(e)) {
      const callee = unwrap(e.expression)
      // `items.map((i) => <Badge …/>)`: the callback's JSX, rendered once per item (an empty list renders nothing).
      if (ts.isPropertyAccessExpression(callee) && /^(?:map|flatMap)$/.test(callee.name.text) && e.arguments[0]) {
        const fn = unwrap(e.arguments[0])
        if (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) return alt([alt(returnsOf(fn).map((r) => faceOfExpr(r, seen))), EMPTY])
      }
      // A same-file function's return.
      if (ts.isIdentifier(callee)) {
        const fn = functionOf(callee)
        if (fn && !seen.has(fn)) return alt(returnsOf(fn).map((r) => faceOfExpr(r, new Set([...seen, fn]))))
      }
      return OTHER
    }
    if (ts.isIdentifier(e)) {
      if (e.text === 'undefined') return EMPTY
      const binding = resolve(e)
      const held = binding && ts.isVariableDeclaration(binding.decl) && binding.decl.parent.flags & ts.NodeFlags.Const ? binding.init : undefined
      if (held && !seen.has(binding!.decl)) return faceOfExpr(held, new Set([...seen, binding!.decl]))
      // A prop, a parameter or an import: out of reach, read as the control's own content.
      return OTHER
    }
    return OTHER
  }
  /** The same-file function a callee names: a function declaration, or a const holding an arrow or a function. */
  const functionOf = (callee: ts.Identifier): ts.Node | null => {
    const binding = resolve(callee)
    if (!binding) return null
    if (ts.isFunctionDeclaration(binding.decl)) return binding.decl
    const init = binding.init && unwrap(binding.init)
    return init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) ? init : null
  }
  const faceOfChildren = (children: readonly ts.JsxChild[], seen: Set<ts.Node>): Face =>
    seq(children.map((child) => {
      if (ts.isJsxText(child)) return child.containsOnlyTriviaWhiteSpaces ? EMPTY : OTHER
      if (ts.isJsxExpression(child)) return child.expression ? faceOfExpr(child.expression, seen) : EMPTY
      return faceOfNode(child, seen)
    }))
  /** What a control's face holds: its children, or a `children` attribute. */
  const faceInside = (el: Element, seen: Set<ts.Node>): Face => {
    const children = childrenOf(el)
    if (children.length) return faceOfChildren(children, seen)
    for (const attr of openingOf(el).attributes.properties) {
      if (ts.isJsxAttribute(attr) && attr.name.getText() === 'children' && attr.initializer) {
        return ts.isJsxExpression(attr.initializer) ? (attr.initializer.expression ? faceOfExpr(attr.initializer.expression, seen) : EMPTY) : faceOfExpr(attr.initializer as ts.Expression, seen)
      }
    }
    return EMPTY
  }
  function faceOfNode(node: ts.JsxElement | ts.JsxSelfClosingElement | ts.JsxFragment, seen: Set<ts.Node>): Face {
    if (ts.isJsxFragment(node)) return faceOfChildren(node.children, seen)
    const kind = kindOf(openingOf(node).tagName)
    if (kind === 'badge') return BADGE
    if (kind === 'control') return OTHER
    if (classTokens(node).includes('sr-only')) return EMPTY
    const tag = tagOf(node)
    if (kind === 'intrinsic' && SELF_FACE.has(tag)) return OTHER
    const inside = faceInside(node, seen)
    // A childless element still paints (an icon, a dot); one with children is read through.
    return inside.badge || inside.other ? inside : OTHER
  }

  const out: string[] = []
  const at = (node: ts.Node) => `${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const kind = kindOf(openingOf(node).tagName)
      const traits = controlTraits(node)
      if (kind === 'badge') {
        for (const trait of traits) out.push(`${at(node)} a Badge takes ${trait}`)
      } else if (kind === 'control' || traits.length) {
        const face = faceInside(node, new Set())
        if (face.badge && !face.other) out.push(`${at(node)} a Badge is the whole face of a <${tagOf(node)}>`)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** Every tracked .tsx and .jsx file outside tests/. */
const sources = (): string[] =>
  execFileSync('git', ['ls-files', '*.tsx', '*.jsx'], { cwd: FRONTEND, encoding: 'utf8' })
    .split('\n')
    .filter((rel) => rel && !rel.startsWith('tests/'))

describe('a Badge is a label, never a control', () => {
  it('flags each form of a Badge as a control, passes each look-alike, and marks the gaps', () => {
    const imports = "import Link from 'next/link'\nimport { Badge, Button } from '@/components/ui'\n"
    // A form is JSX (held as `const a = …`) or whole statements.
    const flagged = (code: string) => badgeControls(imports + (code.startsWith('<') ? `const a = ${code}` : code)).length > 0
    // A control whose face is a Badge and nothing else.
    const faces: Record<string, string> = {
      'a Link': '<Link href="/x"><Badge variant="brand">Generate</Badge></Link>',
      'a button': '<button type="button"><Badge>Go</Badge></button>',
      'the DS Button': '<Button><Badge>Go</Badge></Button>',
      'an <a>': '<a href="/x"><Badge>Go</Badge></a>',
      'a summary': '<details><summary><Badge>More</Badge></summary></details>',
      'a RetryButton': '<RetryButton failures={[]} focusTarget={ref}><Badge>Retry</Badge></RetryButton>',
      'a renamed Badge import': "import { Badge as Chip } from '@/components/ui'\nconst a = <Link href=\"/x\"><Chip>Generate</Chip></Link>",
      'a namespace member': "import * as UI from '@/components/ui'\nconst a = <Link href=\"/x\"><UI.Badge>Generate</UI.Badge></Link>",
      'a const alias of a namespace member': "import * as UI from '@/components/ui'\nconst Chip = UI.Badge\nconst a = <Link href=\"/x\"><Chip>Go</Chip></Link>",
      'an element access alias': "import * as UI from '@/components/ui'\nconst Chip = UI['Badge']\nconst a = <Link href=\"/x\"><Chip>Go</Chip></Link>",
      'a namespace destructured': "import * as UI from '@/components/ui'\nconst { Badge: Chip } = UI\nconst a = <Link href=\"/x\"><Chip>Go</Chip></Link>",
      'an alias of an alias': "import { Badge as B } from '@/components/ui'\nconst C = B\nconst a = <Link href=\"/x\"><C>Go</C></Link>",
      'a renamed Link': "import NextLink from 'next/link'\nconst a = <NextLink href=\"/x\"><Badge>Go</Badge></NextLink>",
      'Link imported as default': "import { default as Go } from 'next/link'\nconst a = <Go href=\"/x\"><Badge>Go</Badge></Go>",
      'a renamed Button': "import { Button as Action } from '@/components/ui'\nconst a = <Action><Badge>Go</Badge></Action>",
      'a namespace Button': "import * as UI from '@/components/ui'\nconst a = <UI.Button><Badge>Go</Badge></UI.Button>",
      'a whitespace expression beside it': '<Link href="/x">{\' \'}<Badge>Generate</Badge>{" "}</Link>',
      'behind &&': '<Link href="/x">{ready && <Badge>Generate</Badge>}</Link>',
      'a ternary branch': '<Link href="/x">{ready ? <Badge>Generate</Badge> : null}</Link>',
      'behind ??': '<Link href="/x">{chip ?? <Badge>Generate</Badge>}</Link>',
      'a const holding it': 'const face = <Badge>Generate</Badge>\nconst a = <Link href="/x">{face}</Link>',
      'a const of a const': 'const chip = <Badge>Go</Badge>\nconst face = chip\nconst a = <Link href="/x">{face}</Link>',
      'a same-file function’s return': 'const chip = () => <Badge>Go</Badge>\nconst a = <Link href="/x">{chip()}</Link>',
      'a function declaration’s return': 'function chip() { return <Badge>Go</Badge> }\nconst a = <Link href="/x">{chip()}</Link>',
      'a wrapper span': '<Link href="/x"><span className="inline-flex"><Badge>Generate</Badge></span></Link>',
      'a fragment': '<button type="button"><><Badge>Go</Badge></></button>',
      'a wrapper component': '<Link href="/x"><Tooltip content="x"><Badge>Go</Badge></Tooltip></Link>',
      'a hidden name tail beside it': '<Link href="/x"><Badge>Open filing</Badge>{\' \'}<span className="sr-only">(10-K, accession 1)</span></Link>',
      'a mapped list': '<Link href="/x">{items.map((i) => <Badge key={i}>{i}</Badge>)}</Link>',
      'an array': '<Link href="/x">{[<Badge key="a">A</Badge>, <Badge key="b">B</Badge>]}</Link>',
      'a children attribute': '<Link href="/x" children={<Badge>Go</Badge>} />',
      'a div with a role and a handler': '<div role="button" onClick={go}><Badge>Generate</Badge></div>',
      'a span with a tab stop': '<span tabIndex={0} onKeyDown={go}><Badge>Go</Badge></span>',
      'a span with a role in braces': "<span role={'link'}><Badge>Go</Badge></span>",
      'a span with a role it cannot read': '<span role={role}><Badge>Go</Badge></span>',
      'a div taking a handler by a spread of an object literal': '<div {...{ onClick: go }}><Badge>Go</Badge></div>',
      'a div taking a spread it cannot read': '<div {...handlers}><Badge>Go</Badge></div>',
    }
    // A Badge that is a control itself.
    const controls: Record<string, string> = {
      'a handler': '<Badge onClick={go}>Go</Badge>',
      'a keyboard handler': '<Badge onKeyDown={go}>Go</Badge>',
      'an href': '<Badge href="/x">Go</Badge>',
      'a tab stop': '<Badge tabIndex={0}>Go</Badge>',
      'a tabIndex it cannot read': '<Badge tabIndex={index}>Go</Badge>',
      'a control role': '<Badge role="button">Go</Badge>',
      'a control role in braces': "<Badge role={'button'}>Go</Badge>",
      'a role it cannot read': '<Badge role={role}>Go</Badge>',
      'a handler by a spread of an object literal': '<Badge {...{ onClick: go }}>Go</Badge>',
      'a shorthand handler by a spread': '<Badge {...{ onClick }}>Go</Badge>',
      'a spread it cannot read': '<Badge {...props}>Go</Badge>',
      'a renamed Badge with a handler': "import { Badge as Chip } from '@/components/ui'\nconst a = <Chip onClick={go}>Go</Chip>",
    }
    // Look-alikes: a Badge beside the control's own words or icon, or a Badge outside any control.
    const lookAlikes: Record<string, string> = {
      'a label beside the link text': '<Link href="/x"><Badge>New</Badge> <span>Apple annual report</span></Link>',
      'a label after the link text': '<Link href="/x">Open filing <Badge>New</Badge></Link>',
      'a count on a bell': '<button type="button" aria-label="Notifications"><BellIcon className="h-5 w-5" /><Badge>3</Badge></button>',
      'a conditional label beside text': '<Link href="/x">{ready ? <Badge>New</Badge> : null} Open</Link>',
      'a label in a wrapper beside text': '<Link href="/x"><span><Badge>New</Badge> Annual report</span></Link>',
      'a Badge outside any control': '<div className="flex"><Badge>Live</Badge></div>',
      'a Badge with a status role': '<Badge role="status">Live</Badge>',
      'a Badge that is a focus target, not a tab stop': '<Badge tabIndex={-1}>Saved</Badge>',
      'a Badge with a title and a class': '<Badge variant="warning" title="Superseded" className="max-w-full">Superseded</Badge>',
      'a link beside a Badge, not around it': '<span><Badge variant="warning">Superseded</Badge><Link href="/x">View amendment</Link></span>',
    }
    // Gaps: forms of the rule this scan cannot read (the header names them).
    const gaps: Record<string, string> = {
      'a Badge handed in through a prop': 'function Row({ chip }) { return <Link href="/x">{chip}</Link> }',
      'a Badge another module’s function returns': "import { chip } from './chips'\nconst a = <Link href=\"/x\">{chip()}</Link>",
      'a component of another module that wraps its children in a control': "import { Tap } from './tap'\nconst a = <Tap><Badge>Go</Badge></Tap>",
      'a Badge another module re-exports under another name': "import { Chip } from './chips'\nconst a = <Link href=\"/x\"><Chip>Go</Chip></Link>",
    }
    const score = (forms: Record<string, string>) => Object.entries(forms).filter(([, code]) => !flagged(code)).map(([name]) => name)
    expect(score(faces), 'a control with a Badge face the scan missed').toEqual([])
    expect(score(controls), 'a Badge as a control the scan missed').toEqual([])
    expect(Object.keys(lookAlikes).filter((name) => flagged(lookAlikes[name])), 'a look-alike the scan flagged').toEqual([])
    expect(score(gaps), 'every gap is out of reach, as the header says').toEqual(Object.keys(gaps))
    expect(badgeControls('const a = <Link href="/x">\n  <Badge variant="brand">Generate</Badge>\n</Link>')).toEqual([
      'probe.tsx:1 a Badge is the whole face of a <Link>',
    ])
    expect(badgeControls("const a = <Badge role={'button'} {...rest}>Go</Badge>")).toEqual([
      'probe.tsx:1 a Badge takes role="button"',
      'probe.tsx:1 a Badge takes {...spread}',
    ])
  })

  it('no source file uses a Badge as a control', () => {
    const files = sources()
    expect(files.length, 'the source walk found the app').toBeGreaterThan(200)
    expect(files.filter((rel) => readFileSync(path.join(FRONTEND, rel), 'utf8').includes('<Badge')).length, 'the walk reads the files that render a Badge').toBeGreaterThan(20)
    const offenders = files.flatMap((rel) => badgeControls(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel))
    expect(offenders, 'use a Button, a text link or IDENTITY_LINK for the action, and keep the Badge as its label').toEqual([])
  })
})
