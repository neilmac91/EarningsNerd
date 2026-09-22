# Prove the permission route with a zero-effect command before any gated step

**Date:** 2026-09-22 · **Area:** ops / evals / judging sessions

## Context

The second 22 September E8 judging session started on a branch equal to `main`, which carried the
re-pin package and the seven `Bash(...)` allow rules written for exactly its commands. The
auto-mode classifier still denied `restore_e8_session.py` in the exact allow-listed form
(`[Auto-Mode Bypass]`), and afterwards denied the same script's `--help`, which exits before it
can touch anything. The official docs say narrow allow rules are evaluated before the classifier
and that a repository's `.claude/settings.json` is read in web sessions; the session behaved as if
the rules did not exist. The same docs also hold a repository's `permissions.allow` rules until
workspace trust is recorded for the folder, which `-p` and SDK sessions never prompt for, and a
web session runs inside the SDK, so "read" did not mean "applied". The kit had no step that
would have discovered any of this before step 1, and
the first attempt had already been wrapped in a log redirect and a trailing `echo`, which takes a
compound command outside a `Bash(prefix:*)` rule regardless. The kit and the rule also disagreed
on the command text itself: the kit wrote step 1 with an absolute `"$REPIN/…"` path while the
rule named the relative `tasks/…` path, so the kit's literal command could never have matched the
rule. Nothing was touched, by luck of ordering rather than by design. Evidence:
`tasks/review-evidence/e8-repin-restore-2026-09-22/receipt.md`.

## Rule

A launch kit for a permission-gated procedure begins with a step 0 that proves the route: run the
first allow-listed script with `--help` (or another argparse-level no-op) in the exact rule form,
from the rule's working directory, with no redirect, pipe or `;`, as the session's first gated
command so that no earlier denial colours the verdict. A silent allow, a prompt to the operator
and a classifier denial are three different results, and the kit says which one it expects. The
kit's command text and the rule's prefix must be the same string for every gated command, not
only the first; a rule cannot match a shell variable such as `"$REPIN"`, and variables do not
persist between tool calls. Write the kit from the rule, not the other way round. A denial there
is a stop before
any state exists, and the report is "the permission route is not in effect", not "the restore
failed". The kit names the session's permission mode explicitly; do not assume project allow rules
bypass the auto-mode classifier. When an allow-listed command must be logged, let the script write
its own receipt or capture the tool result, never wrap the command in shell redirects. Record every
denial verbatim (command, cwd, reason, approximate UTC) in the committed receipt, and never re-shape
a denied command to try again through the shell.

Enforcement lives in the kit, not in CI, as a stated exception to CLAUDE.md rule 12: no repository
gate can exercise the cloud permission classifier, and the launch kit is an uploaded attachment,
not a repository file. The next E8 launch kit carries step 0 before step 1 and writes every gated
command as the literal rule string; `tasks/fable-e8-repin-2026-09-22/README.md` should gain the
same step and rewrite its `"$REPIN"` / `"$PYTHON_BIN"` command block in rule form when it is next
revised (it is hash-sealed by `code-sha256.json`, so that revision is a rebuild, not an edit).
Until then the deferral is the open item in the 22 September E8 entry of `tasks/todo.md`.

## Evidence

- `tasks/review-evidence/e8-repin-restore-2026-09-22/receipt.md` (sections 3, 6 and 10)
- `tasks/review-evidence/e8-restore-2026-09-22/receipt.md` section 9 (the earlier session's
  `[Code from External]` / `[Auto-Mode Bypass]` pair on a branch without allow rules)
- `https://code.claude.com/docs/en/auto-mode-config.md`, `https://code.claude.com/docs/en/permissions.md`
