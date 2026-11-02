import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import postcss from 'postcss'
import tailwindcss, { type Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'

/**
 * What Tailwind declares for a utility, and whether a class added on top of a component's own competes with it: the
 * shared half of the override gates for components/ui (inputClassesNoOverrides.spec.tsx for the field,
 * cardClassesNoOverrides.spec.tsx for Card and its sections). Not a spec: a module the gates share. `cx` and `clsx` do
 * no tailwind-merge, so of two utilities that set one property in one state, the one later in the STYLESHEET wins,
 * whatever the class order; the rules a finding names, (a) same chain, (b) no twin under an outranking variant and (f)
 * no union twin, are set out in inputClassesNoOverrides.spec.tsx's header. Tailwind itself (this config, globals.css as
 * input) says what each bare utility declares.
 */
export const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

export const config = createRequire(import.meta.url)(path.join(FRONTEND_ROOT, 'tailwind.config.js')) as Config
export const OUTRANKING = new Set(['dark', ...Object.keys(resolveConfig(config).theme.screens as Record<string, unknown>)])
export const PSEUDO_ELEMENTS = new Set(['placeholder', 'before', 'after', 'file', 'marker', 'selection', 'first-line', 'first-letter', 'backdrop'])

/** `dark:hover:!w-auto` → chain {dark, hover}, utility `w-auto`, important. A colon in brackets does not split. */
export function parseClass(token: string) {
  const variants: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i += 1) {
    const c = token[i]
    if (c === '[' || c === '(') depth += 1
    else if (c === ']' || c === ')') depth -= 1
    else if (c === ':' && depth === 0) {
      variants.push(token.slice(start, i))
      start = i + 1
    }
  }
  const raw = token.slice(start)
  return {
    token,
    utility: raw.replace(/^!/, ''),
    important: raw.startsWith('!'),
    arbitrary: variants.some((v) => v.includes('[')),
    target: variants.filter((v) => PSEUDO_ELEMENTS.has(v)).sort().join(':'),
    chain: new Set(variants.filter((v) => !PSEUDO_ELEMENTS.has(v))),
  }
}

/** A declaration, and whether it is Tailwind's composite plumbing: a value reading a `--tw-*` its own rule does
    not set (the box-shadow behind `shadow-*` and `ring-*`). Two plumbing declarations never compete. */
export type Decl = { prop: string; value: string; plumbing: boolean }
/** What a utility declares, per element it styles: '' is the element itself, `placeholder` its ::placeholder. */
export type Entry = { target: string; decls: Decl[] }
export const declCache = new Map<string, Entry[] | null>()
/** Utilities Tailwind generates that style no element of the field itself (`space-x-2` styles its children). */
export const stylesOthers = new Set<string>()
/** Classes that generate no CSS and only mark an element for a variant (`group-focus-within:`, `peer-invalid:`). */
export const MARKER = /^(group|peer)(\/[\w-]+)?$/

export const SIDES = ['top', 'right', 'bottom', 'left']
/** A shorthand competes with its longhands: `p-2` (padding) with `px-3.5` (padding-left, padding-right), `[background:white]`
    with `bg-panel-light` (background-color), `border` (border-width) with `border-x` (border-left-width, …). Expanded
    until each part is a longhand, so `[border:1px_solid_red]` reaches every side's colour. */
export const LONGHANDS: Record<string, string[]> = {
  padding: SIDES.map((s) => `padding-${s}`),
  margin: SIDES.map((s) => `margin-${s}`),
  inset: SIDES,
  'border-width': SIDES.map((s) => `border-${s}-width`),
  'border-style': SIDES.map((s) => `border-${s}-style`),
  'border-color': SIDES.map((s) => `border-${s}-color`),
  'border-radius': ['top-left', 'top-right', 'bottom-right', 'bottom-left'].map((c) => `border-${c}-radius`),
  border: ['border-width', 'border-style', 'border-color'],
  ...Object.fromEntries(SIDES.map((s) => [`border-${s}`, [`border-${s}-width`, `border-${s}-style`, `border-${s}-color`]])),
  background: ['background-color', 'background-image', 'background-position', 'background-size', 'background-repeat', 'background-attachment', 'background-origin', 'background-clip'],
  font: ['font-style', 'font-variant', 'font-weight', 'font-stretch', 'font-size', 'line-height', 'font-family'],
  'scroll-margin': SIDES.map((s) => `scroll-margin-${s}`),
  'scroll-padding': SIDES.map((s) => `scroll-padding-${s}`),
  outline: ['outline-color', 'outline-style', 'outline-width'],
  overflow: ['overflow-x', 'overflow-y'],
  gap: ['row-gap', 'column-gap'],
}

