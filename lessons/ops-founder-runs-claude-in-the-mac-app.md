# Address founder instructions to the Claude desktop app, and give `claude -p` its own login

Date: 2026-09-15   Area: ops

**Context**: W3-7 needed the strong judge to run on the founder's Claude subscription rather than
API credits. The first instructions were written for Terminal.app; the founder runs Claude Code
inside the Mac desktop app. Probes from a hosted session showed the app's sign-in is not lent to
subprocesses: the app-bundled binary answered "Not logged in" and the standalone `~/.local/bin/claude`
"Invalid API key" even with a clean environment, until the founder ran `/login` once in an
interactive `claude` started from the app's own Terminal pane. `--bare` cannot help: it reads
neither OAuth nor the keychain, only `ANTHROPIC_API_KEY`.

**Rule**: Write founder procedures for the app (its Terminal pane, chats and slash commands), not
for Terminal.app. Before any design relies on `claude -p` from a hosted session or a script,
require the one-time standalone login and prove it with
`claude -p --model <alias> --output-format json --tools "" "Reply with exactly: OK"` returning
`"is_error":false`; never use `--bare` for subscription auth, and strip `ANTHROPIC_API_KEY` from
the child environment so the call cannot bill credits.

**Evidence**: this session's probes on 2026-09-15 (bundled 2.1.270 "Not logged in"; standalone
2.1.12 "Invalid API key"; after `/login`, standalone 2.1.272 returned `is_error:false` with
`costBasis: list`); `backend/evals/judge.py::_judge_via_cli`; `.claude/skills/meta/judge-readout/`.
