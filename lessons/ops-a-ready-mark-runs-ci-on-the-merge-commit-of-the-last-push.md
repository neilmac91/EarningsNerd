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

The same morning GitHub faltered before it posted an incident at 09:49 UTC ("Incident with Pull Requests, Git
Operations and Issues"; its 09:50 update added Actions):
- At about 09:41 UTC a push of `e9d2614e6` to #2000 answered 500; its retry moved the branch, but the pull request
  kept `dd7455cd1` as its head for 44 minutes. No CI run started, and the ready mark at 09:42 UTC started none
  either, since the stored head conflicted with main.
- A gated merge of main, pushed at 10:25 UTC after another 500 and a retry, registered at once, and CI ran.
- #2005's merge to main (`28c8eb1ec`, 10:15 UTC) got no `ci.yml` push run, and a merge call for #1998 answered 502
  and did not merge.

**Rule.**
1. Before a ready mark or a re-run whose CI should carry something main gained after the head's last push (a
   workflow, a fixed test, a gate), read the pull request's merge commit: `git fetch origin refs/pull/N/merge` and its
   first parent, or the API's `merge_commit_sha`. Its first parent must be main's tip.
2. If it is not, push a merge of main, gated as any push. A ready mark, a re-run, a read of the pull request and a
   mergeability check each left the stored merge commit as it was. Never an empty commit, a close and reopen, or a
   base change instead.
3. Cancel a run already started on a stale merge commit when it cannot pass, so it holds no runner.
4. After every push, check that the pull request took it: `git ls-remote origin refs/pull/N/head` must give the
   branch's new head before you mark it ready or wait on its CI. When a push answers 5xx, read GitHub's status page
   before retrying. A pull request still on its old head takes the next real push (a gated merge of main), never an
   empty commit or a close and reopen.
5. When GitHub reports an incident, or a push or merge answers 5xx, decide each merge on fresh repository evidence,
   not on the incident's status. Read again, before the merge: the pull request's exact head (`refs/pull/N/head`),
   its required checks on that head, main's push run for each merge since the last backend deploy, and that deploy's
   verification. Hold only while one of those is missing or inconsistent, a required check has not passed, or the
   preceding backend deploy is unverified; once all hold, proceed without waiting for the incident to close. A merge
   in such a window can still get no push run (#2005), and a backend merge then deploys nothing, so read the merge's
   own push run afterwards too.

**Evidence.**
- Runs 41805116530 (#1998) and 41805744474 (#1997): their jobs list `e2e-tests` and no `e2e-shard`.
- `refs/pull/1998/merge` = `401893989`, parents `0245d3fe9` and `f70c760cc`; `refs/pull/1997/merge` = `83e467452`,
  parents `0245d3fe9` and `23be4e272`; `refs/pull/1994/merge` = `5202420f7`, parents `4099416f6` and `51eec27aa`.
- `refs/pull/1995/merge` = `47190bb55`, parents `78e129541` and `5c5eaded1`.
- #2000 read `mergeable: false` at 09:33 UTC: a conflict in `tasks/todo.md` that only main `78e129541` has. Its stored
  merge commit, `299c2d833`, still sat on `0245d3fe9`, so the check reads main and the stored commit does not move.
- `lessons/ops-unmergeable-pr-runs-no-pull-request-workflows.md`: a `pull_request` run builds on that test merge commit,
  and none starts while it cannot be built.
- #2000: from 09:41 to 10:25 UTC `git ls-remote` gave the branch as `e9d2614e6` and `refs/pull/2000/head` as
  `dd7455cd1`, and the pull request's timeline showed no commit event for `e9d2614e6` until `b38ce7f1d` was pushed.
  After that push both read `b38ce7f1d`, and run 41814114906 started.
- githubstatus.com: "Incident with Pull Requests, Git Operations and Issues", opened 09:49:55 UTC on 2026-11-04.
