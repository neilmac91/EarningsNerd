export const meta = {
  name: 'premerge-review',
  description: 'Risk-tiered pre-merge review: records 1 Sonnet lens; routine 1 Opus lens + Sonnet refuters for blockers; high 3 Opus lenses + 2 Opus refuters per blocker/should-fix; missing tier reviews as high',
  phases: [
    { title: 'Review', detail: 'records: one combined lens on Sonnet; routine: one combined lens on Opus; high: correctness / rules+brief / tests+gates on Opus' },
    { title: 'Verify', detail: 'routine: one Sonnet refuter per blocker; high: two Opus refuters per blocker or should-fix' },
  ],
}

// args: { prs: [{ number, branch, title, base?, brief?, tier? }], tier? }
// tier: 'records' | 'routine' | 'high' (AGENTS.md §5 has the file list per tier). The PR's own tier wins;
// args.tier may set 'routine' or 'high' for the batch; 'records' is accepted only on a PR itself; a PR
// with no tier is reviewed as 'high'. An unknown tier fails the run before any agent starts.
const PRS = args.prs
const BATCH_TIER = args.tier === 'routine' || args.tier === 'high' ? args.tier : undefined
if (args.tier && !BATCH_TIER) throw new Error(`args.tier may be routine or high, not "${args.tier}"; set records on the PR itself`)

// Models are named per stage so no review agent inherits the session's premium model (AGENTS.md §5).
const TIERS = {
  records: { lenses: ['combined'], lensModel: 'sonnet', lensEffort: 'medium', refuters: 0, verify: [] },
  routine: { lenses: ['combined'], lensModel: 'opus', lensEffort: 'high', refuters: 1, refuterModel: 'sonnet', refuterEffort: 'medium', verify: ['blocker'] },
  high: { lenses: ['correctness', 'rules-and-brief', 'tests-and-gates'], lensModel: 'opus', refuters: 2, refuterModel: 'opus', verify: ['blocker', 'should-fix'] },
}
const tierOf = (pr) => pr.tier || BATCH_TIER || 'high'
for (const pr of PRS) {
  if (!TIERS[tierOf(pr)]) throw new Error(`unknown tier "${pr.tier}" for PR #${pr.number}; use records | routine | high`)
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          title: { type: 'string' },
          detail: { type: 'string' },
          severity: { type: 'string', enum: ['blocker', 'should-fix', 'nit'] },
          evidence: { type: 'string' },
        },
        required: ['file', 'title', 'detail', 'severity', 'evidence'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['findings', 'summary'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
    corrected_severity: { type: 'string', enum: ['blocker', 'should-fix', 'nit'] },
  },
  required: ['refuted', 'reason'],
}

const COMMON = (pr) => { const BASE = `origin/${pr.base || 'main'}`; return `
Repo: /home/user/EarningsNerd (branches already fetched; do NOT modify the working tree, do not check out branches, do not create worktrees — read-only review via git plumbing).
PR #${pr.number} "${pr.title}", branch origin/${pr.branch}, base ${BASE}.
Use the MERGE-BASE (three-dot) diff:
  git diff ${BASE}...origin/${pr.branch} --stat
  git diff ${BASE}...origin/${pr.branch} -- <path>
Do NOT report "this PR deletes files X" when X simply post-dates the branch point on main (check with: git log --oneline ${BASE}..origin/${pr.branch} and git merge-base ${BASE} origin/${pr.branch}); a normal merge keeps them.
Read files on the branch with: git show origin/${pr.branch}:<path>
Read what this PR is meant to do: ${pr.brief ? `git show ${BASE}:tasks/implementation-briefs-2026-09.md (section ${pr.brief})` : `the PR body (gh api repos/neilmac91/EarningsNerd/pulls/${pr.number} --jq .body)`}.
Read the repo rules: CLAUDE.md on ${BASE} (git show ${BASE}:CLAUDE.md) — the 12 non-negotiable rules, "Where things live", and "Tests". Lessons index: git show ${BASE}:lessons/README.md (open any lesson relevant to your lens with git show ${BASE}:lessons/<file>).
Report ONLY findings you can anchor to a file (and line where possible) in the diff or in code the diff affects, with concrete evidence (quote the line). No style opinions. No findings about things the brief or PR body explicitly put out of scope. If you find nothing at a severity, say so in summary. Severity: blocker = would break prod/CI/a CLAUDE.md rule or silently lose behaviour; should-fix = real defect or gate weakness worth a follow-up commit before merge; nit = cosmetic.`
}

