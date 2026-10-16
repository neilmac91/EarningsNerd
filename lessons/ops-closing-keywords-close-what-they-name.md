# Never put a closing keyword before a reference you do not mean to close; the merge closes it, a pull request included

Date: 2026-10-09 (gate added 2026-10-15; merge-time hook 2026-10-16)   Area: ops

**Context**: GitHub reads a closing keyword (close, closes, closed, fix, fixes, fixed, resolve, resolves,
resolved, in any case, with or without a colon) followed by a reference (`#N`, `OWNER/REPO#N`) in a pull
request's description or in a commit message, and when that pull request merges into the default branch
it closes what the reference names. "Merging the referencing pull request also closes the referenced pull
request" ([GitHub docs](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)).
No workflow runs and no person acts: the close is logged to the merger one second after the merge, with no
commit, and GitHub's linked-issue data does not record it for a pull request.

- 2026-10-09 17:19:33 UTC: lane D's plan PR #1136 squash-merged. Its body reported W0.G's review with the
  past tense of fix, a colon and #1156's number. At 17:19:34 #1156, the open W0.G gate PR, was closed,
  unmerged. It was reopened at 17:29:44 and merged at 22:05:00 as `07bfaa63`; the squash message
  `a782d4e9` held no "1156", so the body was the route. Only the first reference after the keyword acted:
  the #1157–#1162 range in the same sentence stayed open.
- It had happened before, each time from a pull request body. #653's merge (2026-09-04) closed Dependabot
  PR #629 from a triage to-do line copied out of `tasks/implementation-briefs-2026-09.md` ("close" and
  #629). #694's merge (2026-09-05 10:00:16) took #686 one second later, from a capitalised close, #686's
  number and "only when this and #695 supersede it": GitHub ignored the condition, and #695 merged eleven
  minutes later. #949's merge (2026-09-23) probably took #935 the same way; its body was edited after.
  The deliberate uses were three, all in June 2026 (issues #240 and #244, and #482 closing #463 and #464).
- A scan of 800 pull requests (#516–#1342) found the keyword-reference form in 11 titles or bodies,
  mostly harmless prose whose target had already merged ("the closed" before a number, "fix" before a
  merged PR's number, a title "close" before #1177's number). It is a writing habit, not a rare slip.

**Rule**: In a pull request's title, body and commit messages, and in a squash message you type at merge,
never put a form of close, fix or resolve right before an issue or pull request reference: not with a
colon, Markdown marks or a line break between, not with no space, not before `OWNER/REPO#N`, `GH-N` or an
issue or pull URL. Report work with the reference first or another verb: "#1156 carries the fix",
"addressed in #1156", "the review of #1156". A conditional ("only when ...") is ignored. Quoting an
incident or copying a plan line counts, so paraphrase. To close something deliberately, close it by hand
after the merge. After editing a title or body, merge only once the new `review-gate` run has passed. The
previous green result stands until the new run's check appears, which takes seconds, or for good when no
run starts (an Actions outage).

**Gate**: `backend/scripts/review_gate.py` (`review-gate`, a required check on `main`) fails while the
pull request's title, body or any commit message carries such a reference, draft or not and override or
not, and lists each one (`backend/tests/unit/test_review_gate.py`). It matches more than GitHub documents,
so an undocumented form fails closed, and it fails a pull request listing 250 commits, the most GitHub
lists. It reads text as GitHub renders it, so an escaped number sign or an HTML entity counts. A squash
message typed at merge, which no pull-request check can see, is read by
`.claude/hooks/closing_keyword_guard.py` in an agent's session: `.claude/settings.json` runs it before every
Bash command, every Monitor and every GitHub MCP call, and it refuses a merge call (any string handed to a
GitHub MCP merge tool, or to a call handed a merge request as a whole string: a GraphQL document or JSON
request calling a merge mutation, or a REST merge path, URL or route; or a shell line that runs or names `gh
pr merge`, or a REST merge endpoint or GraphQL merge mutation with `gh api` or api.github.com, with every
file the line names to send or read) whose text carries such a reference, with the gate's own pattern
(`backend/tests/unit/test_closing_keyword_guard.py`). It also reads each typed title and message joined as
GitHub writes the commit, the title, a blank line, then the message, so a title that ends in a keyword
before a message that starts with a reference counts. A line that only names a merge, such as a comment
quoting one, is refused too; such text goes in a body file. Not gated: a merge whose message the shell or a
command builds as the line runs (a variable, a `$'...'` escape, a brace expansion, or the output of any
command but a plain `cat`) or that reads a file over 1 MiB, a glob's files past its first 16, or a file
named relative to a directory the line changes into first, a merge with more than three `-R`/`--repo`
options in a row, a title or message past the last 16 of each a merge call types (gh writes the last) or a
here-document past a line's first 16, a title's keyword and its message's reference more than 1,024
characters from where the two meet, a typed title or message whose other half is GitHub's default (a merge
commit's default title names its branch), a merge a script or a gh alias runs or whose URL sits in a file a
command reads as its configuration (curl's `-K`, wget's `-i`), a merge through an MCP request tool that
spreads its target over fields of its own or through a GitHub MCP server registered under a name without
"github", a merge made in a session that loads no repository hooks or by a person, and a merge made after an
edit but before its new gate run's check appears.

**Evidence**: #1136 (its body's closing note) and #1156 (closed 17:19:34 UTC with no commit, reopened at
17:29:44, comment 6085958257); #653 with #629 and #694 with #686 (each close one second after the merge,
by the merger, with no commit); the gate's pull request, whose body carries the 800-PR scan and the
mutation proofs.
