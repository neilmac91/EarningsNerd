import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import postcss from 'postcss'
import tailwindcss, { type Config } from 'tailwindcss'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { dataDirectionText, directionChip, directionText } from '@/lib/financialTone'

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
 * Plus the precondition every token here rests on: a class only reaches production CSS if a
 * tailwind.config.js `content` glob scans the module that composes it. lib/ was missing, so
 * lib/financialTone's directionChip shipped without its /20 borders or its flat tint.
 *
 * And §3's Source Voice Rule, the one type role a surface can misuse without a token change: the editorial face
 * (Newsreader) sets only the filing's own words, on the surfaces EDITORIAL_SURFACES names (below).
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
 * next/font var" rule — that naive form fails on five sanctioned sites today. Per
 * lessons/arch-structural-gates-over-prose-rules.md, "fixing" a sanctioned exception must fail
 * here too, so each exception is pinned to its exact shape rather than merely skipped.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (rel: string) => readFileSync(path.join(frontendDir, rel), 'utf8')

const designSystem = read('DESIGN_SYSTEM.md')
const globalsCssRaw = read('app/globals.css')
const fontsRaw = read('app/fonts.ts')

/** Source with comments removed, so a matcher can never be satisfied by code that is switched off.
 *  Quote-aware, because `//` inside a string literal is not a comment. Two separate findings on this
 *  PR were this one defect: a next/font variable renamed in the live option while the old name
 *  survived in a comment above it, and a `--font-heading` wrapped in `/* … *\/` — each left every
 *  assertion green while the browser had no such variable at all. `lineComments` is off for CSS,
 *  which has no `//` form and where an unquoted `url(https://…)` would otherwise be eaten. */
const stripComments = (src: string, { lineComments = true } = {}): string => {
  let out = ''
  let i = 0
  while (i < src.length) {
    const c = src[i]
    if (c === '"' || c === "'" || c === '`') {
      out += c
      i += 1
      while (i < src.length && src[i] !== c) {
        if (src[i] === '\\') {
          out += src[i]
          i += 1
        }
        if (i < src.length) {
          out += src[i]
          i += 1
        }
      }
      out += src[i] ?? ''
      i += 1
      continue
    }
    if (lineComments && c === '/' && src[i + 1] === '/') {
      while (i < src.length && src[i] !== '\n') i += 1
      continue
    }
    if (c === '/' && src[i + 1] === '*') {
      i += 2
      while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) i += 1
      i += 2
      continue
    }
    out += c
    i += 1
  }
  return out
}

