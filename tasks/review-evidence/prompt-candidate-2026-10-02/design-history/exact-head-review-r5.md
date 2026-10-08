# Exact-head review, round 5 (head `998aff32`): findings as received

Two independent lenses (model behaviour, rules/gates/custody) reviewed head
`998aff329aa41ae95c8a6978a6f0dd84c9cf5ce3` (the round-4 fix commit on merge `3264cdcc`, base `b40fa703`). Verdicts:
model-behaviour APPROVE, rules-gates-custody APPROVE. Both returned nits only. The findings below are the reviewers'
text as handed to the implementer, kept verbatim (line-wrapped only), followed by what each lens ran. The README
section "Review round 5" records how each finding was resolved.

## Nits

### R5-N1. model-behaviour

**Where:** composed_quotes.py docstring 'Not copied from F: its markdown reading (emphasis delimiters * _ ~,
backslash escapes and character references)' (and the 'unless F reads a nested quotation or the display differs from
the text (below)' pointer); PREREGISTRATION.md 'Why the raw audit…' parenthetical, 'Two parts of F's reading are not
copied' bullet, and the Handback limitation; README measurement paragraph and Limitations

**Finding:** The not-copied list reads as complete, but F's display reading changes more than emphasis, escapes and
character references. I tested each case against the real unsupported_prose_quotations at this head. In every one, F
publishes and the reading classes the quotation composed, a false failure the disclosures do not name. (1) Code
spans: `"Net income `7,571.6`"` (ASML), and a longer MD&A quotation with a code span inside. F's display keeps the
code content without backticks, but the reading keeps the backticks. (2) Block markers on the continuation line of a
quotation that crosses a line break: `> MD&A says "…to\n> RMB1,023,670…"` and `MD&A says "…to\n- RMB1,023,670…"`. F's
display drops the `>` and `- ` markers, but the reading keeps them. These shapes became reachable once pairs could
cross line breaks (round 3 sent such rows to the fallback). (3) Default-ignorable characters that F strips before
reading (_DEFAULT_IGNORABLE_RE), e.g. U+2060 or U+FE0F inside a verified MD&A quotation. normalize_for_match's copy
folds only U+00AD, U+200B–200D and U+FEFF. All three routes are stricter than F, so a pass stays valid. A Q-run hit
would print its span, and the measured exposure is 0. Across the 432 retained rows (420 published answers and 12
withheld candidates): 0 backticks, 0 default-ignorables, and 0 quotations crossing a line break or holding a block
marker. This is the same class as R4-N3 (named routes, zero exposure), not a validity issue.

**Fix:** Optional, before freeze. Make the not-copied description explicitly non-exhaustive, or extend it, in the
docstring, PREREGISTRATION (both places and the handback) and README. For example: "F's display reading
(_rendered_text and its default-ignorable drop): emphasis delimiters, backslash escapes, character references,
code-span backticks, block markers on a quotation's continuation lines, and default-ignorable characters". Add the
measured 0 counts beside the existing ones. In the handback, "any span holding markdown emphasis, a backslash escape
or a character reference" could become "any span whose text differs from F's display of it". Optionally add probe
cases for a code span and a blockquote continuation, tagged disclosed.

### R5-N2. model-behaviour

**Where:** PREREGISTRATION.md 'Registered measurement': 'Across all 432 rows of the 24 retained runs (including run
37072989252 and the 12 withheld candidates), no row holds a backslash, a character reference, one of those three
marks or an odd number of marks.'

**Finding:** Read literally, "no row holds a backslash" is wrong for three rows. In 37005114216 ASML d1, 37029156902
BABA native d1 and 37029964566 BABA native d1, the candidate_deltas (citation JSON) hold literal backslashes (5, 4
and 4). Their answers and prose hold none. The measured surface is each published row's answer plus each withheld
row's full candidate. The README states that correctly ("published answers and withheld candidates"), and the
implementer's report says so too. Only the frozen file's wording says "row".

**Fix:** Optional: replace "no row holds" with "no published answer and no withheld candidate holds" (or similar).

### R5-N3. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:349-350 (Unknown-cost calls: 'it
stops the lane only when the charged total fails the spend rule') against :344-345 (Rule: 'Budget risk stops the
lane: a failed spend rule, or the balance case…') and :365-370 (balance-case bullets); README 'Review round 4' row
R4-N4 repeats the same sentence

