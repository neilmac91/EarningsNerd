/* =============================================================================
   trailingArrowInk.spec.ts: a trailing arrow takes its control's ink
   -----------------------------------------------------------------------------
   TrailingArrowLabel draws a label's last word and its arrow in one no-wrap
   run, the arrow aria-hidden and with no ink of its own (DESIGN_SYSTEM.md §4,
   Trailing arrow). Its arrowClassName sizes and spaces the arrow and may move
   it, never an ink: an arrow given a colour parts from its label's ink and from
   the label's hover, and no other gate reads it (chief design on #1911,
   6556730911). So this scan fails a text-, fill- or stroke- class in every
   arrowClassName the app writes, in the component's own default and in the
   classes the component writes on its run and its arrow, behind any variant
   prefix (dark:, hover:, group-hover:) and with Tailwind's `!` before or
   after: the arrow holds no text, so none of those has a job there, and the
   run keeps its control's ink.

   It reads each file's TypeScript AST (tests/unit/classListScan.ts's parser),
   so comments never count. A value is read to its strings through cx() and
   clsx(), a ternary's arms and `&&`/`||`; one the scan cannot read that way (a
   variable, another call, a template with a substitution) fails as unread
   rather than passing unseen. The component's own classes are every string
   and template chunk in its class attributes. Out of reach: an arrowClassName
   passed in a spread of props, a class a parent sets on its svg, and the
   classes of an icon that is not this component's. Planted cases hold the
   reader.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { CLASS_ATTRIBUTE, literalTexts, parse, sourceFiles, tokensOf, unwrapped } from './classListScan'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const COMPONENT = 'components/ui/TrailingArrowLabel.tsx'
const PROP = 'arrowClassName'
// An ink: a text-, fill- or stroke- class, behind any variant prefix and with `!` either side.
const INK = /(?:^|:)!?(?:text|fill|stroke)-/
const JOINERS = new Set(['cx', 'clsx'])

interface Site {
  file: string
  line: number
  // The value's strings, or null where the scan cannot read them.
  texts: string[] | null
}

/** The strings a class value is built from, or null where it is not built from strings alone. */
function readable(node: ts.Node | undefined): string[] | null {
  if (!node) return []
  if (ts.isJsxExpression(node)) return readable(node.expression)
  const expr = unwrapped(node as ts.Expression)
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return [expr.text]
  if (expr.kind === ts.SyntaxKind.TrueKeyword || expr.kind === ts.SyntaxKind.FalseKeyword || expr.kind === ts.SyntaxKind.NullKeyword) return []
  if (ts.isIdentifier(expr) && expr.text === 'undefined') return []
  const all = (parts: (ts.Node | undefined)[]) => {
    const out: string[] = []
    for (const part of parts) {
      const texts = readable(part)
      if (texts === null) return null
      out.push(...texts)
    }
    return out
  }
  if (ts.isCallExpression(expr) && ts.isIdentifier(expr.expression) && JOINERS.has(expr.expression.text)) return all([...expr.arguments])
  // A ternary's arms count together; its condition sets no class.
  if (ts.isConditionalExpression(expr)) return all([expr.whenTrue, expr.whenFalse])
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) return readable(expr.right)
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.BarBarToken) return all([expr.left, expr.right])
  return null
}

