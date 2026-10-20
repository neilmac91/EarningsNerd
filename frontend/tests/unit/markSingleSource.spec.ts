import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The EN monogram is protected (lessons/brand-the-mark-is-protected.md; the founder, 2026-10-11:
 * "I don't want you to change the logo or monogram"). Its geometry has one source,
 * public/assets/earningsnerd-mark-mono.svg, and every rendition copies it byte for byte: the three
 * path outlines (the E, the N, the arrowhead) and the two group transforms that place them. This
 * spec fails when any asset, template, component or export redraws a path, nudges the N against
 * the E, moves one outline with a transform of its own or an extra group, or stretches the mark
 * with a non-uniform scale. Brand work composes around the mark (arrangements, clear space,
 * sizes); it never edits it.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const REPO = path.resolve(FRONTEND, '..')
const CANONICAL = path.join(FRONTEND, 'public/assets/earningsnerd-mark-mono.svg')

const canonical = readFileSync(CANONICAL, 'utf8')
const PATHS = [...canonical.matchAll(/ d="([^"]+)"/g)].map((m) => m[1])
const GROUPS = ['translate(0,-14.8)', 'translate(0.92,6.98) scale(0.9193)']
/** Each outline's opening move: where a copy of it, faithful or not, begins. */
const STARTS = PATHS.map((d) => d.slice(0, d.indexOf('L')))

/**
 * The placement invariant, read as structure rather than substrings: each copy of the mark is the
 * canonical group `translate(0,-14.8)` holding the E outline and the group
 * `translate(0.92,6.98) scale(0.9193)`, which holds the N and the arrowhead, and nothing between
 * them moves an outline (no transform on a path, no extra group, no transform in a style or a
 * class). A transform above the outer group places the whole mark and is allowed; the stretch check
 * below keeps it uniform. SVG, HTML, JSX and the chart export's concatenated string share the tag
 * syntax, so one reader serves them all (the founder's review of PR #1226 moved only the stacked
 * logo's arrowhead and every substring check stayed green). A stylesheet rule aimed at the paths
 * from elsewhere is beyond this scan; the renditions' stylesheets size the whole svg only.
 */
