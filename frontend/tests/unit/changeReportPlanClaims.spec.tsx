import { render, screen, within } from '@testing-library/react'
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'

/**
 * The landing's Change Report claims, held to what production serves (D-046's pricing truth; CLAUDE.md rules 4
 * and 12).
 *
 * Production serves every reader the report's metric deltas only: the XBRL metric changes against the prior filing,
 * with no plan gate. The report's risk lines are omitted for everyone (backend/app/services/change_report_service.py
 * sets `risks` to None), and its one plan difference, the Item 1A wording block (backend/app/services/entitlements.py:
 * `section_changes`, every changed paragraph for Pro, the first `section_changes_items` for everyone else), is served
 * only behind ENABLE_SECTION_CHANGES, which backend/app/config.py defaults to False and which no workflow under
 * .github/workflows sets, so production serves no wording diff. Free, Pro and an anonymous reader read the same
 * report. While that holds the landing claims nothing more: the plan table's two Change Report cells read the same
 * (PricingSection.tsx), ProDepth's Change Report row wears no Pro chip, and that row (its line and its product
 * screen) names no risk factor and no wording or language change.
 *
 * The first case reads the flag where production takes it, the Settings default and the workflows' executable
 * lines (test_section_changes_flag_placement.py keeps any setting of it to the three deploy maps), and fails once
 * the flag can ship: that PR restates the landing's Change Report claims from entitlements.py and moves this gate
 * beside them. Its planted forms score the read, and the row's words are read the same way, with planted forms of
 * their own. Out of reach: a value set on the service outside the repository (a console edit), which no file here
 * records, and ProDepth's lead, which speaks for all three features and is review-checked.
 */

