# Run no review round the release owner has declined: raise a suspected material defect on the pull request and let them set the scope

Date: 2026-11-03 (PB-02, #1955)   Area: ops / review

**Context**: On #1955 the chief accepted the engineering at `7614d641` with "No further full review round is required"
and "No new feature or review work is requested". At `4a458bf5` the chief added: "No additional review round is
needed". After the next ready mark, at `037dc992`, the session ran another whole-PR review anyway: the high-tier
`premerge-review` plus a fourth lens for privacy, 20 agents in all. It found one real blocker (the digest the public
Ops log printed could name a tester), 7 should-fix reports and 17 nits. It fixed every one in nine commits, which
changed application code in three files and reset the acceptance. The chief extended acceptance to the result after
focused verification, and called the round "beyond the completion direction": "stop further whole-PR review, extra
lenses/refuters, gate expansion or polish … Reopen only for a demonstrated material launch failure."

**Rule**:
- When the release owner has said no further review round is needed, run none on your own initiative: no whole-PR
  round, no extra lens or refuter, and no gate expansion or polish.
- If you suspect a material defect, such as a privacy or data-loss risk the earlier review did not cover, post it on
  the pull request with its evidence and ask before you act. The owner decides whether it reopens the head and how far
  the fix goes.
- This cuts no review that is running: `ops-replace-a-redundant-review-stage-never-drop-it.md` still holds for a round
  the owner asked for or the tier requires.

Review-checked.

**Evidence**: #1955. The chief's acceptances: issuecomment-6590757481 (`7614d641`) and issuecomment-6591406634
(`4a458bf5`). The ready mark: issuecomment-6591893843 (`037dc992`). The round and its fixes: issuecomment-6594624141,
commits `dfa89edf` to `ff15b23e`. The chief's correction: issuecomment-6597856835.
