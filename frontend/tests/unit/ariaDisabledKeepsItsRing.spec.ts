import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver, type Binding } from './astBindings'

/**
 * Rule-12 gate for lessons/frontend-busy-controls-stay-focusable.md (e) and DESIGN_SYSTEM §4: no element
 * opacity on an aria-disabled control. A control that is busy or unavailable stays focusable
 * (`aria-disabled` plus an early return, never native `disabled`), so it can still show its focus ring,
 * and an element `opacity` fades that ring with everything else the element paints: under `opacity-50`
 * the brand ring on panel fell from 1.97:1 to 1.37:1 in light and from 2.87:1 to 1.68:1 in dark
 * (PopularTickerChips, Chromium 141). The unavailable look fades what the control draws in (its label's
 * ink, its hairline, a switch track's fill) or a child (`group-aria-disabled:opacity-50` on the
 * content), never the element.
 *
 * The scan reads the TypeScript AST of every .ts and .tsx under app/, components/, features/, hooks/ and
 * lib/. Comments never count. Two clauses, no allowlist:
 *
 *  1. No class token, in any string or template chunk of any of those files (a className, a `cx(…)`
 *     argument, a class list held in a module const), puts an `opacity-*` utility behind a variant that
 *     matches the element's own aria-disabled state: `aria-disabled:`, `aria-[disabled=true]:`, or an
 *     arbitrary variant naming `aria-disabled`, under any other variants (`dark:aria-disabled:hover:`).
 *     `group-aria-disabled:` and `peer-aria-disabled:` style another element, whose opacity does not
 *     reach the control's ring, so they pass.
 *  2. A JSX element that carries an `aria-disabled` attribute holds no `opacity-*` class at all, except
 *     behind `disabled:` (a natively disabled control cannot hold focus, so it shows no ring). This is
 *     the pending-opacity shape, a fade a busy flag picks in JS: AlertBell's
 *     `pending || checking ? 'cursor-progress opacity-60' : ''`. It reads every string and template chunk
 *     of the element's className and of what its identifiers name: a const's initializer or a function
 *     declaration's body, resolved in lexical scope, followed transitively and across modules, through
 *     an import (`@/…` or relative, named or default) and a barrel's re-exports (`export { a as b } from`,
 *     `export * from`). So a shared class list such as `fieldUnavailableClass` is read at each control
 *     that takes it, whatever variant it is written behind.
 *
 * What it cannot see: a className or an `aria-disabled` that arrives through a prop or a props spread
 * (a parameter holds what the caller passes); a class list reached through a namespace import
 * (`import * as`; the app has none) or held in a package; an `opacity` set by a `style` prop or by a
 * rule in globals.css (it has none keyed to aria-disabled); an ancestor's opacity.
 */

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']

function walk(dir: string, out: string[]): string[] {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(p) && !p.endsWith('.d.ts')) out.push(p)
  }
  return out
}

/** `dark:aria-disabled:hover:!opacity-50` is variants dark, aria-disabled, hover and the utility
    `!opacity-50`. A colon inside brackets (`[&:hover]:`, `aria-[disabled=true]:`) does not split. */
function parseToken(token: string): { variants: string[]; utility: string } {
  const parts: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i += 1) {
    const c = token[i]
    if (c === '[' || c === '(') depth += 1
    else if (c === ']' || c === ')') depth -= 1
    else if (c === ':' && depth === 0) {
      parts.push(token.slice(start, i))
      start = i + 1
    }
  }
  return { variants: parts, utility: token.slice(start) }
}

/** The element-opacity utility, with `!` or an arbitrary value: not `bg-opacity-*` or `transition-opacity`. */
const fadesElement = (utility: string) => /^!?opacity-/.test(utility)
/** A variant that matches the element's own aria-disabled state. */
const ownAriaDisabled = (variant: string) =>
  variant === 'aria-disabled' || /^aria-\[disabled\b/.test(variant) || (variant.startsWith('[') && variant.includes('aria-disabled'))

const isChunk = (n: ts.Node): n is ts.StringLiteralLike | ts.TemplateHead | ts.TemplateMiddle | ts.TemplateTail =>
  ts.isStringLiteralLike(n) || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)
const tokensOf = (text: string) => text.split(/\s+/).filter(Boolean)

interface Offender {
  line: number
  token: string
  /** `variant`: clause 1. `element`: clause 2. */
  clause: 'variant' | 'element'
}

/** A source file's text, or undefined when there is no such file. */
type Read = (file: string) => string | undefined

interface Module {
  file: string
  sf: ts.SourceFile
  visible: (ref: ts.Identifier) => Binding | undefined
  /** Local name to the app module and the exported name an import brings in. */
  imports: Map<string, { file: string; name: string }>
}

