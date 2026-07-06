# Treat PRs editing the same file within ~3 lines as conflicting — merge them serially

**Area:** git · **Date:** 2026-06-11

While draining the dependabot queue: assumed PRs touching *different lines* of
`backend/requirements.txt` could merge back-to-back without conflicts. Wrong —
git's 3-way merge conflicts when hunks fall within ~3 lines of each other
(context window), not only on identical lines. PR #224 (pydantic, line 4)
conflicted after #222 (python-multipart, line 3) and #223 (email-validator,
line 6) merged.

**Rule:** treat any two PRs editing the same file within a few lines of each
other as conflicting; plan serial merge + rebase between them. Only file-level
disjoint PRs are safely parallel.
