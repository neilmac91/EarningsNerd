# Confirm the branch is checked out before you commit after agents ran in the checkout

Date: 2026-11-13   Area: ops

**Context**: A review workflow's agents were told to work read-only on a commit range. One ran
`git checkout <sha>` to read the head it was given, which left the shared checkout on a detached
HEAD. The main session then made three commits there and ran the full gates on them. The push sent
only the commits the branch already held and reported success, so the newest work was on no
branch until `git status -sb` showed `HEAD (no branch)`.

**Rule**: After any agent stage that shared the checkout, and before each commit and each push,
read `git status -sb`: its first line must name the branch, and after the push it must show
nothing ahead. Brief read-only agents to read a commit with `git diff <a> <b>` and
`git show <sha>:<path>`, and say that `git checkout`, `git switch` and `git stash` are state
changes. If HEAD is detached, move the branch to it with `git branch -f <branch> <sha>` and check
the branch out, in a call of its own before the push (the secret-scan hook refuses a push that
shares a call with a command that moves a ref).

**Evidence**: `git reflog` of the session of 2026-11-13: `checkout: moving from
claude/tender-dijkstra-ocx36v to 97256f6`, then three commits on the detached HEAD; the first push
advanced the branch to `97256f6` only.

**Gate**: `frontend/tests/unit/premergeReviewWorkflow.spec.ts` fails if the review workflow's brief stops
telling any lens or refuter to leave the working tree, the branches and the worktrees alone. Reading
`git status -sb` before each commit and push stays review-checked.
