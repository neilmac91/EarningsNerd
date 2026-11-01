/**
 * Behavioural gate for `.claude/workflows/premerge-review.js` (CLAUDE.md rule 12; AGENTS.md §5).
 *
 * The Python gate `backend/tests/unit/test_agent_workflow_rules.py` checks the script's text. Text
 * checks keep missing JavaScript corner cases (a spread that overrides `model`, a tier key that is
 * undefined for one tier, a loosened vote count), so this spec runs the script itself with stubbed
 * `agent`/`pipeline`/`parallel` and asserts what every stage actually receives and returns:
 *   - every agent call carries a literal, non-premium model and the effort the tier promises;
 *   - the agent counts per tier (records 1, routine 1 + 1 per blocker, high 3 + 2 per serious finding);
 *   - every refuter, on every tier, answers in the one-verdict schema, pinned exactly (types and enums included),
 *     and its prompt asks for a correction only when the claimed severity is wrong;
 *   - every verified report gets its own refuters, the high tier's two on Opus or the routine tier's one on Sonnet,
 *     even when several lenses report one defect (the founder removed #1855's shared refuters on 2026-11-01;
 *     lessons/ops-replace-a-redundant-review-stage-never-drop-it.md):
 *     - statically, the script, parsed, names `agent` exactly twice, each time calling it directly on a prompt that
 *       lensPrompt or refuterPrompt builds, so no stage calls an agent through a call of its own, an alias, `.call`
 *       or a property;
 *     - dynamically, each refuter answers hold, refute, lower, raise or nothing, drawn per report, refuter and seed,
 *       and the result is compared with the judge's rules applied to each report's own answers alone. The reviews:
 *       on the high tier, every combination of one to three lenses, one to eight should-fix defects and one or two
 *       copies, each with a blocker, plus three of up to 198 reports in three copies; on the routine tier, one to
 *       four blocker defects in one to three copies. The copies of a defect share its file, its line (or its lack of
 *       one) and its title, and a lens's second copy of the last defect claims the other serious severity. Each runs
 *       on a PR numbered 1 and on one with a real number, title and branch. In each: no agent runs but the lenses
 *       and the refuters; each refuter's prompt is exactly the one it gets when its report is the review's only
 *       finding; each verified report has its own refuters #1 to #N; and each report is confirmed, refuted or left
 *       unverified, at its severity and under its lens, as its own answers decide, with `incomplete` and `mergeable`
 *       to match;
 *     - out of reach: a stage that reuses the refuters' own call (a helper that builds the refuter prompt and calls
 *       `agent`) or reaches an agent by a name built at run time, and that acts only on reviews those shapes do not
 *       include, or only on what they hold fixed (the clock, randomness, the runtime);
 *   - each refuter holds a finding at its corrected severity, or at the claimed one when it sets none or sets one
 *     outside the three severities, and the highest holding wins whichever refuter gives it: a should-fix raised
 *     to blocker, by one refuter or both, is a confirmed blocker and blocks the merge, even when the other refuter
 *     restates or lowers it; a lowering needs every refuter of the tier (both on the high tier), so a claimed
 *     blocker that one refuter lowers while the other is silent still blocks the merge, while the routine tier's
 *     one refuter lowers a blocker alone; two lowerings that agree confirm the finding at the lower severity, nit
 *     included, and two that disagree confirm it at the higher of the two; a raise never outlives a refutation: a
 *     finding one refuter raises to blocker while the other refutes it, or whose one vote refutes and raises at
 *     once, is refuted, and a claimed blocker one of its two refuters refutes is refuted; a finding with a vote
 *     missing stays unverified at its claimed severity whatever the other refuter holds;
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
import ts from 'typescript'
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

// Each lens reports its own should-fix in its own file, so a verdict that lands on the wrong finding shows by title.
const shouldOnly = (label: string): Findings => {
  const lens = label.split(':').pop() as string
  return { findings: [{ file: `${lens}.py`, title: `should-${lens}`, detail: 'd', severity: 'should-fix', evidence: 'e' }], summary: 's' }
}

// The refuters' schema, exactly: a type or an enum that drifts would let a real refuter refute every blocker or never
// raise one, which the stubbed agents below cannot show.
const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
    corrected_severity: { type: 'string', enum: ['blocker', 'should-fix', 'nit'] },
  },
  required: ['refuted', 'reason'],
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
  confirmed: Array<{ title: string; severity: string; detail?: string; lens?: string }>
  refuted: Array<{ title: string }>
  unverified: Array<{ title: string; severity: string }>
  nits: unknown[]
}

// `refuted`, a boolean or a function of the refuter's label and prompt, sets each refuter's vote; `corrected`, a
// function of the same, gives a refuter's corrected severity. Any agent that is not a lens answers as a refuter.
function stub(
  nullFor?: (label: string) => boolean,
  opts: {
    refuted?: boolean | ((label: string, prompt: string) => boolean)
    findings?: Findings | ((label: string) => Findings)
    corrected?: (label: string, prompt: string) => string | undefined
  } = {},
) {
  const calls: Call[] = []
  const agent = async (prompt: string, o: { label: string; model?: unknown; effort?: unknown; schema?: unknown }) => {
    calls.push({ label: o.label, model: o.model, effort: o.effort, prompt, schema: o.schema })
    if (nullFor && nullFor(o.label)) return null
    if (o.label.startsWith('review:')) return typeof opts.findings === 'function' ? opts.findings(o.label) : (opts.findings ?? FINDINGS)
    const refuted = typeof opts.refuted === 'function' ? opts.refuted(o.label, prompt) : (opts.refuted ?? false)
    const corrected = opts.corrected?.(o.label, prompt)
    return { refuted, reason: 'r', ...(corrected ? { corrected_severity: corrected } : {}) }
  }
  return { agent, calls }
}

const titles = (xs: Array<{ title: string }>) => xs.map((x) => x.title).sort()

const severities = (r: Result) => Object.fromEntries(r.confirmed.map((c) => [c.title, c.severity]))

const pr = (tier?: string) => ({ number: 1, branch: 'x', title: 'T', base: 'main', ...(tier ? { tier } : {}) })

describe('premerge-review.js behaves as AGENTS.md §5 promises', () => {
  it('runs records on one Sonnet lens, routine on one Opus lens plus a Sonnet refuter per blocker, high on three Opus lenses plus two Opus refuters per serious finding', async () => {
    const expected: Record<string, { agents: number; lensModel: string; lensEffort: unknown; refuterModel?: string; refuterEffort?: unknown; confirmed: string[]; unverified: string[] }> = {
      records: { agents: 1, lensModel: 'sonnet', lensEffort: 'medium', confirmed: [], unverified: ['blocker', 'should'] },
      routine: { agents: 2, lensModel: 'opus', lensEffort: 'high', refuterModel: 'sonnet', refuterEffort: 'medium', confirmed: ['blocker'], unverified: ['should'] },
      high: { agents: 3 + 6 * 2, lensModel: 'opus', lensEffort: undefined, refuterModel: 'opus', refuterEffort: undefined, confirmed: ['blocker', 'blocker', 'blocker', 'should', 'should', 'should'], unverified: [] },
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
        expect(call.model, `${tier} ${call.label}`).toBe(isLens ? want.lensModel : want.refuterModel)
        expect(call.effort, `${tier} ${call.label}`).toBe(isLens ? want.lensEffort : want.refuterEffort)
        if (isLens) continue
        // Every refuter, on every tier, answers in the one-verdict schema and is asked for a correction only when the
        // claimed severity is wrong, which is what lets the judge hold a silent refuter at the claimed severity.
        expect(call.schema, `${tier} ${call.label}`).toEqual(VERDICT_SCHEMA)
        expect(call.prompt, `${tier} ${call.label}`).toContain('If it stands but the severity is wrong, keep refuted=false and set corrected_severity.')
      }
    }
  })

  it('gives every verified report its own refuters on both tiers, each shown that report alone and judged on its own votes, whatever the lenses, defects, copies, claims and votes: nothing groups the copies or shares their refuters, votes or view', async () => {
    // Statically: the script names `agent` exactly twice, each time calling it directly on a prompt that lensPrompt or
    // refuterPrompt builds, so no stage calls an agent of its own through a new call, an alias, `.call` or a property.
    const sourceFile = ts.createSourceFile(SCRIPT, readFileSync(SCRIPT, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.JS)
    const uses: string[] = []
    const visit = (node: ts.Node): void => {
      if (ts.isIdentifier(node) && node.text === 'agent') {
        const call = node.parent
        const first = ts.isCallExpression(call) && call.expression === node ? call.arguments[0] : undefined
        uses.push(first && ts.isCallExpression(first) && ts.isIdentifier(first.expression) ? first.expression.text : `not a call on a built prompt: ${node.parent.getText(sourceFile).slice(0, 60)}`)
      }
      ts.forEachChild(node, visit)
    }
    visit(sourceFile)
    expect(uses.sort()).toEqual(['lensPrompt', 'refuterPrompt'])

    // Dynamically, against the judge AGENTS.md §5 describes, applied to each report's own refuters' answers alone.
    type Answer = 'hold' | 'refute' | 'lower' | 'raise' | 'missing'
    type Report = { id: string; lens: string; title: string; claimed: string; file: string; line?: number; detail: string; evidence: string }
    const RANK: Record<string, number> = { nit: 1, 'should-fix': 2, blocker: 3 }
    const LOWER: Record<string, string> = { blocker: 'should-fix', 'should-fix': 'nit' }
    const fnv = (text: string) => {
      let h = 2166136261
      for (let k = 0; k < text.length; k++) h = Math.imul(h ^ text.charCodeAt(k), 16777619) >>> 0
      return h
    }
    const run = load()
    // [tier, lenses that report, blocker defects, should-fix defects, copies of every defect per lens]: on the high
    // tier every combination of one to three lenses, one to eight should-fix defects and one or two copies, and three
    // larger reviews (up to 198 reports); on the routine tier, one to four blocker defects in one to three copies.
    type Shape = [string, number, number, number, number]
    const SHAPES: Shape[] = [
      ...[1, 2, 3].flatMap((l) => [1, 2, 3, 4, 5, 6, 7, 8].flatMap((s) => [1, 2].map((c): Shape => ['high', l, 1, s, c]))),
      ['high', 1, 3, 9, 3], ['high', 2, 2, 12, 3], ['high', 3, 2, 20, 3],
      ...[1, 2, 4].flatMap((b) => [0, 1].flatMap((s) => [1, 2, 3].map((c): Shape => ['routine', 1, b, s, c]))),
    ]
    for (const [tier, lensCount, blockers, shoulds, copies] of SHAPES) {
      const T = tier === 'high'
        ? { lenses: ['correctness', 'rules-and-brief', 'tests-and-gates'], refuters: 2, verify: ['blocker', 'should-fix'], model: 'opus', effort: undefined }
        : { lenses: ['combined'], refuters: 1, verify: ['blocker'], model: 'sonnet', effort: 'medium' }
      const defects = [
        ...Array.from({ length: blockers }, (_, k) => ({ title: `blocker ${k + 1}`, file: `src/a${k + 1}.py`, line: 7 as number | undefined, claimed: 'blocker' })),
        ...Array.from({ length: shoulds }, (_, k) => ({ title: `should-fix ${k + 1}`, file: `src/b${k + 1}.py`, line: k % 2 ? 9 : undefined, claimed: 'should-fix' })),
      ]
      // Every reporting lens reports every defect `copies` times. The copies of a defect share its file, line (or its
      // lack of one) and title; each copy carries its own numbered tag in its detail and evidence, and a lens's second
      // copy of the last defect claims the other serious severity.
      const reports: Report[] = []
      for (const lens of T.lenses.slice(0, lensCount)) {
        for (const [d, defect] of defects.entries()) {
          for (let copy = 1; copy <= copies; copy++) {
            const id = `[#${String(reports.length).padStart(3, '0')}]`
            const claimed = d === defects.length - 1 && copy === 2 ? (defect.claimed === 'blocker' ? 'should-fix' : 'blocker') : defect.claimed
            reports.push({
              id, lens, title: defect.title, claimed, file: defect.file, line: defect.line,
              detail: `${id} ${defect.title}, in the ${lens} lens's words, copy ${copy}`,
              evidence: `${id} the ${lens} lens's evidence of ${defect.title}, copy ${copy}`,
            })
          }
        }
      }
      const finding = (r: Report) => ({ file: r.file, ...(r.line ? { line: r.line } : {}), title: r.title, detail: r.detail, severity: r.claimed, evidence: r.evidence })
      const tagged = (prompt: string) => reports.filter((r) => prompt.includes(r.id))
      const verified = reports.filter((r) => T.verify.includes(r.claimed))
      // Seed 0 draws each refuter's answer from all five, a missing vote included, on a PR numbered 1; seed 1 draws from
      // the four votes, on a PR with a real number, title and branch.
      for (const seed of [0, 1]) {
        const where = `${tier}, ${lensCount} lens(es), ${blockers} blocker and ${shoulds} should-fix defect(s), ${copies} cop(ies), seed ${seed}`
        const thePr = seed === 0 ? pr(tier) : { number: 1873, branch: 'claude/a-real-branch', title: 'fix(api): a real title', base: 'main', tier }
        // The prompt each refuter of a report gets when that report is its review's only finding.
        const solo = new Map<string, string>()
        for (const r of verified) {
          await run({ prs: [thePr] }, async (prompt: string, o: { label: string }) => {
            if (o.label.startsWith('review:')) return { findings: o.label.endsWith(`:${r.lens}`) ? [finding(r)] : [], summary: 's' }
            solo.set(`${r.id}${o.label.slice(o.label.lastIndexOf('#'))}`, prompt)
            return { refuted: false, reason: 'r' }
          })
        }
        const pool: Answer[] = seed === 0 ? ['hold', 'hold', 'refute', 'lower', 'raise', 'missing'] : ['hold', 'hold', 'refute', 'lower', 'raise']
        const answer = (r: Report, n: number): Answer => pool[fnv(`${r.id}#${n}@${seed}`) % pool.length]
        const correction = (r: Report, a: Answer) => (a === 'lower' ? LOWER[r.claimed] : a === 'raise' ? 'blocker' : undefined)
        const calls: Call[] = []
        const [result] = (await run({ prs: [thePr] }, async (prompt: string, o: { label: string; model?: unknown; effort?: unknown; schema?: unknown }) => {
          calls.push({ label: o.label, model: o.model, effort: o.effort, prompt, schema: o.schema })
          if (o.label.startsWith('review:')) return { findings: reports.filter((r) => r.lens === o.label.split(':').pop()).map(finding), summary: 's' }
          const r = tagged(prompt)[0]
          const n = Number(o.label.split('#').pop())
          const a = r ? answer(r, n) : 'refute'
          if (a === 'missing') return null
          const corrected = r ? correction(r, a) : undefined
          return { refuted: a === 'refute', reason: `${r?.id} #${n}`, ...(corrected ? { corrected_severity: corrected } : {}) }
        })) as Result[]
        // What each report's own answers give it.
        const want = { confirmed: [] as string[][], refuted: [] as string[], unverified: [] as string[][] }
        for (const r of reports) {
          const votes = T.verify.includes(r.claimed) ? Array.from({ length: T.refuters }, (_, k) => answer(r, k + 1)).filter((a) => a !== 'missing') : []
          if (!T.verify.includes(r.claimed) || votes.length < T.refuters) want.unverified.push([r.id, r.claimed])
          else if (votes.includes('refute')) want.refuted.push(r.id)
          else want.confirmed.push([r.id, votes.map((a) => correction(r, a) ?? r.claimed).reduce((x, y) => (RANK[y] > RANK[x] ? y : x)), r.lens])
        }
        // The lenses and the tier's refuters of every verified report are the only agents.
        expect(calls.map((c) => c.label.split(':')[0]).sort(), where).toEqual([...Array(T.lenses.length).fill('review'), ...Array(verified.length * T.refuters).fill('verify')])
        expect(result.agents, where).toBe(T.lenses.length + verified.length * T.refuters)
        expect(result, where).not.toHaveProperty('groups')
        // Each refuter is shown exactly what it would be shown were its report the review's only finding, so nothing of
        // another report reaches it, in any form; it answers in the one-verdict schema, on the tier's model.
        const seen = new Map<string, string[]>()
        for (const call of calls.filter((c) => c.label.startsWith('verify:'))) {
          const shown = tagged(call.prompt)
          expect(shown.map((r) => r.id), `${where}: ${call.label}`).toHaveLength(1)
          const n = call.label.slice(call.label.lastIndexOf('#'))
          expect(call.prompt === solo.get(`${shown[0].id}${n}`), `${where}: ${call.label} for ${shown[0].id} differs from its report's own prompt`).toBe(true)
          expect([call.model, call.effort, call.schema], `${where}: ${call.label}`).toEqual([T.model, T.effort, VERDICT_SCHEMA])
          seen.set(shown[0].id, [...(seen.get(shown[0].id) ?? []), n])
        }
        // Every verified report has its own refuters, #1 to #N.
        expect([...seen.keys()].sort(), where).toEqual(verified.map((r) => r.id).sort())
        for (const r of verified) expect(seen.get(r.id)?.sort(), `${where}: ${r.id}`).toEqual(Array.from({ length: T.refuters }, (_, k) => `#${k + 1}`))
        // Every report lands where its own answers put it, at the severity they give it, under the lens that found it.
        const idOf = (text: string) => text.match(/\[#\d{3}\]/)?.[0] ?? text
        expect(result.confirmed.map((c) => [idOf(String(c.detail)), c.severity, String(c.lens)]).sort(), where).toEqual(want.confirmed.sort())
        expect(result.refuted.map((x) => idOf((x as { reasons?: string[] }).reasons?.join(' ') ?? '')).sort(), where).toEqual(want.refuted.sort())
        expect(result.unverified.map((u) => [idOf(String((u as { detail?: string }).detail)), u.severity]).sort(), where).toEqual(want.unverified.sort())
        const incomplete = verified.some((r) => want.unverified.some(([id]) => id === r.id))
        expect(result.incomplete, where).toBe(incomplete)
        expect(result.mergeable, where).toBe(!incomplete && !want.confirmed.some(([, s]) => s === 'blocker') && !want.unverified.some(([, s]) => s === 'blocker'))
      }
    }
  }, 120_000)

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
    expect(results.map((r) => r.agents)).toEqual([3 + 6 * 2, 2])
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
    const one: Findings = { findings: [{ file: 'b.py', title: 'should', detail: 'd', severity: 'should-fix', evidence: 'e' }], summary: 's' }
    const { agent } = stub((label) => label.startsWith('verify:') && label.endsWith('#2'), { findings: one })
    const [result] = (await load()({ prs: [pr('high')] }, agent)) as Result[]
    expect(titles(result.unverified)).toEqual(['should', 'should', 'should'])
    expect(result.confirmed).toHaveLength(0)
    expect(result.incomplete).toBe(true)
    expect(result.mergeable).toBe(false)
  })

  it("carries a refuter's corrected severity: a should-fix raised to blocker, by both refuters or by either one, is a confirmed blocker that blocks the merge", async () => {
    // Both of correctness's refuters raise it, only refuter #2 raises tests-and-gates, and nothing corrects rules-and-brief.
    const both = stub(undefined, { findings: shouldOnly, corrected: (label) => (label.includes(':correctness.py#') || label.endsWith(':tests-and-gates.py#2') ? 'blocker' : undefined) })
    const [raised] = (await load()({ prs: [pr('high')] }, both.agent)) as Result[]
    expect(severities(raised)).toEqual({ 'should-correctness': 'blocker', 'should-rules-and-brief': 'should-fix', 'should-tests-and-gates': 'blocker' })
    expect(raised.incomplete).toBe(false)
    expect(raised.mergeable).toBe(false)
    // One refuter's raise alone blocks the merge, whichever refuter gives it.
    for (const refuter of ['#1', '#2']) {
      const one = stub(undefined, { findings: shouldOnly, corrected: (label) => (label.endsWith(`:rules-and-brief.py${refuter}`) ? 'blocker' : undefined) })
      const [single] = (await load()({ prs: [pr('high')] }, one.agent)) as Result[]
      expect(severities(single), refuter).toEqual({ 'should-correctness': 'should-fix', 'should-rules-and-brief': 'blocker', 'should-tests-and-gates': 'should-fix' })
      expect(single.mergeable, refuter).toBe(false)
    }
    // Without corrections the same findings stay should-fixes, and the PR is mergeable.
    const plain = stub(undefined, { findings: shouldOnly })
    const [kept] = (await load()({ prs: [pr('high')] }, plain.agent)) as Result[]
    expect(Object.values(severities(kept))).toEqual(['should-fix', 'should-fix', 'should-fix'])
    expect(kept.mergeable).toBe(true)
  })

  it("takes the highest of the refuters' corrections whichever refuter gives it: a raise to blocker survives the other refuter restating or lowering the severity", async () => {
    // The tests-and-gates finding's refuters correct it: #1 says one thing, #2 another, in both orders. The blocker
    // wins each time, whichever refuter gave it. Below blocker the same rule holds: nit against should-fix gives
    // should-fix, and the PR stays mergeable.
    const pairs: Array<[string, string, string]> = [
      ['nit', 'blocker', 'blocker'], ['blocker', 'nit', 'blocker'], ['should-fix', 'blocker', 'blocker'], ['blocker', 'should-fix', 'blocker'],
      ['nit', 'should-fix', 'should-fix'], ['should-fix', 'nit', 'should-fix'],
    ]
    for (const [first, second, expected] of pairs) {
      const s = stub(undefined, { findings: shouldOnly, corrected: (label) => (label.includes(':tests-and-gates.py#') ? (label.endsWith('#1') ? first : second) : undefined) })
      const [r] = (await load()({ prs: [pr('high')] }, s.agent)) as Result[]
      expect(severities(r), `${first} then ${second}`).toEqual({ 'should-correctness': 'should-fix', 'should-rules-and-brief': 'should-fix', 'should-tests-and-gates': expected })
      expect(r.mergeable, `${first} then ${second}`).toBe(expected !== 'blocker')
    }
    // Two lowerings that agree confirm the finding as a nit, and the PR stays mergeable.
    const low = stub(undefined, { findings: shouldOnly, corrected: (label) => (label.includes(':tests-and-gates.py#') ? 'nit' : undefined) })
    const [lowered] = (await load()({ prs: [pr('high')] }, low.agent)) as Result[]
    expect(severities(lowered)).toEqual({ 'should-correctness': 'should-fix', 'should-rules-and-brief': 'should-fix', 'should-tests-and-gates': 'nit' })
    expect(lowered.mergeable).toBe(true)
  })

  it('holds a finding at its claimed severity for a refuter that sets no correction, so a lowering needs both refuters: a claimed blocker that one refuter lowers while the other is silent still blocks the merge, and two lowerings that disagree confirm the higher', async () => {
    // Every lens reports the blocker (a.py) and a should-fix (b.py); refuter #1 lowers each, refuter #2 sets nothing.
    const lowerFirst = stub(undefined, { corrected: (label) => (label.endsWith(':a.py#1') ? 'should-fix' : label.endsWith(':b.py#1') ? 'nit' : undefined) })
    const [held] = (await load()({ prs: [pr('high')] }, lowerFirst.agent)) as Result[]
    expect(held.confirmed.filter((c) => c.title === 'blocker').map((c) => c.severity)).toEqual(['blocker', 'blocker', 'blocker'])
    expect(held.confirmed.filter((c) => c.title === 'should').map((c) => c.severity)).toEqual(['should-fix', 'should-fix', 'should-fix'])
    expect(held.incomplete).toBe(false)
    expect(held.mergeable).toBe(false)
    // The same lowerings from both refuters take effect, and the lowered blockers free the merge.
    const lowerBoth = stub(undefined, { corrected: (label) => (label.includes(':a.py#') ? 'should-fix' : label.includes(':b.py#') ? 'nit' : undefined) })
    const [lowered] = (await load()({ prs: [pr('high')] }, lowerBoth.agent)) as Result[]
    expect(lowered.confirmed.filter((c) => c.title === 'blocker').map((c) => c.severity)).toEqual(['should-fix', 'should-fix', 'should-fix'])
    expect(lowered.confirmed.filter((c) => c.title === 'should').map((c) => c.severity)).toEqual(['nit', 'nit', 'nit'])
    expect(lowered.mergeable).toBe(true)
    // Two lowerings that disagree confirm the finding at the higher of the two, whichever refuter gives it; two
    // that agree confirm the lower, nit included.
    for (const [first, second, expected] of [['nit', 'should-fix', 'should-fix'], ['should-fix', 'nit', 'should-fix'], ['nit', 'nit', 'nit']]) {
      const lowerSplit = stub(undefined, { corrected: (label) => (label.includes(':a.py#') ? (label.endsWith('#1') ? first : second) : undefined) })
      const [split] = (await load()({ prs: [pr('high')] }, lowerSplit.agent)) as Result[]
      expect(split.confirmed.filter((c) => c.title === 'blocker').map((c) => c.severity), `${first} then ${second}`).toEqual([expected, expected, expected])
      expect(split.mergeable, `${first} then ${second}`).toBe(true)
    }
    // A correction outside the three severities is no correction: that refuter holds the claimed severity, so the other
    // refuter's lowering, alone, does not take effect.
    const bogus = stub(undefined, { corrected: (label) => (label.endsWith(':a.py#1') ? 'critical' : label.endsWith(':a.py#2') ? 'should-fix' : undefined) })
    const [unchanged] = (await load()({ prs: [pr('high')] }, bogus.agent)) as Result[]
    expect(unchanged.confirmed.filter((c) => c.title === 'blocker').map((c) => c.severity)).toEqual(['blocker', 'blocker', 'blocker'])
    expect(unchanged.mergeable).toBe(false)
  })

  it("lets the routine tier's one refuter lower a blocker alone: the corrected severity confirms and the PR is mergeable", async () => {
    for (const lowered of ['should-fix', 'nit']) {
      const s = stub(undefined, { corrected: (label) => (label.endsWith('a.py#1') ? lowered : undefined) })
      const [r] = (await load()({ prs: [pr('routine')] }, s.agent)) as Result[]
      expect(r.agents, lowered).toBe(2)
      expect(r.confirmed.map((c) => [c.title, c.severity]), lowered).toEqual([['blocker', lowered]])
      expect(titles(r.unverified), lowered).toEqual(['should'])
      expect(r.incomplete, lowered).toBe(false)
      expect(r.mergeable, lowered).toBe(true)
    }
  })

  it('refutes a finding one refuter raises to blocker while the other refutes it, or whose one vote refutes and raises at once: a raise never outlives a refutation', async () => {
    const all = ['should-correctness', 'should-rules-and-brief', 'should-tests-and-gates']
    // The third row has one vote refute and raise at once, with the other refuter holding the claim.
    for (const [raiser, refuter] of [['#1', '#2'], ['#2', '#1'], ['#1', '#1']]) {
      const s = stub(undefined, { findings: shouldOnly, refuted: (label) => label.endsWith(refuter), corrected: (label) => (label.endsWith(raiser) ? 'blocker' : undefined) })
      const [r] = (await load()({ prs: [pr('high')] }, s.agent)) as Result[]
      expect(r.confirmed, `${raiser} raises, ${refuter} refutes`).toHaveLength(0)
      expect(titles(r.refuted), `${raiser} raises, ${refuter} refutes`).toEqual(all)
      expect(r.mergeable, `${raiser} raises, ${refuter} refutes`).toBe(true)
    }
  })

  it('refutes a claimed blocker that one of its two refuters refutes while the other holds it: a finding stands only if every attempt fails', async () => {
    for (const refuter of ['#1', '#2']) {
      const s = stub(undefined, { refuted: (label) => label.includes('a.py') && label.endsWith(refuter) })
      const [r] = (await load()({ prs: [pr('high')] }, s.agent)) as Result[]
      expect(titles(r.refuted), refuter).toEqual(['blocker', 'blocker', 'blocker'])
      expect(titles(r.confirmed), refuter).toEqual(['should', 'should', 'should'])
      expect(r.incomplete, refuter).toBe(false)
      expect(r.mergeable, refuter).toBe(true)
    }
  })

  it('keeps a finding with a vote missing unverified at its claimed severity, whatever the other refuter holds', async () => {
    // The should-fixes' refuter #2 returns nothing while #1 raises each to blocker, then lowers each to nit; the
    // blockers' pairs are whole.
    const isShould = (label: string) => label.startsWith('verify:') && !label.includes('a.py')
    for (const held of ['blocker', 'nit']) {
      const s = stub((label) => isShould(label) && label.endsWith('#2'), { corrected: (label) => (isShould(label) && label.endsWith('#1') ? held : undefined) })
      const [r] = (await load()({ prs: [pr('high')] }, s.agent)) as Result[]
      expect(r.unverified.map((u) => [u.title, u.severity]), held).toEqual([['should', 'should-fix'], ['should', 'should-fix'], ['should', 'should-fix']])
      expect(titles(r.confirmed), held).toEqual(['blocker', 'blocker', 'blocker'])
      expect(r.refuted, held).toHaveLength(0)
      expect(r.incomplete, held).toBe(true)
      expect(r.mergeable, held).toBe(false)
    }
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