const LENS_BODY = {
  correctness: (pr) => `LENS: CORRECTNESS. Hunt for bugs and regressions introduced by this diff: wrong logic, unhandled paths, behaviour silently lost by deletions (grep the whole tree on the branch for every symbol/route/setting the diff removes or renames — e.g. git grep -n <symbol> origin/${pr.branch} -- . ), shell/YAML mistakes in workflows (quote every changed shell line and reason about set -e, exit codes, quoting, GitHub Actions expression syntax), Python typing/async misuse, test fixtures that would not fail on the bad case. Try to actually execute anything cheap and safe that proves or disproves a suspicion (e.g. python -c on a pure function extracted via git show, yaml.safe_load on a workflow via git show ... | python -c). Do not run the full test suites.`,
  'rules-and-brief': (pr) => `LENS: RULES AND BRIEF COMPLIANCE. Check every one of CLAUDE.md's 12 rules against the diff (one summary orchestrator; filing-only summaries; migrations no-Alembic/idempotent/lock-guarded; entitlements single source; SEC transport owners and limiter; contract tests locked — list any edits to test_summary_stream_contract / background-generation characterization / auth flow / Stripe webhook tests; datetime via app/utils/datetimes utcnow()/iso_z() and no datetime.utcnow()/naive now; config via Settings not os.getenv; validate at boundaries; Filing URL invariants; design-system; rules-become-gates). Then check the brief or PR body: every scope item done or explicitly reported undone? Anything done that was marked out of scope, or files that collide with another open PR on the same lines (gh api repos/neilmac91/EarningsNerd/pulls?state=open, then diff --stat the overlapping branches)? Docs changed where code changed ("docs vs code")?`,
  'tests-and-gates': (pr) => `LENS: TESTS AND GATES. For every new or changed test: does it live in a sanctioned root (backend/tests/{unit,integration,smoke,performance}, frontend/tests/{unit,e2e})? Would it FAIL on the defect it claims to guard (construct the counter-example mentally or with a quick python -c against the extracted function)? Is any allow-list/gate weaker than it looks (regex false negatives, exemptions that swallow the bad case, date-based tests that flip on a calendar day — compute the flip date)? Are removed tests' behaviours still covered elsewhere? For workflow changes: is there a test pinning the new knob (rule 12), and does the test read the right file/step name? Note any test that depends on network, wall-clock, or ordering.`,
}
LENS_BODY.combined = (pr) => `LENS: COMBINED (one pass, three concerns, in this order of weight).
1. ${LENS_BODY.correctness(pr)}
2. ${LENS_BODY['rules-and-brief'](pr)}
3. ${LENS_BODY['tests-and-gates'](pr)}
Spend most of the pass on correctness. Report at most the findings you can evidence; do not pad.`

const lensPrompt = (pr, key) => `${COMMON(pr)}

${LENS_BODY[key](pr)}`

