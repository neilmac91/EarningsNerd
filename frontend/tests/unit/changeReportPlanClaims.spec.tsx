import { render, screen, within } from '@testing-library/react'
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'

/**
 * The landing's Change Report claims, held to what production serves (D-046's pricing truth; CLAUDE.md rules 4
 * and 12).
 *
 * backend/app/services/entitlements.py gives the Change Report one plan difference: the Item 1A wording block
 * (`section_changes`: every changed paragraph for Pro, the first `section_changes_items` for everyone else). The
 * block is served only behind ENABLE_SECTION_CHANGES, which backend/app/config.py defaults to False and which no
 * workflow under .github/workflows sets, so production serves no wording diff; the report's other parts (the XBRL
 * metric changes, the risk-factor diff) carry no plan gate. Free, Pro and an anonymous reader read the same report.
 * While that holds the landing claims nothing more: the plan table's two Change Report cells read the same
 * (PricingSection.tsx), and ProDepth's Change Report row wears no Pro chip.
 *
 * The first case reads the flag where production takes it, the Settings default and the workflows' executable
 * lines (test_section_changes_flag_placement.py keeps any setting of it to the three deploy maps), and fails once
 * the flag can ship: that PR restates the landing's Change Report claims from entitlements.py and moves this gate
 * beside them. Its planted forms score the read. Out of reach: a value set on the service outside the repository
 * (a console edit), which no file here records.
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
  'section_changes_items for the teaser). Restate the landing\'s Change Report claims from entitlements.py (the plan ' +
  'table\'s row in features/marketing/components/PricingSection.tsx, the Pro chip and the line on ProDepth\'s ' +
  'Change Report row) and move this gate beside them.'

const SAME_REPORT =
  `Free and Pro read the same Change Report while ${FLAG} stays off (its one plan difference, entitlements.py's ` +
  'wording block, ships behind that flag), so the landing claims no difference. Ship the flag first, then restate ' +
  'the claims from entitlements.py.'

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

describe("the landing's Change Report claims while production serves no wording diff", () => {
  it(`finds ${FLAG} off in production: config.py's default and every workflow`, () => {
    const workflows = readdirSync(WORKFLOWS)
      .filter((file) => /\.ya?ml$/.test(file))
      .map((file) => [file, readFileSync(path.join(WORKFLOWS, file), 'utf8')] as const)
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
})
