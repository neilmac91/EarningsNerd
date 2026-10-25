import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The analysis figure surfaces (the metrics table's sheet and the KPI cards; DESIGN_SYSTEM.md, Analysis table and
 * Analysis KPI) have their own inks, measured with APCA against the ground they sit on. Two rules hold them:
 *
 * 1. Scope. The figure surfaces' tokens stay on those surfaces. The data inks amend CLAUDE.md rule 11's "chip/delta
 *    text = the 700-level tokens" for these surfaces alone (green-800 for a light gain, rose-200 for a dark loss), so
 *    the gain/loss data inks are written once, in lib/financialTone's dataDirectionText, and dataDirectionText is read
 *    only by the two surfaces; every other delta keeps directionText and the 700 level. The sheet, rule, figure, note
 *    and data-dark warning tokens and the figure face are named only by the files that draw those surfaces.
 * 2. Contrast. Every pair the surfaces draw meets its APCA tier (apca-w3 0.1.9's SA98G constants, below): figures
 *    and metric names |Lc| >= 90; change lines, headings and labels >= 75; marks and the missing-value dash >= 60;
 *    rules >= 15 and a hovered row's rules >= 30. The app-wide secondary ink is held here too: it reads in dark as
 *    in light (|Lc| >= 75 on the dark panel and page), and tertiary's dark twin stays text-safe (4.5:1).
 * 3. Balance. In dark the gain and loss data inks match in contrast and chroma, so neither direction reads louder
 *    (emerald-300 beside rose-200 did), and dark primary stays a step above the secondary ink it once all but met.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

const FIGURE_SURFACES = [
  'features/analysis/components/MetricsTable.tsx',
  'features/analysis/components/KpiStrip.tsx',
  'features/analysis/components/DataNoteMark.tsx',
]
/** Each token family of the figure surfaces, and the only files that may name it (behind any utility: text-, bg-, border-). */
const SCOPE: { what: string; pattern: RegExp; files: string[] }[] = [
  { what: 'the gain/loss data inks', pattern: /(?<!\w)(?:gain|loss)-data(?:-dark)?(?![\w-])/, files: ['lib/financialTone.ts'] },
  { what: 'dataDirectionText', pattern: /\bdataDirectionText\b/, files: ['lib/financialTone.ts', 'features/analysis/components/MetricsTable.tsx', 'features/analysis/components/KpiStrip.tsx'] },
  { what: 'the data-dark warning ink', pattern: /(?<!\w)warning-data-dark(?![\w-])/, files: ['features/analysis/components/DataNoteMark.tsx'] },
  { what: 'the figure and note inks', pattern: /(?<!\w)(?:figure|note)-(?:light|dark)(?![\w-])/, files: [...FIGURE_SURFACES, 'lib/financialTone.ts'] },
  { what: 'the sheet and its rules', pattern: /(?<!\w)(?:well|rule|rule-strong)-(?:light|dark)(?![\w-])/, files: ['components/ui/DataTable.tsx'] },
  // The figure face also sets the evidence dialog's figures (SourceValue), where the minus must draw as it does in the cell.
  { what: 'the figure face', pattern: /(?<![\w-])font-figure(?![\w-])/, files: [...FIGURE_SURFACES, 'features/analysis/components/SourceValue.tsx'] },
]

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : walk(full)
    return /\.(?:[cm]?[jt]sx?|css)$/.test(entry.name) && !/\.(?:spec|test)\.|\.d\.ts$/.test(entry.name) ? [full] : []
  })
}
/** Code without its comments: a comment that names a token (globals.css explains the figure face) is not a use. */
const code = (text: string) => text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1')
const SOURCES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir))).map((file) => ({
  rel: path.relative(ROOT, file).split(path.sep).join('/'),
  text: code(readFileSync(file, 'utf8')),
}))

