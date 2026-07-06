# A mechanical proof must run against COMMITTED state — a proof that can't fail proves nothing

**Area:** refactor · **Date:** 2026-07-06

F3.1's first pure-move proof ran `git diff origin/main..HEAD` while the moves were still UNCOMMITTED in the working tree — so it compared two identical commits and 'passed' vacuously. The proof could not have failed, so it proved nothing. Fixed by committing first, then re-running (21 files, 25/25 symmetric import-only edits). The S1 surgery script used the same discipline: anchor assertions that abort if any target line drifted.

**Rule:** before trusting a mechanical proof (AST diff, git rename-detection, an allow-list grep), confirm it runs against committed state and CAN fail — deliberately break it once, or assert on anchors, so a green result is meaningful. A verification you can't make fail is theater.
