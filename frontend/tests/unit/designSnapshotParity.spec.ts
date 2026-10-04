/* =============================================================================
   designSnapshotParity.spec.ts — the root DESIGN.md snapshot stays source-true
   -----------------------------------------------------------------------------
   DESIGN.md's frontmatter and .impeccable/design.json are derived copies of the
   token sources (tailwind.config.js + globals.css). CLAUDE.md § Design
   documentation asks for them to be refreshed together; nothing fails visibly
   when a copy drifts, so this spec compares the copies that must agree:
     1. frontmatter tokens vs source, for the documented subset. Omissions and
        aliases are listed below; units are compared by value (#FFF = #ffffff,
        0 = 0em), not by spelling.
     2. sidecar colorMeta vs frontmatter. Tonal-ramp steps must be source
        colors: Impeccable's detector treats every step as an allowed palette
        color, so a synthetic ramp silently widens palette enforcement.
     3. sidecar shadows / motion / breakpoints vs source.
     4. the sidecar narrative vs the DESIGN.md text it duplicates.
     5. specimens: every color traces to a frontmatter color or sidecar shadow,
        and the panel-fit rules from review hold (constrained host, no viewport
        queries, dark keyed to the app's own .dark signal).
   It does not judge the prose itself.
============================================================================= */

import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const config = require('../../tailwind.config.js')
const defaultTheme = require('tailwindcss/defaultTheme')
const tailwindColors = require('tailwindcss/colors')

const REPO = path.join(__dirname, '../../..')
const read = (p: string) => fs.readFileSync(path.join(REPO, p), 'utf8')
const designMd = read('DESIGN.md')
const sidecar = JSON.parse(read('.impeccable/design.json'))
const globalsCss = read('frontend/app/globals.css')

type Yaml = { [key: string]: string | number | Yaml }

/** Strict reader for the frontmatter's YAML subset (nested maps of quoted strings and numbers).
 *  Anything else throws, so an unexpected construct fails loudly instead of parsing wrong. */
function parseFrontmatter(md: string): Yaml {
  const block = md.match(/^---\n([\s\S]*?)\n---\n/)
  if (!block) throw new Error('DESIGN.md has no frontmatter')
  const root: Yaml = {}
  const stack: { indent: number; node: Yaml }[] = [{ indent: -1, node: root }]
  for (const line of block[1].split('\n')) {
    const m = line.match(/^( *)("[^"]+"|[\w.-]+):(?: (.+))?$/)
    if (!m) throw new Error(`unsupported frontmatter line: ${line}`)
    const [, spaces, rawKey, raw] = m
    const key = rawKey.startsWith('"') ? JSON.parse(rawKey) : rawKey
    while (spaces.length <= stack[stack.length - 1].indent) stack.pop()
    const parent = stack[stack.length - 1].node
    if (raw === undefined) {
      parent[key] = {}
      stack.push({ indent: spaces.length, node: parent[key] as Yaml })
    } else if (raw.startsWith('"')) parent[key] = JSON.parse(raw)
    else if (/^-?\d+(\.\d+)?$/.test(raw)) parent[key] = Number(raw)
    else throw new Error(`unsupported frontmatter value: ${line}`)
  }
  return root
}

const fm = parseFrontmatter(designMd)
const fmColors = fm.colors as Record<string, string>

/** [r, g, b, a] for the hex / rgb() / rgba() spellings the sources use. */
function rgba(value: string): number[] {
  const v = value.trim().toLowerCase()
  const hex = v.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/)
  if (hex) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join('') : hex[1]
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).concat(1)
  }
  const fn = v.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/)
  if (fn) return [Number(fn[1]), Number(fn[2]), Number(fn[3]), fn[4] === undefined ? 1 : Number(fn[4])]
  throw new Error(`unrecognised color: ${value}`)
}

