/* =============================================================================
   wordmarkSingleSource.spec.ts — guardrail (v3, Q1; backend reach, BG-27)
   -----------------------------------------------------------------------------
   components/EarningsNerdLogo.tsx is the ONE source of the two-tone wordmark
   (variant="full" | "wordmark"). Header and AuthShell hand-composed
   `Earnings<em>Nerd</em>` before v3 and drifted in size and tracking; this spec
   fails if any other file renders the italic "Nerd" half by hand.

   Outside React the wordmark has to be composed by hand, since nothing renders
   a mail or a PDF through the component: those renditions are named in
   SANCTIONED_BACKEND, and the scan of backend/app holds the list to an equality
   (D-040), so a new hand-composed rendition fails until it is named here with
   its reason, and a removed one fails until its entry goes. The PDF rendition's
   colours ("Earnings" in the ink, "Nerd" italic in brand-strong) are read from
   its rendered stylesheet by backend/tests/unit/test_export_palette_parity.py;
   the mail's are review-checked until its header port (E54). The brand
   templates (docs/brand/templates, scripts/brand/og-template.html) are artwork,
   outside this scan, as before.

   What counts as the italic half: "Nerd" alone in an element that sets it
   italic, or any element that sets italic opened right after "Earnings",
   whatever it holds (`f"Earnings<em>{half()}</em>"`). An element sets italic
   when it is one the browser's and WeasyPrint's own stylesheets slant (`em`,
   `i`, `cite`, `var`, `dfn`, `address`), when its style or an attribute sets
   font-style italic or oblique (`style="font-style: italic"`, SVG's
   `font-style="italic"`, JSX's `fontStyle: 'italic'`), or when it carries the
   `italic` utility class (never `not-italic`). The backend scan reads Python's
   string parts (pythonTokens.ts), not its text: literals side by side or
   joined by `+` read as one string, and a name the same file binds to such a
   string (by `=`, an annotated `=` or `+=`, every value it is given, in no
   order) reads as its value where it is joined or filled into an f-string's
   `{name}`; a comment is never read. Out of reach (review): a half imported
   from another module, a string built by a call (`"".join`, `.format()`, `%`),
   a tuple or other unpacking binding, an element made italic by a class whose
   rule lives in a stylesheet, and in TSX, which the scan reads as text, a half
   held in a variable or a tag holding a `>` before the italic. The planted
   forms below score both readers.
============================================================================= */

import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { pythonTokens, type Token } from './pythonTokens'

const ROOT = path.join(__dirname, '../..')
const REPO = path.join(ROOT, '..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const SOURCE = 'components/EarningsNerdLogo.tsx'
/** An opening tag that sets its text italic, in any of the forms the header names. */
const ITALIC = [
  String.raw`<(?:em|i|cite|var|dfn|address)\b[^>]*>`,
  String.raw`<[\w.:-]+\b[^>]*?(?:font-?style\s*[:=]\s*[{"'\s]*(?:italic|oblique)|\bclass(?:Name)?=[^>]*?(?<![\w-])italic(?![\w-]))[^>]*>`,
].join('|')
const HAND_ROLLED = new RegExp(String.raw`Earnings\s*(?:${ITALIC})|(?:${ITALIC})\s*Nerd\s*<\/`, 'i')
const BACKEND = path.join(REPO, 'backend/app')
/** The renditions no React component can render, each with its reason. */
const SANCTIONED_BACKEND = [
  'backend/app/services/email_service.py', // the transactional mail's header
  'backend/app/services/pdf_branding.py', // the PDF masthead of both exports
]

function walk(dir: string, test: (name: string) => boolean, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name !== '__pycache__') walk(p, test, out)
    } else if (test(entry.name)) out.push(p)
  }
  return out
}

/** At most this many strings per expression, so a name bound many times cannot multiply without end. */
const MAX_VALUES = 64

/** The strings a Python file builds from its literals: literals side by side or joined by `+` read as
    one, and a name the file binds to such a string reads as its value where it is joined or filled into
    an f-string's `{name}`. */
function pythonStrings(src: string): string[] {
  const toks = pythonTokens(src).filter((t) => !(t.kind === 'op' && t.text === '\\'))
  const op = (t: Token | undefined, text: string) => t?.kind === 'op' && t.text === text
  const bound = new Map<string, string[]>()
  /** An f-string's `{name}` fields filled from the names bound so far, each once (a value is not refilled). */
  const fill = (text: string): string[] => {
    let filled = ['']
    let from = 0
    for (const field of text.matchAll(/\{(\w+)\}/g)) {
      const literal = text.slice(from, field.index)
      filled = filled.flatMap((head) => (bound.get(field[1]) ?? [field[0]]).map((value) => head + literal + value)).slice(0, MAX_VALUES)
      from = field.index! + field[0].length
    }
    return filled.map((head) => head + text.slice(from))
  }
  const operand = (j: number): string[] | null => {
    const t = toks[j]
    if (t?.kind === 'str') return fill(t.text)
    if (t?.kind === 'name' && bound.has(t.text) && !op(toks[j + 1], '(') && !op(toks[j + 1], '[') && !op(toks[j - 1], '.')) {
      return bound.get(t.text)!
    }
    return null
  }
  /** The values of the string expression that starts at token i. */
  const read = (i: number): string[] | null => {
    let values = operand(i)
    if (!values) return null
    let j = i + 1
    for (;;) {
      const next = toks[j]?.kind === 'str' ? j : op(toks[j], '+') ? j + 1 : -1
      const more = next < 0 ? null : operand(next)
      if (!more) return values
      values = values.flatMap((v) => more.map((m) => v + m)).slice(0, MAX_VALUES)
      j = next + 1
    }
  }
  // A binding: `name = <string expression>`, `name: type = …` or `name += …`, never `==` or an attribute.
  for (let pass = 0; pass < 3; pass++) {
    toks.forEach((t, j) => {
      if (t.kind !== 'name' || op(toks[j - 1], '.')) return
      const extend = op(toks[j + 1], '+') && op(toks[j + 2], '=')
      const at = extend ? j + 3 : op(toks[j + 1], '=') ? j + 2
        : op(toks[j + 1], ':') && toks[j + 2]?.kind === 'name' && op(toks[j + 3], '=') ? j + 4 : -1
      if (at < 0 || op(toks[at], '=')) return
      const value = read(at)
      if (!value) return
      const before = bound.get(t.text) ?? []
      const values = extend && before.length ? before.flatMap((b) => value.map((v) => b + v)) : value
      bound.set(t.text, [...new Set([...before, ...values])].slice(0, MAX_VALUES))
    })
  }
  return toks.flatMap((_, i) => read(i) ?? [])
}