**Finding:** The new wording contradicts itself. An unknown-cost call is said to stop the lane 'only when the charged
total fails the spend rule'. Two lines later, a run with unknown-cost calls whose balance delta exceeds the known
cost plus the charges stops the lane even when the charged total passes the spend rule. The Rule bullet and the
balance-case bullets are the more specific and more conservative text, so a careful operator stops, and the ceiling
is not at risk. Reserved per-run cost is 0.1725 against an actual Copilot run of about 0.006–0.008, and 0.19 against
about 0.18 for eval-baseline. Otherwise the decision is internally consistent: no unknown calls means charges = 0, so
the replace-the-charge window is empty, a smaller delta means 'not settled', and a larger delta is reported as other
owners' spend. A balance-case stop is a spend stop, which gives Incomplete under Outcome. Two smaller points. First,
'the run's known cost is exact' holds only up to the pinned rates. I confirmed AsyncOpenAI is built with
max_retries=0, so the SDK makes no unlogged retries. Second, steps 2 and 3 never require the DeepSeek balance to be
read before each ready transition and after each download, so the new balance-case stop is only operative if the
operator reads the balance anyway, as in past practice (e.g. D27).

**Fix:** Change the sentence to '…and it stops the lane only when the charged total fails the spend rule, or in the
balance case below', and make the same change in README row R4-N4. Optional: in steps 2 and 3, read the DeepSeek
balance before each ready transition and after each artifact download, and change 'exact' to 'complete under the
pinned rates'.

### R5-N4. rules-gates-custody

**Where:** PREREGISTRATION.md:127-128 (step 2, reused by step 3: '`mergeable_state` is not the check: it reads
`draft`, `blocked` or `unstable` on a draft PR or with failing non-required checks')

**Finding:** The check itself is right. The REST `mergeable` field is computed on draft PRs, and the 're-read while
it is null' clause is needed: my first reads of draft #1035 and #1069 both returned null/unknown. The stated reason
is inaccurate for this repo, though. On re-read, draft #1035 returned mergeable=true with mergeable_state=clean, not
`draft`, and draft #1069 returned false/dirty. main has no branch protection (required_status_checks returns 404
'Branch not protected'), so `blocked` is not produced here. In any case `blocked` comes from protection rules, not
from failing non-required checks; only `unstable` does. The rule is unaffected.

**Fix:** Optional: trim the clause to '`mergeable_state` is not the check (it can read `unstable` with failing
non-required checks)', or drop the reason.

### R5-N5. rules-gates-custody

