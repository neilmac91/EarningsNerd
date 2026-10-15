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
"a review request". Never write the at-mention, inside backticks or not, except in a comment whose only
purpose is to request a review and which starts with that command, the form the condition of
`review-gate.yml`'s `rerun-on-review-request` job matches. Quoting a sentence that contains the mention
counts as a mention, so paraphrase it. When a pull request's title or body already carries the mention,
edit it out as a precaution. Nothing showed that an edit starts another task: #1337 kept the mention in
its title through a push and its ready transition, and no second task came. Leave a comment that carries
it, as evidence, and do not repeat it.

**Gate**: none yet. No gate can stop the first trigger, because Codex sees GitHub's event when it is sent,
before any workflow reads the text. The review gate fetches the pull request, its body included, on every
pull-request event, so a check there could only detect the mention after Codex had seen it. A preventive
gate would be a hook that refuses an agent's GitHub write carrying the mention (E63 in `tasks/todo.md`).

**Evidence**: #1336 comments 6188268721 (the mention) and 6188281463 (Codex's task reply); #1337's
`renamed` event (2026-10-15 09:59:05 UTC) and comment 6188792348; #1337's corrected title and body.