/** Every matcher below reads the comment-free view, never the raw file. */
const globalsCss = stripComments(globalsCssRaw, { lineComments: false })
const fonts = stripComments(fontsRaw)

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

  /** `grep -rnE` reads every file under the directories it is pointed at and skips only binaries.
   *  This scanner does the same instead of allowlisting source extensions: an allowlist quietly
   *  narrows the gate below the rule it claims to enforce, so a legacy token in
   *  `features/analysis/demo/demo-analysis.json` — or in any data/asset file added later — would
   *  pass CI and still fail the founder's own §12 grep.
   *
   *  The file set comes from `git ls-files`, not from walking the filesystem with a skip list. A
   *  skip list is a guess at what git already knows exactly: the first version of this walk skipped
   *  any directory named `dist` or `coverage`, none of which is gitignored here, so a tracked
   *  `features/dist/` would have been invisible to the gate. */
  const BINARY = /\.(png|jpe?g|gif|webp|avif|ico|woff2?|ttf|otf|eot|mp4|webm|pdf|zip)$/i
  const trackedUnder = (dirs: string[]): string[] =>
    execFileSync('git', ['ls-files', '-z'], {
      cwd: frontendDir,
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
    })
      .split('\0')
      .filter((f) => f && dirs.some((d) => f.startsWith(`${d}/`)) && !BINARY.test(f))
      .map((f) => path.join(frontendDir, f))

  it('reads its pattern from the doc rule 11 actually names', () => {
    const pattern = legacyPattern()
    // Sanity: the extracted pattern must still match the things it exists to ban, or a doc edit
    // could quietly neuter the gate while leaving it green.
    expect(pattern.test('text-emerald-500')).toBe(true)
    expect(pattern.test('font-grotesque')).toBe(true)
    expect(pattern.test('text-text-primary-light')).toBe(false)
    // tertiary-dark is tertiary-light's text-safe twin (gray-400), no longer the banned gray-600 it was.
    expect(pattern.test('text-text-tertiary-dark')).toBe(false)
  })

  it('returns zero hits across app, components and features', () => {
    const pattern = legacyPattern()
    const files = trackedUnder(['app', 'components', 'features'])
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
  /** The five sanctioned exceptions, each pinned to its exact shape at the end of this block. */
  const SANCTIONED_STACKS = ['body', 'figure', 'sans']
  const SANCTIONED_CSS_VARS = ['--font-body', '--font-active']

  /** The fontFamily object Tailwind itself will consume, obtained by EVALUATING the config rather
   *  than parsing it. Two regex attempts at this were each narrower than the rule: the first read a
   *  fixed table of names, the second matched only bare-identifier keys and so ignored a valid
   *  quoted one like `'display-alt'`. Text matching keeps losing to JavaScript syntax; the loaded
   *  object cannot, and it also covers keys built by a spread or a helper. */
  const fontFamilies = (): Record<string, string[]> => {
    const required = createRequire(import.meta.url)
    const config = required(path.join(frontendDir, 'tailwind.config.js')) as {
      theme?: { extend?: { fontFamily?: Record<string, string[]> } }
    }
    const families = config.theme?.extend?.fontFamily
    if (!families) throw new Error('tailwind.config.js exposes no theme.extend.fontFamily')
    return families
  }
  const stack = (key: string): string[] => {
    const value = fontFamilies()[key]
    if (!value) throw new Error(`tailwind.config.js has no fontFamily.${key} stack`)
    return value
  }
  /** `--name: <value>;` out of globals.css. CSS custom properties cannot be quoted or computed, so
   *  reading the text is sound here in a way it is not for the JavaScript config. */
  const cssVar = (name: string): string => {
    const m = globalsCss.match(new RegExp(`\\n\\s*${name}: ([^;]*);`))
    if (!m) throw new Error(`app/globals.css has no ${name}`)
    return m[1].trim()
  }

  // A fixed table of names checks only the stacks that existed when it was written, so a stack or
  // var added by a later theme change is simply never looked at — the same "gate narrower than the
  // rule it enforces" defect as an extension allowlist. These two tests close that: every declared
  // name must be classified as var-led or sanctioned, so adding one without deciding which fails.
  it('classifies every fontFamily stack, so a new one cannot slip past ungated', () => {
    expect(Object.keys(fontFamilies()).sort()).toEqual(
      [...Object.keys(VAR_LED_STACKS), ...SANCTIONED_STACKS].sort(),
    )
  })

  it('classifies every :root font variable, so a new one cannot slip past ungated', () => {
    // [\w-] rather than [a-z-]: a variable named --font-UI or --font-ui2 is just as much a font
    // stack, and a gate that cannot see it is the same defect one layer down.
    const declared = [...globalsCss.matchAll(/\n\s*(--font-[\w-]+):/g)].map((m) => m[1])
    expect(declared.slice().sort()).toEqual(
      [...Object.keys(VAR_LED_CSS_VARS), ...SANCTIONED_CSS_VARS].sort(),
    )
  })

  /** The variables the next/font loaders actually emit, read from each call's OPTIONS rather than
   *  from the file's text. A whole-file substring search passes on a stale mention. */
  const emittedFontVars = (): string[] => {
    const imported = fonts.match(/import \{([^}]*)\} from 'next\/font\/google'/)
    if (!imported) throw new Error('app/fonts.ts no longer imports from next/font/google')
    const loaders = imported[1].split(',').map((n) => n.trim()).filter(Boolean)
    return loaders.flatMap((loader) =>
      [...fonts.matchAll(new RegExp(`\\b${loader}\\(\\{([^{}]*)\\}\\)`, 'g'))].flatMap((call) =>
        [...call[1].matchAll(/variable:\s*'([^']+)'/g)].map((v) => v[1]),
      ),
    )
  }

  it('emits exactly the three next/font variables from app/fonts.ts, the root fonts the layout imports', () => {
    // Bidirectional: renaming a live option fails, and so does adding a fourth loader without
    // classifying it. If a variable is renamed here, every stack below points at nothing.
    expect(emittedFontVars().sort()).toEqual([...NEXT_FONT_VARS].sort())
  })

  it.each(Object.entries(VAR_LED_STACKS))(
    'tailwind fontFamily.%s leads with var(%s)',
    (key, expected) => {
      expect(stack(key)[0]).toBe(`var(${expected})`)
    },
  )

  it.each(Object.entries(VAR_LED_CSS_VARS))('globals.css %s leads with var(%s)', (name, expected) => {
    expect(cssVar(name).split(',')[0].trim()).toBe(`var(${expected})`)
  })

  // The five sanctioned exceptions, each pinned to its exact shape. DESIGN_SYSTEM §12 item 3
  // spells out the `body` one; `sans` and `--font-active` are role indirections that reach a
  // next/font var one hop later; `figure` leads with the one-glyph minus face (app/globals.css),
  // then the data stack. Pinning them means neither "fixing" them to lead with a next/font var
  // nor breaking the indirection can pass.
  it('tailwind fontFamily.body stays system-first with the var ahead of the webfont', () => {
    const parts = stack('body')
    expect(parts[0]).toBe('-apple-system')
    const varAt = parts.indexOf('var(--font-inter)')
    const interAt = parts.indexOf('Inter')
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
    expect(stack('sans')[0]).toBe('var(--font-body)')
  })

  // `figure` leads with the one-glyph minus face (globals.css @font-face, unicode-range U+002D), then is the data stack
  // exactly, so every glyph but the hyphen-minus is the data role's.
  it('tailwind fontFamily.figure is the minus face, then exactly the data stack', () => {
    expect(stack('figure')).toEqual(['"EN Figure Minus"', ...stack('data')])
    expect(globalsCss).toMatch(/@font-face \{\s*font-family: 'EN Figure Minus';[^}]*unicode-range: U\+002D;/)
  })

  it('globals.css --font-active stays the --font-body back-compat alias', () => {
    expect(cssVar('--font-active')).toBe('var(--font-body)')
  })

  it('keeps the purged legacy families out of the config', () => {
    // tailwind.config.js: "fontFamily.system / .grotesque were PURGED at the v2 cutover … The
    // v2.1 export resurrected them; #497 re-removed them." Third time is not the charm.
    expect(Object.keys(fontFamilies())).not.toContain('system')
    expect(Object.keys(fontFamilies())).not.toContain('grotesque')
  })
})