/** A logical property names the physical one it sets in this left-to-right app (no `dir="rtl"` anywhere): `ps-0`
    (padding-inline-start) competes with `px-cap-5` (padding-left), `rounded-s-none` with `rounded-xl`. Values carry over
    as they are, since a logical property is the physical one under another name, not a shorthand. */
const LOGICAL: Record<string, string[]> = (() => {
  const out: Record<string, string[]> = {}
  for (const box of ['padding', 'margin', 'scroll-padding', 'scroll-margin']) {
    out[`${box}-inline`] = [`${box}-left`, `${box}-right`]
    out[`${box}-block`] = [`${box}-top`, `${box}-bottom`]
    out[`${box}-inline-start`] = [`${box}-left`]
    out[`${box}-inline-end`] = [`${box}-right`]
    out[`${box}-block-start`] = [`${box}-top`]
    out[`${box}-block-end`] = [`${box}-bottom`]
  }
  Object.assign(out, {
    'inset-inline': ['left', 'right'], 'inset-block': ['top', 'bottom'],
    'inset-inline-start': ['left'], 'inset-inline-end': ['right'], 'inset-block-start': ['top'], 'inset-block-end': ['bottom'],
    'border-start-start-radius': ['border-top-left-radius'], 'border-start-end-radius': ['border-top-right-radius'],
    'border-end-start-radius': ['border-bottom-left-radius'], 'border-end-end-radius': ['border-bottom-right-radius'],
    'inline-size': ['width'], 'block-size': ['height'], 'min-inline-size': ['min-width'], 'max-inline-size': ['max-width'],
    'min-block-size': ['min-height'], 'max-block-size': ['max-height'],
  })
  for (const part of ['', '-width', '-style', '-color']) {
    out[`border-inline${part}`] = [`border-left${part}`, `border-right${part}`]
    out[`border-block${part}`] = [`border-top${part}`, `border-bottom${part}`]
    out[`border-inline-start${part}`] = [`border-left${part}`]
    out[`border-inline-end${part}`] = [`border-right${part}`]
    out[`border-block-start${part}`] = [`border-top${part}`]
    out[`border-block-end${part}`] = [`border-bottom${part}`]
  }
  return out
})()