const refuterPrompt = (pr, f, i) => { const BASE = `origin/${pr.base || 'main'}`; return `${COMMON(pr)}

You are an independent skeptic #${i + 1}. A reviewer claims this finding about PR #${pr.number}:
  file: ${f.file}${f.line ? ':' + f.line : ''}
  title: ${f.title}
  severity claimed: ${f.severity}
  detail: ${f.detail}
  evidence: ${f.evidence}
Try to REFUTE it by reading the actual code on the branch (git show origin/${pr.branch}:<path>, git grep on the branch, two-dot diff vs ${BASE}). A finding is refuted if the code does not behave as claimed, the "defect" is out of the PR's scope by the brief or PR body, it is already handled elsewhere on the branch, or the evidence is misquoted. If it stands but the severity is wrong, keep refuted=false and set corrected_severity. Default to refuted=true if you cannot confirm it from the code. Give a one-paragraph reason with file:line.` }

const results = await pipeline(
  PRS,
  async (pr) => {
    const tier = tierOf(pr)
    const T = TIERS[tier]
    log(`PR #${pr.number}: ${tier} tier — ${T.lenses.length} ${T.lensModel} lens(es)`)
    const per = await parallel(T.lenses.map((key) => () =>
      agent(lensPrompt(pr, key), { label: `review:${pr.number}:${key}`, phase: 'Review', schema: FINDINGS_SCHEMA, model: T.lensModel, ...(T.lensEffort ? { effort: T.lensEffort } : {}) })
        .then((r) => (r ? r.findings.map((f) => ({ ...f, lens: key })) : null))
    ))
    // A lens that returned nothing (skipped or died) is missing review output, never clearance.
    const missing = T.lenses.filter((_, i) => per[i] === null)
    return { pr, tier, findings: per.filter(Boolean).flat(), missingLenses: missing }
  },
  async ({ pr, tier, findings, missingLenses }) => {
    const T = TIERS[tier]
    const nits = findings.filter((f) => f.severity === 'nit')
    const toVerify = findings.filter((f) => T.verify.includes(f.severity))
    const unverified = findings.filter((f) => f.severity !== 'nit' && !T.verify.includes(f.severity))
    log(`PR #${pr.number} (${tier}): ${toVerify.length} to verify, ${unverified.length} reported unverified, ${nits.length} nits; ${T.refuters} ${T.refuterModel || ''} refuter(s) each${missingLenses.length ? `; MISSING lenses: ${missingLenses.join(', ')}` : ''}`)
    const verified = await parallel(toVerify.map((f) => () =>
      parallel(Array.from({ length: T.refuters }, (_, i) => () =>
        agent(refuterPrompt(pr, f, i), { label: `verify:${pr.number}:${f.file.split('/').pop()}#${i + 1}`, phase: 'Verify', schema: VERDICT_SCHEMA, model: T.refuterModel, ...(T.refuterEffort ? { effort: T.refuterEffort } : {}) })
      )).then((votes) => {
        const v = votes.filter(Boolean)
        // Fewer votes than refuters = a refuter returned nothing: the finding stays unverified, not refuted.
        const complete = v.length === T.refuters
        const stands = complete && v.every((x) => !x.refuted)
        const sev = v.map((x) => x.corrected_severity).filter(Boolean)[0] || f.severity
        return { ...f, complete, stands, severity: stands ? sev : f.severity, votes: v.map((x) => ({ refuted: x.refuted, reason: x.reason })) }
      })
    ))
    const confirmed = verified.filter(Boolean).filter((x) => x.complete && x.stands)
    const refuted = verified.filter(Boolean).filter((x) => x.complete && !x.stands)
    const unverifiedAll = unverified.concat(verified.filter(Boolean).filter((x) => !x.complete))
    const incomplete = missingLenses.length > 0
    return {
      pr: pr.number,
      branch: pr.branch,
      tier,
      incomplete,
      mergeable: !incomplete && confirmed.filter((c) => c.severity === 'blocker').length === 0 && unverifiedAll.filter((c) => c.severity === 'blocker').length === 0,
      confirmed,
      refuted: refuted.map((r) => ({ title: r.title, file: r.file, reasons: r.votes.map((v) => v.reason) })),
      unverified: unverifiedAll,
      nits,
      agents: T.lenses.length + toVerify.length * T.refuters,
    }
  },
)

return results.filter(Boolean)