/** CSS lengths compared by value: `0` and `0em` are the same zero. */
function length(value: string | number | undefined): string | undefined {
  if (value === undefined) return undefined
  const m = String(value).trim().match(/^(-?[\d.]+)(em|rem|px)?$/)
  if (!m) return String(value)
  return Number(m[1]) === 0 ? '0' : `${Number(m[1])}${m[2] ?? ''}`
}

/** Tailwind color tree → dashed token names (`brand.strong-dark` → `brand-strong-dark`, DEFAULT → parent). */
function flatten(tree: Record<string, unknown>, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(tree)) {
    const name = key === 'DEFAULT' ? prefix : prefix ? `${prefix}-${key}` : key
    if (typeof value === 'string') out[name] = value
    else Object.assign(out, flatten(value as Record<string, unknown>, name))
  }
  return out
}

/** `--name: value;` declarations from the first block that starts with `selector {`. */
function cssVars(selector: string): Record<string, string> {
  const start = globalsCss.indexOf(`${selector} {`)
  const body = globalsCss.slice(start, globalsCss.indexOf('}', start)).replace(/\/\*[\s\S]*?\*\//g, '')
  return Object.fromEntries([...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]))
}
const rootVars = cssVars(':root')
const darkVars = cssVars('.dark')
const resolveVar = (value: string) => value.replace(/^var\((--[\w-]+)\)$/, (_, name) => rootVars[name] ?? value)

// The Tailwind default the snapshot names (`bg-white`), alongside the project's own color tree.
const SOURCE_COLORS = { ...flatten(config.theme.extend.colors), white: tailwindColors.white }
/** Source colors left out on purpose; DESIGN.md › Colors states why. */
const OMITTED_COLORS = [
  'text-tertiary-dark',
  ...['grid', 'axis', 'label', 'crosshair', 'ref', 'tip'].flatMap((k) => [`chart-${k}-light`, `chart-${k}-dark`]),
]
/** Source aliases: the snapshot records only the token each one equals. */
const COLOR_ALIASES: Record<string, string> = {
  gain: 'gain-light',
  loss: 'loss-light',
  'text-heading-light': 'text-primary-light',
  'text-heading-dark': 'text-primary-dark',
}
const OMITTED_RADII = ['md'] // legacy 10px, excluded from the 4/8/12/16/24 scale
const OMITTED_SHADOWS = ['glow-brand', 'glow-brand-sm', 'glow-brand-lg'] // configured but unused

/** Frontmatter typography role → its source. `size` keys tailwind fontSize; `tracking` overrides it. */
const TYPE_ROLES: Record<string, { family: string; size?: string; tracking?: string }> = {
  display: { family: 'heading', size: '6xl' },
  headline: { family: 'heading', size: '3xl' },
  title: { family: 'heading', size: '2xl' },
  'card-title': { family: 'heading', size: 'sm' },
  body: { family: 'body' }, // root browser sample (16px / 1.5), not a configured size
  'body-base': { family: 'body', size: 'base' },
  ui: { family: 'body', size: 'sm' },
  button: { family: 'body', size: 'sm' },
  label: { family: 'body', size: 'xs', tracking: 'var(--track-eyebrow)' },
  data: { family: 'data' },
  'data-xs': { family: 'data', size: 'data-xs' },
  'filing-reader': { family: 'editorial' }, // size and leading checked against globals.css below
}

