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
 * the E, or stretches the mark with a non-uniform scale. Brand work composes around the mark
 * (arrangements, clear space, sizes); it never edits it.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const REPO = path.resolve(FRONTEND, '..')
const CANONICAL = path.join(FRONTEND, 'public/assets/earningsnerd-mark-mono.svg')

const canonical = readFileSync(CANONICAL, 'utf8')
const PATHS = [...canonical.matchAll(/ d="([^"]+)"/g)].map((m) => m[1])
const GROUPS = ['translate(0,-14.8)', 'translate(0.92,6.98) scale(0.9193)']
/** Each outline's opening move: where a copy of it, faithful or not, begins. */
const STARTS = PATHS.map((d) => d.slice(0, d.indexOf('L')))

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

  it.each(FILES.map((file) => [rel(file), file]))('%s never stretches the mark', (_name, file) => {
    for (const m of readFileSync(file, 'utf8').matchAll(/scale\(\s*(-?[\d.]+)\s*[, ]\s*(-?[\d.]+)\s*\)/g)) {
      expect(m[1], `non-uniform ${m[0]}`).toBe(m[2])
    }
  })
})