type Tag = { name: string; close: boolean; selfClosing: boolean; attrs: Record<string, string>; at: number }
type Node = { tag: Tag; children: Node[] }
const TAG = /<(\/?)(svg|g|path|use|symbol)\b((?:[^>"'{]|"[^"]*"|'[^']*'|\{[^}]*\})*)>/g
const ATTR = /([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{([^}]*)\}?)/g
const MOVES = /transform|translate|scale|rotate|matrix|skew/i

function attributes(raw: string): Record<string, string> {
  const attrs: Record<string, string> = {}
  for (const m of raw.matchAll(ATTR)) attrs[m[1]] = m[4] !== undefined ? `{${m[4]}}` : (m[2] ?? m[3] ?? '')
  return attrs
}

function markInstances(source: string): { count: number; problems: string[] } {
  const tags: Tag[] = [...source.matchAll(TAG)].map((m) => ({
    name: m[2],
    close: m[1] === '/',
    selfClosing: /\/\s*$/.test(m[3]),
    attrs: attributes(m[3]),
    at: m.index ?? 0,
  }))
  const problems: string[] = []
  const parse = (i: number): { node: Node; next: number } => {
    const tag = tags[i]
    const node: Node = { tag, children: [] }
    if (tag.selfClosing) return { node, next: i + 1 }
    let j = i + 1
    while (j < tags.length && !(tags[j].close && tags[j].name === tag.name)) {
      if (tags[j].close) {
        problems.push(`unbalanced </${tags[j].name}> at offset ${tags[j].at}`)
        return { node, next: j + 1 }
      }
      const child = parse(j)
      node.children.push(child.node)
      j = child.next
    }
    return { node, next: j + 1 }
  }
  /** A style or class that can move an element (an inline `transform`, a Tailwind `translate-x-1`). */
  const movedBy = (attrs: Record<string, string>) => ['style', 'class', 'className'].find((name) => MOVES.test(attrs[name] ?? ''))
  const unmoved = (node: Node, what: string) => {
    if (node.tag.attrs.transform !== undefined) problems.push(`${what} carries its own transform "${node.tag.attrs.transform}" at offset ${node.tag.at}`)
    const by = movedBy(node.tag.attrs)
    if (by) problems.push(`${what} is moved by its ${by} at offset ${node.tag.at}`)
  }
  const outline = (node: Node | undefined, d: string, what: string) => {
    if (!node || node.tag.name !== 'path' || node.tag.attrs.d !== d) {
      problems.push(`${what} is not where the canonical file puts it`)
      return
    }
    unmoved(node, what)
    if (node.children.length) problems.push(`${what} wraps other elements at offset ${node.tag.at}`)
  }

  let count = 0
  tags.forEach((tag, i) => {
    if (tag.close || tag.name !== 'g' || tag.attrs.transform !== GROUPS[0]) return
    count += 1
    const outer = parse(i).node
    const outerBy = movedBy(outer.tag.attrs)
    if (outerBy) problems.push(`the outer group is moved by its ${outerBy} at offset ${tag.at}`)
    const inner = outer.children.find((c) => c.tag.name === 'g')
    if (outer.children.length !== 2) problems.push(`the outer group at offset ${tag.at} holds ${outer.children.length} elements, not the E and one group`)
    outline(outer.children.find((c) => c.tag.name === 'path'), PATHS[0], 'the E')
    if (!inner || inner.tag.attrs.transform !== GROUPS[1]) {
      problems.push(`the N and arrowhead group at offset ${tag.at} is missing or placed differently`)
      return
    }
    const innerBy = movedBy(inner.tag.attrs)
    if (innerBy) problems.push(`the N and arrowhead group is moved by its ${innerBy} at offset ${inner.tag.at}`)
    if (inner.children.length !== 2) problems.push(`the N and arrowhead group at offset ${inner.tag.at} holds ${inner.children.length} elements, not two outlines`)
    outline(inner.children.find((c) => c.tag.attrs.d === PATHS[1]), PATHS[1], 'the N')
    outline(inner.children.find((c) => c.tag.attrs.d === PATHS[2]), PATHS[2], 'the arrowhead')
  })
  return { count, problems }
}

const list = (dir: string, test: (name: string) => boolean) =>
  readdirSync(dir).filter(test).map((name) => path.join(dir, name))

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name !== 'node_modules') walk(p, out)
    } else if (/\.(tsx?|mjs|js|html|svg)$/.test(entry.name) && !/\.(spec|test)\.tsx?$/.test(entry.name)) out.push(p)
  }
  return out
}

/** The renditions the brand ships, named, plus any other file that carries an outline's start. */
const NAMED = [
  ...list(path.join(FRONTEND, 'public/assets'), (n) => /^earningsnerd-.*\.svg$/.test(n)),
  ...list(path.join(REPO, 'docs/brand/templates'), (n) => /\.(svg|html)$/.test(n)),
  path.join(FRONTEND, 'scripts/brand/og-template.html'),
]
const DISCOVERED = ['app', 'components', 'features', 'lib', 'scripts']
  .flatMap((dir) => walk(path.join(FRONTEND, dir)))
  .filter((file) => STARTS.some((start) => readFileSync(file, 'utf8').includes(start)))
const FILES = [...new Set([...NAMED, ...DISCOVERED])].filter((file) => file !== CANONICAL)
const rel = (file: string) => path.relative(REPO, file).split(path.sep).join('/')