describe('DESIGN.md frontmatter matches the token sources', () => {
  it('every documented color equals its source token', () => {
    const drift = Object.entries(fmColors)
      .filter(([name, value]) => !(name in SOURCE_COLORS) || String(rgba(value)) !== String(rgba(SOURCE_COLORS[name])))
      .map(([name, value]) => `${name}: DESIGN.md ${value}, source ${SOURCE_COLORS[name] ?? '(missing)'}`)
    expect(drift).toEqual([])
  })

  it('classifies every project color token as documented, omitted or an alias', () => {
    const unclassified = Object.keys(SOURCE_COLORS).filter(
      (name) => !(name in fmColors) && !OMITTED_COLORS.includes(name) && !(name in COLOR_ALIASES),
    )
    expect(unclassified, 'add the token to DESIGN.md, or record the omission here and in DESIGN.md › Colors').toEqual([])
    const stale = [...OMITTED_COLORS, ...Object.keys(COLOR_ALIASES)].filter((name) => !(name in SOURCE_COLORS))
    expect(stale).toEqual([])
    for (const [alias, target] of Object.entries(COLOR_ALIASES)) {
      expect(SOURCE_COLORS[alias], `${alias} is no longer an alias of ${target}`).toBe(SOURCE_COLORS[target])
    }
  })

  it('rounded and spacing steps equal the configured scale', () => {
    const radii = { ...config.theme.extend.borderRadius, full: defaultTheme.borderRadius.full }
    for (const name of OMITTED_RADII) delete radii[name]
    expect(fm.rounded).toEqual(radii)

    const spacing = { ...defaultTheme.spacing, ...config.theme.extend.spacing }
    for (const [step, value] of Object.entries(fm.spacing as Yaml)) expect(value, `spacing.${step}`).toBe(spacing[step])
    expect(Object.keys(fm.spacing as Yaml)).toEqual(expect.arrayContaining(Object.keys(config.theme.extend.spacing)))
  })

  it('typography roles equal their source family, size, leading and tracking', () => {
    const roles = fm.typography as Record<string, Record<string, string | number>>
    expect(Object.keys(roles).sort()).toEqual(Object.keys(TYPE_ROLES).sort())
    for (const [role, src] of Object.entries(TYPE_ROLES)) {
      const doc = roles[role]
      expect(doc.fontFamily, `${role}.fontFamily`).toBe(config.theme.extend.fontFamily[src.family].join(', '))
      if (!src.size) continue
      const [fontSize, opts] = config.theme.extend.fontSize[src.size]
      expect([doc.fontSize, doc.lineHeight], `${role} size/leading`).toEqual([fontSize, opts.lineHeight])
      const tracking = src.tracking ?? opts.letterSpacing
      expect(length(doc.letterSpacing), `${role}.letterSpacing`).toBe(length(tracking && resolveVar(tracking)))
    }
    const reader = globalsCss.match(/\.filing-reader \{[^}]*font-size:\s*([^;]+);[^}]*line-height:\s*([^;]+);/)
    expect([roles['filing-reader'].fontSize, roles['filing-reader'].lineHeight]).toEqual([reader?.[1], reader?.[2]])
  })
})

