# Search the open pull requests for the row's ID again right before the first push

Date: 2026-10-31   Area: ops

**Context**: Several sessions take rows from `tasks/todo.md` at once. At about 23:35 UTC on 2026-10-30 one
session picked E248 after reading the open pull requests, and none named it. At 00:04 another session, which the
founder had asked to fix E248, opened #1845 for it. The first session pushed its own fix and opened #1847 at 00:15,
and only its routine lens, reading the open pull requests, found #1845: the two changed the same hunks of the same
five files. #1847 closed as a duplicate, after about an hour and a half of builds, browser probes and mutation
proofs spent on a row another session was already fixing.

**Rule**: Right before the first push of a branch for a row, search the open pull requests again, for the row's ID
(`is:pr is:open E248`) and for the files the change touches, as you did when picking the row: a check at the pick
alone misses a pull request opened while you work. When a fresh pull request names the row, the row is taken: stop
and compare the two, keep the one the founder asked for, or else the more complete one, and close the other with a
comment that hands over what it adds.

**Evidence**: #1845, opened 2026-10-31 at 00:04 UTC on the founder's "Fix E247 and E248 in new PRs", and #1847,
opened at 00:15 and closed at 00:21 as its duplicate, both for E248; #1847's routine lens named the overlap, and its
closing comment handed #1845 three measurements.
