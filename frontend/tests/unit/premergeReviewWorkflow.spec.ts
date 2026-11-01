/**
 * Behavioural gate for `.claude/workflows/premerge-review.js` (CLAUDE.md rule 12; AGENTS.md §5).
 *
 * The Python gate `backend/tests/unit/test_agent_workflow_rules.py` checks the script's text. Text
 * checks keep missing JavaScript corner cases (a spread that overrides `model`, a tier key that is
 * undefined for one tier, a loosened vote count), so this spec runs the script itself with stubbed
 * `agent`/`pipeline`/`parallel` and the runtime's other hooks, and asserts what every stage actually receives and returns:
 *   - every agent call carries a literal, non-premium model and the effort the tier promises;
 *   - the agent counts per tier (records 1, routine 1 + 1 per blocker, high 3 + 2 per serious finding);
 *   - every refuter, on every tier, answers in the one-verdict schema, pinned exactly (types and enums included),
 *     and its prompt asks for a correction only when the claimed severity is wrong;
 *   - every verified report gets its own refuters, the high tier's two on Opus or the routine tier's one on Sonnet,
 *     even when one defect is reported more than once, by one lens or by several (the founder removed #1855's shared
 *     refuters on 2026-11-01; lessons/ops-replace-a-redundant-review-stage-never-drop-it.md). Four cases gate it:
 *     - the static case parses the script: it must refer to `agent` exactly twice, each time calling it directly on a
 *       prompt that lensPrompt or refuterPrompt builds, and name none of the ways the runtime or this harness offers to
 *       another agent or to a binding by a name built at run time (`workflow`, `budget`, `arguments`, `eval`,
 *       `Function`, `globalThis`, `global`, `self`, `window`, `this`). So a stage that calls an agent through a new call,
 *       a prompt held in a variable, chosen at run time or extended, an alias, `.call`, `.apply`, a property or one of
 *       those names fails, and so does a renamed prompt builder, which means updating the check. The case also scores
 *       the check on sources planted into a stand-in with the script's two calls, each marked flagged, look-alike or gap;
 *       some flagged ones keep the two references, so only the form of a call decides them;
 *     - the exhaustive case runs one defect reported twice (by one lens twice, or on the high tier by two lenses;
 *       claimed alike or not) with every combination of its refuters' answers;
 *     - the verbatim case runs two reports identical in every field a refuter sees (one lens's, or on the high tier two
 *       lenses') with every combination of their refuters' answers. No tag can tell them apart, so it holds every answer
 *       to one report: each answer given serves exactly one report, through refuters of different numbers, and each
 *       report lands as the answers it carries decide. For the same reason it compares the refuters' prompts with the
 *       copies' own as a whole, so refuters that trade prompts pass it;
 *     - the sweep runs, on the high tier, every combination of the seven sets of reporting lenses, zero or one blocker
 *       defect, one to eight should-fix defects and one or two copies, plus three reviews of up to 198 reports in
 *       three copies; on the routine tier, one to four blocker defects with zero or one should-fix defect, in one to
 *       three copies. About one copy in four, drawn, claims the other serious severity, and each reporting lens also
 *       reports a nit about half the time, drawn per lens. A defect's copies share its file, its line (or its lack of
 *       one) and its title, and by turns its evidence, its detail or neither. Each refuter answers hold (twice as often as each other
 *       answer), refute, lower, raise or nothing, drawn per shape, PR, report and refuter. On each tier and PR, every
 *       severity the tier verifies meets every combination of its refuters' answers, `incomplete` and `mergeable` each
 *       come out both ways, and reviews with nits and without both run.
 *     The dynamic cases run each review on three PRs: one numbered 1 with its tier set on the batch; one shaped like
 *     the call AGENTS.md §5 documents (a real number, title and branch, base main, the tier on the PR); and one shaped
 *     like the handover's call (a brief, another base, the tier left to the batch or to the default). On the high tier,
 *     the three take their tier from the batch, the PR and the default. Each lens's summary names the reports it made.
 *     In every review: no agent runs but the lenses and the refuters; each refuter's prompt is exactly the one it gets
 *     when its report is the review's only finding (compared as a whole in the verbatim case); each verified report has
 *     its own refuters #1 to #N; each report is confirmed, refuted, left unverified or kept as a nit as its own answers
 *     decide, a confirmed or unverified one at its severity and under its lens; and `incomplete` and `mergeable` match;
 *     - out of reach: a change that acts only on reviews these leave out (a larger review, a batch of several PRs, a
 *       tier set on both a PR and its batch, a lens that returns nothing, or a mix of claims and answers the sweep's
 *       draws never produce, such as an exact count of verified reports), only on what they hold fixed (the form of the
 *       files, titles and words, and the date and time they run at, which a script can still read through `Intl`) or
 *       only where this harness and the runtime differ (the runtime blocks clock and randomness reads beyond the three
 *       the harness makes throw, such as `Date()` called without `new`, a `Date` reached through an instance or
 *       `performance.now()`; the two have different globals and engines; and each run in the runtime has built-ins of
 *       its own, where runs here share the host's; so a change can tell which one it runs in, by whether `process` or
 *       `Temporal` exists or by a mark an earlier run left on `JSON`, say, and act only in the runtime), and that
 *       either calls no agent of its own (it judges a copy on another copy's votes, say) or reaches one through the
 *       lenses' or the refuters' own call (a helper that builds their prompt and calls `agent`) or through a name built
 *       at run time that the static case does not list (the Function constructor reached as a property, say);
 *   - each refuter holds a finding at its corrected severity, or at the claimed one when it sets none or sets one
 *     outside the three severities, and the highest holding wins whichever refuter gives it: a should-fix raised
 *     to blocker, by one refuter or both, is a confirmed blocker and blocks the merge, even when the other refuter
 *     restates or lowers it; a lowering needs every refuter of the tier (both on the high tier), so a claimed
 *     blocker that one refuter lowers while the other is silent still blocks the merge, while the routine tier's
 *     one refuter lowers a blocker alone; two lowerings that agree confirm the finding at the lower severity, nit
 *     included, and two that disagree confirm it at the higher of the two; no correction outlives a refutation: a
 *     finding one refuter raises to blocker while the other refutes it, or whose one vote refutes and raises or
 *     lowers at once, is refuted, and a claimed blocker one of its two refuters refutes is refuted; a finding with a
 *     vote missing stays unverified at its claimed severity whatever the other refuter holds;
 *   - a missing tier reviews as high, an unknown tier or a batch-wide `records` fails before any agent;
 *   - a complete vote lands where it should: every unrefuted finding in `confirmed`, a blocker there
 *     or left unverified makes the PR not mergeable, a refuted blocker frees it, no findings is mergeable;
 *   - a PR's own tier beats the batch tier;
 *   - a lens that returns nothing makes the result `incomplete` and not mergeable;
 *   - a refuter that returns nothing leaves the finding unverified, never refuted, and makes the result
 *     `incomplete`, so a should-fix whose required refutation never ran is not clearance;
 *   - a verification that throws keeps its finding (unverified) instead of dropping it. It throws as it can in the
 *     runtime, where `parallel` and `agent` throw once a run has started all the agents it may: the case caps the run at
 *     two agents, so the lens and the first of two blockers' refuters use them and the second blocker's refuters' call
 *     throws;
 *   - an inherited property name (`constructor`, `toString`, `__proto__`) is an unknown tier.
 * `pipeline` and `parallel` follow the documented runtime semantics: a throwing stage drops its item to null, and a
 * thunk that throws, at once or later, resolves to null; as in the runtime, `parallel` and `agent` themselves throw
 * only once the run has started all the agents it may, which no case but that one reaches. `budget` has no target,
 * and `workflow` is passed on to `agent` under a `workflow:` label, so a guarded call to it runs here as it would in
 * the runtime and counts as one agent too many. As in the runtime, the script runs in strict mode, each run gets fresh
 * hooks and its own copies of `args` and of each agent's result, parsed from JSON, and `Date.now()`, an argless
 * `new Date()` and `Math.random()` throw.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { isDeepStrictEqual } from 'node:util'
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

function load({ agentCap = Infinity }: { agentCap?: number } = {}): (args: unknown, agent: unknown) => Promise<unknown> {
  const source = readFileSync(SCRIPT, 'utf8').replace(/^export const meta/m, 'const meta')
  // The runtime's clock and randomness throw, as the Workflow reference documents: Date.now(), an argless new Date()
  // and Math.random().
  const throws = (what: string) => (): never => {
    throw new Error(`${what} throws in the Workflow runtime`)
  }
  // Strict, as the runtime compiles it: a strict function exposes no `.arguments` property and no stack frame's
  // function. The `arguments` binding still reaches these hooks by position here, though not in the runtime, where the
  // script's top level has none; the static case flags it.
  const factory = new Function('args', 'agent', 'pipeline', 'parallel', 'log', 'phase', 'budget', 'workflow', 'Date', 'Math', `'use strict'; return (async () => {${source}})()`)
  // The runtime gives each run a context of its own: new hooks, and `args` and each agent's result parsed afresh from
  // JSON. So nothing a run writes into them, or leaves on a hook, reaches another run or another agent's result. Shared
  // here, a script that wrote a PR's tier back onto it would turn the cases' batch-tier runs into PR-tier runs, and
  // one that tagged two lenses' findings in place would fail a case it passes in the runtime.
  const own = (value: unknown) => (value === undefined ? undefined : JSON.parse(JSON.stringify(value)))
  return (args, agent) => {
    // The runtime caps the agents a run may start (at 1000) and checks the cap in `parallel` and `agent`, which throw
    // once it is reached; the case for a verification that throws sets a cap low enough to reach.
    let started = 0
    const atCap = () => {
      if (started >= agentCap) throw new Error(`the run has started all ${agentCap} of its agents`)
    }
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
    // Each thunk settles on its own, as in the runtime: one that throws, synchronously or not, resolves to null.
    const parallel = async (thunks: Array<() => Promise<unknown>>) => {
      if (thunks.length) atCap()
      return Promise.all(
        thunks.map(async (thunk) => {
          try {
            return await thunk()
          } catch {
            return null
          }
        }),
      )
    }
    const log = () => undefined
    const phase = () => undefined
    const RuntimeDate = new Proxy(Date, {
      construct: (target, argArray, newTarget) => (argArray.length ? Reflect.construct(target, argArray, newTarget) : throws('new Date()')()),
      get: (target, key, receiver) => (key === 'now' ? throws('Date.now()') : Reflect.get(target, key, receiver)),
    })
    const RuntimeMath = Object.create(Math, { random: { value: throws('Math.random()') } })
    // The runtime's token budget when no target is set, as the Workflow reference documents it.
    const budget = Object.freeze({ total: null, spent: () => 0, remaining: () => Infinity })
    const stub = agent as (prompt: unknown, o: unknown) => Promise<unknown>
    const ownAgent = async (prompt: unknown, o: unknown) => {
      atCap()
      started += 1
      return own(await stub(prompt, o))
    }
    // `workflow` runs a saved workflow whose agents count as this run's own, so it reaches the stub as one more agent.
    const workflow = (ref: unknown, input?: unknown) =>
      ownAgent(JSON.stringify({ ref, input }), { label: `workflow:${JSON.stringify(ref)}` })
    return factory(own(args), ownAgent, pipeline, parallel, log, phase, budget, workflow, RuntimeDate, RuntimeMath) as Promise<unknown>
  }
}

type Verdict = { title: string; severity: string; detail?: string; evidence?: string; lens?: string; votes?: Array<{ refuted: boolean; reason: string }> }
type Result = {
  tier: string
  agents: number
  incomplete: boolean
  mergeable: boolean
  confirmed: Verdict[]
  refuted: Array<{ title: string; reasons?: string[] }>
  unverified: Verdict[]
  nits: Verdict[]
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

// The static half of the pair-per-report gate. The script may refer to `agent` exactly twice, each time calling it
// directly on the prompt one of these builds.
const AGENT_USES = ['lensPrompt', 'refuterPrompt']
// Names that reach an agent, or a binding by a name built at run time, without naming `agent`: the runtime's `workflow`
// (its agents count as this run's own) and `budget` (a stage that reads it can only be fitting the agents to their cost,
// which AGENTS.md §5's fixed counts rule out); `arguments`, which reaches this harness's hooks by position; and `eval`,
// `Function` and the global object's names, which reach a binding by a name built at run time.
const REACHING_NAMES = new Set(['workflow', 'budget', 'arguments', 'eval', 'Function', 'globalThis', 'global', 'self', 'window'])

// Each reference to `agent` in `source`, as the prompt builder it is called directly on or as the code that holds or
// calls it otherwise, and each use of a reaching name or `this`, sorted. The name after a dot and an object literal's
// key spelled like one of them are not references; any other spelling counts (a destructured key, a method or a class
// field named `agent`), which keeps the check strict.
function agentUses(source: string): string[] {
  const file = ts.createSourceFile('premerge-review.js', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS)
  const uses: string[] = []
  const isKey = (node: ts.Node) => (ts.isPropertyAccessExpression(node.parent) || ts.isPropertyAssignment(node.parent)) && node.parent.name === node
  const visit = (node: ts.Node): void => {
    if (ts.isIdentifier(node) && node.text === 'agent' && !isKey(node)) {
      const call = node.parent
      const first = ts.isCallExpression(call) && call.expression === node ? call.arguments[0] : undefined
      uses.push(first && ts.isCallExpression(first) && ts.isIdentifier(first.expression) ? first.expression.text : `agent held or called otherwise: ${call.getText(file).slice(0, 80)}`)
    } else if ((ts.isIdentifier(node) && REACHING_NAMES.has(node.text) && !isKey(node)) || node.kind === ts.SyntaxKind.ThisKeyword) {
      uses.push(`a reaching name: ${node.parent.getText(file).slice(0, 80)}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return uses.sort()
}

// The dynamic half: reviews whose every refuter answers on its own, compared with the judge AGENTS.md §5 describes,
// applied to each report's own refuters' answers alone.
type Answer = 'hold' | 'refute' | 'lower' | 'raise' | 'missing'
type Report = { id: string; lens: string; title: string; claimed: string; file: string; line?: number; detail: string; evidence: string }
type Tier = { lenses: string[]; refuters: number; verify: string[]; model: string; effort?: string }
const ANSWERS: Answer[] = ['hold', 'refute', 'lower', 'raise', 'missing']
const REFUTING: Record<'high' | 'routine', Tier> = {
  high: { lenses: ['correctness', 'rules-and-brief', 'tests-and-gates'], refuters: 2, verify: ['blocker', 'should-fix'], model: 'opus' },
  routine: { lenses: ['combined'], refuters: 1, verify: ['blocker'], model: 'sonnet', effort: 'medium' },
}
const RANK: Record<string, number> = { nit: 1, 'should-fix': 2, blocker: 3 }
const LOWER: Record<string, string> = { blocker: 'should-fix', 'should-fix': 'nit' }
const OTHER: Record<string, string> = { blocker: 'should-fix', 'should-fix': 'blocker' }
const correction = (r: Report, a: Answer) => (a === 'lower' ? LOWER[r.claimed] : a === 'raise' ? 'blocker' : undefined)

// Each review runs on three PRs: the fixture's, numbered 1 with its tier set on the batch (the script's header takes
// routine or high there); one shaped like the call AGENTS.md §5 documents (a real number, title and branch, base main,
// the tier on the PR); and one shaped like the call tasks/handover-wave2-2026-09.md documents (a brief and no tier),
// with another base, its tier left to the batch (routine) or to the default (high). So on the high tier the tier comes
// from each of its sources: the batch, the PR and the default.
const runsOf = (tier: 'high' | 'routine') => [
  { name: 'PR #1', args: { prs: [pr()], tier } },
  { name: 'PR #1873', args: { prs: [{ number: 1873, branch: 'claude/a-real-branch', title: 'fix(api): a real title', base: 'main', tier }] } },
  {
    name: 'PR #1874',
    args: { prs: [{ number: 1874, branch: 'claude/another-branch', title: 'feat(ui): another real title', base: 'release', brief: 'WS-6' }], ...(tier === 'routine' ? { tier } : {}) },
  },
]

const tagsIn = (reports: Report[], text: string) => reports.filter((r) => text.includes(r.id))
const finding = (r: Report) => ({ file: r.file, ...(r.line ? { line: r.line } : {}), title: r.title, detail: r.detail, severity: r.claimed, evidence: r.evidence })

// Runs one review of `reports` on `args`. Each lens reports its own reports, with a summary that names them; each
// refuter answers as `answerOf` gives for the one report its prompt names, and puts that report's tag in its reason.
async function reviewWith(run: ReturnType<typeof load>, args: unknown, reports: Report[], answerOf: (r: Report, n: number) => Answer) {
  const calls: Call[] = []
  const [result] = (await run(args, async (prompt: string, o: { label: string; model?: unknown; effort?: unknown; schema?: unknown }) => {
    calls.push({ label: o.label, model: o.model, effort: o.effort, prompt, schema: o.schema })
    if (o.label.startsWith('review:')) {
      const mine = reports.filter((r) => r.lens === o.label.split(':').pop())
      return { findings: mine.map(finding), summary: mine.length ? `reported ${mine.map((r) => r.id).join(', ')}` : 'nothing to report' }
    }
    const r = tagsIn(reports, prompt)[0]
    const n = Number(o.label.split('#').pop())
    const a = r ? answerOf(r, n) : 'refute'
    if (a === 'missing') return null
    const corrected = r ? correction(r, a) : undefined
    return { refuted: a === 'refute', reason: `${r?.id} #${n}`, ...(corrected ? { corrected_severity: corrected } : {}) }
  })) as Result[]
  return { calls, result }
}

// The prompt each refuter of each of `verified` gets when that report is its review's only finding.
async function soloPrompts(run: ReturnType<typeof load>, args: unknown, verified: Report[]) {
  const solo = new Map<string, string>()
  for (const r of verified) {
    const { calls } = await reviewWith(run, args, [r], () => 'hold')
    for (const c of calls.filter((x) => x.label.startsWith('verify:'))) solo.set(`${r.id}${c.label.slice(c.label.lastIndexOf('#'))}`, c.prompt)
  }
  return solo
}

// Checks one review against the rule. Returns what broke it (nothing when the rule holds) and the outcome its reports'
// own answers give. The checks are plain comparisons, asserted once per review, which keeps the exhaustive case fast.
function ownVerdictProblems(T: Tier, reports: Report[], calls: Call[], result: Result, solo: Map<string, string>, answerOf: (r: Report, n: number) => Answer) {
  const problems: string[] = []
  const same = (got: unknown, want: unknown, what: string) => {
    if (!isDeepStrictEqual(got, want)) problems.push(`${what}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`)
  }
  const verified = reports.filter((r) => T.verify.includes(r.claimed))
  // The lenses and the tier's refuters of every verified report are the only agents.
  same(calls.map((c) => c.label.split(':')[0]).sort(), [...Array(T.lenses.length).fill('review'), ...Array(verified.length * T.refuters).fill('verify')], 'agents run')
  same(result.agents, T.lenses.length + verified.length * T.refuters, 'agents counted')
  if ('groups' in result) problems.push('the result carries groups')
  // Each refuter is shown exactly what it would be shown were its report the review's only finding, so nothing of
  // another report reaches it, in any form; it answers in the one-verdict schema, on the tier's model.
  const seen = new Map<string, string[]>()
  for (const call of calls.filter((c) => c.label.startsWith('verify:'))) {
    const shown = tagsIn(reports, call.prompt)
    if (shown.length !== 1) {
      problems.push(`${call.label} is shown ${shown.map((r) => r.id).join(', ') || 'no report'}`)
      continue
    }
    const n = call.label.slice(call.label.lastIndexOf('#'))
    if (call.prompt !== solo.get(`${shown[0].id}${n}`)) problems.push(`${call.label} for ${shown[0].id} differs from its report's own prompt`)
    same([call.model, call.effort, call.schema], [T.model, T.effort, VERDICT_SCHEMA], `${call.label}: model, effort and schema`)
    seen.set(shown[0].id, [...(seen.get(shown[0].id) ?? []), n])
  }
  // Every verified report has its own refuters, #1 to #N.
  same([...seen.keys()].sort(), verified.map((r) => r.id).sort(), 'reports with refuters')
  for (const r of verified) same(seen.get(r.id)?.sort(), Array.from({ length: T.refuters }, (_, k) => `#${k + 1}`), `${r.id}'s refuters`)
  // Every report lands where its own answers put it; a confirmed or unverified one at the severity they give it and
  // under the lens that found it, and a nit among the nits.
  const want = reports.map((r) => {
    if (r.claimed === 'nit') return [r.id, 'nit', 'nit', r.lens]
    if (!T.verify.includes(r.claimed)) return [r.id, 'unverified', r.claimed, r.lens]
    const votes = Array.from({ length: T.refuters }, (_, k) => answerOf(r, k + 1)).filter((a) => a !== 'missing')
    if (votes.length < T.refuters) return [r.id, 'unverified', r.claimed, r.lens]
    if (votes.includes('refute')) return [r.id, 'refuted']
    return [r.id, 'confirmed', votes.map((a) => correction(r, a) ?? r.claimed).reduce((x, y) => (RANK[y] > RANK[x] ? y : x)), r.lens]
  })
  const ids = (text: string) => tagsIn(reports, text).map((r) => r.id).join(' and ')
  const got = [
    ...result.confirmed.map((c) => [ids(`${c.detail} ${c.evidence}`), 'confirmed', c.severity, String(c.lens)]),
    ...result.refuted.map((x) => [ids((x.reasons ?? []).join(' ')), 'refuted']),
    ...result.unverified.map((u) => [ids(`${u.detail} ${u.evidence}`), 'unverified', u.severity, String(u.lens)]),
    ...result.nits.map((x) => [ids(`${x.detail} ${x.evidence}`), 'nit', x.severity, String(x.lens)]),
  ]
  same(got.sort(), want.sort(), 'verdicts')
  const incomplete = want.some(([id, kind]) => kind === 'unverified' && verified.some((r) => r.id === id))
  const mergeable = !incomplete && !want.some(([, kind, severity]) => kind !== 'refuted' && severity === 'blocker')
  same(result.incomplete, incomplete, 'incomplete')
  same(result.mergeable, mergeable, 'mergeable')
  return { problems, incomplete, mergeable }
}

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

  it("refers to `agent` only in the lenses' call and the refuters' call, each on its own built prompt, and names no other way to an agent: scored on planted sources, flagged, look-alike and gap", () => {
    expect(agentUses(readFileSync(SCRIPT, 'utf8')), 'the script may call agent only directly on lensPrompt(…) and refuterPrompt(…), once each').toEqual(AGENT_USES)
    // The planted cases go into a stand-in with the script's two calls, so they score the check, not the script's wording.
    const script = [
      "const lensPrompt = (pr, key) => 'review ' + key",
      "const refuterPrompt = (pr, f, i) => 'refute ' + f.title + ', skeptic #' + (i + 1)",
      'const judge = (f, votes) => ({ ...f, votes })',
      'const results = await pipeline(PRS, async (pr) => {',
      "  const findings = await parallel(LENSES.map((key) => () => agent(lensPrompt(pr, key), { label: 'review:' + key })))",
      '  return parallel(findings.flat().map((f) => () =>',
      "    parallel([0, 1].map((i) => () => agent(refuterPrompt(pr, f, i), { label: 'verify:' + f.file + '#' + (i + 1) }))).then((votes) => judge(f, votes))))",
      '})',
      'return results.filter(Boolean)',
    ].join('\n')
    expect(agentUses(script), 'the stand-in').toEqual(AGENT_USES)
    const END = 'return results.filter(Boolean)'
    const PIPELINE = 'const results = await pipeline('
    const LENS_CALL = 'agent(lensPrompt(pr, key), {'
    const REFUTER_CALL = 'agent(refuterPrompt(pr, f, i), {'
    const add = (code: string) => (src: string) => src.replace(END, `${code}\n${END}`)
    const swap = (call: string, replacement: string) => (src: string) => src.replace(call, replacement)
    const helper = (call: string, helperCall: string, definition: string) => (src: string) => swap(call, helperCall)(src).replace(PIPELINE, `${definition}\n${PIPELINE}`)
    const PLANTED: Array<[string, 'flag' | 'clean' | 'gap', (src: string) => string]> = [
      // Flagged with the two references kept, so only the form of each call decides them, not the count or the names.
      ["the refuters' call on another builder", 'flag', swap(REFUTER_CALL, 'agent(groupPrompt(pr, f, i), {')],
      ["the lenses' call on the refuters' builder", 'flag', swap(LENS_CALL, 'agent(refuterPrompt(pr, key, 0), {')],
      ["the refuters' call on a prompt chosen at run time", 'flag', swap(REFUTER_CALL, "agent(PRS.length > 1 ? refuterPrompt(pr, f, i) + ' and the others' : refuterPrompt(pr, f, i), {")],
      ["the refuters' call on a prompt held in a variable", 'flag', swap(REFUTER_CALL, 'agent(heldPrompt, {')],
      ["the refuters' call on an extended prompt", 'flag', swap(REFUTER_CALL, 'agent(refuterPrompt(pr, f, i) + otherReports, {')],
      ["the refuters' call through `.call`", 'flag', swap(REFUTER_CALL, 'agent.call(null, refuterPrompt(pr, f, i), {')],
      // Flagged: a stage that reaches an agent outside the two calls.
      ['a new call on a prompt of its own', 'flag', add("const groups = await agent(groupPrompt(results), { label: 'group', model: 'sonnet' })")],
      ['a call on a prompt held in a variable', 'flag', add("const p = lensPrompt(PRS[0], 'correctness')\nawait agent(p, {})")],
      ['a third call on a built prompt', 'flag', add("await agent(lensPrompt(PRS[0], 'correctness'), {})")],
      ['an optional call', 'flag', add('await agent?.(refuterPrompt(PRS[0], {}, 0), {})')],
      ['an alias', 'flag', add('const ask = agent')],
      ['`.call`', 'flag', add('await agent.call(null, groupPrompt(results), {})')],
      ['`.apply`', 'flag', add('await agent.apply(null, [groupPrompt(results), {}])')],
      ['a property', 'flag', add('const stages = { ask: agent }')],
      ['a shorthand property', 'flag', add('const tools = { agent }')],
      ['a helper on any prompt', 'flag', add('const ask = (p, o) => agent(p, o)')],
      ['a call after a `//` inside a string', 'flag', add("const url = 'https://example.com//'; await agent(groupPrompt(results), {})")],
      ["the runtime's `workflow`, guarded", 'flag', add("const groups = typeof workflow === 'function' ? await workflow('dedupe-findings', results) : null")],
      ["the runtime's `budget`", 'flag', add('const lean = budget.total !== null && budget.remaining() < 100000')],
      ['`arguments`', 'flag', add('const ask = arguments[1]')],
      ['`eval`', 'flag', add("const ask = eval('ag' + 'ent')")],
      ['`Function`', 'flag', add("const ask = Function('return ag' + 'ent')()")],
      ['`globalThis`', 'flag', add("const ask = globalThis['ag' + 'ent']")],
      ['`global`', 'flag', add("const ask = global['ag' + 'ent']")],
      ['`self`', 'flag', add("const ask = self['ag' + 'ent']")],
      ['`window`', 'flag', add("const ask = window['ag' + 'ent']")],
      ['`this`', 'flag', add("const ask = this['ag' + 'ent']")],
      // Look-alikes: code that reaches no agent.
      ['`agent(` inside a string', 'clean', add("const s = 'agent(groupPrompt(results), {})'")],
      ['`agent(` inside a template', 'clean', add('const t = `agent(' + '${PRS.length})`')],
      ['`agent(` inside comments', 'clean', add('// agent(groupPrompt(results))\n/* agent(groupPrompt(results)) */')],
      ['words that contain it', 'clean', add('const agents = 1\nconst agentCount = agents + results.length')],
      ['a key and a property named `agent`', 'clean', add("const stamped = results.map((r) => ({ ...r, agent: 'premerge' }))\nconst first = stamped.length ? stamped[0].agent : null")],
      // Gaps the header names: the static case passes them, and only the dynamic cases can catch them, in their reviews.
      ["a helper that builds the refuters' prompt and calls `agent`", 'gap', helper(REFUTER_CALL, 'askRefuter(pr, f, i, {', 'const askRefuter = (pr, f, i, o) => agent(refuterPrompt(pr, f, i), o)')],
      ["a helper that builds the lenses' prompt and calls `agent`", 'gap', helper(LENS_CALL, 'askLens(pr, key, {', 'const askLens = (pr, key, o) => agent(lensPrompt(pr, key), o)')],
      ["a change that calls no agent: a copy judged on another copy's votes", 'gap', (src) => src.replace('.then((votes) => judge(f, votes))', '.then((votes) => judge(f, votesOfFirstCopy(f, votes)))')],
      ['the Function constructor reached as a property', 'gap', add("const ask = [].constructor.constructor('return ag' + 'ent')()")],
    ]
    for (const [name, mark, plant] of PLANTED) {
      const planted = plant(script)
      expect(planted, `${name}: the plant must change the script`).not.toBe(script)
      const passes = JSON.stringify(agentUses(planted)) === JSON.stringify(AGENT_USES)
      expect(passes ? (mark === 'flag' ? 'missed' : mark) : mark === 'flag' ? 'flag' : `flagged, though ${mark}`, name).toBe(mark)
    }
  })

  it("judges each of two reports of one defect on its own refuters' answers alone, for every combination of those answers, on both tiers and every PR, from one lens or two, claimed alike or not", async () => {
    const run = load()
    for (const tier of ['high', 'routine'] as const) {
      const T = REFUTING[tier]
      // One lens's two copies, or (high only) two lenses' one each, of one defect: same file, line, title and evidence.
      const arrangements = tier === 'high' ? [['tests-and-gates', 'tests-and-gates'], ['rules-and-brief', 'correctness']] : [['combined', 'combined']]
      const claims = [['should-fix', 'should-fix'], ['blocker', 'blocker'], ['should-fix', 'blocker'], ['blocker', 'should-fix']]
      for (const lenses of arrangements) {
        for (const claimed of claims) {
          const reports: Report[] = lenses.map((lens, k) => ({
            id: `[#00${k}]`, lens, title: 'one defect', claimed: claimed[k], file: 'src/one.py', line: 12,
            detail: `[#00${k}] one defect, in the ${lens} lens's words`, evidence: 'src/one.py:12 is the line both reports quote',
          }))
          const verified = reports.filter((r) => T.verify.includes(r.claimed))
          const slots = verified.length * T.refuters
          for (const { name, args } of runsOf(tier)) {
            const solo = await soloPrompts(run, args, verified)
            for (let k = 0; k < ANSWERS.length ** slots; k++) {
              const answerOf = (r: Report, n: number) => ANSWERS[Math.floor(k / ANSWERS.length ** (verified.indexOf(r) * T.refuters + n - 1)) % ANSWERS.length]
              const where = `${tier}, ${lenses.join(' then ')}, claimed ${claimed.join(' then ')}, ${name}, answers ${verified.flatMap((r) => Array.from({ length: T.refuters }, (_, n) => answerOf(r, n + 1))).join(' ')}`
              const { calls, result } = await reviewWith(run, args, reports, answerOf)
              expect(ownVerdictProblems(T, reports, calls, result, solo, answerOf).problems, where).toEqual([])
            }
          }
        }
      }
    }
  }, 120_000)

  it("judges two reports identical in every field a refuter sees on separate refuters' answers, for every combination of those answers: each answer serves one report, which lands as its own answers decide", async () => {
    const run = load()
    for (const tier of ['high', 'routine'] as const) {
      const T = REFUTING[tier]
      // One lens's two verbatim copies, or (high only) two lenses' one each.
      const arrangements = tier === 'high' ? [['rules-and-brief', 'rules-and-brief'], ['correctness', 'tests-and-gates']] : [['combined', 'combined']]
      for (const lenses of arrangements) {
        for (const claimed of T.verify) {
          const copy = { file: 'src/one.py', line: 12, title: 'one defect', detail: 'one defect, worded alike by both reports', severity: claimed, evidence: 'src/one.py:12 is the line both reports quote' }
          const lensAnswer = (label: string) => {
            const mine = lenses.filter((lens) => label.endsWith(`:${lens}`)).map(() => copy)
            return { findings: mine, summary: mine.length ? `reported one defect ${mine.length} time(s)` : 'nothing to report' }
          }
          for (const { name, args } of runsOf(tier)) {
            // The prompt each refuter number gets when one copy, from a given lens, is the review's only finding; the
            // refuters' prompts must be exactly those of each copy's own refuters.
            const solo = new Map<string, string>()
            for (const lens of new Set(lenses)) {
              await run(args, async (prompt: string, o: { label: string }) => {
                if (o.label.startsWith('review:')) return { findings: o.label.endsWith(`:${lens}`) ? [copy] : [], summary: 'reported one defect' }
                solo.set(`${lens} ${o.label.slice(o.label.lastIndexOf('#'))}`, prompt)
                return { refuted: false, reason: 'r' }
              })
            }
            const ownPrompts = lenses.flatMap((lens) => Array.from({ length: T.refuters }, (_, k) => solo.get(`${lens} #${k + 1}`))).sort()
            // The refuters' answers by call order; each answer's reason names its call.
            for (let k = 0; k < ANSWERS.length ** (2 * T.refuters); k++) {
              const given: Array<{ answer: Answer; number: string }> = []
              const calls: Call[] = []
              const [result] = (await run(args, async (prompt: string, o: { label: string; model?: unknown; effort?: unknown; schema?: unknown }) => {
                calls.push({ label: o.label, model: o.model, effort: o.effort, prompt, schema: o.schema })
                if (o.label.startsWith('review:')) return lensAnswer(o.label)
                const answer = ANSWERS[Math.floor(k / ANSWERS.length ** given.length) % ANSWERS.length]
                given.push({ answer, number: o.label.slice(o.label.lastIndexOf('#')) })
                if (answer === 'missing') return null
                const corrected = answer === 'lower' ? LOWER[claimed] : answer === 'raise' ? 'blocker' : undefined
                return { refuted: answer === 'refute', reason: `answer ${given.length - 1}`, ...(corrected ? { corrected_severity: corrected } : {}) }
              })) as Result[]
              const where = `${tier}, ${lenses.join(' then ')}, claimed ${claimed}, ${name}, answers ${given.map((g) => g.answer).join(' ')}`
              const problems: string[] = []
              const verifies = calls.filter((c) => c.label.startsWith('verify:'))
              if (calls.length - verifies.length !== T.lenses.length || verifies.length !== 2 * T.refuters) problems.push(`${calls.length - verifies.length} lenses and ${verifies.length} refuters ran`)
              if (!isDeepStrictEqual(verifies.map((c) => c.prompt).sort(), ownPrompts)) problems.push("the refuters' prompts differ from their reports' own")
              // Each report carries the answers it was judged on: every answer given serves exactly one report, through
              // refuters of different numbers, and each report lands as its own answers decide.
              const entries = [
                ...result.confirmed.map((c) => ({ got: `confirmed ${c.severity} under ${c.lens}`, lens: c.lens, used: (c.votes ?? []).map((v) => v.reason) })),
                ...result.refuted.map((x) => ({ got: 'refuted', lens: undefined, used: x.reasons ?? [] })),
                ...result.unverified.map((u) => ({ got: `unverified ${u.severity} under ${u.lens}`, lens: u.lens, used: (u.votes ?? []).map((v) => v.reason) })),
              ]
              if (entries.length !== 2) problems.push(`${entries.length} reports came back`)
              const answered = given.flatMap((g, n) => (g.answer === 'missing' ? [] : [`answer ${n}`]))
              if (!isDeepStrictEqual(entries.flatMap((e) => e.used).sort(), answered.sort())) problems.push(`answers used ${JSON.stringify(entries.map((e) => e.used))}, given ${JSON.stringify(answered)}`)
              const lensesBack = entries.flatMap((e) => (e.lens ? [e.lens] : []))
              if (lensesBack.some((lens) => lensesBack.filter((l) => l === lens).length > lenses.filter((l) => l === lens).length)) problems.push(`lenses ${JSON.stringify(lensesBack)} for reports from ${JSON.stringify(lenses)}`)
              for (const e of entries) {
                const own = e.used.map((reason) => given[Number(reason.split(' ')[1])])
                if (new Set(own.map((g) => g?.number)).size !== own.length) problems.push(`a report was judged on two answers from refuters of one number: ${JSON.stringify(e.used)}`)
                const answers = own.map((g) => g?.answer)
                const want = answers.length < T.refuters ? `unverified ${claimed}`
                  : answers.includes('refute') ? 'refuted'
                    : `confirmed ${answers.map((a) => (a === 'lower' ? LOWER[claimed] : a === 'raise' ? 'blocker' : claimed)).reduce((x, y) => (RANK[y] > RANK[x] ? y : x))}`
                if (!e.got.startsWith(want)) problems.push(`a report carrying ${JSON.stringify(e.used)} is ${e.got}, want ${want}`)
              }
              const missing = given.filter((g) => g.answer === 'missing').length
              if (entries.reduce((n, e) => n + T.refuters - e.used.length, 0) !== missing) problems.push(`${missing} answer(s) missing, but the reports lack ${JSON.stringify(entries.map((e) => T.refuters - e.used.length))}`)
              const incomplete = entries.some((e) => e.got.startsWith('unverified'))
              if (result.incomplete !== incomplete) problems.push(`incomplete is ${result.incomplete}`)
              if (result.mergeable !== (!incomplete && !entries.some((e) => /^(confirmed|unverified) blocker/.test(e.got)))) problems.push(`mergeable is ${result.mergeable}`)
              expect(problems, where).toEqual([])
            }
          }
        }
      }
    }
  }, 120_000)

  it('gives every verified report its own refuters on both tiers, each shown that report alone and judged on its own votes, in every review the sweep runs: nothing groups the copies or shares their refuters, votes or view', async () => {
    const run = load()
    // FNV-1a, then murmur3's 32-bit finalizer, so every character of the key reaches the low bits the draws read
    // (FNV-1a's lowest bit alone is the parity of the key's characters, which tied a report's two refuters together).
    const draw = (key: string) => {
      let h = 2166136261
      for (let k = 0; k < key.length; k++) h = Math.imul(h ^ key.charCodeAt(k), 16777619)
      h = Math.imul(h ^ (h >>> 16), 0x85ebca6b)
      h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35)
      return (h ^ (h >>> 16)) >>> 0
    }
    // A refuter holds the claim twice as often as it gives each other answer.
    const POOL: Answer[] = ['hold', ...ANSWERS]
    const HIGH = REFUTING.high.lenses
    const LENS_SETS = [1, 2, 3, 4, 5, 6, 7].map((m) => HIGH.filter((_, k) => m & (1 << k)))
    // [tier, lenses that report, blocker defects, should-fix defects, copies of every defect per lens].
    type Shape = ['high' | 'routine', string[], number, number, number]
    const SHAPES: Shape[] = [
      ...LENS_SETS.flatMap((lenses) => [0, 1].flatMap((b) => [1, 2, 3, 4, 5, 6, 7, 8].flatMap((s) => [1, 2].map((c): Shape => ['high', lenses, b, s, c])))),
      ['high', [HIGH[0]], 3, 9, 3], ['high', [HIGH[1], HIGH[2]], 2, 12, 3], ['high', HIGH, 2, 20, 3],
      ...[1, 2, 3, 4].flatMap((b) => [0, 1].flatMap((s) => [1, 2, 3].map((c): Shape => ['routine', ['combined'], b, s, c]))),
    ]
    // What the draws gave on each tier and PR: each claimed severity's combinations of answers, and each outcome of a
    // review with a report to verify.
    const met = new Map<string, Set<string>>()
    const meet = (key: string, value: string) => met.set(key, (met.get(key) ?? new Set<string>()).add(value))
    for (const [tier, lensSet, blockers, shoulds, copies] of SHAPES) {
      const T = REFUTING[tier]
      const defects = [
        ...Array.from({ length: blockers }, (_, k) => ({ title: `blocker ${k + 1}`, file: `src/a${k + 1}.py`, line: 7 as number | undefined, claimed: 'blocker' })),
        ...Array.from({ length: shoulds }, (_, k) => ({ title: `should-fix ${k + 1}`, file: `src/b${k + 1}.py`, line: k % 2 ? 9 : undefined, claimed: 'should-fix' })),
      ]
      for (const { name, args } of runsOf(tier)) {
        const where = `${tier}, ${lensSet.join(' + ')} reporting, ${blockers} blocker and ${shoulds} should-fix defect(s), ${copies} cop(ies), ${name}`
        // Every reporting lens reports every defect `copies` times, and about half the time (drawn per lens) a nit as well; each copy's
        // tag rides in a field its copies do not share.
        const reports: Report[] = []
        for (const lens of lensSet) {
          for (const [d, defect] of defects.entries()) {
            for (let copy = 1; copy <= copies; copy++) {
              const id = `[#${String(reports.length).padStart(3, '0')}]`
              reports.push({
                id, lens, title: defect.title, file: defect.file, line: defect.line,
                claimed: draw(`${where}: the claim of ${id}`) % 4 === 0 ? OTHER[defect.claimed] : defect.claimed,
                detail: d % 3 === 1 ? `${defect.title}, worded alike by every copy` : `${id} ${defect.title}, in the ${lens} lens's words, copy ${copy}`,
                evidence: d % 3 === 0 ? `${defect.file}${defect.line ? `:${defect.line}` : ''} is the line every copy quotes` : `${id} the ${lens} lens's evidence of ${defect.title}, copy ${copy}`,
              })
            }
          }
          if (draw(`${where}: ${lens}'s nit`) % 2 === 0) {
            const id = `[#${String(reports.length).padStart(3, '0')}]`
            reports.push({ id, lens, title: 'a nit', file: 'src/c.py', line: 3, claimed: 'nit', detail: `${id} a nit, in the ${lens} lens's words`, evidence: `${id} the ${lens} lens's evidence of a nit` })
          }
        }
        const verified = reports.filter((r) => T.verify.includes(r.claimed))
        const answerOf = (r: Report, n: number): Answer => POOL[draw(`${where}: ${r.id} #${n}`) % POOL.length]
        const solo = await soloPrompts(run, args, verified)
        const { calls, result } = await reviewWith(run, args, reports, answerOf)
        const outcome = ownVerdictProblems(T, reports, calls, result, solo, answerOf)
        expect(outcome.problems, where).toEqual([])
        for (const r of verified) meet(`${tier}, ${name}, claimed ${r.claimed}`, Array.from({ length: T.refuters }, (_, k) => answerOf(r, k + 1)).join(' + '))
        if (verified.length) {
          meet(`${tier}, ${name}`, `incomplete ${outcome.incomplete}`)
          meet(`${tier}, ${name}`, `mergeable ${outcome.mergeable}`)
          meet(`${tier}, ${name}`, `nits ${reports.some((r) => r.claimed === 'nit')}`)
        }
      }
    }
    // On each tier and PR, every severity the tier verifies met every combination of its refuters' answers, and both
    // outcomes of `incomplete` and of `mergeable` occurred, in reviews with nits and without: a draw that ties answers
    // together, or reviews that fix an outcome, fail here.
    for (const tier of ['high', 'routine'] as const) {
      const T = REFUTING[tier]
      const combos = T.refuters === 2 ? ANSWERS.flatMap((a) => ANSWERS.map((b) => `${a} + ${b}`)) : [...ANSWERS]
      for (const { name } of runsOf(tier)) {
        for (const claimed of T.verify) expect([...(met.get(`${tier}, ${name}, claimed ${claimed}`) ?? [])].sort(), `${tier}, ${name}, claimed ${claimed}`).toEqual([...combos].sort())
        expect([...(met.get(`${tier}, ${name}`) ?? [])].sort(), `${tier}, ${name}`).toEqual(['incomplete false', 'incomplete true', 'mergeable false', 'mergeable true', 'nits false', 'nits true'])
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
    const { agent, calls } = stub()
    const results = (await load()({ prs: [pr('high'), pr()], tier: 'routine' }, agent)) as Result[]
    expect(results.map((r) => r.tier)).toEqual(['high', 'routine'])
    expect(results.map((r) => r.agents)).toEqual([3 + 6 * 2, 2])
    // The agents a batch actually runs, not only the ones it reports: a stage that fires only in a batch shows here.
    expect(calls).toHaveLength(3 + 6 * 2 + 2)
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

  it('refutes a finding one refuter raises to blocker while the other refutes it, or whose one vote refutes and raises or lowers at once: no correction outlives a refutation', async () => {
    const all = ['should-correctness', 'should-rules-and-brief', 'should-tests-and-gates']
    // The last two rows have one vote refute and correct at once, raising and then lowering, with the other refuter
    // holding the claim.
    for (const [corrected, corrector, refuter] of [['blocker', '#1', '#2'], ['blocker', '#2', '#1'], ['blocker', '#1', '#1'], ['nit', '#1', '#1']]) {
      const s = stub(undefined, { findings: shouldOnly, refuted: (label) => label.endsWith(refuter), corrected: (label) => (label.endsWith(corrector) ? corrected : undefined) })
      const [r] = (await load()({ prs: [pr('high')] }, s.agent)) as Result[]
      const where = `${corrector} sets ${corrected}, ${refuter} refutes`
      expect(r.confirmed, where).toHaveLength(0)
      expect(titles(r.refuted), where).toEqual(all)
      expect(r.mergeable, where).toBe(true)
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
    // Two blockers on a run capped at two agents, as the runtime caps a run: the lens and the first blocker's refuter use
    // the cap, so the second blocker's refuters' `parallel` call throws, and with it that blocker's verification.
    const twoBlockers: Findings = {
      findings: [
        { file: 'a.py', title: 'first blocker', detail: 'd', severity: 'blocker', evidence: 'e' },
        { file: 'b.py', title: 'second blocker', detail: 'd', severity: 'blocker', evidence: 'e' },
      ],
      summary: 's',
    }
    const calls: Call[] = []
    const agent = async (prompt: string, o: { label: string; model?: unknown; effort?: unknown; schema?: unknown }) => {
      calls.push({ label: o.label, model: o.model, effort: o.effort, prompt, schema: o.schema })
      return o.label.startsWith('review:') ? twoBlockers : { refuted: true, reason: 'r' }
    }
    const [result] = (await load({ agentCap: 2 })({ prs: [pr('routine')] }, agent)) as Result[]
    expect(calls.map((c) => c.label)).toEqual(['review:1:combined', 'verify:1:a.py#1'])
    expect(titles(result.refuted)).toEqual(['first blocker'])
    expect(titles(result.unverified)).toEqual(['second blocker'])
    expect(result.confirmed).toHaveLength(0)
    expect(result.incomplete).toBe(true)
    expect(result.mergeable).toBe(false)
  })
})