/** A rule's declarations as longhands. A multi-value shorthand keeps its whole value, so it differs from a longhand. */
export function longhands(decls: { prop: string; value: string }[]): Decl[] {
  const own = new Set(decls.map((d) => d.prop))
  const expand = (prop: string, value: string, plumbing: boolean, depth = 0): Decl[] => {
    const logical = LOGICAL[prop]
    if (logical && depth < 4) return logical.flatMap((p) => expand(p, value, plumbing, depth + 1))
    const parts = LONGHANDS[prop]
    if (!parts || depth >= 4) return [{ prop, value, plumbing }]
    // A shorthand of several values keeps them whole, so it differs from a longhand; one value (a function such as
    // `min(1.25rem, 5vw)` included, whose spaces sit inside its parentheses) is each longhand's value.
    let bare = value
    for (let prev = ''; prev !== bare; ) [prev, bare] = [bare, bare.replace(/\([^()]*\)/g, '')]
    const each = /\s/.test(bare.trim()) ? `${prop}(${value})` : value
    return parts.flatMap((p) => expand(p, each, plumbing, depth + 1))
  }
  return decls.flatMap(({ prop, value }) => {
    const plumbing = !prop.startsWith('--') && [...value.matchAll(/var\((--tw-[\w-]+)/g)].some((m) => !own.has(m[1]))
    return expand(prop, value, plumbing)
  })
}

/** Unescapes a CSS identifier: `px-3\.5` → `px-3.5`, `\2c ` → `,`. */
export const unescapeCss = (s: string) =>
  s.replace(/\\([0-9a-fA-F]{1,6}) ?|\\(.)/g, (_, hex: string | undefined, ch: string | undefined) => (hex ? String.fromCodePoint(parseInt(hex, 16)) : ch!))

/** What Tailwind declares for each bare utility, read off the rules whose selector is that one class, alone or with
    a pseudo-element (`.placeholder-x::placeholder`). A utility whose rules style anything else is noted in stylesOthers. */
export async function loadDeclarations(utilities: string[]): Promise<void> {
  const missing = [...new Set(utilities)].filter((u) => !declCache.has(u))
  if (!missing.length) return
  const from = path.join(FRONTEND_ROOT, 'app/globals.css')
  const css = await postcss([tailwindcss({ ...config, content: [{ raw: missing.join(' '), extension: 'html' }], safelist: [] })]).process(
    readFileSync(from, 'utf8'),
    { from },
  )
  for (const u of missing) declCache.set(u, null)
  const CLASS = /\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)/g
  css.root.walkRules((rule) => {
    const own = rule.parent?.type === 'root' && rule.selector.match(/^\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[\w-])+)(?:::(-(?:moz|webkit|ms)-(?:input-)?)?([\w-]+))?$/)
    if (own) {
      const name = unescapeCss(own[1])
      if (!missing.includes(name)) return
      const decls: { prop: string; value: string }[] = []
      rule.walkDecls((d) => {
        decls.push({ prop: d.prop, value: d.value.trim() })
      })
      declCache.set(name, [...(declCache.get(name) ?? []), { target: own[3] ?? '', decls: longhands(decls) }])
      return
    }
    for (const m of rule.selector.matchAll(CLASS)) {
      const name = unescapeCss(m[1])
      if (missing.includes(name)) stylesOthers.add(name)
    }
  })
}

export const joinTarget = (a: string, b: string) => [a, b].filter(Boolean).sort().join(':')

/** `[padding-top,padding-bottom]`, with a full set of longhands named by its shorthand: `[border-color]`. */
export function propList(props: string[]): string {
  let out = [...new Set(props)]
  for (const [short, parts] of Object.entries(LONGHANDS)) {
    if (parts.every((p) => out.includes(p))) out = [...out.filter((p) => !parts.includes(p)), short]
  }
  return `[${out.join(',')}]`
}

export const sameSet = (a: Set<string>, b: Set<string>) => a.size === b.size && [...a].every((x) => b.has(x))

export type Parsed = ReturnType<typeof parseClass>
/** Variant pairs that cannot hold on one element at once (a disabled control takes no focus), so rule (f) skips them. */
export const EXCLUSIVE: [string, string][] = [
  ['disabled', 'enabled'], ['disabled', 'focus'], ['disabled', 'focus-visible'], ['disabled', 'focus-within'],
  ['motion-safe', 'motion-reduce'], ['portrait', 'landscape'], ['ltr', 'rtl'], ['contrast-more', 'contrast-less'],
]
export const isSubset = (x: Set<string>, y: Set<string>) => [...x].every((v) => y.has(v))

