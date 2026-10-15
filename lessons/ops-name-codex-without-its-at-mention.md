# Name Codex in GitHub text without its at-mention; one outside a review request starts a Codex task

Date: 2026-10-15   Area: ops

**Context**: The Codex GitHub app (`chatgpt-codex-connector[bot]`) answers its at-mention, the at sign
followed by `codex` in any case. It answers in a comment, and most likely in a pull request's title or
body, not only when a comment starts with its review command. A mention inside prose starts a Codex cloud
task: Codex reads the pull request, works on it in its own sandbox and replies with a summary. That is
Codex work on the account whose code-review usage limit stopped reviews on 2026-10-12
(#1259, issuecomment-6119596080). Whether a task draws on the same limit is not established here.

- 2026-10-15 08:52:18 UTC: a status comment on #1336 named the review command mid-sentence, in
  backticks (issuecomment-6188268721). At 08:53:03 Codex replied with a task report saying it had made
  no change (issuecomment-6188281463).
- #1337 opened at 09:06:58 UTC. Its title carried the command in backticks; the pull request's
  `renamed` event of 09:59:05 keeps the old title. By its author's account, its body named the command
  several times. At 09:21:54 Codex replied with a task summary (issuecomment-6188792348): it had changed
  the step's run lookup to paginate, with tests and docs, committed twice in its sandbox and "prepared a
  draft follow-up PR". None of that reached `origin`.

GitHub logged no `mentioned` event for either mention, so backticks do not keep Codex out. Repository
files, such as the review gate's workflow comment and `docs/OPERATIONS.md`, name the command as
documentation.

**Rule**: In a pull request's title, body or comments, and in an issue, write "Codex's review command" or
"a review request". Never write the at-mention, inside backticks or not, except in a new conversation
comment that is the review command alone, with at most the attribution footer: a form the condition of
`review-gate.yml`'s `rerun-on-review-request` job matches. Quoting a sentence that contains the mention
counts as a mention, so paraphrase it. When a pull request's title or body already carries the mention,
edit it out as a precaution. Nothing showed that an edit starts another task: #1337 kept the mention in
its title through a push and its ready transition, and no second task came. Leave a comment that carries
it, as evidence, and do not repeat it.

**Gate**: `.claude/hooks/codex_mention_guard.py`, which `.claude/settings.json` runs before every Bash
command and every call to an MCP server whose name contains "github" in any case
(`backend/tests/unit/test_codex_mention_guard.py`). It refuses a GitHub MCP write whose `title` or `body`
carries the mention. It also refuses a Bash command line whose text, as written or with its quotes
removed, names `gh pr` or `gh issue` (create or new, comment, edit, review, close, reopen), `gh api` or
api.github.com, when the mention is in that text or in a file one of the line's GitHub writes sends as a
body: gh's `--body-file`, `-F` or `--input`, an `@file` value, wget's `--post-file` or `--body-file`,
curl's `-T` or `--upload-file`, or a file redirected with `<` or piped from a plain `cat` into a command
that reads its body from standard input (one given `-`, `/dev/stdin` or `/dev/fd/0`, or httpie, which
reads it unasked). A GitHub write is a command (newlines and `;`, `&`, `&&`, `||`, `|` and `|&` separate
them; a comment or a here-document's text is none) in which a word `gh`, or a path ending in `/gh`,
starts a `gh pr`/`gh issue` write or `gh api` wherever it stands (`sudo gh api`), or that names
api.github.com. Reads count too, so a read or an edit that searches such text with a regular expression
(grep, sed, jq `test()`) writes the pattern as `[@]codex`. Its one exception is a new conversation
comment that is the review command alone, with at most the attribution footer: the body of the GitHub MCP
`add_issue_comment` tool, or a whole command `gh pr comment` (or `gh issue comment`) with at most one
pull-request argument, `-R`/`--repo` if needed, and that one `--body`. A hook that crashes or cannot
start lets the call through, so the gate fails open. It is a guardrail, not a boundary. It cannot see
text a command builds as it runs (a variable, a command or process substitution, a body piped from
anything but a plain `cat`, a file named relative to a directory the command enters first), a program
other than httpie that reads its body from standard input unasked, the body files of a command another
shell runs (`bash -c`, a here-document fed to a shell), a body file over 1 MiB, not a regular file, or
under /proc, /sys or /dev, the commit messages `gh pr create --fill` copies, a GitHub MCP server
registered under a name without "github", a session that loads no repository hooks (a cloud session with
several repositories, a local folder not yet trusted, `disableAllHooks`), or a person's own write. So
this lesson stays in session reading. A check in a workflow would come too late: Codex sees GitHub's
event when it is sent, before any workflow reads the text.

**Evidence**: #1336 comments 6188268721 (the mention) and 6188281463 (Codex's task reply); #1337's
`renamed` event (2026-10-15 09:59:05 UTC) and comment 6188792348; #1337's corrected title and body.