/** Every arrowClassName in `source`: each JSX attribute of that name, and each binding of it with a default. */
function arrowClassSites(source: string, file: string): Site[] {
  const sourceFile = parse(source, file)
  const sites: Site[] = []
  const at = (node: ts.Node) => sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
  const visit = (node: ts.Node): void => {
    if (ts.isJsxAttribute(node) && node.name.getText(sourceFile) === PROP) {
      sites.push({ file, line: at(node), texts: node.initializer ? readable(node.initializer) : null })
    } else if (ts.isBindingElement(node) && node.initializer && (node.propertyName ?? node.name).getText(sourceFile) === PROP) {
      sites.push({ file, line: at(node), texts: readable(node.initializer) })
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return sites
}

/** The tokens of every string and template chunk in `source`'s class attributes: the classes a component writes itself. */
function ownClassTokens(source: string, file: string): string[] {
  const sourceFile = parse(source, file)
  const texts: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxAttribute(node) && CLASS_ATTRIBUTE.test(node.name.getText(sourceFile)) && node.initializer) texts.push(...literalTexts(node.initializer))
    else ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return texts.flatMap(tokensOf)
}

const inks = (site: Site) => (site.texts ?? []).flatMap(tokensOf).filter((token) => INK.test(token))
const where = (site: Site) => `${site.file}:${site.line}`

function scan(): Site[] {
  return sourceFiles(ROOT, SCAN_DIRS).flatMap((file) => arrowClassSites(fs.readFileSync(path.join(ROOT, file), 'utf8'), file))
}

describe('a trailing arrow takes its control ink (DESIGN_SYSTEM.md §4, Trailing arrow)', () => {
  const sites = scan()

  it('reads the component default and every arrowClassName the app writes', () => {
    const files = new Set(sites.map((site) => site.file))
    // The default and the three callers that size their own arrow (E275); the dashboard's take the default.
    for (const file of [COMPONENT, 'features/marketing/components/HeroExample.tsx', 'features/filings/components/ComparePeriodsCard.tsx', 'app/waitlist/page.tsx']) {
      expect(files.has(file), `${file}: the scan reads its arrowClassName`).toBe(true)
    }
    const fallback = sites.find((site) => site.file === COMPONENT)
    expect(fallback?.texts?.flatMap(tokensOf), 'the component default sizes and spaces the arrow').toEqual(['ml-1', 'h-4', 'w-4'])
  })

  it('reads every arrowClassName to its strings', () => {
    expect(sites.filter((site) => site.texts === null).map(where), 'an arrowClassName the scan cannot read').toEqual([])
  })

  it('gives no arrow an ink: no text-, fill- or stroke- class under any variant', () => {
    expect(sites.filter((site) => inks(site).length > 0).map((site) => `${where(site)} ${inks(site).join(' ')}`)).toEqual([])
  })

  it('adds no ink of its own: no text-, fill- or stroke- class the component writes on its run or its arrow', () => {
    const own = ownClassTokens(fs.readFileSync(path.join(ROOT, COMPONENT), 'utf8'), COMPONENT)
    expect(own, 'the scan reads the classes the component writes').toEqual(expect.arrayContaining(['whitespace-nowrap', 'align-text-bottom']))
    expect(own.filter((token) => INK.test(token))).toEqual([])
  })
})

describe('the arrowClassName reader, on planted sources', () => {
  const planted = (source: string) => arrowClassSites(source, 'planted.tsx')

  it('finds an ink in a plain string, behind a variant, in a joiner, in either arm and after `!`', () => {
    const sites = planted(`
      export const A = () => <TrailingArrowLabel arrowClassName="ml-1 h-4 w-4 text-brand-strong">Open</TrailingArrowLabel>
      export const B = () => <TrailingArrowLabel arrowClassName={cx('h-4 w-4', 'dark:group-hover:fill-white')}>Open</TrailingArrowLabel>
      export const C = ({ open }: { open: boolean }) => <TrailingArrowLabel arrowClassName={clsx('h-4', open ? 'w-4' : '!stroke-current')}>Open</TrailingArrowLabel>
      export const D = ({ on }: { on: boolean }) => <TrailingArrowLabel arrowClassName={cx('h-4', on && 'hover:text-brand-strong-dark!')}>Open</TrailingArrowLabel>
    `)
    expect(sites.map(inks)).toEqual([['text-brand-strong'], ['dark:group-hover:fill-white'], ['!stroke-current'], ['hover:text-brand-strong-dark!']])
  })

  it('reads the default a destructured prop takes', () => {
    const sites = planted(`
      export function TrailingArrowLabel({ children, arrowClassName = 'ml-1 h-4 w-4 text-current' }: { children: string; arrowClassName?: string }) {
        return <span className={arrowClassName}>{children}</span>
      }
    `)
    expect(sites.map(inks)).toEqual([['text-current']])
  })

  it('fails a value it cannot read rather than passing it unseen', () => {
    const sites = planted(`
      const tone = 'text-brand-strong'
      export const A = () => <TrailingArrowLabel arrowClassName={tone}>Open</TrailingArrowLabel>
      export const B = () => <TrailingArrowLabel arrowClassName={\`h-4 \${tone}\`}>Open</TrailingArrowLabel>
      export const C = () => <TrailingArrowLabel arrowClassName={arrowFor('next')}>Open</TrailingArrowLabel>
    `)
    expect(sites.map((site) => site.texts)).toEqual([null, null, null])
  })

  it('passes size, spacing and motion, and never counts a comment', () => {
    const sites = planted(`
      export const A = () => (
        <>
          {/* arrowClassName="text-brand-strong" */}
          <TrailingArrowLabel arrowClassName={cx('ml-1.5 h-3.5 w-3.5', 'transition-transform duration-fast group-hover:translate-x-0.5 motion-reduce:group-hover:translate-x-0')}>Open</TrailingArrowLabel>
        </>
      )
    `)
    expect(sites).toHaveLength(1)
    expect(sites.map(inks)).toEqual([[]])
  })

  it('reads the classes a component writes itself, on its run, on its arrow and in a template', () => {
    const own = ownClassTokens(`
      export function Label({ children, arrowClassName = 'ml-1 h-4 w-4', tone }: { children: string; arrowClassName?: string; tone: string }) {
        return (
          <span className="whitespace-nowrap hover:text-brand-strong">
            {children}
            <ArrowRightIcon aria-hidden="true" className={cx('inline-block align-text-bottom dark:fill-white', arrowClassName)} />
            <span className={\`h-4 stroke-\${tone}\`} />
          </span>
        )
      }
    `, 'planted.tsx')
    expect(own.filter((token) => INK.test(token))).toEqual(['hover:text-brand-strong', 'dark:fill-white', 'stroke-'])
  })
})