**Where:** PREREGISTRATION.md:104-107 (precondition 6: 'three lenses: correctness and scope, model behaviour,
rules/gates/custody'), and README 'Review round 4' ('Two lenses…')

**Finding:** Precondition 6 requires a three-lens exact-head review of the head that contains the file. Round 4 on
f848de27 had two lenses, and this delta round on 998aff32 appears to be lens-split the same way. I did cover the
scope checks in this lens: backend/ and .github are identical to f848de27, the diff touches only the folder,
scope_hashes.py passes, prompt_identity.py passes and the trailers are correct. Unless the step-0 comment says which
lens covered correctness and scope on the frozen head, precondition 6 is not literally met at freeze. This is not a
file defect.

**Fix:** No file edit. In the step-0 comment on #1029, give a verdict for each of the three lenses on the frozen head
itself, or name the lens whose scope checks stand for 'correctness and scope' on 998aff32. Also post the full-gate
tails from the operator's run on 998aff32, as the reworded precondition 6 requires.

### R5-N6. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/scope_hashes.txt:2-4 (head 955c3098…) and README Files
paragraph ('…against the round-4 commit as it stood before this file was rewritten')

**Finding:** The committed scope proof names head 955c309866bf4eff71e7cd4e7fba7a3ae6d24230. That is the amended-away
intermediate commit: it is not on any branch, and pushing the branch will not publish it, so no other party can fetch
it later to check the annotation. I verified the annotation locally while the object still exists: `git diff --stat
955c3098 998aff32` shows only scope_hashes.txt. Re-running `scope_hashes.py b40fa703 HEAD` on 998aff32 gives RESULT:
PASS and differs only in the head line. In the README sentence, 'this file' could mean the README or
scope_hashes.txt.

**Fix:** Optional: say in the annotation and the README that 955c3098 is a local, unpushed commit and that the
verification route is to re-run the script on the frozen head. Or have the step-0 comment carry that re-run's head
line and RESULT. Change 'this file' to 'scope_hashes.txt'.

## What each lens ran (as received)

### model-behaviour (APPROVE)

I confirmed that /home/user/wt/prompt-candidate HEAD is 998aff329aa41ae95c8a6978a6f0dd84c9cf5ce3 with a clean status.
`git diff --quiet f848de27…998aff32 -- backend .github` exits 0. `--name-only` lists 8 files, all in
tasks/review-evidence/prompt-candidate-2026-10-02/: PREREGISTRATION.md, README.md, composed_quotes.py,
composed_quotes_probe.py, composed_quotes_probe.txt, design-history/exact-head-review-r4.md,
run_validity_post1066.txt and scope_hashes.txt. I made one detached scratch worktree at 998aff32
(scratchpad/prompt-candidate/wt-r5rev-mb) and removed it afterwards with `git worktree remove --force`. I never
edited the implementer tree, committed or pushed, and called no provider: real keys were unset, and a mock key
covered the backend import. My only network call was one read-only `gh api` GET.

Checks:
- **composed_quotes.py, 23 runs:** re-ran it on the same 23 retained runs. Exit 1. The committed composed_quotes.txt
  reproduces byte for byte (5-line header + output + 'exit 1', cmp equal; unchanged since f848de27). Run 37072989252
  exits 0 with every count 0.
- **composed_quotes_probe.py:** re-ran it against the 37063120532 sources. Exit 0. The committed file reproduces byte
  for byte (3-line header + output + 'exit 0'). Summary: 38 cases — 33 agree, 2 F-withheld legs, 3 disclosed false
  failures, 0 untagged.
- **Code against F:** read the new PAIR `"([^"]*)"` and PAIRING_FOLD against copilot_service._quotation_reading,
  _rendered_text, _displayed_quotation_reasons and _DEFAULT_IGNORABLE_RE.
  - PAIRING_FOLD maps one character to one, and positions stay aligned with the located spans.
  - The audit FOLD and PAIRING_FOLD together cover exactly F's six marks.
  - `paired` is false exactly when the mark count is odd.
  - A pair's text never contains one of the six marks.
- **My own adversarial probes against the real `unsupported_prose_quotations`:** 51 answers in two batches (42 + 9).
  - Covered: line-break and blank-line quotations, CRLF, empty and double-empty quotes, mixed glyphs, ＂ / „…” / ‟…”
    labels and compositions, nested curly and straight, escapes, `&quot;` / `&#34;` / `&ldquo;` / `&#36;`, code
    spans, blockquote and list continuations, U+2060 / U+FE0F, ellipses (elided across a break), labels with [n],
    three or more quotations, a label inside emphasis, headings, lists, tables, the R4-N1 example and an unclosed
    quote.
  - Results: 33 agree, 9 F-withheld legs (unpublished, so they fail via the F-withheld count), 9 false failures.
  - 4 of the false failures fall under the disclosed classes: `&#34;` (odd count), `&#36;`, and the hard-break
    backslash.
  - The other 5 are not disclosed: two code spans, a blockquote continuation, a list continuation and two
    default-ignorables (finding 1).
  - On a published answer the reading is never more lenient than F.
- **Measurement over the retained data:**
  - 402 published answers (23 runs), and 432 rows (420 published + 12 withheld candidates, 24 runs).
  - 0 of each: backslash, character reference, `&`, backtick, ＂/„/‟, odd count, line-break pair, empty pair, `*_~`,
    default-ignorable.
  - Using F's own `_rendered_text` + `_quotation_reading` on the 27 answers with marks: 15 audit-checked spans, all
    15 are in-order pairs and match F spans; 0 nested; the in-order pairs equal F's spans on all 27 rows.
  - The 3 rows with backslashes hold them only in candidate citation JSON (finding 2).
- **Other files:**
  - The artifact digest via `gh api` GET is sha256:fe4b718e…5f0c (78712108 bytes, not expired) and matches
    run_validity_post1066.txt.
  - scope_hashes.py b40fa703 HEAD gives RESULT: PASS. Its output matches the committed txt apart from the head line.
    955c3098 exists, its parent is f848de27, and it differs from HEAD only in scope_hashes.txt.
  - PREREGISTRATION sha256 is 68a6240e…6d5c, as reported. The commit trailers are the two required lines.

Not run: the full backend pytest suite (the operator runs it).

### rules-gates-custody (APPROVE)

I reviewed head 998aff329aa41ae95c8a6978a6f0dd84c9cf5ce3. `git -C /home/user/wt/prompt-candidate rev-parse HEAD`
returns that SHA and the status is clean. I worked in a detached scratch worktree,
…/scratchpad/prompt-candidate/wt-rr5, which I removed afterwards with `git worktree remove --force` and pruned.
/home/user/wt/prompt-candidate was not touched: it is still at 998aff32 with 0 status lines. I made no edits, commits
or pushes. The scratch venv python ran with OPENAI_API_KEY, DEEPSEEK_API_KEY and OPENAI_BASE_URL unset, and the probe
used the mock key. No provider was called. GitHub access was gh api GETs only. I did not run the full backend pytest.

Scope:
- `git diff --quiet f848de27 998aff32 -- backend .github` exits 0.
- `git diff --name-only f848de27 998aff32` lists 8 files, all in tasks/review-evidence/prompt-candidate-2026-10-02/:
  PREREGISTRATION.md, README.md, composed_quotes.py, composed_quotes_probe.py, composed_quotes_probe.txt,
  design-history/exact-head-review-r4.md, run_validity_post1066.txt, scope_hashes.txt.
- Parent is f848de27.
- The trailers parse as exactly `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
  https://claude.ai/code/session_01XCLCs7hHjZamJ3x4bQMaCL`.
- PREREGISTRATION.md sha256 is 68a6240efc6318780b522b16492584cd865270e66ba20122882b11eb0bdb6d5c, which matches the
  report.
- Intermediate commit 955c3098 has parent f848de27 and differs from the head only in scope_hashes.txt.

Telemetry path:
- All 9 retained reports (scratchpad/eval-*/eval_*.json) have `summary` keys == ['baseline'] and no top-level
  incurred_provider_usage.
- `summary.baseline.incurred_provider_usage` holds calls, unknown_calls, prompt, completion and cache tokens: 631
  calls, 0 unknown.
- All 9 ci-execution.txt files record `--candidates baseline`.

Artifact digest:
- `gh api …/actions/runs/37072989252/artifacts` returns copilot-fidelity-37072989252: 78712108 bytes, expired false,
  digest sha256:fe4b718ef8be6907068cdb2ddc83727e1550eecc3b4131030855a3d0775b5f0c. This matches
  run_validity_post1066.txt.
- Custody's 'expected equal' claim holds for eval-baseline. The API digest equals the local a.zip sha256 for eval
  runs 37061778841 (d8f003bd…) and 37051282050 (a1c73245…). All workflows use upload-artifact@v7.

Mergeable:
- On first read, draft PRs #1035 and #1069 had mergeable null. On re-read, #1035 was true/clean and #1069
  false/dirty.
- main has no branch protection (404).

Spend:
- I checked the reworded section for internal consistency and against the 0.75 ceiling and found one wording
  contradiction (nit 1). The ceiling is not at risk.
- AsyncOpenAI is built with max_retries=0 in both provider_requests.py and openai_service.py.

Main: currently 82556d6e. The compare b40fa703...main is ahead 9 with 120 files, none under backend/ or .github, so
precondition 2 would hold now.

Review record:
- design-history/exact-head-review-r4.md contains all 38 texts from fix-r3-result.json (9×where/finding/fix/severity
  plus 2 ran), with whitespace normalized and 0 missing.
- The README 'Review round 4' table maps R4-N1 to N9 to the right nits (N1–N3 model behaviour, N4–N9 rules), and each
  resolution matches the diff.
- No stale wording remains: no '30 synthetic', `[^"\n]`, `summary.incurred`, 'is budget risk', 'still applies' or
  'tails in the step-0'.

Evidence claims, recounted independently over the 24 runs: 432 rows (420 published, 12 withheld candidates, 0 empty).
0 have a backslash, 0 an '&', 0 a ＂, „ or ‟ mark, and 0 an odd mark count.

Scripts, run from the worktree:
- scope_hashes.py b40fa703 HEAD: exit 0, RESULT: PASS. It differs from the committed txt only in the head line
  (955c3098 → 998aff32), plus the committed round-4 annotation and 'exit 0' lines.
- prompt_identity.py backend b40fa703: exit 0, 'all identity checks passed'. It differs only in the checkout HEAD
  line (and the committed 'exit 0').
- composed_quotes.py on the 23 runs: exit 1, body byte-identical to composed_quotes.txt apart from its header note.
  On 37072989252: exit 0, all counts 0.
- composed_quotes_probe.py: exit 0, identical to the committed txt apart from the trailing 'exit 0'. Result: '38
  cases: F-withheld leg 2, FALSE FAILURE 3, agree 33; untagged FALSE FAILURE 0'. Cases 31–38 match the README and
  PREREG descriptions.

Tests:
- From backend/, the 12 files found by `grep -rl "tasks/" tests --include='*.py'` plus test_acceptance_outputs.py and
  test_e8_restore_session.py: 386 passed, 9 warnings, exit 0, HEAD 998aff32, clean status.
- The only test_*.py or *_test.py under tasks/ is tasks/fable-e8-repin-2026-09-22/tests/test_e8_addon.py. Its sha256
  d79de757…7456 equals code-sha256.json, and the fable folder is unchanged vs b40fa703.

Codex decision 5958742492, items 1–7, re-checked against the whole PREREGISTRATION. No regression this round:
- The 0.75 ceiling and the 0.19 + 3×0.1725 = 0.7075 reservation are unchanged.
- Unknown charges are still retained and charged.
- Budget risk and validity stops are kept, and the balance case adds a stop.
- No retry, replacement or candidate edit is allowed.
- Checks 1–5 and R are unchanged.
- No merge or production prompt release follows, and the handback limitations are expanded, not reduced.
- Precondition 6 is now stricter: the gate must run on the exact frozen head.
