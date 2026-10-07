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
     2. sidecar colorMeta vs frontmatter. Tonal-ramp and roundedMeta values
        must be documented tokens: Impeccable's detector treats every one as an
        allowed palette color or radius, so synthetic steps silently widen it.
     3. sidecar shadows / motion / breakpoints vs source.
     4. the sidecar narrative vs the DESIGN.md text it duplicates.
     5. specimens: each `--ds-*` palette variable equals the token its role names
        in both themes, every other color is a frontmatter color or sidecar
        shadow, and the panel-fit rules from review hold (constrained host, no
        viewport queries, dark keyed to the app's own .dark signal in both the
        source spelling and the lowercase one Turbopack serves).
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
const designMd = read('DESIGN.md').replace(/\r\n/g, '\n')
const sidecar = JSON.parse(read('.impeccable/design.json'))
const globalsCss = read('frontend/app/globals.css').replace(/\r\n/g, '\n')

type Yaml = { [key: string]: string | number | Yaml }

/** Strict reader for the frontmatter's YAML subset (nested maps of quoted strings and numbers).
 *  Anything else throws, so an unexpected construct fails loudly instead of parsing wrong. */
const FRONTMATTER = /^---\n([\s\S]*?)\n---\n/
function parseFrontmatter(md: string): Yaml {
  const block = md.match(FRONTMATTER)
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
/** DESIGN.md after its frontmatter; a later `---` rule cannot shift it. */
const designBody = designMd.slice(designMd.match(FRONTMATTER)![0].length)

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

/** `--name: value;` declarations from every top-level `selector {…}` block in globals.css. */
function cssVars(selector: string): Record<string, string> {
  const css = globalsCss.replace(/\/\*[\s\S]*?\*\//g, '')
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const blocks = [...css.matchAll(new RegExp(`(?:^|[\\s}])${escaped}\\s*\\{([^}]*)\\}`, 'g'))].map((m) => m[1])
  if (!blocks.length) throw new Error(`globals.css has no ${selector} block`)
  return Object.fromEntries(blocks.flatMap((b) => [...b.matchAll(/(--[\w-]+):\s*([^;]+);/g)]).map((m) => [m[1], m[2].trim()]))
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
const DOCUMENTED_SCREENS = ['sm', 'md', 'lg'] // DESIGN.md › Layout; xl/2xl are not part of the shared conventions
/** A portable stack drops the next/font `var(--font-*)` entries, which exist only inside the app. */
const portableStack = (family: string) =>
  config.theme.extend.fontFamily[family].filter((f: string) => !f.startsWith('var(')).join(', ')

/** Specimen palette role → its token in [light, dark]. `token@alpha` is the token at that opacity,
 *  `shadow:name` a sidecar shadow, `none` no value, and a null dark entry means the light value
 *  serves both themes (so the dark block must not redeclare it). Mirrors the source components. */
const SPECIMEN_ROLES: Record<string, [string, string | null]> = {
  page: ['background-light', 'background-dark'],
  panel: ['panel-light', 'panel-dark'],
  ink: ['text-primary-light', 'text-primary-dark'],
  secondary: ['text-secondary-light', 'text-secondary-dark'],
  muted: ['text-tertiary-light', 'text-secondary-dark'],
  line: ['border-light', 'border-dark'],
  'panel-line': ['border-light', 'white@0.1'],
  brand: ['brand', 'brand-dark'],
  strong: ['brand-strong', 'brand-strong-dark'],
  tint: ['brand-weak', 'brand-weak-dark'],
  'brand-line': ['brand-border', 'brand-border-dark'],
  pressed: ['brand-border@0.6', 'brand-border-dark'],
  'primary-ink': ['white', 'background-dark'],
  'primary-hover': ['brand-strong', 'brand-strong-dark'],
  'primary-active': ['brand-emphasis', 'brand-fill-dark'],
  'primary-disabled': ['brand@0.45', 'brand-dark@0.35'],
  'primary-disabled-ink': ['white@0.8', 'background-dark@0.6'],
  ring: ['shadow:ring-brand', 'shadow:ring-brand-dark'],
  e1: ['shadow:e1', null],
  e2: ['shadow:e2', 'none'],
  e5: ['shadow:e5', 'none'],
  field: ['white', 'white@0.05'],
  'field-disabled': ['background-light', 'white@0.05'],
  error: ['error-light', 'error-dark'],
  flat: ['flat-light', 'flat-dark'],
  warning: ['warning-light', 'warning-dark'],
  'warning-tint': ['warning-light@0.1', 'warning-dark@0.15'],
  gain: ['gain-text', 'gain-dark'],
  loss: ['loss-text', 'loss-dark'],
  hover: ['white', 'white@0.03'],
  header: ['background-light@0.8', 'background-dark@0.8'],
  'header-line': ['border-light', 'white@0.06'],
}

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
    const omittedButDocumented = [...OMITTED_COLORS, ...Object.keys(COLOR_ALIASES)].filter((name) => name in fmColors)
    expect(omittedButDocumented, 'a documented token cannot also be listed as omitted or an alias').toEqual([])
    for (const [alias, target] of Object.entries(COLOR_ALIASES)) {
      expect(SOURCE_COLORS[alias], `${alias} is no longer an alias of ${target}`).toBe(SOURCE_COLORS[target])
    }
  })

  it('rounded and spacing steps equal the configured scale', () => {
    const radii = { ...config.theme.extend.borderRadius, full: defaultTheme.borderRadius.full }
    expect(OMITTED_RADII.filter((name) => !(name in radii)), 'stale radius omission').toEqual([])
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
      expect(doc.fontFamily, `${role}.fontFamily`).toBe(portableStack(src.family))
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

  it('carries only documented tonal-ramp steps and radii', () => {
    const documented = new Set(Object.values(fmColors).map((c) => String(rgba(c))))
    const synthetic = Object.entries<Record<string, unknown>>(ext.colorMeta).flatMap(([name, meta]) =>
      ((meta.tonalRamp as string[] | undefined) ?? [])
        .filter((step) => !/^(#|rgba?\()/i.test(step) || !documented.has(String(rgba(step))))
        .map((step) => `${name}: ${step}`),
    )
    expect(synthetic, 'Impeccable accepts every ramp step as a palette color').toEqual([])

    // The detector also widens its radius list from roundedMeta (canonical/value/values/aliases).
    const radii = new Set(Object.values(fm.rounded as Yaml).map((r) => length(r as string)))
    const extraRadii = Object.entries<unknown>(ext.roundedMeta ?? {}).flatMap(([name, meta]) => {
      const m = (meta && typeof meta === 'object' ? meta : { value: meta }) as Record<string, unknown>
      const values = [m.canonical, m.value, ...((m.values as unknown[]) ?? []), ...((m.aliases as unknown[]) ?? [])]
      return values.filter((v) => v !== undefined && !radii.has(length(v as string))).map((v) => `${name}: ${v}`)
    })
    expect(extraRadii, 'Impeccable accepts every roundedMeta value as a radius').toEqual([])
  })

  it('shadows, motion and breakpoints equal their sources', () => {
    const shadows = { ...config.theme.extend.boxShadow }
    expect(OMITTED_SHADOWS.filter((name) => !(name in shadows)), 'stale shadow omission').toEqual([])
    for (const name of OMITTED_SHADOWS) delete shadows[name]
    expect(Object.fromEntries(ext.shadows.map((s: { name: string; value: string }) => [s.name, s.value]))).toEqual(shadows)
    const motion = Object.fromEntries(
      Object.entries(rootVars).filter(([name]) => /^--(duration|ease)-/.test(name)).map(([name, v]) => [name.slice(2), v]),
    )
    expect(Object.fromEntries(ext.motion.map((m: { name: string; value: string }) => [m.name, m.value]))).toEqual(motion)
    expect(config.theme.screens ?? config.theme.extend.screens, 'breakpoints are Tailwind defaults').toBeUndefined()
    expect(Object.fromEntries(ext.breakpoints.map((b: { name: string; value: string }) => [b.name, b.value]))).toEqual(
      Object.fromEntries(DOCUMENTED_SCREENS.map((name) => [name, defaultTheme.screens[name]])),
    )
  })

  it('narrative equals the DESIGN.md text it duplicates', () => {
    const body = designBody
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
  const COLOR = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|oklch|oklab|lab|lch|color-mix|color)\([^)]*\)/gi
  const shadowByName: Record<string, string> = Object.fromEntries(
    sidecar.extensions.shadows.map((s: { name: string; value: string }) => [s.name, s.value]),
  )
  /** Declarations in one specimen block: the light `.ds-stage{…}` or the one inside the dark query. */
  const paletteVars = (block: string | undefined) =>
    Object.fromEntries([...(block ?? '').matchAll(/--ds-([\w-]+):([^;}]+)/g)].map((m) => [m[1], m[2].trim()]))
  const expected = (spec: string) => {
    if (spec === 'none') return 'none'
    if (spec.startsWith('shadow:')) return shadowByName[spec.slice(7)]
    const [token, alpha] = spec.split('@')
    const value = rgba(fmColors[token])
    return String(alpha ? [...value.slice(0, 3), Number(alpha)] : value)
  }
  const actual = (value: string) => (value === 'none' || value.includes(' ') ? value : String(rgba(value)))

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

  it('give every palette variable the token its role names, in both themes', () => {
    const wrong = components.flatMap((c) => {
      const light = paletteVars(c.css.match(/^:host\{[^}]*\}\.ds-stage\{([^}]*)\}/)?.[1])
      const dark = paletteVars(c.css.match(/@container style\([^{]*\{\.ds-stage\{([^}]*)\}\}/)?.[1])
      if (!light.page || !dark.page) return [`${c.refersTo}: palette blocks not found`]
      return [
        ...Object.keys({ ...light, ...dark }).filter((role) => !(role in SPECIMEN_ROLES)).map((r) => `--ds-${r}: no role`),
        ...Object.entries(light).flatMap(([role, value]) => {
          const spec = SPECIMEN_ROLES[role]
          if (!spec) return []
          const out: string[] = []
          if (actual(value) !== expected(spec[0])) out.push(`--ds-${role} light ${value}, expected ${spec[0]}`)
          if (spec[1] === null && role in dark) out.push(`--ds-${role} has one value for both themes`)
          if (spec[1] !== null && !(role in dark)) out.push(`--ds-${role} has no dark value`)
          if (spec[1] !== null && role in dark && actual(dark[role]) !== expected(spec[1])) {
            out.push(`--ds-${role} dark ${dark[role]}, expected ${spec[1]}`)
          }
          return out
        }),
      ].map((msg) => `${c.refersTo}: ${msg}`)
    })
    expect(wrong).toEqual([])
  })

  it('use no named colors in color-bearing declarations', () => {
    const KEYWORDS = new Set(['transparent', 'currentcolor', 'inherit', 'initial', 'none', 'solid', 'dashed', 'inset'])
    const PROP = /^(--ds-[\w-]+|color|background(-color)?|border(-(top|right|bottom|left))?(-color)?|outline(-color)?|fill|stroke|box-shadow|caret-color|accent-color|text-decoration(-color)?)$/
    const named = components.flatMap((c) =>
      [...c.css.matchAll(/\{([^{}]*)\}/g)].flatMap((block) =>
        block[1].split(';').flatMap((decl) => {
          const [prop, ...rest] = decl.split(':')
          if (!PROP.test(prop.trim())) return []
          let value = rest.join(':')
          while (/var\([^()]*\)/.test(value)) value = value.replace(/var\([^()]*\)/g, ' ')
          value = value.replace(COLOR, ' ').replace(/-?[\d.]+[a-z%]*/gi, ' ')
          return (value.match(/[a-z][\w-]*/gi) ?? [])
            .filter((word) => !KEYWORDS.has(word.toLowerCase()))
            .map((word) => `${c.refersTo}: ${prop.trim()} uses ${word}`)
        }),
      ),
    )
    expect(named).toEqual([])
  })

  it('size to their panel stage and key dark mode to the app theme signal', () => {
    // Turbopack (lightningcss) serves hex lowercased, so the query lists the source and served spellings.
    const value = darkVars['--heading-color']
    const spellings = [...new Set([value, value.toLowerCase()])]
    const signal = `@container ${spellings.map((v) => `style(--heading-color: ${v})`).join(' or ')}{`
    for (const c of components) {
      // The panel mounts each specimen in a bare host inside a centered flex stage.
      expect(c.css.startsWith(':host{display:block;width:100%}'), `${c.refersTo}: unconstrained host`).toBe(true)
      // Viewport queries fire on the browser, not the ~350px panel; use container queries.
      expect(c.css, `${c.refersTo}: viewport width query`).not.toMatch(/@media[^{]*width/)
      // The panel sets no theme class; the app's `.dark` custom property is what reaches the specimen.
      expect(c.css, `${c.refersTo}: dark signal`).toContain(signal)
      expect(c.css, `${c.refersTo}: theme hook the panel never sets`).not.toMatch(/:root|:host\(\.dark\)|prefers-color-scheme/)
    }
  })
})