describe('the EN monogram has one source and is never redrawn', () => {
  it('the canonical file defines the three outlines', () => {
    expect(PATHS).toHaveLength(3)
    expect(STARTS.every((start) => start.startsWith('M'))).toBe(true)
    expect(markInstances(canonical), 'the canonical file passes its own placement check').toEqual({ count: 1, problems: [] })
  })

  it('finds the renditions it guards (the check stays meaningful)', () => {
    const names = FILES.map(rel)
    expect(names.filter((n) => n.startsWith('frontend/public/assets/')).length).toBeGreaterThanOrEqual(13)
    expect(names).toEqual(expect.arrayContaining([
      'frontend/components/EarningsNerdLogoIcon.tsx',
      'frontend/scripts/brand/og-template.html',
      'docs/brand/templates/business-card-front.svg',
    ]))
  })

  it.each(FILES.map((file) => [rel(file), file]))('%s copies every outline and placement byte for byte', (_name, file) => {
    const source = readFileSync(file, 'utf8')
    PATHS.forEach((d, i) => {
      expect(source.includes(d), `outline ${i + 1} is missing or redrawn`).toBe(true)
      // every copy of this outline that starts here must be the canonical one, whole
      let at = source.indexOf(STARTS[i])
      while (at !== -1) {
        expect(source.startsWith(d, at), `outline ${i + 1} is edited at offset ${at}`).toBe(true)
        at = source.indexOf(STARTS[i], at + 1)
      }
    })
    for (const group of GROUPS) expect(source.includes(group), `placement "${group}" changed`).toBe(true)
  })

  it.each(FILES.map((file) => [rel(file), file]))('%s places the outlines through the canonical groups and nothing else', (_name, file) => {
    const source = readFileSync(file, 'utf8')
    const marks = markInstances(source)
    expect(marks.problems, 'the transform hierarchy differs from earningsnerd-mark-mono.svg').toEqual([])
    expect(marks.count, 'no copy of the mark found').toBeGreaterThan(0)
    // every copy of every outline sits inside one of those marks, in its canonical place
    PATHS.forEach((d, i) => expect(source.split(d).length - 1, `outline ${i + 1} also appears outside a canonical mark`).toBe(marks.count))
  })

  it.each(FILES.map((file) => [rel(file), file]))('%s never stretches the mark', (_name, file) => {
    for (const m of readFileSync(file, 'utf8').matchAll(/scale\(\s*(-?[\d.]+)\s*[, ]\s*(-?[\d.]+)\s*\)/g)) {
      expect(m[1], `non-uniform ${m[0]}`).toBe(m[2])
    }
  })
})

/**
 * The social card (public/og-image.png, rendered from og-template.html by `npm run brand:assets`) carries
 * the highlight as well as the mark, so its template keeps the highlight's two measured rules
 * (docs/brand/06-system.md §6): the hairline under the tint is 2px whatever the type size, and the
 * highlight never runs across a line break, so the headline breaks before the marked phrase rather
 * than letting it wrap at 84px (OG-01, BG-18).
 */
describe('the social card template keeps the highlight whole and its hairline at 2px', () => {
  const template = readFileSync(path.join(FRONTEND, 'scripts/brand/og-template.html'), 'utf8')
  const markRule = template.match(/\.mark\s*\{([^}]*)\}/)?.[1] ?? ''
  const headline = template.match(/<div class="headline">([\s\S]*?)<\/div>/)?.[1] ?? ''
  const marked = [...headline.matchAll(/<span class="mark">([\s\S]*?)<\/span>/g)]

  it('draws the hairline at 2px', () => {
    expect(markRule, 'the .mark rule is missing').not.toBe('')
    expect(markRule.match(/box-shadow:\s*inset 0 (-?\d+(?:\.\d+)?)px 0/)?.[1], 'the .mark hairline').toBe('-2')
  })

  it('starts the marked phrase on its own line and never breaks inside it', () => {
    expect(marked.length, 'the headline carries one marked phrase').toBe(1)
    const [whole, phrase] = marked[0]
    expect(phrase, 'a line break inside the marked phrase').not.toMatch(/<br/i)
    expect(headline.slice(0, headline.indexOf(whole)), 'the headline breaks before the marked phrase').toMatch(/<br\s*\/?>\s*$/i)
  })
})