describe('.impeccable/design.json agrees with DESIGN.md and the sources', () => {
  const ext = sidecar.extensions

  it('colorMeta canonicals equal the frontmatter colors', () => {
    expect(Object.keys(ext.colorMeta).sort()).toEqual(Object.keys(fmColors).sort())
    for (const [name, meta] of Object.entries<Record<string, unknown>>(ext.colorMeta)) {
      expect(String(rgba(String(meta.canonical))), `colorMeta.${name}.canonical`).toBe(String(rgba(fmColors[name])))
    }
  })

  it('carries only source-backed tonal-ramp steps', () => {
    const source = new Set(Object.values(SOURCE_COLORS).map((c) => String(rgba(c))))
    const synthetic = Object.entries<Record<string, unknown>>(ext.colorMeta).flatMap(([name, meta]) =>
      ((meta.tonalRamp as string[] | undefined) ?? [])
        .filter((step) => !/^(#|rgba?\()/i.test(step) || !source.has(String(rgba(step))))
        .map((step) => `${name}: ${step}`),
    )
    expect(synthetic, 'Impeccable accepts every ramp step as a palette color').toEqual([])
  })

  it('shadows, motion and breakpoints equal their sources', () => {
    const shadows = { ...config.theme.extend.boxShadow }
    for (const name of OMITTED_SHADOWS) delete shadows[name]
    expect(Object.fromEntries(ext.shadows.map((s: { name: string; value: string }) => [s.name, s.value]))).toEqual(shadows)
    const motion = Object.fromEntries(
      Object.entries(rootVars).filter(([name]) => /^--(duration|ease)-/.test(name)).map(([name, v]) => [name.slice(2), v]),
    )
    expect(Object.fromEntries(ext.motion.map((m: { name: string; value: string }) => [m.name, m.value]))).toEqual(motion)
    for (const bp of ext.breakpoints) expect(bp.value, `breakpoint ${bp.name}`).toBe(defaultTheme.screens[bp.name])
  })

  it('narrative equals the DESIGN.md text it duplicates', () => {
    const body = designMd.split('\n---\n')[1]
    const overview = body.match(/\*\*Creative North Star: "(.+)"\*\*\n\n([\s\S]+?)\n\n\*\*Key Characteristics:\*\*\n((?:- .+\n)+)/)
    const bullets = (heading: string) => body.split(`### ${heading}\n\n`)[1].split('\n\n')[0].trimEnd().split('\n').map((l) => l.slice(2))
    const rules = body.split(/^## /m).flatMap((section) => {
      const name = section.split('\n')[0]
      const key = name.startsWith('Elevation') ? 'elevation' : name.toLowerCase()
      return [...section.matchAll(/^\*\*(The .+? Rule)\.\*\* (.+)$/gm)].map((m) => ({ name: m[1], body: m[2], section: key }))
    })
    expect(sidecar.narrative).toEqual({
      northStar: overview?.[1],
      overview: overview?.[2],
      keyCharacteristics: overview?.[3].trim().split('\n').map((l) => l.slice(2)),
      rules,
      dos: bullets('Do:'),
      donts: bullets("Don't:"),
    })
  })
})

describe('sidecar specimens fit the Impeccable panel and trace to the snapshot', () => {
  const components: { refersTo: string; html: string; css: string }[] = sidecar.components
  const shadowValues = sidecar.extensions.shadows.map((s: { value: string }) => s.value)
  const palette = new Set(Object.values(fmColors).map((c) => String(rgba(c).slice(0, 3))))
  const COLOR = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\([^)]*\)/gi

  it('refer to frontmatter components', () => {
    expect(components.map((c) => c.refersTo).filter((ref) => !(ref in (fm.components as Yaml)))).toEqual([])
  })

  it('use only frontmatter colors (any alpha) and verbatim sidecar shadows', () => {
    const untraced = components.flatMap((c) => {
      const text = shadowValues.reduce((css: string, shadow: string) => css.split(shadow).join(''), c.css + c.html)
      return (text.match(COLOR) ?? [])
        .filter((color: string) => !/^(#|rgba?\()/i.test(color) || !palette.has(String(rgba(color).slice(0, 3))))
        .map((color: string) => `${c.refersTo}: ${color}`)
    })
    expect(untraced).toEqual([])
  })

  it('size to their panel stage and key dark mode to the app theme signal', () => {
    const signal = `@container style(--heading-color: ${darkVars['--heading-color']})`
    for (const c of components) {
      // The panel mounts each specimen in a bare host inside a centered flex stage.
      expect(c.css.startsWith(':host{display:block;width:100%}'), `${c.refersTo}: unconstrained host`).toBe(true)
      // Viewport queries fire on the browser, not the ~350px panel; use container queries.
      expect(c.css, `${c.refersTo}: viewport width query`).not.toMatch(/@media\s*\([^)]*width/)
      // The panel sets no theme class; the app's `.dark` custom property is what reaches the specimen.
      expect(c.css, `${c.refersTo}: dark signal`).toContain(signal)
      expect(c.css, `${c.refersTo}: theme hook the panel never sets`).not.toMatch(/:root|:host\(\.dark\)|prefers-color-scheme/)
    }
  })
})
