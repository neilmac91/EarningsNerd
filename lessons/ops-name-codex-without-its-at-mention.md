# Name Codex in GitHub text without its at-mention; an at-mention outside a review request starts a paid Codex task

Date: 2026-10-15   Area: ops

**Context**: Codex answers an at-mention of itself in a comment or a pull request's body, not only
a comment that starts with the review command. A mention inside prose starts a Codex cloud task:
Codex reads the pull request, may write code on a branch of its own, and replies with a summary.
Each task spends the same Codex credits the review gate depends on.

- On 2026-10-15 a status comment on #1336 named the review command mid-sentence. Codex ran a task
  and replied that it had made no change (issuecomment-6188281463).
- #1337 opened at 09:06:58 UTC with a body that named the command several times. At 09:21:54 Codex
  replied with a task summary (issuecomment-6188792348). It had rewritten the pull request's step,
  committed twice and "prepared a draft follow-up PR". None of that reached `origin`.

The rule is about text on GitHub. Repository files, such as the review gate's workflow comment and
`docs/OPERATIONS.md`, name the command as documentation.

**Rule**: In a pull request's title, body or comments, and in an issue, write "Codex's review
command" or "a review request". Never write the at-mention, inside backticks or not, except in a
comment whose only purpose is to request a review and which starts with that command. Quoting a
sentence that contains it counts as a mention: paraphrase instead. When a pull request already
carries the mention, remove it before its next edit.

No repository gate can check text on GitHub, so this rule is prose only. The review gate reads the
body but runs only after Codex has already seen the event.

**Evidence**: #1336 comments 6188268721 (the mention) and 6188281463 (Codex's task reply); #1337's
opening body and comment 6188792348; #1337's corrected title and body (edited 2026-10-15 ~10:00 UTC).
