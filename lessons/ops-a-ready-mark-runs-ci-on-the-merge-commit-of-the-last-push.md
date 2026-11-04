# A ready mark runs CI on the merge commit GitHub stored at the head's last push; to bring a change on main to an unchanged head, push a merge of main

Date: 2026-11-04 · Area: ops / CI

**Context.** At 08:56 UTC on 2026-11-04 #1990 put CI's browser suite in five shards on main (`78e129541`). A single
`e2e-tests` job could no longer finish within F59's 35-minute limit on the private repository's 2-vCPU runners. Two
drafts whose heads predated it were then marked ready, on the plan that "the ready mark's run builds on the merge with
main, so it picks up the shards with no push" (#1997, 07:40 UTC):
- #1998's ready mark started run 41805116530 at 09:09 UTC, and #1997's started run 41805744474 at 09:13 UTC. Each ran
  the old single `e2e-tests` job and no `e2e-shard`. Each built on the merge commit GitHub had stored at the branch's
  last push, on main `0245d3fe9`: `401893989` (01:08 UTC) and `83e467452` (01:55 UTC).
- At 09:34 UTC the API still gave those merge commits as `merge_commit_sha`, with `mergeable: true`, for both. It also
  gave #1994's, built at 23:25 UTC the day before on main `4099416f6`. The mergeability checks had read the new main
  without rebuilding the stored merge commits.
- #1995, pushed at 09:14 UTC, and #2003, opened at 09:23 UTC, built on `78e129541` and ran the shards.

Both runs were cancelled, since the limit cuts the single job, and each branch took a merge of main.

**Rule.**
1. Before a ready mark or a re-run whose CI should carry something main gained after the head's last push (a
   workflow, a fixed test, a gate), read the pull request's merge commit: `git fetch origin refs/pull/N/merge` and its
   first parent, or the API's `merge_commit_sha`. Its first parent must be main's tip.
2. If it is not, push a merge of main, gated as any push. A ready mark, a re-run, a read of the pull request and a
   mergeability check each left the stored merge commit as it was. Never an empty commit, a close and reopen, or a
   base change instead.
3. Cancel a run already started on a stale merge commit when it cannot pass, so it holds no runner.

**Evidence.**
- Runs 41805116530 (#1998) and 41805744474 (#1997): their jobs list `e2e-tests` and no `e2e-shard`.
- `refs/pull/1998/merge` = `401893989`, parents `0245d3fe9` and `f70c760cc`; `refs/pull/1997/merge` = `83e467452`,
  parents `0245d3fe9` and `23be4e272`; `refs/pull/1994/merge` = `5202420f7`, parents `4099416f6` and `51eec27aa`.
- `refs/pull/1995/merge` = `47190bb55`, parents `78e129541` and `5c5eaded1`.
- #2000 read `mergeable: false` at 09:33 UTC: a conflict in `tasks/todo.md` that only main `78e129541` has. Its stored
  merge commit, `299c2d833`, still sat on `0245d3fe9`, so the check reads main and the stored commit does not move.
- `lessons/ops-unmergeable-pr-runs-no-pull-request-workflows.md`: a `pull_request` run builds on that test merge commit,
  and none starts while it cannot be built.
