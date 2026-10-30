/**
 * Behavioural gate for `.claude/workflows/premerge-review.js` (CLAUDE.md rule 12; AGENTS.md §5).
 *
 * The Python gate `backend/tests/unit/test_agent_workflow_rules.py` checks the script's text. Text
 * checks keep missing JavaScript corner cases (a spread that overrides `model`, a tier key that is
 * undefined for one tier, a loosened vote count), so this spec runs the script itself with stubbed
 * `agent`/`pipeline`/`parallel` and asserts what every stage actually receives and returns:
 *   - every agent call carries a literal, non-premium model and the effort the tier promises;
 *   - the agent counts per tier (records 1, routine 1 + 1 per blocker, high 3 + 2 per blocker + 1 dedupe
 *     + 2 per group of should-fix reports of one defect, or 2 per should-fix when the dedupe gives no valid
 *     grouping, fails, or has fewer than two lenses' should-fixes to group);
 *   - the high tier's group refuters vote on every report of their group on its own claim: each verdict lands
 *     on the report it names, each refuter's vote counts once, a report missing from a refuter's verdicts or
 *     given two is unverified, one report can stand while another is refuted, and the dedupe, the group
 *     refuters and the lone refuters each get their own schema, pinned exactly (types and enums included);
 *     a blocker is never grouped, and the dedupe runs only on should-fixes from two or more lenses;
 *   - one refuter's corrected severity reaches the result on both paths: a should-fix raised to blocker,
 *     grouped or alone, by one refuter or both, is a confirmed blocker and blocks the merge;
 *   - a missing tier reviews as high, an unknown tier or a batch-wide `records` fails before any agent;
 *   - a complete vote lands where it should: every unrefuted finding in `confirmed`, a blocker there
 *     or left unverified makes the PR not mergeable, a refuted blocker frees it, no findings is mergeable;
 *   - a PR's own tier beats the batch tier;
 *   - a lens that returns nothing makes the result `incomplete` and not mergeable;
 *   - a refuter that returns nothing leaves the finding unverified, never refuted, and makes the result
 *     `incomplete`, so a should-fix whose required refutation never ran is not clearance;
 *   - a verification that throws keeps its finding (unverified) instead of dropping it;
 *   - an inherited property name (`constructor`, `toString`, `__proto__`) is an unknown tier.
 * `pipeline` and `parallel` follow the documented runtime semantics: a throwing stage drops its item
 * to null, and a throwing thunk resolves to null.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const SCRIPT = path.join(repoRoot, '.claude/workflows/premerge-review.js')
const ALLOWED_MODELS = new Set(['sonnet', 'opus', 'haiku'])

type Call = { label: string; model: unknown; effort: unknown; prompt: string; schema: unknown }
type Findings = { findings: Array<Record<string, unknown>>; summary: string }

const FINDINGS: Findings = {
  findings: [
    { file: 'a.py', line: 1, title: 'blocker', detail: 'd', severity: 'blocker', evidence: 'e' },
    { file: 'b.py', title: 'should', detail: 'd', severity: 'should-fix', evidence: 'e' },
    { file: 'c.py', title: 'nit', detail: 'd', severity: 'nit', evidence: 'e' },
  ],
  summary: 's',
}

// Each lens reports its own should-fix, so a verdict or a grouping that lands on the wrong report shows by title.
// The dedupe's pool is then the three should-fixes in lens order: correctness 0, rules-and-brief 1, tests-and-gates 2.
const lensFindings = (label: string): Findings => {
  const lens = label.split(':').pop() as string
  return {
    findings: [
      { file: 'a.py', line: 1, title: 'blocker', detail: 'd', severity: 'blocker', evidence: 'e' },
      { file: `${lens}.py`, title: `should-${lens}`, detail: 'd', severity: 'should-fix', evidence: 'e' },
      { file: 'c.py', title: 'nit', detail: 'd', severity: 'nit', evidence: 'e' },
    ],
    summary: 's',
  }
}

const schemaKeys = (schema: unknown) => Object.keys((schema as { properties?: object } | undefined)?.properties ?? {}).sort()

// The refuters' schemas, exactly: a type or an enum that drifts would let a real refuter refute every
// blocker or never raise one, which the stubbed agents below cannot show.
const CORRECTED = { type: 'string', enum: ['blocker', 'should-fix', 'nit'] }
const LONE_VERDICT_SCHEMA = {
  type: 'object',
  properties: { refuted: { type: 'boolean' }, reason: { type: 'string' }, corrected_severity: CORRECTED },
  required: ['refuted', 'reason'],
}
const GROUP_VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: { report: { type: 'integer' }, refuted: { type: 'boolean' }, reason: { type: 'string' }, corrected_severity: CORRECTED },
        required: ['report', 'refuted', 'reason'],
      },
    },
  },
  required: ['verdicts'],
}

function load(): (args: unknown, agent: unknown) => Promise<unknown> {
  const source = readFileSync(SCRIPT, 'utf8').replace(/^export const meta/m, 'const meta')
  const pipeline = async (items: unknown[], ...stages: Array<(...a: unknown[]) => unknown>) =>
    Promise.all(
      items.map(async (item, index) => {
        let value: unknown = item
        try {
          for (const stage of stages) value = await stage(value, item, index)
        } catch {
          return null
        }
        return value
      }),
    )
  const parallel = async (thunks: Array<() => Promise<unknown>>) =>
    Promise.all(thunks.map((thunk) => thunk().catch(() => null)))
  const log = () => undefined
  const phase = () => undefined
  const factory = new Function('args', 'agent', 'pipeline', 'parallel', 'log', 'phase', `return (async () => {${source}})()`)
  return (args, agent) => factory(args, agent, pipeline, parallel, log, phase) as Promise<unknown>
}

type Result = {
  tier: string
  agents: number
  incomplete: boolean
  mergeable: boolean
  confirmed: Array<{ title: string; severity: string }>
  refuted: Array<{ title: string }>
  unverified: Array<{ title: string; severity: string }>
  nits: unknown[]
}

type Verdicts = (label: string) => Array<{ report: number; refuted: boolean; reason: string; corrected_severity?: string }>

// With no `groups`, the dedupe returns nothing, and the script verifies each finding on its own.
// `corrected` gives a lone refuter's corrected severity by its label.
function stub(
  nullFor?: (label: string) => boolean,
  opts: {
    refuted?: boolean
    findings?: Findings | ((label: string) => Findings)
    groups?: unknown
    verdicts?: Verdicts
    corrected?: (label: string) => string | undefined
  } = {},
) {
  const calls: Call[] = []
  const agent = async (prompt: string, o: { label: string; model?: unknown; effort?: unknown; schema?: unknown }) => {
    calls.push({ label: o.label, model: o.model, effort: o.effort, prompt, schema: o.schema })
    if (nullFor && nullFor(o.label)) return null
    if (o.label.startsWith('review:')) return typeof opts.findings === 'function' ? opts.findings(o.label) : (opts.findings ?? FINDINGS)
    if (o.label.startsWith('dedupe:')) return opts.groups === undefined ? null : { groups: opts.groups }
    if (/^verify:\d+:group\d+#/.test(o.label)) {
      const n = (prompt.match(/^report \d+:$/gm) ?? []).length
      const all = Array.from({ length: n }, (_, report) => ({ report, refuted: opts.refuted ?? false, reason: 'r' }))
      return { verdicts: opts.verdicts ? opts.verdicts(o.label) : all }
    }
    const corrected = opts.corrected?.(o.label)
    return { refuted: opts.refuted ?? false, reason: 'r', ...(corrected ? { corrected_severity: corrected } : {}) }
  }
  return { agent, calls }
}

const titles = (xs: Array<{ title: string }>) => xs.map((x) => x.title).sort()

const pr = (tier?: string) => ({ number: 1, branch: 'x', title: 'T', base: 'main', ...(tier ? { tier } : {}) })

describe('premerge-review.js behaves as AGENTS.md §5 promises', () => {
  it('runs records on one Sonnet lens, routine on one Opus lens plus a Sonnet refuter per blocker, high on three Opus lenses plus two Opus refuters per serious finding', async () => {
    const expected: Record<string, { agents: number; lensModel: string; lensEffort: unknown; refuterModel?: string; refuterEffort?: unknown; confirmed: string[]; unverified: string[] }> = {
      records: { agents: 1, lensModel: 'sonnet', lensEffort: 'medium', confirmed: [], unverified: ['blocker', 'should'] },
      routine: { agents: 2, lensModel: 'opus', lensEffort: 'high', refuterModel: 'sonnet', refuterEffort: 'medium', confirmed: ['blocker'], unverified: ['should'] },
      high: { agents: 3 + 1 + 6 * 2, lensModel: 'opus', lensEffort: undefined, refuterModel: 'opus', refuterEffort: undefined, confirmed: ['blocker', 'blocker', 'blocker', 'should', 'should', 'should'], unverified: [] },
    }
    for (const [tier, want] of Object.entries(expected)) {
      const { agent, calls } = stub()
      const [result] = (await load()({ prs: [pr(tier)] }, agent)) as Result[]
      expect(result.tier, tier).toBe(tier)
      expect(result.agents, tier).toBe(want.agents)
      expect(calls.length, tier).toBe(want.agents)
      // A complete, unrefuted vote confirms the finding; a blocker confirmed or left unverified blocks the merge.
      expect(titles(result.confirmed), tier).toEqual(want.confirmed)
      expect(titles(result.unverified), tier).toEqual(want.unverified)
      expect(result.refuted, tier).toHaveLength(0)
      expect(result.nits.length, tier).toBeGreaterThan(0)
      expect(result.incomplete, tier).toBe(false)
      expect(result.mergeable, tier).toBe(false)
      for (const call of calls) {
        expect(ALLOWED_MODELS.has(call.model as string), `${tier} ${call.label} model=${String(call.model)}`).toBe(true)
        const isLens = call.label.startsWith('review:')
        if (call.label.startsWith('dedupe:')) {
          expect(tier).toBe('high')
          expect([call.model, call.effort], `${tier} ${call.label}`).toEqual(['sonnet', 'medium'])
          continue
        }
        expect(call.model, `${tier} ${call.label}`).toBe(isLens ? want.lensModel : want.refuterModel)
        expect(call.effort, `${tier} ${call.label}`).toBe(isLens ? want.lensEffort : want.refuterEffort)
      }
    }
  })

  it('moves a finding every refuter refutes to refuted and frees the merge, and clears a PR with no findings', async () => {
    const refutedAll = stub(undefined, { refuted: true })
    const [routine] = (await load()({ prs: [pr('routine')] }, refutedAll.agent)) as Result[]
    expect(titles(routine.refuted)).toEqual(['blocker'])
    expect(routine.confirmed).toHaveLength(0)
    expect(titles(routine.unverified)).toEqual(['should'])
    expect(routine.mergeable).toBe(true)
    const [high] = (await load()({ prs: [pr('high')] }, stub(undefined, { refuted: true }).agent)) as Result[]
    expect(titles(high.refuted)).toEqual(['blocker', 'blocker', 'blocker', 'should', 'should', 'should'])
    expect(high.confirmed).toHaveLength(0)
    expect(high.mergeable).toBe(true)
    const clean = stub(undefined, { findings: { findings: [], summary: 'clean' } })
    const [records] = (await load()({ prs: [pr('records')] }, clean.agent)) as Result[]
    expect(records.agents).toBe(1)
    expect(records.confirmed.length + records.unverified.length + records.nits.length).toBe(0)
    expect(records.mergeable).toBe(true)
  })

  it("lets a PR's own tier beat the batch tier", async () => {
    const { agent } = stub()
    const results = (await load()({ prs: [pr('high'), pr()], tier: 'routine' }, agent)) as Result[]
    expect(results.map((r) => r.tier)).toEqual(['high', 'routine'])
    expect(results.map((r) => r.agents)).toEqual([3 + 1 + 6 * 2, 2])
  })

  it('reviews a PR with no tier as high', async () => {
    const { agent, calls } = stub()
    const [result] = (await load()({ prs: [pr()] }, agent)) as Array<Record<string, unknown>>
    expect(result.tier).toBe('high')
    expect(calls.filter((c) => c.label.startsWith('review:')).length).toBe(3)
  })

  it('fails before any agent on an unknown tier or a batch-wide records tier, instead of dropping the PR', async () => {
    const inherited = ['constructor', 'toString', '__proto__', 'hasOwnProperty'].map((tier) => ({ prs: [pr(tier)] }))
    for (const args of [{ prs: [pr('High')] }, { prs: [pr()], tier: 'records' }, ...inherited]) {
      const { agent, calls } = stub()
      await expect(load()(args, agent)).rejects.toThrow()
      expect(calls.length, JSON.stringify(args)).toBe(0)
    }
  })

  it('treats a lens that returns nothing as missing review output, never clearance', async () => {
    const { agent } = stub((label) => label.startsWith('review:'))
    const [result] = (await load()({ prs: [pr('routine')] }, agent)) as Array<Record<string, unknown>>
    expect(result.incomplete).toBe(true)
    expect(result.mergeable).toBe(false)
  })

  it('leaves a high-tier finding unverified when one of its two refuters returns nothing, never confirmed on a single vote', async () => {
    const { agent, calls } = stub((label) => label.startsWith('verify:') && label.endsWith('#1'))
    const [result] = (await load()({ prs: [pr('high')] }, agent)) as Array<{ confirmed: unknown[]; refuted: unknown[]; unverified: unknown[]; mergeable: boolean }>
    expect(calls.filter((c) => c.label.startsWith('verify:')).length).toBe(12)
    expect(result.confirmed).toHaveLength(0)
    expect(result.refuted).toHaveLength(0)
    expect(result.unverified).toHaveLength(6)
    expect(result.mergeable).toBe(false)
  })

  it('leaves a finding unverified when a refuter returns nothing, never refuted', async () => {
    const { agent } = stub((label) => label.startsWith('verify:'))
    const [result] = (await load()({ prs: [pr('routine')] }, agent)) as Array<{ refuted: unknown[]; unverified: Array<{ severity: string }>; mergeable: boolean }>
    expect(result.refuted).toHaveLength(0)
    expect(result.unverified.some((f) => f.severity === 'blocker')).toBe(true)
    expect(result.mergeable).toBe(false)
  })

  it('makes the result incomplete, never clearance, when a required refuter returns nothing for a should-fix', async () => {
    const shouldOnly: Findings = { findings: [{ file: 'b.py', title: 'should', detail: 'd', severity: 'should-fix', evidence: 'e' }], summary: 's' }
    const { agent } = stub((label) => label.startsWith('verify:') && label.endsWith('#2'), { findings: shouldOnly })
    const [result] = (await load()({ prs: [pr('high')] }, agent)) as Result[]
    expect(titles(result.unverified)).toEqual(['should', 'should', 'should'])
    expect(result.confirmed).toHaveLength(0)
    expect(result.incomplete).toBe(true)
    expect(result.mergeable).toBe(false)
  })

  it('verifies each high-tier should-fix defect once: two Opus refuters per group, voting on every report; blockers keep their own', async () => {
    const { agent, calls } = stub(undefined, { findings: lensFindings, groups: [[0, 1], [2]] })
    const [result] = (await load()({ prs: [pr('high')] }, agent)) as Array<Result & { groups: string[][] }>
    const verify = calls.filter((c) => c.label.startsWith('verify:'))
    expect(verify.map((c) => c.label).sort()).toEqual([
      'verify:1:a.py#1', 'verify:1:a.py#1', 'verify:1:a.py#1', 'verify:1:a.py#2', 'verify:1:a.py#2', 'verify:1:a.py#2',
      'verify:1:group1#1', 'verify:1:group1#2', 'verify:1:tests-and-gates.py#1', 'verify:1:tests-and-gates.py#2',
    ])
    for (const call of verify) expect([call.model, call.effort]).toEqual(['opus', undefined])
    // A group refuter answers per report; a lone finding keeps the one-verdict schema; the dedupe returns groups.
    for (const call of verify) {
      expect(call.schema, call.label).toEqual(call.label.includes(':group') ? GROUP_VERDICT_SCHEMA : LONE_VERDICT_SCHEMA)
    }
    const dedupe = calls.filter((c) => c.label.startsWith('dedupe:'))
    expect(dedupe).toHaveLength(1)
    expect(schemaKeys(dedupe[0].schema)).toEqual(['groups'])
    expect(dedupe[0].prompt).not.toContain('severity: blocker')
    // The grouping's indices name the pool's reports: group 1 holds correctness and rules-and-brief, not tests-and-gates.
    for (const call of verify.filter((c) => c.label.includes(':group'))) {
      expect((call.prompt.match(/^report \d+:$/gm) ?? []).length).toBe(2)
      expect(call.prompt).toContain('should-correctness')
      expect(call.prompt).toContain('should-rules-and-brief')
      expect(call.prompt).not.toContain('should-tests-and-gates')
    }
    expect(result.agents).toBe(3 + 1 + (3 + 1 + 1) * 2)
    expect(calls).toHaveLength(result.agents)
    expect(titles(result.confirmed)).toEqual(['blocker', 'blocker', 'blocker', 'should-correctness', 'should-rules-and-brief', 'should-tests-and-gates'])
    expect(result.groups).toEqual([['should-correctness', 'should-rules-and-brief']])
    expect(result.incomplete).toBe(false)
    expect(result.mergeable).toBe(false)
    const refutedAll = stub(undefined, { findings: lensFindings, groups: [[0, 1], [2]], refuted: true })
    const [freed] = (await load()({ prs: [pr('high')] }, refutedAll.agent)) as Result[]
    expect(titles(freed.refuted)).toEqual(['blocker', 'blocker', 'blocker', 'should-correctness', 'should-rules-and-brief', 'should-tests-and-gates'])
    expect(freed.mergeable).toBe(true)
  })

  it("carries a refuter's corrected severity on both paths: a should-fix raised to blocker, grouped or alone, is a confirmed blocker that blocks the merge", async () => {
    const shouldOnly = (label: string): Findings => {
      const lens = label.split(':').pop() as string
      return { findings: [{ file: `${lens}.py`, title: `should-${lens}`, detail: 'd', severity: 'should-fix', evidence: 'e' }], summary: 's' }
    }
    // Group 1 holds correctness (report 0) and rules-and-brief (report 1); its refuters raise report 0 only.
    const verdicts: Verdicts = () => [{ report: 0, refuted: false, reason: 'r', corrected_severity: 'blocker' }, { report: 1, refuted: false, reason: 'r' }]
    const severities = (r: Result) => Object.fromEntries(r.confirmed.map((c) => [c.title, c.severity]))
    const both = stub(undefined, { findings: shouldOnly, groups: [[0, 1], [2]], verdicts, corrected: (label) => (label.includes('tests-and-gates.py#') ? 'blocker' : undefined) })
    const [raised] = (await load()({ prs: [pr('high')] }, both.agent)) as Result[]
    expect(severities(raised)).toEqual({ 'should-correctness': 'blocker', 'should-rules-and-brief': 'should-fix', 'should-tests-and-gates': 'blocker' })
    expect(raised.incomplete).toBe(false)
    expect(raised.mergeable).toBe(false)
    // The group's correction alone blocks the merge.
    const grouped = stub(undefined, { findings: shouldOnly, groups: [[0, 1], [2]], verdicts })
    const [fromGroup] = (await load()({ prs: [pr('high')] }, grouped.agent)) as Result[]
    expect(severities(fromGroup)).toEqual({ 'should-correctness': 'blocker', 'should-rules-and-brief': 'should-fix', 'should-tests-and-gates': 'should-fix' })
    expect(fromGroup.mergeable).toBe(false)
    // One refuter's correction is enough on either path: group refuter #1 only, lone refuter #2 only.
    const firstOfGroup: Verdicts = (label) => [
      { report: 0, refuted: false, reason: 'r', ...(label.endsWith('#1') ? { corrected_severity: 'blocker' } : {}) },
      { report: 1, refuted: false, reason: 'r' },
    ]
    const one = stub(undefined, { findings: shouldOnly, groups: [[0, 1], [2]], verdicts: firstOfGroup, corrected: (label) => (label.endsWith('tests-and-gates.py#2') ? 'blocker' : undefined) })
    const [single] = (await load()({ prs: [pr('high')] }, one.agent)) as Result[]
    expect(severities(single)).toEqual({ 'should-correctness': 'blocker', 'should-rules-and-brief': 'should-fix', 'should-tests-and-gates': 'blocker' })
    expect(single.mergeable).toBe(false)
    // Without corrections the same reports stay should-fixes, and the PR is mergeable.
    const plain = stub(undefined, { findings: shouldOnly, groups: [[0, 1], [2]] })
    const [kept] = (await load()({ prs: [pr('high')] }, plain.agent)) as Result[]
    expect(Object.values(severities(kept))).toEqual(['should-fix', 'should-fix', 'should-fix'])
    expect(kept.mergeable).toBe(true)
  })

  it('sends each group verdict to the report it names', async () => {
    // Every group refuter refutes report 0 (should-correctness) and keeps report 1 (should-rules-and-brief).
    const verdicts: Verdicts = () => [{ report: 0, refuted: true, reason: 'r' }, { report: 1, refuted: false, reason: 'r' }]
    const { agent } = stub(undefined, { findings: lensFindings, groups: [[0, 1], [2]], verdicts })
    const [result] = (await load()({ prs: [pr('high')] }, agent)) as Result[]
    expect(titles(result.refuted)).toEqual(['should-correctness'])
    expect(titles(result.confirmed)).toEqual(['blocker', 'blocker', 'blocker', 'should-rules-and-brief', 'should-tests-and-gates'])
    expect(result.incomplete).toBe(false)
  })

  it("counts each group refuter's vote once: a report either refuter refutes is refuted, and a missing refuter leaves its reports unverified", async () => {
    // Refuter #1 refutes report 0 only, refuter #2 report 1 only.
    const verdicts: Verdicts = (label) => [0, 1].map((report) => ({ report, refuted: label.endsWith(`#${report + 1}`), reason: 'r' }))
    const { agent } = stub(undefined, { findings: lensFindings, groups: [[0, 1], [2]], verdicts })
    const [split] = (await load()({ prs: [pr('high')] }, agent)) as Result[]
    expect(titles(split.refuted)).toEqual(['should-correctness', 'should-rules-and-brief'])
    expect(titles(split.confirmed)).toEqual(['blocker', 'blocker', 'blocker', 'should-tests-and-gates'])
    expect(split.incomplete).toBe(false)
    const missing = stub((label) => label === 'verify:1:group1#2', { findings: lensFindings, groups: [[0, 1], [2]] })
    const [gap] = (await load()({ prs: [pr('high')] }, missing.agent)) as Result[]
    expect(titles(gap.unverified)).toEqual(['should-correctness', 'should-rules-and-brief'])
    expect(titles(gap.confirmed)).toEqual(['blocker', 'blocker', 'blocker', 'should-tests-and-gates'])
    expect(gap.incomplete).toBe(true)
    expect(gap.mergeable).toBe(false)
  })

  it('verifies each finding on its own when the dedupe returns nothing, throws, or gives a grouping that is not a partition', async () => {
    const bad: unknown[] = [undefined, 'x', [[0, 1], [1, 2]], [[0, 1]], [[0, 1, 2, 3]], [[0.5, 1, 2]], [[], [0, 1, 2]], [[-1, 0, 1, 2]], [['0', 1, 2]], [[0], 1, 2]]
    for (const groups of bad) {
      const { agent, calls } = stub(undefined, { groups })
      const [result] = (await load()({ prs: [pr('high')] }, agent)) as Array<Result & { groups: string[][] }>
      expect(result.agents, JSON.stringify(groups)).toBe(3 + 1 + 6 * 2)
      expect(calls.filter((c) => c.label.includes(':group')), JSON.stringify(groups)).toHaveLength(0)
      expect(result.groups, JSON.stringify(groups)).toEqual([])
      expect(result.confirmed, JSON.stringify(groups)).toHaveLength(6)
    }
    const { agent: base, calls } = stub(undefined, { groups: [[0, 1, 2]] })
    const throwing = async (prompt: string, o: { label: string }) => {
      if (o.label.startsWith('dedupe:')) {
        calls.push({ label: o.label, model: undefined, effort: undefined, prompt, schema: undefined })
        throw new Error('dedupe failed')
      }
      return base(prompt, o)
    }
    const [result] = (await load()({ prs: [pr('high')] }, throwing)) as Array<Result & { groups: string[][] }>
    expect(result.agents).toBe(3 + 1 + 6 * 2)
    expect(result.confirmed).toHaveLength(6)
    expect(result.incomplete).toBe(false)
  })

  it('never calls the dedupe without should-fixes from two lenses, and never groups a blocker', async () => {
    const blockersOnly: Findings = { findings: [{ file: 'a.py', title: 'blocker', detail: 'd', severity: 'blocker', evidence: 'e' }], summary: 's' }
    const one = stub(undefined, { findings: blockersOnly, groups: [[0, 1, 2]] })
    const [result] = (await load()({ prs: [pr('high')] }, one.agent)) as Result[]
    expect(one.calls.filter((c) => c.label.startsWith('dedupe:'))).toHaveLength(0)
    expect(result.agents).toBe(3 + 3 * 2)
    // Two should-fixes, both from one lens: nothing to deduplicate across lenses.
    const twoFromOne = (label: string): Findings =>
      label.endsWith(':correctness')
        ? { findings: ['should-1', 'should-2'].map((title) => ({ file: 'b.py', title, detail: 'd', severity: 'should-fix', evidence: 'e' })), summary: 's' }
        : blockersOnly
    const single = stub(undefined, { findings: twoFromOne, groups: [[0, 1]] })
    const [lone] = (await load()({ prs: [pr('high')] }, single.agent)) as Result[]
    expect(single.calls.filter((c) => c.label.startsWith('dedupe:'))).toHaveLength(0)
    expect(lone.agents).toBe(3 + 4 * 2)
    expect(titles(lone.confirmed)).toEqual(['blocker', 'blocker', 'should-1', 'should-2'])
  })

  it('lets one report of a group stand while another is refuted, and leaves a report unverified when a group refuter omits its verdict or gives two', async () => {
    const splitVerdicts: Verdicts = () => [0, 1, 2].map((report) => ({ report, refuted: report === 1, reason: 'r' }))
    const split = stub(undefined, { findings: lensFindings, groups: [[0, 1, 2]], verdicts: splitVerdicts })
    const [a] = (await load()({ prs: [pr('high')] }, split.agent)) as Result[]
    expect(titles(a.confirmed)).toEqual(['blocker', 'blocker', 'blocker', 'should-correctness', 'should-tests-and-gates'])
    expect(titles(a.refuted)).toEqual(['should-rules-and-brief'])
    expect(a.incomplete).toBe(false)
    // Refuter #1 gives report 0 twice and omits report 2: both are unverified; report 1 stays refuted.
    const broken: Verdicts = (label) =>
      label.endsWith('#1')
        ? [{ report: 0, refuted: false, reason: 'r' }, { report: 0, refuted: false, reason: 'r' }, { report: 1, refuted: true, reason: 'r' }]
        : splitVerdicts(label)
    const partial = stub(undefined, { findings: lensFindings, groups: [[0, 1, 2]], verdicts: broken })
    const [b] = (await load()({ prs: [pr('high')] }, partial.agent)) as Result[]
    expect(titles(b.unverified)).toEqual(['should-correctness', 'should-tests-and-gates'])
    expect(titles(b.refuted)).toEqual(['should-rules-and-brief'])
    expect(titles(b.confirmed)).toEqual(['blocker', 'blocker', 'blocker'])
    expect(b.incomplete).toBe(true)
    expect(b.mergeable).toBe(false)
  })

  it('keeps a finding whose verification throws, as unverified, and marks the result incomplete', async () => {
    const blockerOnly: Findings = { findings: [{ file: 'a.py', title: 'blocker', detail: 'd', severity: 'blocker', evidence: 'e' }], summary: 's' }
    const calls: Call[] = []
    const agent = async (prompt: string, o: { label: string; model?: unknown; effort?: unknown; schema?: unknown }) => {
      calls.push({ label: o.label, model: o.model, effort: o.effort, prompt, schema: o.schema })
      if (o.label.startsWith('review:')) return blockerOnly
      // A vote whose fields throw when read: the verification stage throws after its agents returned.
      return { get refuted(): boolean { throw new Error('unreadable vote') }, reason: 'r' }
    }
    const [result] = (await load()({ prs: [pr('routine')] }, agent)) as Result[]
    expect(calls.filter((c) => c.label.startsWith('verify:'))).toHaveLength(1)
    expect(titles(result.unverified)).toEqual(['blocker'])
    expect(result.confirmed).toHaveLength(0)
    expect(result.refuted).toHaveLength(0)
    expect(result.incomplete).toBe(true)
    expect(result.mergeable).toBe(false)
  })
})