/** Rule (f). Returns the union chain when the outcome there is left to variant order. */
export function cooccurring(a: Parsed, aTarget: string, f: Parsed, props: string[], field: string[], added: Parsed[]): string | undefined {
  if (isSubset(a.chain, f.chain) || isSubset(f.chain, a.chain)) return undefined
  if (EXCLUSIVE.some(([x, y]) => (a.chain.has(x) && f.chain.has(y)) || (a.chain.has(y) && f.chain.has(x)))) return undefined
  const fieldParsed = field.map(parseClass)
  const setsHere = (t: Parsed) =>
    (declCache.get(t.utility) ?? []).filter((e) => joinTarget(t.target, e.target) === aTarget).flatMap((e) => e.decls).filter((d) => props.includes(d.prop))
  // A chain the field styles itself: a differing class there is rule (a)'s finding, an equal one changes nothing.
  if (fieldParsed.some((g) => sameSet(g.chain, a.chain) && setsHere(g).length)) return undefined
  const union = new Set([...a.chain, ...f.chain])
  const holders = [...fieldParsed, ...added]
    .filter((t) => !t.arbitrary && isSubset(t.chain, union))
    .map((t) => ({ chain: t.chain, decls: setsHere(t).filter((d) => !d.plumbing) }))
    .filter((t) => t.decls.length)
  for (const prop of props) {
    const setting = holders.filter((h) => h.decls.some((d) => d.prop === prop))
    const maximal = setting.filter((h) => !setting.some((o) => o.chain.size > h.chain.size && isSubset(h.chain, o.chain)))
    if (new Set(maximal.flatMap((h) => h.decls.filter((d) => d.prop === prop).map((d) => d.value))).size > 1) return [...union].sort().join('+')
  }
  return undefined
}

export function competing(field: string[], added: string[]): string[] {
  const out = new Set<string>()
  /** (f), one per added class and union state, naming the field class with the longest chain there. */
  const unionFindings = new Map<string, { size: number; text: string }>()
  const parsedAdded = added.map(parseClass)
  for (const a of parsedAdded) {
    if (a.important) out.add(`${a.token} (important)`)
    if (a.arbitrary) {
      out.add(`${a.token} (arbitrary variant)`)
      continue
    }
    const aEntries = declCache.get(a.utility)
    if (!aEntries) {
      if (!MARKER.test(a.utility) && !stylesOthers.has(a.utility)) out.add(`${a.token} (not a class Tailwind generates)`)
      continue
    }
    for (const ae of aEntries) {
      const aTarget = joinTarget(a.target, ae.target)
      for (const f of field.map(parseClass)) {
        for (const fe of declCache.get(f.utility) ?? []) {
          if (joinTarget(f.target, fe.target) !== aTarget) continue
          const props = fe.decls
            .filter((d) => ae.decls.some((x) => x.prop === d.prop && x.value !== d.value && !(x.plumbing && d.plumbing)))
            .map((d) => d.prop)
          if (!props.length) continue
          const list = propList(props)
          if (sameSet(a.chain, f.chain)) {
            out.add(`${a.token} vs ${f.token} ${list} (same chain)`)
            continue
          }
          const lacking = [...f.chain].filter((v) => OUTRANKING.has(v) && !a.chain.has(v))
          const rest = [...f.chain].filter((v) => !OUTRANKING.has(v))
          if (!lacking.length || !rest.every((v) => a.chain.has(v))) {
            // (f) owns the pairs in one theme and screen; a field chain under a dark/screen variant `a` lacks is (b)'s.
            const union = lacking.length ? undefined : cooccurring(a, aTarget, f, props, field, parsedAdded)
            if (union) {
              const key = `${a.token} ${union}`
              const held = unionFindings.get(key)
              if (!held || f.chain.size > held.size) unionFindings.set(key, { size: f.chain.size, text: `${a.token} vs ${f.token} ${list} (no ${union} twin)` })
            }
            continue
          }
          const want = new Set([...a.chain, ...lacking])
          const twin = parsedAdded.some((t) =>
            sameSet(t.chain, want) &&
            (declCache.get(t.utility) ?? []).some((te) => joinTarget(t.target, te.target) === aTarget && te.decls.some((d) => props.includes(d.prop))),
          )
          if (!twin) out.add(`${a.token} vs ${f.token} ${list} (no ${lacking.join('+')} twin)`)
        }
      }
    }
  }
  for (const { text } of unionFindings.values()) out.add(text)
  return [...out]
}
