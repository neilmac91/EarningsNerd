/**
 * Behavioural gate for `.claude/workflows/premerge-review.js` (CLAUDE.md rule 12; AGENTS.md §5).
 *
 * The Python gate `backend/tests/unit/test_agent_workflow_rules.py` checks the script's text. Text
 * checks keep missing JavaScript corner cases (a spread that overrides `model`, a tier key that is
 * undefined for one tier, a loosened vote count), so this spec runs the script itself with stubbed
 * `agent`/`pipeline`/`parallel` and asserts what every stage actually receives and returns:
 *   - every agent call carries a literal, non-premium model and the effort the tier promises;
 *   - the agent counts per tier (records 1, routine 1 + 1 per blocker, high 3 + 2 per serious finding);
 *   - a missing tier reviews as high, an unknown tier or a batch-wide `records` fails before any agent;
 *   - a lens that returns nothing makes the result `incomplete` and not mergeable;
 *   - a refuter that returns nothing leaves the finding unverified, never refuted.
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

type Call = { label: string; model: unknown; effort: unknown }
type Findings = { findings: Array<Record<string, unknown>>; summary: string }

const FINDINGS: Findings = {
  findings: [
    { file: 'a.py', line: 1, title: 'blocker', detail: 'd', severity: 'blocker', evidence: 'e' },
    { file: 'b.py', title: 'should', detail: 'd', severity: 'should-fix', evidence: 'e' },
    { file: 'c.py', title: 'nit', detail: 'd', severity: 'nit', evidence: 'e' },
  ],
  summary: 's',
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

function stub(nullFor?: (label: string) => boolean) {
  const calls: Call[] = []
  const agent = async (_prompt: string, opts: { label: string; model?: unknown; effort?: unknown }) => {
    calls.push({ label: opts.label, model: opts.model, effort: opts.effort })
    if (nullFor && nullFor(opts.label)) return null
    if (opts.label.startsWith('review:')) return FINDINGS
    return { refuted: false, reason: 'r' }
  }
  return { agent, calls }
}

const pr = (tier?: string) => ({ number: 1, branch: 'x', title: 'T', base: 'main', ...(tier ? { tier } : {}) })

describe('premerge-review.js behaves as AGENTS.md §5 promises', () => {
  it('runs records on one Sonnet lens, routine on one Opus lens plus a Sonnet refuter per blocker, high on three Opus lenses plus two Opus refuters per serious finding', async () => {
    const expected: Record<string, { agents: number; lensModel: string; lensEffort: unknown; refuterModel?: string; refuterEffort?: unknown }> = {
      records: { agents: 1, lensModel: 'sonnet', lensEffort: 'medium' },
      routine: { agents: 2, lensModel: 'opus', lensEffort: 'high', refuterModel: 'sonnet', refuterEffort: 'medium' },
      high: { agents: 3 + 6 * 2, lensModel: 'opus', lensEffort: undefined, refuterModel: 'opus', refuterEffort: undefined },
    }
    for (const [tier, want] of Object.entries(expected)) {
      const { agent, calls } = stub()
      const [result] = (await load()({ prs: [pr(tier)] }, agent)) as Array<Record<string, unknown>>
      expect(result.tier, tier).toBe(tier)
      expect(result.agents, tier).toBe(want.agents)
      expect(calls.length, tier).toBe(want.agents)
      for (const call of calls) {
        expect(ALLOWED_MODELS.has(call.model as string), `${tier} ${call.label} model=${String(call.model)}`).toBe(true)
        const isLens = call.label.startsWith('review:')
        expect(call.model, `${tier} ${call.label}`).toBe(isLens ? want.lensModel : want.refuterModel)
        expect(call.effort, `${tier} ${call.label}`).toBe(isLens ? want.lensEffort : want.refuterEffort)
      }
    }
  })

  it('reviews a PR with no tier as high', async () => {
    const { agent, calls } = stub()
    const [result] = (await load()({ prs: [pr()] }, agent)) as Array<Record<string, unknown>>
    expect(result.tier).toBe('high')
    expect(calls.filter((c) => c.label.startsWith('review:')).length).toBe(3)
  })

  it('fails before any agent on an unknown tier or a batch-wide records tier, instead of dropping the PR', async () => {
    for (const args of [{ prs: [pr('High')] }, { prs: [pr()], tier: 'records' }]) {
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
})
