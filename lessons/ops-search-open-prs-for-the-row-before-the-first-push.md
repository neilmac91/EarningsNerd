# Search the open pull requests for the row's ID again right before the first push

Date: 2026-10-31   Area: ops

**Context**: Several sessions take rows from `tasks/todo.md` at once. At about 23:35 UTC on 2026-10-30 one
session picked E248 after reading the open pull requests, and none named it. At 00:04 another session, which the
founder had asked to fix E248, opened #1845 for it. The first session pushed its own fix at 00:15 and opened #1847 at
00:16, and only its own review, which read the open pull requests, found #1845: the two changed the same hunks of the
same five files. #1847 closed as a duplicate at 00:21, after about three quarters of an hour of builds, browser
probes and mutation proofs spent on a row another session was already fixing; its cases then went into #1845.

The search before the first push then caught the next one, but only after the work was done. At 20:52 UTC on
2026-10-31 a session picked E258, and no open pull request named it. It built the change locally for an hour (the
engine's seam, its specs, production builds, browser checks and mutation proofs) and searched again at 21:50, before
its first push: #1880, opened at 21:44:55 by another session, named E258 and touched the same files. No duplicate
pull request opened, but two sessions had each spent the hour on one row, and neither could see the other's branch,
since neither had pushed.

**Rule**: Right before the first push of a branch for a row, search the open pull requests again, for the row's ID
(`is:pr is:open E248`) and for the files the change touches, as you did when picking the row: a check at the pick
alone misses a pull request opened while you work. When a fresh pull request names the row, the row is taken: stop
and compare the two, keep the one the founder asked for, or else the more complete one, and close the other with a
comment that hands over what it adds.

Claim the row early, too. A branch nobody has pushed is invisible to another session's search, so once a row will
take more than a few minutes, push its branch and open its draft (AGENTS.md: every pull request opens as a draft)
as soon as its first commit exists, and only then build and verify. A first commit that only marks the row in flight
in `tasks/todo.md` is records-only, so the CI run on that commit skips the browser checks; the code pushed after it
runs them. Close a draft you abandon, so the row is free again.

**Evidence**: #1845, opened 2026-10-31 at 00:04 UTC on the founder's "Fix E247 and E248 in new PRs", and #1847,
opened at 00:16 and closed at 00:21 as its duplicate, both for E248. #1847's closing comment hands #1845 three
measurements; chief design's comment on #1847 at 00:23 asks that its unique cases go to #1845, and #1845's comment at
02:34 says they did. For E258: #1880, opened at 21:44:55 UTC, and the handover comment on it (6549623891) from the
session that had picked E258 at 20:52, from a branch it never pushed: a check of #1880's plans against main's and an
assertion #1880's own proofs had found missing. That session's next pull request, #1882, opened as a draft 29
seconds after its first commit (21:56:39 and 21:57:08 UTC), before any build or check ran; that commit was its whole
change, records and a code comment, not a records-only claim.
