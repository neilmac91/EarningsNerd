/* =============================================================================
   pulseMotionReduce.spec.ts — guardrail (rule 12; DESIGN_SYSTEM §11 Reduced motion)
   -----------------------------------------------------------------------------
   An infinite pulse or ping loop (`animate-pulse`, `animate-ping`) ships with its
   reduced-motion variant in the SAME class string: the loop is either
   `motion-safe:` itself, or the string carries `motion-reduce:` + the loop's own
   variant prefix + `animate-none`. The prefix must match because a variant raises
   specificity: `hover:animate-pulse motion-reduce:animate-none` still pulses on
   hover under reduced motion, so it fails here.

   Why a gate: the Copilot's "Reading the filing…" dot pulsed under reduced
   motion while every other pulse in the app was guarded (critique v3.1 DC-PULSE),
   and nothing in CI looked. A loop composed apart from its guard (`cx('animate-
   pulse', …)`) fails too: put the guard in the same literal.

   Scope: every tracked, non-binary file under each directory Tailwind reads
   classes from (tailwind.config.js `content`: app, components, features, hooks
   and lib today; designSystemDoneGate.spec.ts keeps every class-composing module
   inside one), listed by `git ls-files`, so a new file counts once it is staged.
   Code files are read through the TypeScript AST, so a comment never counts; any
   other text file is read line by line with CSS comments removed (an `@apply`
   line is a class string). No allowlist: every existing loop is guarded.
============================================================================= */

import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const FRONTEND = path.join(__dirname, '../..')
/** The directories of tailwind.config.js `content` (every entry is `./<dir>/**…`), read from the config Tailwind uses. */
const SCAN_DIRS: string[] = (createRequire(import.meta.url)('../../tailwind.config.js').content as string[]).map((glob) => {
  const dir = /^\.\/([^/*]+)\//.exec(glob)?.[1]
  if (!dir) throw new Error(`content entry ${JSON.stringify(glob)} is not ./<dir>/**; teach this gate its shape`)
  return dir
})
const BINARY = /\.(png|jpe?g|gif|webp|avif|ico|svg|woff2?|ttf|otf|eot|mp4|webm|pdf|zip)$/i
const CODE = /\.(js|jsx|ts|tsx|mjs|cjs)$/

/** A pulse/ping utility behind any variant prefix (dark:, [&>:last-child]:after:, …), with an optional `!`. */
const LOOP = /^(.*?)!?animate-(pulse|ping)$/

/** The unguarded pulse/ping tokens of one class string. */
function unguardedLoops(classString: string): string[] {
  const tokens = classString.split(/\s+/).filter(Boolean)
  const present = new Set(tokens.map((t) => t.replace(/!(?=animate-none$)/, '')))
  return tokens.filter((token) => {
    const match = LOOP.exec(token)
    if (!match) return false
    const prefix = match[1]
    if (prefix.split(':').includes('motion-safe')) return false
    return !present.has(`motion-reduce:${prefix}animate-none`) && !present.has(`${prefix}motion-reduce:animate-none`)
  })
}

/** Every string literal and template chunk in a code file (comments are not nodes). */
function codeStrings(file: string, source: string): string[] {
  const kind = /x$/.test(file) ? ts.ScriptKind.TSX : /\.m?jsx?$|\.cjs$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    if (ts.isStringLiteralLike(n) || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)) out.push(n.text)
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return out
}

function scan(): { files: number; loops: number; offenders: string[] } {
  const tracked = execFileSync('git', ['ls-files', '-z', '--', ...SCAN_DIRS], { cwd: FRONTEND, encoding: 'utf8' })
    .split('\0')
    .filter((f) => f && !BINARY.test(f))
  let loops = 0
  const offenders: string[] = []
  for (const file of tracked) {
    const source = fs.readFileSync(path.join(FRONTEND, file), 'utf8')
    const strings = CODE.test(file) ? codeStrings(file, source) : source.replace(/\/\*[\s\S]*?\*\//g, '').split('\n')
    for (const s of strings) {
      loops += s.split(/\s+/).filter((t) => LOOP.test(t)).length
      for (const token of unguardedLoops(s)) offenders.push(`${file}: ${token}`)
    }
  }
  return { files: tracked.length, loops, offenders }
}

describe('pulse/ping loops respect reduced motion', () => {
  it('reads a class string the way the CSS cascade does', () => {
    expect(unguardedLoops('h-1.5 w-1.5 animate-pulse rounded-full')).toEqual(['animate-pulse'])
    expect(unguardedLoops('animate-pulse motion-reduce:animate-none')).toEqual([])
    expect(unguardedLoops('animate-ping motion-reduce:!animate-none')).toEqual([])
    expect(unguardedLoops('motion-safe:animate-ping')).toEqual([])
    expect(unguardedLoops('[&>:last-child]:after:animate-pulse motion-reduce:[&>:last-child]:after:animate-none')).toEqual([])
    expect(unguardedLoops('dark:animate-pulse dark:motion-reduce:animate-none')).toEqual([])
    // The guard must carry the loop's own variants, or the variant's specificity wins under reduced motion.
    expect(unguardedLoops('hover:animate-pulse motion-reduce:animate-none')).toEqual(['hover:animate-pulse'])
    expect(unguardedLoops('animate-pulse motion-reduce:transition-none')).toEqual(['animate-pulse'])
  })

  it('finds no unguarded loop in any directory Tailwind reads classes from', () => {
    expect(SCAN_DIRS).toEqual(expect.arrayContaining(['app', 'components', 'features', 'hooks', 'lib']))
    const { files, loops, offenders } = scan()
    // Anti-vacuity: a broken walk and a clean tree both look green, so the scan must see the app and its loops.
    expect(files).toBeGreaterThan(100)
    expect(loops).toBeGreaterThanOrEqual(3)
    expect(
      offenders,
      'Add the reduced-motion variant in the same class string: motion-reduce:<same variants>animate-none (DESIGN_SYSTEM §11).',
    ).toEqual([])
  })
})
