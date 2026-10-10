import { readdirSync, readFileSync, statSync } from 'node:fs'
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
 *     of the element's className and of what its identifiers name in the same file (a const's
 *     initializer, a function declaration's body), resolved in lexical scope and followed transitively.
 *
 * What it cannot see: a class list imported from another module and held behind no `aria-disabled:`
 * variant (clause 2 follows same-file names only); a className or an `aria-disabled` that arrives through
 * a props spread; an `opacity` set by a `style` prop or by a rule in globals.css (it has none keyed to
 * aria-disabled); an ancestor's opacity.
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

/** Every offending class token in one source file, and how many aria-disabled elements it holds. */
function fadingTokens(source: string, fileName: string): { offenders: Offender[]; controls: number } {
  const kind = fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, kind)
  const visible = bindingResolver(sf)
  const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
  const offenders: Offender[] = []
  let controls = 0

  /** The class text a className expression can hold: its own chunks, and those its same-file names reach. */
  const classChunks = (expr: ts.Node, seen: Set<Binding>, out: string[]): string[] => {
    const visit = (n: ts.Node): void => {
      if (isChunk(n)) out.push(n.text)
      else if (ts.isIdentifier(n)) {
        // `styles.chip` names a property, not a local binding.
        if (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) return
        // A const's initializer or a function declaration's body. A parameter or a destructured prop
        // holds what the caller passes, which this file does not show.
        const binding = visible(n)
        const held = binding && (binding.init ?? (ts.isFunctionDeclaration(binding.decl) ? binding.alias : undefined))
        if (!binding || !held || seen.has(binding)) return
        seen.add(binding)
        classChunks(held, seen, out)
      }
      ts.forEachChild(n, visit)
    }
    visit(expr)
    return out
  }

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
        for (const token of className ? classChunks(className, new Set(), []).flatMap(tokensOf) : []) {
          const { variants, utility } = parseToken(token)
          // Clause 1 already reports a fade behind the element's own aria-disabled variant.
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

const tokensIn = (source: string) => fadingTokens(source, 'Fixture.tsx').offenders.map((o) => `${o.clause} ${o.token}`)

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

  it('no class fades an aria-disabled control as a whole', () => {
    const offenders: string[] = []
    let controls = 0
    for (const file of ROOTS.flatMap((root) => walk(path.join(frontendRoot, root), []))) {
      const found = fadingTokens(readFileSync(file, 'utf8'), file)
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
