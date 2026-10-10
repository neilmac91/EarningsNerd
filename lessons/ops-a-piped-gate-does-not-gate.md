# A verification command in a commit chain is never piped away; its exit status gates the commit

Date: 2026-10-10 · Area: ops / verification

**Context.** The CODE RED chief ran the runtime-records gate inside a commit-and-push chain as
`pytest … | tail -1 && git commit … && git push`. The gate failed (closure 172 resolved a label inside
the closure that registered it), but `tail` returned 0, so the chain committed and pushed head
`7d65c89` of PR neilmac91/EarningsNerd#1172 with the gate red. The "1 failed" line was printed and
read seconds later; the correction landed one minute after (chief defect 10,
`tasks/code-red-20261004/runtime/control/DECISIONS-21.md`). CI caught it too, but a push that
reaches CI red costs a cycle and the reviewers' trust.

**Rule.** When a verification step decides whether a commit or push happens, its exit status must be
the thing that decides: run it unpiped, or set `pipefail` for the chain, and grep the summary only
after the status has been checked. Prefer `set -euo pipefail` at the top of any chain that ends in a
commit or push, and never follow a test run with `| tail`, `| grep` or `| head` on the same line as
the `&&` that commits.

**Evidence.** `tasks/code-red-20261004/runtime/control/DECISIONS-21.md` (disclosure 7);
`tasks/code-red-20261004/runtime/control/APPOINTMENTS.json` (`chief_defects`, 2026-10-10T04:05Z);
PR neilmac91/EarningsNerd#1172 heads `7d65c89` (gate red) and `351319f` (gate green).