/** What a name holds, and the module whose names it is written in. */
interface Held {
  node: ts.Node
  mod: Module
}

const hasModifier = (n: ts.Node, kind: ts.SyntaxKind) =>
  ts.canHaveModifiers(n) && (ts.getModifiers(n)?.some((m) => m.kind === kind) ?? false)

/**
 * The scan over one set of files (`read`), with `@/` resolved against `root`. Returns, for a file, every
 * offending class token in it and how many aria-disabled elements it holds.
 */
function fadeScanner(read: Read, root: string): (file: string) => { offenders: Offender[]; controls: number } {
  const modules = new Map<string, Module | undefined>()

  /** The app file an import specifier names; undefined for a package. */
  const resolve = (from: string, specifier: string): string | undefined => {
    const base = specifier.startsWith('@/')
      ? path.join(root, specifier.slice(2))
      : specifier.startsWith('.')
        ? path.resolve(path.dirname(from), specifier)
        : undefined
    if (!base) return undefined
    return [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts'), path.join(base, 'index.tsx')].find(
      (file) => /\.tsx?$/.test(file) && read(file) !== undefined,
    )
  }

  const load = (file: string): Module | undefined => {
    if (modules.has(file)) return modules.get(file)
    const source = read(file)
    let mod: Module | undefined
    if (source !== undefined) {
      const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
      const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
      const imports: Module['imports'] = new Map()
      for (const s of sf.statements) {
        if (!ts.isImportDeclaration(s) || !ts.isStringLiteral(s.moduleSpecifier) || !s.importClause) continue
        const target = resolve(file, s.moduleSpecifier.text)
        if (!target) continue
        const { name, namedBindings } = s.importClause
        if (name) imports.set(name.text, { file: target, name: 'default' })
        if (namedBindings && ts.isNamedImports(namedBindings)) {
          for (const el of namedBindings.elements) imports.set(el.name.text, { file: target, name: (el.propertyName ?? el.name).text })
        }
      }
      mod = { file, sf, visible: bindingResolver(sf), imports }
    }
    modules.set(file, mod)
    return mod
  }

  /** What `name` exported from `mod` holds, through a barrel's re-exports. */
  const exported = (mod: Module, name: string, seen: Set<string>): Held | undefined => {
    if (seen.has(mod.file)) return undefined
    seen.add(mod.file)
    const stars: Module[] = []
    for (const s of mod.sf.statements) {
      if (ts.isVariableStatement(s) && hasModifier(s, ts.SyntaxKind.ExportKeyword)) {
        for (const d of s.declarationList.declarations) {
          if (ts.isIdentifier(d.name) && d.name.text === name && d.initializer) return { node: d.initializer, mod }
        }
      } else if (ts.isFunctionDeclaration(s) && s.body && hasModifier(s, ts.SyntaxKind.ExportKeyword)) {
        const exportedAs = hasModifier(s, ts.SyntaxKind.DefaultKeyword) ? 'default' : s.name?.text
        if (exportedAs === name) return { node: s.body, mod }
      } else if (ts.isExportAssignment(s) && !s.isExportEquals && name === 'default') {
        return { node: s.expression, mod }
      } else if (ts.isExportDeclaration(s)) {
        const from = s.moduleSpecifier && ts.isStringLiteral(s.moduleSpecifier) ? resolve(mod.file, s.moduleSpecifier.text) : undefined
        const target = from ? load(from) : undefined
        if (!s.exportClause) {
          if (target) stars.push(target)
        } else if (ts.isNamedExports(s.exportClause)) {
          const el = s.exportClause.elements.find((e) => e.name.text === name)
          if (!el) continue
          const local = el.propertyName ?? el.name
          if (s.moduleSpecifier) return target ? exported(target, local.text, seen) : undefined
          return ts.isIdentifier(local) ? held(local, mod) : undefined
        }
      }
    }
    for (const star of stars) {
      const found = exported(star, name, seen)
      if (found) return found
    }
    return undefined
  }

  /**
   * What the name at `ref` holds: a const's initializer or a function declaration's body, in this module
   * or in the one it is imported from. A parameter or a destructured prop holds what the caller passes,
   * which no file shows, and it shadows an import of the same name.
   */
  const held = (ref: ts.Identifier, mod: Module): Held | undefined => {
    const binding = mod.visible(ref)
    if (binding) {
      const node = binding.init ?? (ts.isFunctionDeclaration(binding.decl) ? binding.alias : undefined)
      return node ? { node, mod } : undefined
    }
    const imported = mod.imports.get(ref.text)
    const from = imported && load(imported.file)
    return from ? exported(from, imported.name, new Set()) : undefined
  }

  /** The class text a className expression can hold: its own chunks, and those the names in it reach. */
  const classChunks = (expr: ts.Node, mod: Module, seen: Set<ts.Node>, out: string[]): string[] => {
    const visit = (n: ts.Node): void => {
      if (isChunk(n)) out.push(n.text)
      else if (ts.isIdentifier(n)) {
        // `styles.chip` names a property, not a binding.
        if (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) return
        const target = held(n, mod)
        if (!target || seen.has(target.node)) return
        seen.add(target.node)
        classChunks(target.node, target.mod, seen, out)
      }
      ts.forEachChild(n, visit)
    }
    visit(expr)
    return out
  }

  return (file) => {
    const mod = load(file)
    const offenders: Offender[] = []
    let controls = 0
    if (!mod) return { offenders, controls }
    const { sf } = mod
    const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1

    const visit = (n: ts.Node): void => {
      if (isChunk(n)) {
        for (const token of tokensOf(n.text)) {
          const { variants, utility } = parseToken(token)
          if (fadesElement(utility) && variants.some(ownAriaDisabled)) offenders.push({ line: lineOf(n), token, clause: 'variant' })
        }
      }
      if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
        const attribute = (name: string) =>
          n.attributes.properties.find((a): a is ts.JsxAttribute => ts.isJsxAttribute(a) && a.name.getText(sf) === name)
        const className = attribute('className')?.initializer
        if (attribute('aria-disabled')) {
          controls += 1
          for (const token of className ? classChunks(className, mod, new Set(), []).flatMap(tokensOf) : []) {
            const { variants, utility } = parseToken(token)
            // Clause 1 already reports a fade behind the element's own aria-disabled variant, where it is written.
            if (!fadesElement(utility) || variants.includes('disabled') || variants.some(ownAriaDisabled)) continue
            offenders.push({ line: lineOf(n), token, clause: 'element' })
          }
        }
      }
      ts.forEachChild(n, visit)
    }
    visit(sf)
    return { offenders, controls }
  }
}

