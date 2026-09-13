import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Structural gate for DESIGN_SYSTEM.md §12, the definition-of-done for any theme/token change.
 *
 * CLAUDE.md rule 11 makes §12's grep the FORMAL done-gate ("Done-gate = the legacy-color grep in
 * DESIGN_SYSTEM.md returns nothing AND both themes verified on preview"), and rule 12, two lines
 * below it, says exactly that kind of rule must carry machine enforcement because "prose-only
 * rules rot". This one has rotted twice by the project's own record: tailwind.config.js says the
 * font-var wiring "was missed in BOTH the v2 and v2.1 exports", and that "fontFamily.system /
 * .grotesque were PURGED at the v2 cutover … The v2.1 export resurrected them; #497 re-removed
 * them."
 *
 * Two of §12's five items are mechanically checkable and are gated here:
 *   - item 2, grep #1 (legacy brand colors / type roles) — the pattern is READ FROM THE DOC rather
 *     than copied, so the gate can never guard something other than what rule 11 names.
 *   - item 3, the font-var packaging gate.
 *
 * Deliberately NOT gated:
 *   - item 2's second grep (raw durations / cubic-bezier outside token homes). It returns ~39 hits
 *     today, overwhelmingly false positives — prose in comments, "308s"/"404s" in copy, and the
 *     sanctioned globals.css token home. It needs a narrowed pattern or a frozen allowlist before
 *     it can be a gate; gating it as written would land red and be disabled within a week.
 *   - item 1 (app-wide) and item 4 (both themes on a Vercel preview) are not source-checkable.
 *     Item 5 is the ordinary gate command list. CI ≠ correct visuals, and this spec does not
 *     pretend otherwise.
 *
 * The font-var half is an explicit, BIDIRECTIONAL allowlist, not a blanket "must lead with a
 * next/font var" rule — that naive form fails on four sanctioned sites today. Per
 * lessons/arch-structural-gates-over-prose-rules.md, "fixing" a sanctioned exception must fail
 * here too, so each exception is pinned to its exact shape rather than merely skipped.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (rel: string) => readFileSync(path.join(frontendDir, rel), 'utf8')

const designSystem = read('DESIGN_SYSTEM.md')
const tailwindConfig = read('tailwind.config.js')
const globalsCss = read('app/globals.css')
const layout = read('app/layout.tsx')

/** The three next/font variables. next/font self-hosts under hashed family names exposed ONLY as
 *  these vars, so a literal-only stack silently never resolves. */
const NEXT_FONT_VARS = ['--font-inter', '--font-geist-mono', '--font-newsreader'] as const

// --------------------------------------------------------------------------- item 2, grep #1
describe('DESIGN_SYSTEM §12 item 2 — legacy colors and type roles are gone', () => {
  /** Pull the grep's own pattern out of the doc, so doc and gate cannot drift apart. */
  const legacyPattern = (): RegExp => {
    const m = designSystem.match(/grep -rnE '((?:[^'\\]|\\.)*)' app components features/)
    if (!m) throw new Error('DESIGN_SYSTEM.md §12 no longer contains the legacy-color grep')
    return new RegExp(m[1])
  }

  const SKIP = new Set(['node_modules', '.next', '__pycache__', 'dist', 'coverage'])
  /** `grep -rnE` reads every file under the directories it is pointed at and skips only binaries.
   *  This scanner does the same instead of allowlisting source extensions: an allowlist quietly
   *  narrows the gate below the rule it claims to enforce, so a legacy token in
   *  `features/analysis/demo/demo-analysis.json` — or in any data/asset file added later — would
   *  pass CI and still fail the founder's own §12 grep. */
  const BINARY = /\.(png|jpe?g|gif|webp|avif|ico|woff2?|ttf|otf|eot|mp4|webm|pdf|zip)$/i
  const walk = (dir: string, acc: string[] = []): string[] => {
    for (const entry of readdirSync(dir)) {
      if (SKIP.has(entry)) continue
      const full = path.join(dir, entry)
      if (statSync(full).isDirectory()) walk(full, acc)
      else if (!BINARY.test(entry)) acc.push(full)
    }
    return acc
  }

  it('reads its pattern from the doc rule 11 actually names', () => {
    const pattern = legacyPattern()
    // Sanity: the extracted pattern must still match the things it exists to ban, or a doc edit
    // could quietly neuter the gate while leaving it green.
    expect(pattern.test('text-emerald-500')).toBe(true)
    expect(pattern.test('font-grotesque')).toBe(true)
    expect(pattern.test('text-text-primary-light')).toBe(false)
  })

  it('returns zero hits across app, components and features', () => {
    const pattern = legacyPattern()
    const files = ['app', 'components', 'features'].flatMap((d) => walk(path.join(frontendDir, d)))
    expect(files.length).toBeGreaterThan(100)

    const hits: string[] = []
    for (const file of files) {
      readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
        if (pattern.test(line)) hits.push(`${path.relative(frontendDir, file)}:${i + 1}: ${line.trim()}`)
      })
    }
    expect(hits, `legacy tokens found — DESIGN_SYSTEM §12 item 2:\n${hits.join('\n')}`).toEqual([])
  })
})