const flags = vi.hoisted(() => ({ analysis: false }))
vi.mock('@/lib/featureFlags', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/featureFlags')>()
  return {
    ...actual,
    ENABLE_PRO_TRIAL: false,
    ENABLE_FPI_FILINGS: false,
    get ENABLE_ANALYSIS() {
      return flags.analysis
    },
  }
})
vi.mock('@/lib/analytics', () => ({ default: { homepageSectionViewed: vi.fn(), billingCycleToggled: vi.fn() } }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

import PricingSection from '@/features/marketing/components/PricingSection'
import ProDepth from '@/features/marketing/components/ProDepth'

const FLAG = 'ENABLE_SECTION_CHANGES'
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const CONFIG = path.join(ROOT, 'backend/app/config.py')
const WORKFLOWS = path.join(ROOT, '.github/workflows')

/** pydantic's spellings of a false bool; any other value, a `${…}` the deploy expands included, may ship the flag. */
const OFF = new Set(['0', 'false', 'f', 'no', 'n', 'off'])

const RESTATE =
  `${FLAG} can now ship, so the Change Report differs by plan (entitlements.py: section_changes, and ` +
  'section_changes_items for the teaser) and serves its Item 1A wording diff. Restate the landing\'s Change Report ' +
  'claims from entitlements.py (the plan table\'s row in features/marketing/components/PricingSection.tsx, the Pro ' +
  'chip and the line on ProDepth\'s Change Report row, whose risk and language clauses come back with the flag, ' +
  'tasks/todo.md E27) and move this gate beside them.'

const SAME_REPORT =
  `Free and Pro read the same Change Report while ${FLAG} stays off (its one plan difference, entitlements.py's ` +
  'wording block, ships behind that flag), so the landing claims no difference. Ship the flag first, then restate ' +
  'the claims from entitlements.py.'

const METRIC_DELTAS_ONLY =
  'Production serves every reader the Change Report\'s metric deltas only: change_report_service.py omits its risk ' +
  `lines for everyone, and its wording diff ships behind ${FLAG}, which is off. Say what changed against the prior ` +
  'filing, metric by metric, computed from XBRL; the risk and language clauses come back with the flag (tasks/todo.md ' +
  'E27).'

/**
 * The words in a piece of copy that name what production withholds while the flag is off: a risk factor (the
 * report's risk lines) or a change of wording or language (the Item 1A wording diff, which pairs paragraphs and marks
 * the words that moved). Whole words in any case; a word may run into a count, as a subhead's textContent does
 * ("No longer cited2"), so the end of a word is the end of its letters.
 */
const WITHHELD = /\b(?:risks?|languages?|wordings?|words?|redlines?|paragraphs?|item\s*1a|cited)(?![a-z])/gi
function namesWhatProductionWithholds(copy: string): string[] {
  return [...copy.matchAll(WITHHELD)].map((match) => match[0])
}

/**
 * Whether production can serve the wording diff: the Settings default is True, or an executable line of a workflow
 * gives the flag a value that is not a false spelling (or names it without a value the read can take). Throws when
 * config.py declares no default, so a renamed or moved field cannot leave the gate reading nothing.
 */
function flagShips(config: string, workflows: ReadonlyArray<readonly [string, string]>): boolean {
  const defaults = [...config.matchAll(new RegExp(`^\\s*${FLAG}\\s*:\\s*bool\\s*=\\s*(True|False)\\b`, 'gm'))]
  if (defaults.length !== 1) throw new Error(`config.py declares ${FLAG}'s default ${defaults.length} times, not once`)
  if (defaults[0][1] === 'True') return true
  for (const [, text] of workflows) {
    for (const line of text.split('\n')) {
      if (line.trimStart().startsWith('#') || !line.includes(FLAG)) continue
      const values = [...line.matchAll(new RegExp(`${FLAG}\\s*[=:]\\s*["']?([^,\\s"']+)`, 'g'))].map((m) => m[1].toLowerCase())
      if (values.length === 0 || values.some((value) => !OFF.has(value))) return true
    }
  }
  return false
}

/** Every workflow under .github/workflows, by file name. */
const workflowFiles = () =>
  readdirSync(WORKFLOWS)
    .filter((file) => /\.ya?ml$/.test(file))
    .map((file) => [file, readFileSync(path.join(WORKFLOWS, file), 'utf8')] as const)

/** Whether production can serve the wording diff, read where production takes the flag. */
const productionShipsTheFlag = () => flagShips(readFileSync(CONFIG, 'utf8'), workflowFiles())

/** ProDepth's Change Report row as rendered: its heading, its line and its product screen, read from the nearest
 *  element that holds both the heading and the demo. */
function changeReportRow(): HTMLElement {
  const heading = screen.getByRole('heading', { level: 3, name: 'Change Report' })
  const demo = document.querySelector('[data-capture="change-report"]')
  // Anti-vacuity: the demo renders, so the read takes the product screen along with the line.
  expect(demo, 'the Change Report demo renders').not.toBeNull()
  let row: HTMLElement | null = heading.parentElement
  while (row && !row.contains(demo)) row = row.parentElement
  expect(row, 'one element holds the Change Report heading and its demo').not.toBeNull()
  return row!
}

const DEFAULT_OFF = `class Settings(BaseSettings):\n    ${FLAG}: bool = False\n`

describe('the read of whether production serves the wording diff (planted forms)', () => {
  it('is off for a False default and workflows that set nothing, a comment, or a false spelling', () => {
    expect(flagShips(DEFAULT_OFF, [])).toBe(false)
    expect(flagShips(DEFAULT_OFF, [['ci.yml', `  # ${FLAG}=true goes on all three maps when it flips\n`]])).toBe(false)
    expect(flagShips(DEFAULT_OFF, [['ci.yml', `      --update-env-vars=ENVIRONMENT=production,${FLAG}=false,DB_POOL_SIZE=3\n`]])).toBe(false)
  })
  it('is on for a True default, a map that sets it on, an env entry, a value the deploy expands, or a bare mention', () => {
    expect(flagShips(`    ${FLAG}: bool = True\n`, [])).toBe(true)
    expect(flagShips(DEFAULT_OFF, [['ci.yml', `      --update-env-vars=ENVIRONMENT=production,${FLAG}=true\n`]])).toBe(true)
    expect(flagShips(DEFAULT_OFF, [['ops.yml', `      ${FLAG}: "1"\n`]])).toBe(true)
    expect(flagShips(DEFAULT_OFF, [['ci.yml', `      --update-env-vars=A=1,${FLAG}=\${SECTION_CHANGES}\n`]])).toBe(true)
    expect(flagShips(DEFAULT_OFF, [['ci.yml', `      echo "${FLAG} is set by hand"\n`]])).toBe(true)
  })
  it('throws when config.py declares no default for the flag', () => {
    expect(() => flagShips('class Settings(BaseSettings):\n    OTHER: bool = False\n', [])).toThrow(/0 times/)
  })
})

describe('the read of what a Change Report line names that production withholds (planted forms)', () => {
  it('finds a risk factor, a wording or language change, and a screen that shows the risk lines', () => {
    expect(
      namesWhatProductionWithholds(
        'What changed against the prior filing: metric deltas computed from XBRL, risk factors that are new, and language no longer cited.',
      ),
    ).toEqual(['risk', 'language', 'cited'])
    expect(namesWhatProductionWithholds('See how the Item 1A wording moved since the last 10-K.')).toEqual(['Item 1A', 'wording'])
    expect(namesWhatProductionWithholds('New Risks, and the words that left, paragraph by paragraph, in redlines.')).toEqual([
      'Risks',
      'words',
      'paragraph',
      'paragraph',
      'redlines',
    ])
    // WhatChanged's subheads as their textContent runs, each into its count.
    expect(namesWhatProductionWithholds('New risk factors2No longer cited1')).toEqual(['risk', 'cited'])
  })
  it('passes the metric deltas, and a word that only begins like one', () => {
    expect(
      namesWhatProductionWithholds('What changed against the prior filing, metric by metric, computed from XBRL. Both plans include it.'),
    ).toEqual([])
    expect(namesWhatProductionWithholds('Revenue, net income and diluted EPS all rose against the prior fiscal year.')).toEqual([])
    expect(namesWhatProductionWithholds('A risky wordsmith')).toEqual([])
  })
})

describe("the landing's Change Report claims while production serves no wording diff", () => {
  it(`finds ${FLAG} off in production: config.py's default and every workflow`, () => {
    const workflows = workflowFiles()
    // Anti-vacuity: the read reaches the deploy's maps (ci.yml's three service and job maps among them).
    const ci = workflows.find(([file]) => file === 'ci.yml')?.[1] ?? ''
    expect((ci.match(/--update-env-vars=/g) ?? []).length).toBeGreaterThanOrEqual(3)
    expect(flagShips(readFileSync(CONFIG, 'utf8'), workflows), RESTATE).toBe(false)
  })

  it("gives the Change Report to both plans alike in the landing's plan table", () => {
    render(<PricingSection accessMode="public" showBeta={false} />)
    const row = screen.getByRole('rowheader', { name: 'Change Report' }).closest('tr')!
    const [free, pro] = within(row).getAllByRole('cell').map((cell) => cell.textContent)
    expect(free, `the plan table gives the Change Report's two plans different cells. ${SAME_REPORT}`).toBe(pro)
    expect(free).toBe('Included')
  })

  it.each([false, true])("puts no Pro chip on ProDepth's Change Report row (analysis route on: %s)", (analysis) => {
    flags.analysis = analysis
    render(<ProDepth />)
    const chip = (title: string) =>
      within(screen.getByRole('heading', { level: 3, name: title }).parentElement!).queryByText('Pro', { exact: true })
    // Anti-vacuity: the read finds the chip where Pro has a feature in full.
    expect(chip('Ask this Filing')).toBeInTheDocument()
    expect(chip('Change Report'), `ProDepth puts the Pro chip on its Change Report row. ${SAME_REPORT}`).toBeNull()
    expect(screen.getByText(/Both plans include it\.$/)).toBeInTheDocument()
  })

  it.each([false, true])(
    "names no risk factor and no wording change on ProDepth's Change Report row while the flag is off (analysis route on: %s)",
    (analysis) => {
      flags.analysis = analysis
      render(<ProDepth />)
      const copy = changeReportRow().textContent ?? ''
      // Anti-vacuity: the read holds the row's line.
      expect(copy).toMatch(/Both plans include it\./)
      // With the flag on, the first case fails instead, and its PR restates this row.
      const named = productionShipsTheFlag() ? [] : namesWhatProductionWithholds(copy)
      expect(named, `ProDepth's Change Report row names ${named.join(', ')}. ${METRIC_DELTAS_ONLY}`).toEqual([])
    },
  )
})
