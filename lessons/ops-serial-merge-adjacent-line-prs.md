# Serialize merges of PRs that edit the same file within a few lines

Date: 2026-06-11   Area: ops

**Context**: While draining the dependabot queue, assumed PRs touching different lines of the same file could merge back-to-back. Wrong — git's 3-way merge conflicts when hunks fall within ~3 lines of each other (the context window), not only on identical lines.

**Rule**: Treat any two PRs editing the same file within a few lines of each other as conflicting; plan serial merge + rebase between them. Only file-level disjoint PRs are safely parallel.

**Evidence**: `backend/requirements.txt`: PR #224 (pydantic, line 4) conflicted after #222 (python-multipart, line 3) and #223 (email-validator, line 6) merged.