// --------------------------------------------------------------------------- item 3
describe('DESIGN_SYSTEM §12 item 3 — every font stack reaches its next/font variable', () => {
  /** Stacks and :root vars that must LEAD with the named next/font variable. */
  const VAR_LED_STACKS: Record<string, string> = {
    heading: '--font-inter',
    editorial: '--font-newsreader',
    data: '--font-geist-mono',
    mono: '--font-geist-mono',
  }
  const VAR_LED_CSS_VARS: Record<string, string> = {
    '--font-heading': '--font-inter',
    '--font-editorial': '--font-newsreader',
    '--font-data': '--font-geist-mono',
  }
  /** The four sanctioned exceptions, each pinned to its exact shape at the end of this block. */
  const SANCTIONED_STACKS = ['body', 'sans']
  const SANCTIONED_CSS_VARS = ['--font-body', '--font-active']

  /** `key: [...]` out of tailwind.config.js's fontFamily block. */
  const stack = (key: string): string => {
    const m = tailwindConfig.match(new RegExp(`\\n\\s*${key}: \\[([^\\]]*)\\]`))
    if (!m) throw new Error(`tailwind.config.js has no fontFamily.${key} stack`)
    return m[1]
  }
  /** `--name: <value>;` out of globals.css. */
  const cssVar = (name: string): string => {
    const m = globalsCss.match(new RegExp(`\\n\\s*${name}: ([^;]*);`))
    if (!m) throw new Error(`app/globals.css has no ${name}`)
    return m[1].trim()
  }

  /** The fontFamily block, delimited by the indentation of its own opening line, so a brace that
   *  later appears inside one of its comments cannot throw the scan off. */
  const fontFamilyBlock = (): string => {
    const m = tailwindConfig.match(/\n(\s*)fontFamily: \{\n([\s\S]*?)\n\1\},/)
    if (!m) throw new Error('tailwind.config.js has no fontFamily block')
    return m[2]
  }

  // A fixed table of names checks only the stacks that existed when it was written, so a stack or
  // var added by a later theme change is simply never looked at — the same "gate narrower than the
  // rule it enforces" defect as an extension allowlist. These two tests close that: every declared
  // name must be classified as var-led or sanctioned, so adding one without deciding which fails.
  it('classifies every fontFamily stack, so a new one cannot slip past ungated', () => {
    const declared = [...fontFamilyBlock().matchAll(/\n\s*([A-Za-z_$][\w$]*): \[/g)].map((m) => m[1])
    expect(declared.slice().sort()).toEqual(
      [...Object.keys(VAR_LED_STACKS), ...SANCTIONED_STACKS].sort(),
    )
  })

  it('classifies every :root font variable, so a new one cannot slip past ungated', () => {
    const declared = [...globalsCss.matchAll(/\n\s*(--font-[a-z-]+):/g)].map((m) => m[1])
    expect(declared.slice().sort()).toEqual(
      [...Object.keys(VAR_LED_CSS_VARS), ...SANCTIONED_CSS_VARS].sort(),
    )
  })

  it('declares the three next/font variables in layout.tsx', () => {
    // If a variable is renamed here, every stack below points at nothing.
    for (const v of NEXT_FONT_VARS) expect(layout).toContain(`variable: '${v}'`)
  })

  it.each(Object.entries(VAR_LED_STACKS))(
    'tailwind fontFamily.%s leads with var(%s)',
    (key, expected) => {
      expect(stack(key).split(',')[0].trim()).toBe(`'var(${expected})'`)
    },
  )

  it.each(Object.entries(VAR_LED_CSS_VARS))('globals.css %s leads with var(%s)', (name, expected) => {
    expect(cssVar(name).split(',')[0].trim()).toBe(`var(${expected})`)
  })

  // The four sanctioned exceptions, each pinned to its exact shape. DESIGN_SYSTEM §12 item 3
  // spells out the `body` one; `sans` and `--font-active` are role indirections that reach a
  // next/font var one hop later. Pinning them means neither "fixing" them to lead with a
  // next/font var nor breaking the indirection can pass.
  it('tailwind fontFamily.body stays system-first with the var ahead of the webfont', () => {
    const parts = stack('body').split(',').map((s) => s.trim())
    expect(parts[0]).toBe("'-apple-system'")
    const varAt = parts.indexOf("'var(--font-inter)'")
    const interAt = parts.indexOf("'Inter'")
    expect(varAt).toBeGreaterThan(-1)
    expect(varAt).toBeLessThan(interAt)
  })

  it('globals.css --font-body stays system-first with the var ahead of the webfont', () => {
    const parts = cssVar('--font-body').split(',').map((s) => s.trim())
    expect(parts[0]).toBe('-apple-system')
    const varAt = parts.indexOf('var(--font-inter)')
    const interAt = parts.indexOf("'Inter'")
    expect(varAt).toBeGreaterThan(-1)
    expect(varAt).toBeLessThan(interAt)
  })

  it('tailwind fontFamily.sans stays the --font-body role indirection', () => {
    expect(stack('sans').split(',')[0].trim()).toBe("'var(--font-body)'")
  })

  it('globals.css --font-active stays the --font-body back-compat alias', () => {
    expect(cssVar('--font-active')).toBe('var(--font-body)')
  })

  it('keeps the purged legacy families out of the config', () => {
    // tailwind.config.js: "fontFamily.system / .grotesque were PURGED at the v2 cutover … The
    // v2.1 export resurrected them; #497 re-removed them." Third time is not the charm.
    expect(tailwindConfig).not.toMatch(/\n\s*(system|grotesque): \[/)
  })
})