// ---- APCA (apca-w3 0.1.9, SA98G) ------------------------------------------------------------------------------
const luminance = (hex: string) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  return 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.072175 * b ** 2.4
}
const soft = (y: number) => (y > 0.022 ? y : y + (0.022 - y) ** 1.414)
/** Lc of text `fg` on ground `bg`: positive for dark text on a light ground, negative for light on dark. */
function apca(fg: string, bg: string): number {
  const text = soft(luminance(fg))
  const ground = soft(luminance(bg))
  if (Math.abs(ground - text) < 0.0005) return 0
  if (ground > text) {
    const sapc = (ground ** 0.56 - text ** 0.57) * 1.14
    return sapc < 0.1 ? 0 : (sapc - 0.027) * 100
  }
  const sapc = (ground ** 0.65 - text ** 0.62) * 1.14
  return sapc > -0.1 ? 0 : (sapc + 0.027) * 100
}
const wcag = (a: string, b: string) => {
  const rel = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl
  }
  const [hi, lo] = [rel(a), rel(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** OKLCH chroma (Björn Ottosson's OKLab), the colourfulness two inks of one lightness are compared by. */
function chroma(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  const [l, m, s] = [
    0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
    0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
    0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
  ].map(Math.cbrt)
  return Math.hypot(1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s)
}

const colors = (createRequire(import.meta.url)('../../tailwind.config.js') as { theme: { extend: { colors: Record<string, Record<string, unknown>> } } }).theme.extend.colors
const token = (pathName: string): string => {
  const value = pathName.split('.').reduce<unknown>((node, key) => (node as Record<string, unknown>)?.[key], colors)
  if (typeof value !== 'string' || !/^#[0-9A-Fa-f]{6}$/.test(value)) throw new Error(`${pathName} is not a hex token: ${String(value)}`)
  return value
}

/** [role, ink token, ground token, minimum |Lc|], per theme. The table's heading row and metric column sit on panel. */
const PAIRS: [string, string, string, number][] = [
  ...(['light', 'dark'] as const).flatMap((theme): [string, string, string, number][] => {
    const sheet = `well.${theme}`
    const panel = `panel.${theme}`
    const gain = theme === 'light' ? 'gain.data' : 'gain.data-dark'
    const loss = theme === 'light' ? 'loss.data' : 'loss.data-dark'
    const review = theme === 'light' ? 'warning.light' : 'warning.data-dark'
    const flat = theme === 'light' ? 'text.secondary.light' : 'note.dark'
    return [
      [`${theme} table value`, `figure.${theme}`, sheet, 90],
      [`${theme} metric name`, `figure.${theme}`, panel, 90],
      [`${theme} heading row`, `text.secondary.${theme}`, panel, 75],
      [`${theme} currency line`, `text.secondary.${theme}`, panel, 75],
      [`${theme} table gain`, gain, sheet, 75],
      [`${theme} table loss`, loss, sheet, 75],
      [`${theme} table flat change`, flat, sheet, 75],
      [`${theme} table mark`, `note.${theme}`, sheet, 60],
      [`${theme} table review letter`, review, sheet, 60],
      [`${theme} KPI value`, `figure.${theme}`, panel, 75],
      [`${theme} KPI label and period`, `text.secondary.${theme}`, panel, 75],
      [`${theme} KPI gain`, gain, panel, 75],
      [`${theme} KPI loss`, loss, panel, 75],
      [`${theme} KPI mark`, `note.${theme}`, panel, 60],
      [`${theme} KPI review letter`, review, panel, 60],
      [`${theme} rule on the sheet`, `rule.${theme}`, sheet, 15],
      [`${theme} rule on the panel frame`, `rule.${theme}`, panel, 15],
      [`${theme} hovered rule on the sheet`, `rule.strong-${theme}`, sheet, 30],
      [`${theme} hovered rule on the panel frame`, `rule.strong-${theme}`, panel, 30],
    ]
  }),
  ['dark secondary ink on the panel', 'text.secondary.dark', 'panel.dark', 75],
  ['dark secondary ink on the page', 'text.secondary.dark', 'background.dark', 75],
]

describe('the analysis figure surfaces keep their own inks', () => {
  it('names each figure-surface token only where the surfaces are drawn', () => {
    expect(SOURCES.length).toBeGreaterThan(300)
    const strays = SCOPE.flatMap(({ what, pattern, files }) =>
      SOURCES.filter((source) => pattern.test(source.text) && !files.includes(source.rel)).map((source) => `${source.rel}: ${what}`))
    expect(strays, 'figure-surface tokens outside the figure surfaces (other deltas keep directionText and the 700 level)').toEqual([])
    // Each family is in use where it is allowed, so a renamed token cannot leave its line passing vacuously.
    for (const { what, pattern, files } of SCOPE) expect(SOURCES.some((source) => files.includes(source.rel) && pattern.test(source.text)), what).toBe(true)
  })

  it('meets every APCA tier it is drawn at', () => {
    const misses = PAIRS.map(([role, ink, ground, minimum]) => ({ role, ink, ground, minimum, lc: apca(token(ink), token(ground)) }))
      .filter(({ lc, minimum }) => Math.abs(lc) < minimum)
      .map(({ role, ink, ground, minimum, lc }) => `${role}: ${ink} ${token(ink)} on ${ground} ${token(ground)} is Lc ${lc.toFixed(1)}, under ${minimum}`)
    expect(misses).toEqual([])
  })

  it("keeps tertiary's dark twin text-safe and below the secondary ink", () => {
    for (const ground of ['panel.dark', 'background.dark']) {
      expect(wcag(token('text.tertiary.dark'), token(ground)), `tertiary-dark on ${ground}`).toBeGreaterThanOrEqual(4.5)
      expect(Math.abs(apca(token('text.tertiary.dark'), token(ground))), `tertiary-dark stays quieter than secondary on ${ground}`)
        .toBeLessThan(Math.abs(apca(token('text.secondary.dark'), token(ground))) - 15)
    }
  })

  it('matches the dark gain and loss data inks in contrast and chroma, so neither direction reads louder', () => {
    for (const ground of ['well.dark', 'panel.dark']) {
      const [gain, loss] = [apca(token('gain.data-dark'), token(ground)), apca(token('loss.data-dark'), token(ground))]
      expect(Math.abs(gain - loss), `gain Lc ${gain.toFixed(1)} against loss Lc ${loss.toFixed(1)} on ${ground}`).toBeLessThanOrEqual(1)
    }
    const [gain, loss] = [chroma(token('gain.data-dark')), chroma(token('loss.data-dark'))]
    expect(Math.abs(gain - loss), `gain chroma ${gain.toFixed(3)} against loss chroma ${loss.toFixed(3)}`).toBeLessThanOrEqual(0.01)
  })

  it('keeps dark primary, the one heading ink, a step above the secondary ink', () => {
    // At #D7DADC primary sat 1.05:1 from the gray-300 secondary, so dark body copy and its supporting text met.
    expect(wcag(token('text.primary.dark'), token('text.secondary.dark'))).toBeGreaterThanOrEqual(1.2)
    expect(token('text.heading.dark')).toBe(token('text.primary.dark'))
    for (const ground of ['panel.dark', 'background.dark']) expect(Math.abs(apca(token('text.primary.dark'), token(ground))), ground).toBeGreaterThanOrEqual(90)
  })

  it('computes APCA and OKLCH chroma as their references do', () => {
    // Reference values from apca-w3 0.1.9: APCAcontrast(sRGBtoY(fg), sRGBtoY(bg)).
    expect(apca('#000000', '#FFFFFF')).toBeCloseTo(106.04, 1)
    expect(apca('#FFFFFF', '#000000')).toBeCloseTo(-107.88, 1)
    expect(apca('#1A1A17', '#FBFAF6')).toBeCloseTo(101.3, 1)
    expect(apca('#9CA3AF', '#1F2937')).toBeCloseTo(-48.6, 1)
    expect(apca('#888888', '#888888')).toBe(0)
    // OKLCH chroma against its published values: pure red is oklch(0.628 0.2577 29.2), pure blue oklch(0.452 0.3132
    // 264.1) (between them every column of OKLab's first matrix), a neutral grey 0.
    expect(chroma('#FF0000')).toBeCloseTo(0.2577, 4)
    expect(chroma('#0000FF')).toBeCloseTo(0.3132, 4)
    expect(chroma('#888888')).toBeCloseTo(0, 4)
  })
})
