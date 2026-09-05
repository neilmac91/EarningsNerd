export const meta = {
  name: 'premerge-review',
  description: 'Adversarial pre-merge review of PRs: 3 lenses per PR, each finding independently refuted twice',
  phases: [
    { title: 'Review', detail: 'correctness / rules+brief compliance / tests+gates per PR' },
    { title: 'Verify', detail: 'two independent refuters per blocker or should-fix finding' },
  ],
}

const PRS = args.prs

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
The PR branch may have been cut from an OLDER main and carry a cherry-picked "ruff pin" commit whose files are now identical on main. So use the MERGE-BASE (three-dot) diff, and IGNORE any hunks in backend/ruff.toml, backend/requirements-dev.txt, or the ci.yml "Install dependencies" step that merely match what main already has:
  git diff ${BASE}...origin/${pr.branch} --stat
  git diff ${BASE}...origin/${pr.branch} -- <path>
Do NOT report "this PR deletes files X" when X simply post-dates the branch point on main (check with: git log --oneline ${BASE}..origin/${pr.branch} and git merge-base ${BASE} origin/${pr.branch}); a normal merge keeps them.
Read files on the branch with: git show origin/${pr.branch}:<path>
Read the brief this PR implements: git show ${BASE}:tasks/implementation-briefs-2026-09.md  (section ${pr.brief})
Read the repo rules: CLAUDE.md on ${BASE} (git show ${BASE}:CLAUDE.md) — the 12 non-negotiable rules, "Where things live", and "Tests" roots. Lessons index: git show ${BASE}:lessons/README.md (open any lesson relevant to your lens with git show ${BASE}:lessons/<file>).
Report ONLY findings you can anchor to a file (and line where possible) in the diff or in code the diff affects, with concrete evidence (quote the line). No style opinions. No findings about things the brief explicitly put out of scope. If you find nothing at a severity, say so in summary. Severity: blocker = would break prod/CI/a CLAUDE.md rule or silently lose behaviour; should-fix = real defect or gate weakness worth a follow-up commit before merge; nit = cosmetic.`
}

const LENSES = [
  {
    key: 'correctness',
    prompt: (pr) => `${COMMON(pr)}

LENS: CORRECTNESS. Hunt for bugs and regressions introduced by this diff: wrong logic, unhandled paths, behaviour silently lost by deletions (grep the whole tree on the branch for every symbol/route/setting the diff removes or renames — e.g. git grep -n <symbol> origin/${pr.branch} -- . ), shell/YAML mistakes in workflows (quote every changed shell line and reason about set -e, exit codes, quoting, GitHub Actions expression syntax), Python typing/async misuse, test fixtures that would not fail on the bad case. Try to actually execute anything cheap and safe that proves or disproves a suspicion (e.g. python -c on a pure function extracted via git show, yaml.safe_load on a workflow via git show ... | python -c). Do not run the full test suites.`,
  },
  {
    key: 'rules-and-brief',
    prompt: (pr) => `${COMMON(pr)}

LENS: RULES AND BRIEF COMPLIANCE. Check every one of CLAUDE.md's 12 rules against the diff (one summary orchestrator; filing-only summaries; migrations no-Alembic/idempotent; entitlements single source; all sec.gov via services/edgar; contract tests locked — list any edits to test_summary_stream_contract / background-generation characterization / auth flow / Stripe webhook tests; datetime via app/utils/datetimes utcnow()/iso_z() and no datetime.utcnow()/naive now; config via Settings not os.getenv; validate at boundaries; Filing URL invariants; design-system; rules-become-gates). Then check the brief section: every Scope item done or explicitly reported undone? Anything done that the brief marked Out or that belongs to a sibling workstream (scope creep, file collisions with other wave-1 branches: ws1-gate-hardening, ws2-migration-ledger, ws4-universe-refresh, ws8a-dead-integration-teardown, ws8b-rule-gates, ws5a-observability-public-pages, ws5b-reading-surface — fetch and diff --stat those that exist to spot overlapping files)? Docs changed where code changed ("docs vs code")?`,
  },
  {
    key: 'tests-and-gates',
    prompt: (pr) => `${COMMON(pr)}

LENS: TESTS AND GATES. For every new or changed test: does it live in a sanctioned root (backend/tests/{unit,integration,smoke,performance}, frontend/tests/{unit,e2e})? Would it FAIL on the defect it claims to guard (construct the counter-example mentally or with a quick python -c against the extracted function)? Is any allow-list/gate weaker than it looks (regex false negatives, exemptions that swallow the bad case, date-based tests that flip on a calendar day — compute the flip date)? Are removed tests' behaviours still covered elsewhere? For workflow changes: is there a test pinning the new knob (rule 12), and does the test read the right file/step name? Note any test that depends on network, wall-clock, or ordering.`,
  },
]

const results = await pipeline(
  PRS,
  (pr) => parallel(LENSES.map((l) => () =>
    agent(l.prompt(pr), { label: `review:${pr.number}:${l.key}`, phase: 'Review', schema: FINDINGS_SCHEMA })
      .then((r) => (r ? r.findings.map((f) => ({ ...f, lens: l.key })) : []))
  )).then((per) => ({ pr, findings: per.filter(Boolean).flat() })),
  async ({ pr, findings }) => {
    const nits = findings.filter((f) => f.severity === 'nit')
    const serious = findings.filter((f) => f.severity !== 'nit')
    log(`PR #${pr.number}: ${serious.length} serious, ${nits.length} nits from review; verifying serious`)
    const BASE = `origin/${pr.base || 'main'}`
    const verified = await parallel(serious.map((f) => () =>
      parallel([0, 1].map((i) => () =>
        agent(`${COMMON(pr)}

You are an independent skeptic #${i + 1}. A reviewer claims this finding about PR #${pr.number}:
  file: ${f.file}${f.line ? ':' + f.line : ''}
  title: ${f.title}
  severity claimed: ${f.severity}
  detail: ${f.detail}
  evidence: ${f.evidence}
Try to REFUTE it by reading the actual code on the branch (git show origin/${pr.branch}:<path>, git grep on the branch, two-dot diff vs ${BASE}). A finding is refuted if the code does not behave as claimed, the "defect" is out of the PR's scope by the brief, it is already handled elsewhere on the branch, or the evidence is misquoted. If it stands but the severity is wrong, keep refuted=false and set corrected_severity. Default to refuted=true if you cannot confirm it from the code. Give a one-paragraph reason with file:line.`,
          { label: `verify:${pr.number}:${f.file.split('/').pop()}#${i + 1}`, phase: 'Verify', schema: VERDICT_SCHEMA })
      )).then((votes) => {
        const v = votes.filter(Boolean)
        const stands = v.length > 0 && v.every((x) => !x.refuted)
        const sev = v.map((x) => x.corrected_severity).filter(Boolean)[0] || f.severity
        return { ...f, stands, severity: stands ? sev : f.severity, votes: v.map((x) => ({ refuted: x.refuted, reason: x.reason })) }
      })
    ))
    const confirmed = verified.filter(Boolean).filter((x) => x.stands)
    const refuted = verified.filter(Boolean).filter((x) => !x.stands)
    return {
      pr: pr.number,
      branch: pr.branch,
      mergeable: confirmed.filter((c) => c.severity === 'blocker').length === 0,
      confirmed,
      refuted: refuted.map((r) => ({ title: r.title, file: r.file, reasons: r.votes.map((v) => v.reason) })),
      nits,
    }
  },
)

return results.filter(Boolean)