/** The offenders of `file` among in-memory `files`, keyed by path under a root of `/app`. */
const tokensAmong = (files: Record<string, string>, file: string) =>
  fadeScanner((f) => files[f], '/app')(file).offenders.map((o) => `${o.clause} ${o.token}`)
const tokensIn = (source: string) => tokensAmong({ '/app/Fixture.tsx': source }, '/app/Fixture.tsx')

describe('no element opacity on an aria-disabled control (rule-12 gate)', () => {
  it('sees an opacity behind the element’s own aria-disabled variant wherever a class list is written, and nothing else', () => {
    expect(
      tokensIn(`
        const CHIP = ['inline-flex rounded-full', 'focus-visible:shadow-ring-brand aria-disabled:opacity-50'].join(' ')
        export const fieldUnavailable = cx('aria-disabled:bg-background-light', 'dark:aria-disabled:hover:!opacity-[.6]')
        const arbitrary = \`rounded \${wide ? 'w-full' : ''} aria-[disabled=true]:opacity-40 [&[aria-disabled=true]]:opacity-30\`
        export const Row = () => <button className="text-sm aria-disabled:opacity-50" />
      `),
    ).toEqual([
      'variant aria-disabled:opacity-50',
      'variant dark:aria-disabled:hover:!opacity-[.6]',
      'variant aria-[disabled=true]:opacity-40',
      'variant [&[aria-disabled=true]]:opacity-30',
      'variant aria-disabled:opacity-50',
    ])
    expect(
      tokensIn(`
        // aria-disabled:opacity-50 would fade the ring too.
        const LOOK = cx(
          'aria-disabled:cursor-not-allowed aria-disabled:text-brand-strong/50 aria-disabled:border-brand-border/50',
          'aria-disabled:bg-opacity-50 aria-disabled:transition-opacity disabled:opacity-50 opacity-70',
        )
        export const Row = () => (
          <button className="group aria-disabled:text-error-light/50">
            <span className="group-aria-disabled:opacity-50 peer-aria-disabled:opacity-50" />
          </button>
        )
      `),
    ).toEqual([])
  })

  it('sees any other opacity class on an element that carries aria-disabled, through same-file names, and nothing else', () => {
    // AlertBell's shape before this gate: the busy flag picks the fade in JS.
    expect(
      tokensIn(`
        export const Bell = ({ pending, checking }) => (
          <button
            disabled={checking}
            aria-disabled={pending || undefined}
            className={cx('h-7 w-7 rounded-lg', pending || checking ? 'cursor-progress opacity-60' : '', className)}
          />
        )
      `),
    ).toEqual(['element opacity-60'])
    expect(
      tokensIn(`
        const CHIP = ['rounded-full', 'hover:opacity-80'].join(' ')
        const dim = (busy) => (busy ? 'opacity-50' : '')
        function look(busy) {
          return cx(CHIP, dim(busy))
        }
        export const Chip = ({ busy }) => {
          const faded = \`\${busy ? 'opacity-40' : ''} px-3\`
          return (
            <>
              <button aria-disabled={busy || undefined} className={look(busy)} />
              <Button aria-disabled={busy || undefined} className={faded} />
            </>
          )
        }
      `),
    ).toEqual(['element hover:opacity-80', 'element opacity-50', 'element opacity-40'])
    expect(
      tokensIn(`
        const dim = 'opacity-50'
        export const Row = ({ busy, dim }) => (
          <li className="opacity-70">
            <button disabled={busy} className="opacity-60" />
            <button aria-disabled={busy || undefined} className={cx('group disabled:opacity-60 disabled:hover:opacity-60', dim, styles.dim)}>
              <span className="opacity-50 group-aria-disabled:opacity-50" />
            </button>
          </li>
        )
      `),
    ).toEqual([])
  })

  it('follows a class list across modules: an import, a barrel’s re-exports and a default export, and nothing a package or a parameter holds', () => {
    const files = {
      '/app/components/ui/Input.tsx': `
        const FIELD = 'w-full rounded-lg disabled:opacity-60'
        export function inputClasses() {
          return cx(FIELD)
        }
        export const fieldUnavailableClass = cx('aria-disabled:cursor-not-allowed', 'opacity-60')
      `,
      '/app/components/ui/Look.ts': `
        const dim = 'hover:opacity-80'
        export { dim as busyLook }
        export default 'opacity-30'
      `,
      '/app/components/ui/index.ts': `
        export { fieldUnavailableClass as unavailable, inputClasses } from './Input'
        export * from './Look'
      `,
      '/app/features/Row.tsx': `
        import { clsx } from 'clsx'
        import { unavailable, inputClasses, busyLook } from '@/components/ui'
        import fade from '../components/ui/Look'
        export const Row = ({ busy }) => (
          <>
            <select aria-disabled={busy || undefined} className={clsx(inputClasses(), unavailable)} />
            <button aria-disabled={busy || undefined} className={busy ? busyLook : fade} />
          </>
        )
      `,
      '/app/features/Quiet.tsx': `
        import { clsx } from 'clsx'
        import { unavailable, busyLook } from '@/components/ui'
        import { missing } from '@/components/ui/Nowhere'
        export const Quiet = ({ busy, unavailable: passed }) => (
          <>
            <select className={clsx(unavailable, busyLook)} />
            <button aria-disabled={busy || undefined} className={clsx(passed, missing, clsx)} />
          </>
        )
        export const Shadowed = ({ busy, busyLook }) => <button aria-disabled={busy || undefined} className={busyLook} />
      `,
    }
    // Each is reported at the control that takes it: its own module holds no aria-disabled variant to report.
    expect(tokensAmong(files, '/app/features/Row.tsx')).toEqual(['element opacity-60', 'element hover:opacity-80', 'element opacity-30'])
    expect(tokensAmong(files, '/app/components/ui/Input.tsx')).toEqual([])
    expect(tokensAmong(files, '/app/features/Quiet.tsx')).toEqual([])
  })

  it('no class fades an aria-disabled control as a whole', () => {
    const offenders: string[] = []
    let controls = 0
    const scan = fadeScanner((file) => (existsSync(file) && statSync(file).isFile() ? readFileSync(file, 'utf8') : undefined), frontendRoot)
    for (const file of ROOTS.flatMap((root) => walk(path.join(frontendRoot, root), []))) {
      const found = scan(file)
      controls += found.controls
      for (const o of found.offenders) offenders.push(`${path.relative(frontendRoot, file)}:${o.line} ${o.token}`)
    }
    // The scan reached the app: its aria-disabled controls are in what it read.
    expect(controls).toBeGreaterThan(0)
    expect(
      offenders,
      'An element opacity on an aria-disabled control fades its focus ring: the control stays focusable. Fade what ' +
        'it draws in instead (label ink and hairline at /50 on the tokens it already uses, both themes), or a child ' +
        '(`group-aria-disabled:opacity-50`); a natively disabled state keeps `disabled:opacity-*`. ' +
        'DESIGN_SYSTEM §4, lessons/frontend-busy-controls-stay-focusable.md (e).',
    ).toEqual([])
  })
})