// --------------------------------------------------------------------------- tailwind content
describe('tailwind content scans every module that composes classes', () => {
  /** Loaded, not parsed, for the same reason as fontFamilies() above. */
  const config = createRequire(import.meta.url)(path.join(frontendDir, 'tailwind.config.js')) as Config

  /** Each content glob as (directory, extensions). Every entry is `./<dir>/**\/*.{exts}` today; an
   *  entry of any other shape throws, so this model of what Tailwind scans cannot drift from the
   *  globs it models. That includes a one-extension brace like `{ts}`: Tailwind's glob library reads
   *  it literally and matches nothing (Tailwind only warns). The production-build test below checks
   *  the same globs through Tailwind's own resolution, independently of this model. */
  const contentGlobs = (): { dir: string; exts: string[] }[] => {
    if (!Array.isArray(config.content)) throw new Error('tailwind.config.js content is not an array')
    return config.content.map((glob) => {
      const m = typeof glob === 'string' ? glob.match(/^\.\/([\w-]+)\/\*\*\/\*\.\{(\w+(?:,\w+)+)\}$/) : null
      if (!m) throw new Error(`content entry ${JSON.stringify(glob)} is not ./<dir>/**/*.{exts}; teach this gate its shape`)
      return { dir: m[1], exts: m[2].split(',') }
    })
  }
  const isScanned = (file: string): boolean =>
    contentGlobs().some(({ dir, exts }) => file.startsWith(`${dir}/`) && exts.includes(path.extname(file).slice(1)))

  /** Every class Tailwind generates for `content`, read off the selectors it emits. With a
   *  `stylesheet`, that file is the input, so its own `@layer` classes (`tnum`, `tabular`) count too. */
  const generatedClasses = async (
    content: Config['content'],
    { safelist = [], stylesheet }: { safelist?: string[]; stylesheet?: string } = {},
  ): Promise<Set<string>> => {
    const from = stylesheet && path.join(frontendDir, stylesheet)
    const input = from ? readFileSync(from, 'utf8') : '@tailwind components; @tailwind utilities;'
    const css = await postcss([tailwindcss({ ...config, content, safelist })]).process(input, { from })
    const classes = new Set<string>()
    css.root.walkRules((rule) => {
      for (const m of rule.selector.matchAll(/\.((?:\\.|[\w-])+)/g)) classes.add(m[1].replace(/\\(.)/g, '$1'))
    })
    return classes
  }

  /** The classes one module composes, as Tailwind itself extracts them. Bare words (`block`,
   *  `table`, `visible`) are dropped: they are ordinary English and identifiers, so keeping them
   *  would flag config files and type declarations. A module that composes classes carries a
   *  hyphen, variant, opacity or arbitrary value (`border-gain-light/20`). */
  const composedClasses = async (file: string): Promise<string[]> => {
    const raw = readFileSync(path.join(frontendDir, file), 'utf8')
    // The safelisted bare word keeps Tailwind's "No utility classes were detected" warning quiet
    // for class-free modules; the filter drops it again.
    const classes = await generatedClasses([{ raw, extension: path.extname(file).slice(1) }], { safelist: ['hidden'] })
    return [...classes].filter((c) => /[-:/[]/.test(c)).sort()
  }

  /** Tracked paths that never ship to the browser, so nothing in them needs generating. */
  const NOT_APP_CODE: Record<string, string> = {
    'tests/': 'specs assert on class strings; they never render in the app',
    'design/': 'design-handoff mock-ups and bundles; the app imports none of it',
    'tailwind.config.js': 'the token definitions themselves; class names appear as keys and comments',
    'eslint.config.mjs': 'lint config; its design-rule selectors and messages name the banned classes, and it never ships',
    'eslint.gridBaseTrack.mjs': 'lint rule; its comments and message name the grid classes it checks, and it never ships',
    'eslint.designRules.mjs': 'lint rules; their patterns and messages name the stripe, form-code and four-up grid classes they ban, and they never ship',
  }
  const isAppCode = (file: string): boolean =>
    !Object.keys(NOT_APP_CODE).some((p) => (p.endsWith('/') ? file.startsWith(p) : file === p))
  const CODE = /\.(js|jsx|ts|tsx|mjs|cjs|mdx)$/
  const tracked = execFileSync('git', ['ls-files', '-z'], { cwd: frontendDir, encoding: 'utf8' })
    .split('\0')
    .filter(Boolean)

  it('has no stale NOT_APP_CODE entries', () => {
    for (const p of Object.keys(NOT_APP_CODE)) {
      expect(tracked.some((f) => (p.endsWith('/') ? f.startsWith(p) : f === p)), `${p} no longer exists`).toBe(true)
    }
  })

  it('sees the classes a class-map module composes', async () => {
    // Positive control: a detector that silently returns nothing would leave the gate below green.
    const chipClasses = Object.values(directionChip).flatMap((tone) => tone.split(/\s+/))
    expect(await composedClasses('lib/financialTone.ts')).toEqual(expect.arrayContaining(chipClasses))
  })

  it('scans every app module that composes classes', async () => {
    const offenders: string[] = []
    for (const file of tracked.filter((f) => CODE.test(f) && isAppCode(f) && !isScanned(f))) {
      const classes = await composedClasses(file)
      if (classes.length) offenders.push(`${file}: ${classes.join(' ')}`)
    }
    expect(
      offenders,
      'these modules compose Tailwind classes, but no tailwind.config.js content glob scans them, so ' +
        'any class used only there is purged from production CSS. Add the directory (or the ' +
        'extension) to content, or, if the file never ships to the browser, add it to NOT_APP_CODE ' +
        `with the reason:\n${offenders.join('\n')}`,
    ).toEqual([])
  }, 30_000)

  it('emits every class lib/financialTone composes in the production build', async () => {
    // Anchored to frontend/: Tailwind resolves relative globs against the process cwd, not the
    // config file, so a run from another directory would otherwise scan nothing.
    const globs = (config.content as string[]).map((glob) => path.join(frontendDir, glob))
    const built = await generatedClasses(globs, { stylesheet: 'app/globals.css' })
    const composed = [directionText, directionChip, dataDirectionText].flatMap((tones) =>
      Object.values(tones).flatMap((tone) => tone.split(/\s+/)),
    )
    expect(composed.filter((c) => !built.has(c)), 'purged from production CSS').toEqual([])
  }, 30_000)
})

// --------------------------------------------------------------------------- §3, the Source Voice Rule
describe("DESIGN_SYSTEM §3 — Newsreader sets only the filing's own words (the Source Voice Rule)", () => {
  /** Every file that sets the editorial face, and on what. An equality: a file that sets the face and is not listed
   *  fails, and so does a listed file that no longer sets it. The face means the filing's own words: the real filing
   *  viewer, a located quoted passage on a public page and, since D-044, the passages the server located inside the
   *  product. Outside the reader it sets only a marked block (`en-marked`, a passage the server located), whose places
   *  and whose located test tests/unit/brandCopyRules.spec.ts rule 3 holds (DEVICE_PLACES). app/fonts.ts loads the
   *  font and is not a surface: it names the loader and its variable, never the face's class or a var() of it. */
  const EDITORIAL_SURFACES: Record<string, string> = {
    'features/filings/components/copilot/FilingViewer.tsx': 'the real filing viewer: `.filing-reader`, the filing text',
    'features/marketing/components/HeroExample.tsx': "a located quoted passage on a public page: the hero example's evidence row, a marked block",
    'features/summaries/components/SummaryRisks.tsx': "the located excerpts inside the product: the filing page's Risks rows, each a marked block (D-044)",
    'features/summaries/components/SummaryBlocks.tsx': "the summary's quote blocks whose evidence the server located, each a marked block (D-044)",
  }
  const READER = 'features/filings/components/copilot/FilingViewer.tsx'
  /** Planted forms, one component per form, its mark (`flag` or `clean`) in the comment before it: scored by the check
   *  below on every run, so a change to the check that loses a form, or catches a look-alike, fails. */
  const FORMS = 'tests/unit/fixtures/sourceVoiceForms.tsx'

  /** The utilities that set the face: every fontFamily stack Tailwind consumes that leads with Newsreader's variable
   *  (`font-editorial` today), read from the evaluated config, so a second stack is read the day it lands. */
  const families = (createRequire(import.meta.url)(path.join(frontendDir, 'tailwind.config.js')) as {
    theme: { extend: { fontFamily: Record<string, string[]> } }
  }).theme.extend.fontFamily
  const FACE_UTILITIES = Object.entries(families).filter(([, stack]) => stack[0] === 'var(--font-newsreader)').map(([key]) => `font-${key}`)
  const token = (name: string, before = '[\\w-]') => new RegExp(`(?<!${before})${name}(?![\\w-])`)
  const READER_CLASS = token('filing-reader', '[\\w.-]')
  /** What sets the face in a string of app code: a face utility, the reader's own class (a selector's `.filing-reader`
   *  reads the reader and sets nothing), a var() of the face, or the family by name. */
  const SETS_FACE = [
    ...FACE_UTILITIES.map((u) => token(u)),
    READER_CLASS,
    /var\(\s*--font-(?:editorial|newsreader)\s*\)/,
    /^\s*['"]?Newsreader['"]?\s*(?:,|$)/,
  ]

  /** Every string a module writes (literals, template chunks and JSX text), from its syntax tree, so a comment never
   *  counts. */
  const strings = (file: string): { node: ts.Node; text: string }[] => {
    const sf = ts.createSourceFile(file, read(file), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const out: { node: ts.Node; text: string }[] = []
    const visit = (n: ts.Node) => {
      if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n) || ts.isJsxText(n)) out.push({ node: n, text: n.text })
      ts.forEachChild(n, visit)
    }
    visit(sf)
    return out
  }
  const settingFace = (file: string) => strings(file).filter(({ text }) => SETS_FACE.some((re) => re.test(text)))
  /** Outside the reader the face sits only on a marked block, in its own class list: a string that sets the face and
   *  names no `en-marked`, or names the reader's class, is set on something else. */
  const loose = (file: string) => settingFace(file).filter(({ text }) => !token('en-marked').test(text) || READER_CLASS.test(text))
  const APP = execFileSync('git', ['ls-files', '-z', 'app', 'components', 'features', 'hooks', 'lib'], { cwd: frontendDir, encoding: 'utf8' })
    .split('\0')
    .filter((f) => /\.(ts|tsx)$/.test(f))

  it('reads the face from the config and the app (anti-vacuity)', () => {
    expect(FACE_UTILITIES).toEqual(['font-editorial'])
    expect(APP.length).toBeGreaterThan(200)
  })

  it('sets the face only on the surfaces EDITORIAL_SURFACES names, each a passage of the filing (D-044)', () => {
    const surfaces = APP.filter((file) => settingFace(file).length > 0).sort()
    expect(surfaces, "Newsreader means the filing's own words: name the surface and why in EDITORIAL_SURFACES, or set the copy in the body face")
      .toEqual(Object.keys(EDITORIAL_SURFACES).sort())
  })

  it('outside the reader, sets the face only on a marked block, a passage the server located', () => {
    const found = APP.filter((file) => file !== READER).flatMap((file) => loose(file).map(({ text }) => `${file}: ${text.trim()}`))
    expect(found, 'the face sits on the marked block (`en-marked`) of a located passage, in the same class list').toEqual([])
  })

  it(`scores every planted form in ${FORMS} as its mark says`, () => {
    const sf = ts.createSourceFile(FORMS, read(FORMS), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const forms = sf.statements.flatMap((stmt) => {
      if (!ts.isFunctionDeclaration(stmt) || !stmt.name) return []
      const mark = ts.getLeadingCommentRanges(sf.text, stmt.pos)?.map((r) => /^\/\*\*\s*(V\d+) (flag|clean):/.exec(sf.text.slice(r.pos, r.end))).find(Boolean)
      return mark && mark[1] === stmt.name.text ? [{ name: mark[1], mark: mark[2], fn: stmt }] : []
    })
    const named = new Set(loose(FORMS).map(({ node }) => forms.find(({ fn }) => node.pos >= fn.pos && node.end <= fn.end)?.name ?? `outside a form at ${node.pos}`))
    expect(forms.filter((f) => f.mark === 'flag').length, 'the fixture plants forms that break the rule').toBeGreaterThan(0)
    expect(forms.filter((f) => f.mark === 'clean').length, 'the fixture plants look-alikes').toBeGreaterThan(0)
    expect(forms.filter((f) => named.has(f.name) !== (f.mark === 'flag')).map((f) => `${f.name} (${f.mark})`), 'the check reads these forms against their marks').toEqual([])
    expect([...named].filter((name) => !forms.some((f) => f.name === name)), 'the check named a string that is not in a planted form').toEqual([])
  })

  it('in the stylesheet, sets the face only on the reader', () => {
    const rules: string[] = []
    postcss.parse(globalsCssRaw).walkRules((rule) => {
      const sets = rule.nodes.some((n) =>
        (n.type === 'decl' && n.prop === 'font-family' && /--font-(?:editorial|newsreader)|Newsreader/.test(n.value))
        || (n.type === 'atrule' && n.name === 'apply' && FACE_UTILITIES.some((u) => token(u).test(n.params))))
      if (sets) rules.push(rule.selector.replace(/\s+/g, ' ').trim())
    })
    expect(rules, "globals.css sets Newsreader on the filing reader's own rule alone").toEqual(['.filing-reader'])
  })
})