const handRolled = (file: string) => HAND_ROLLED.test(fs.readFileSync(file, 'utf8'))
const handRolledPython = (src: string) => pythonStrings(src).some((s) => HAND_ROLLED.test(s))

describe('the wordmark has one source: EarningsNerdLogo', () => {
  it('no other file hand-composes the italic "Nerd"', () => {
    const offenders: string[] = []
    for (const dir of SCAN_DIRS) {
      for (const file of walk(path.join(ROOT, dir), (name) => /\.tsx?$/.test(name))) {
        const rel = path.relative(ROOT, file).split(path.sep).join('/')
        if (rel !== SOURCE && handRolled(file)) offenders.push(rel)
      }
    }
    expect(offenders, 'render <EarningsNerdLogo variant="wordmark" | "full"> instead').toEqual([])
  })

  it('the source still renders it (the pattern above stays meaningful)', () => {
    expect(fs.readFileSync(path.join(ROOT, SOURCE), 'utf8')).toMatch(HAND_ROLLED)
  })

  it('outside React, only the sanctioned backend renditions compose it', () => {
    const files = walk(BACKEND, (name) => name.endsWith('.py'))
    expect(files.length, 'the scan found backend/app').toBeGreaterThan(100)
    const found = files
      .filter((file) => handRolledPython(fs.readFileSync(file, 'utf8')))
      .map((file) => path.relative(REPO, file).split(path.sep).join('/'))
      .sort()
    expect(found, 'compose the wordmark in a sanctioned rendition, or name this one in SANCTIONED_BACKEND with its reason')
      .toEqual(SANCTIONED_BACKEND)
  })

  it('the readers find the forms Python and TSX write, and pass the look-alikes (planted probe)', () => {
    const flagged = [
      `w = '<span class="wordmark">Earnings<em>Nerd</em></span>'`, // the PDF masthead's markup
      `w = '<td style="color:#1A1A17;">Earnings<em style="color:#3C6650;font-style:italic;">Nerd</em></td>'`, // the mail's
      `w = f"<td>Earnings<em class=\\"accent\\">Nerd</em></td>"`, // a quoted attribute escaped in a Python string
      `w = "Earnings<em>\\n  Nerd\\n</em>"`, // the half split across lines by escapes
      `w = "Earnings<i style='color: #3C6650'>Nerd</i>"`, // the review's probe: an <i>
      `_HALF = "Nerd"\nw = f"Earnings<em>{_HALF}</em>"`, // the review's probe: an f-string's half
      `w = f"Earnings<em>{half()}</em>"`, // a half the reader cannot read, opened right after "Earnings"
      `w = "Earnings" + "<em>Nerd</em>"`, // a join
      `HALF = "Nerd"\nw = "<b>Earnings</b><em>" + HALF + "</em>"`, // a bound name joined between literals
      `FIRST = "Earnings"\nSECOND: str = "Nerd"\nw = f"{FIRST}<em>{SECOND}</em>"`, // both halves bound
      `w = ("Earnings"\n     "<cite>Nerd</cite>")`, // literals side by side across lines, a <cite>
      `w = "Earnings"\nw += "<var>Nerd</var>"`, // an augmented assignment
      `w = '<span style="font-style: oblique">Nerd</span>'`, // an inline style
      `w = '<tspan font-style="italic">Nerd</tspan>'`, // SVG's attribute
      `w = '<span class="wordmark italic">Nerd</span>'`, // the utility class
    ]
    expect(flagged.filter((src) => !handRolledPython(src))).toEqual([])
    const passing = [
      `w = "<span>EarningsNerd</span>"`, // the plain name is not the wordmark
      `w = "Earnings <strong>Nerd</strong>"`, // bold is not the italic half
      `w = "<em>Nerds</em>"`,
      `# Earnings<em>Nerd</em> in a comment`, // a comment renders nothing
      `w = "EarningsNerd · AI summaries of SEC filings"`,
      `w = "Earnings" if x == "<em>" else "Nerd"`, // a condition, not a join
      `w = "Earnings" + other("<em>Nerd")`, // a call's argument, not joined
      `w = '<span class="not-italic">Nerd</span>'`, // the utility that sets it upright
    ]
    expect(passing.filter((src) => handRolledPython(src))).toEqual([])
    const tsx = [
      '<p>Earnings<i>Nerd</i></p>',
      '<span>Earnings</span><span className="italic text-brand">Nerd</span>',
      "<em style={{ fontStyle: 'italic' }}>Nerd</em>",
      '<>Earnings\n  <em className="accent">Nerd</em></>',
    ]
    expect(tsx.filter((text) => !HAND_ROLLED.test(text))).toEqual([])
    expect(HAND_ROLLED.test('<span>EarningsNerd</span>')).toBe(false)
  })
})
