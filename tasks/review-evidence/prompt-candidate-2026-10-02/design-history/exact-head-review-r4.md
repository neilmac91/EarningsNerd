# Exact-head review, round 4 (head `f848de27`): findings as received

Two independent lenses (model behaviour, rules/gates/custody) reviewed head
`f848de27052fdc9815c5c6324db9f54b70834145` (the round-3 fix commit on merge `3264cdcc`, base `b40fa703`). Verdicts:
model-behaviour APPROVE, rules-gates-custody APPROVE. Both returned nits only. The findings below are the reviewers'
text as handed to the implementer, kept verbatim (line-wrapped only), followed by what each lens ran. The README
section "Review round 4" records how each finding was resolved.

## Nits

### R4-N1. model-behaviour

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/composed_quotes.py:64 (PAIR = `"([^"\n]+)"`) and :84
(the unpaired-marks fallback); PREREGISTRATION.md 'Registered measurement', the paragraph starting 'When the in-order
pairing leaves a double mark…'

**Finding:** The fallback for unpaired marks brings back the round-2 false failure in one case: the R3-1 pairing
shape, when the later quotation contains a line break or an empty `""` comes before the label. I reproduced this
against the product's `unsupported_prose_quotations`. For `The "Revenue" line agrees, and MD&A says revenue "further
increased by 3% to\nRMB1,023,670 million (US$148,401 million) in fiscal year 2026" [1].`, F returns [] (publishes),
but the reading marks the row unpaired and classes ` line agrees, and MD&A says revenue ` as composed. The
empty-quote variant `An empty "" pair, the "Revenue" line, and MD&A says revenue "…" [1].` fails the same way. On
`The "Revenue" line reads "Revenue\n996,347" [F1].` the fallback reads the gap as composed rather than the real
composition; the outcome agrees with F only by accident. The frozen text describes the fallback but never says that
such a row can still fail on the pairing shape. Exposure is low: none of the 432 rows in the 24 retained runs,
including withheld candidates and 37072989252, has a quotation across a line break, an empty quotation, or a „ ‟ ＂
mark, and the candidate prompt does not push toward these.

**Fix:** Optional, before the step-0 freeze: change PAIR to `re.compile(r'"([^"]*)"')`. F pairs across line breaks:
probe case 5 publishes such a quotation and case 6 withholds it. With an even count of folded marks, every mark is
then paired in order, so the fallback is reached only on an odd count. I checked this on a copy. composed_quotes.txt
over the 23 runs is byte-identical, probe cases 5 and 6 still agree with F, and all three variants above read
correctly (the cross-line composition is now classed composed). Otherwise, add one sentence to the PREREG and README:
a row with unpaired marks is read as the audit pairs it, so the pairing shape on that row still fails.

### R4-N2. model-behaviour

**Where:** composed_quotes.py docstring :28-31; PREREGISTRATION.md 'Registered measurement' (the parenthetical '… or
a `„`, `‟` or `＂` mark, which the audit's FOLD leaves alone'); README measurement paragraph and Limitations

**Finding:** The wording suggests that any „ ‟ ＂ mark sends the row to the fallback. A pair of ＂ marks between
straight marks, however, leaves an even count of folded marks, so the row is treated as paired even though its pair
is out of phase. Example: `The "Revenue＂ line agrees, and MD&A says revenue ＂<MDA sentence>" [1].` F treats " and ＂
as straight marks of one stretch and publishes. The reading's single pair `Revenue＂ line agrees, …` is classed
composed and the row is not reported as having unpaired marks. The raw audit and the round-2 reading behave the same,
so this is not a regression. 0 of 432 rows hold any of these marks.

**Fix:** Optional: for the pairing pass only, also fold ＂ „ ‟ to `"`. This is a one-to-one character map, so
audit-span positions still line up. Otherwise narrow the parenthetical: a „ ‟ ＂ mark sends the row to the fallback
only when the folded-mark count comes out odd, and when the count stays even the out-of-phase pairing is not
detected.

### R4-N3. model-behaviour

**Where:** PREREGISTRATION.md 'Two parts of F's reading are not copied: its markdown reading…' and README Limitations
/ measurement paragraph ('F's markdown reading (emphasis delimiters `*`, `_`, `~`)')

**Finding:** Markdown escapes and character references are also part of F's markdown reading (`_rendered_text`), and
the reading does not copy them either. The disclosure names only emphasis. Reproduced: `The \"Revenue\" line agrees,
and MD&A says revenue "<MDA>" [1].` F publishes, because it reads the label `"Revenue"`, which is under the floor.
The reading pairs `Revenue\`, which reaches the floor, and classes it composed. The round-2 reading did the same, so
this is not a regression. 0 of 432 rows contain a backslash or a quote entity.

**Fix:** Optional: in the not-copied list and the handback limitation, add 'backslash escapes and character
references' next to emphasis. The 0-of-402 retained-runs statement can say no answer holds a backslash or entity
either.

### R4-N4. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:330-345 (Spend, 'Unknown-cost calls')
with :326 ('Budget risk stops the lane')

**Finding:** The R3-N7 fold-in is arithmetically correct. I reproduced it: 722 Copilot calls in 24 retained
runner.logs, largest prompt 37,115 tokens, giving 0.0070073, which rounds up to 0.0071. 631 calls in 9 eval-baseline
reports, largest one-call prompt 71,040 tokens, plus the 12,000 max_tokens from ai/extraction.py, giving 0.017856,
which rounds up to 0.0179. Rates match llm_pricing.py (0.15/0.60) and AI_PEAK_PRICE_MULTIPLIER is 2.0. The wording is
ambiguous in two places, though. First, 'Each provider call without usage is budget risk' combined with :326 'Budget
risk stops the lane' reads as an automatic stop on the first unknown call. The next sentence instead charges the call
into 'spent so far', so the spend rule decides. Two operators could stop or continue on the same evidence. Second,
the text never says what a balance delta above the known cost plus the charges means. The bounds are 'largest
observed, not hard caps', so such a delta is the case where the charge may understate spend. Exposure is low: 0
unknown calls in all 1,353 retained calls.

**Fix:** Reword the first sentence along these lines: 'Each provider call without usage is charged to "spent so far"
at …; it stops the lane only when the charged total fails the spend rule.' Then state what a delta above the known
cost plus the charges does. Either it keeps the charge and is reported, attributed to other owners' concurrent calls,
or it is budget risk and stops the lane. Pick one before freeze.

### R4-N5. rules-gates-custody

**Where:** PREREGISTRATION.md:121, :328, :336 (`summary.incurred_provider_usage[.unknown_calls]`)

**Finding:** In eval-baseline reports this telemetry is nested under the candidate name, not at the top of `summary`.
All 9 retained reports have `summary.baseline.incurred_provider_usage` with `calls` and `unknown_calls`, and
`summary` has no top-level `incurred_provider_usage`. ci-execution.txt records `--candidates baseline`. The new
unknown-cost bullet repeats the inexact path.

**Fix:** Write `summary.baseline.incurred_provider_usage` (`.unknown_calls`) in step 2, Accounting and the
unknown-cost bullet.

### R4-N6. rules-gates-custody

**Where:** PREREGISTRATION.md:123-134 (step-2 check 'the PR is mergeable', reused by step 3)

**Finding:** The R3-N1/R3-N5 fold-in is correct: three checks, with a failed check giving a validity stop that is
reported, and Incomplete unless a check has already failed. Because a failed mergeable check now stops the lane, the
field matters. Each check runs while the PR is a draft (step 1 opens it as a draft; step 3 converts to draft first).
The REST `mergeable_state` reads `draft` on a draft PR, and can read `blocked` or `unstable` on failing checks such
as the continue-on-error eval-baseline or review-gate. An operator who reads `mergeable_state` would stop the lane
for no reason. The intended condition is that GitHub can build a merge ref (no conflict).

**Fix:** Say: 'the REST `mergeable` field is true (re-read while it is null); `mergeable_state` is not the check.'

### R4-N7. rules-gates-custody

**Where:** PREREGISTRATION.md:94-100 (precondition 4, 'merge-queue owner')

**Finding:** The R3-N4 fold-in is accurate. The open PRs that touch backend/ or .github are exactly #1035 (3 files),
#1069 (31) and #1070 (2). #1072 and #1009 touch neither, and none of them has auto-merge. However, #1029 comment
5963598327 (00:26Z) says 'No further merge ownership is reserved by this completed implementation lane', so no
merge-queue owner exists right now. #1070 is a Dependabot PR with no human author; per that comment it is held under
#1063 with failing checks. The 'owner of each named PR' route therefore needs a named person for #1070.

**Fix:** No file edit is needed. In the precondition-4 claim on #1029, name who acknowledges for each of #1035, #1069
and #1070 (for example the founder, or Codex as coordinator for the held lanes), or get the founder's explicit 'no
backend merges planned'.

### R4-N8. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/run_validity_post1066.txt:3 (zip sha256 prefix only)

**Finding:** The record cites a 16-hex zip prefix copied from the task and says the zip is not retained. The Actions
artifacts API returns the full digest for artifact copilot-fidelity-37072989252 (78,712,108 bytes, not expired):
sha256:fe4b718ef8be6907068cdb2ddc83727e1550eecc3b4131030855a3d0775b5f0c. It matches the prefix. This is a pre-freeze
control, not a qualification run, so custody is not at risk.

**Fix:** Optional: record the full digest from `actions/runs/37072989252/artifacts`. For Q1–Q3, record the API
`digest` beside the locally computed zip sha256 in the custody comment.

### R4-N9. rules-gates-custody

**Where:** PREREGISTRATION.md:103-105 (precondition 6) and README 'Review round 3' closing paragraph

**Finding:** Precondition 6 requires the full backend gate to be green 'on the exact frozen head'. The implementer
reused 198d0e78's gate on the backend-tree identity argument. I ran the gate on f848de27 itself with the #1066 pins
overlay and provider keys unset. ruff exited 0 and bandit exited 0. A clean pytest run gave 5565 passed, 39 skipped,
2 deselected, exit 0. A first pytest run, made while my owner-test runs were going at the same time, had one failure:
test_resend_webhook_handlers::test_first_click_on_an_alert_email_is_stamped_once_and_reported_without_the_address,
with 'I/O operation on closed file'. That test passed 3 of 3 times in isolation and in the clean rerun, and it has
nothing to do with this branch.

**Fix:** In the step-0 comment, give gate tails run on the frozen head SHA itself, not on 198d0e78, so precondition 6
holds as written. If a later fix round moves the head, re-run the gate.

## What each lens ran (as received)

### model-behaviour (APPROVE)

Head discrepancy: the computed task text calls 198d0e78 the "new head" and asks for a worktree there. The branch and
the implementer's report both put the new head at f848de27052fdc9815c5c6324db9f54b70834145, the round-3 commit on top
of 198d0e78. I reviewed f848de27 in my own scratch worktree, rr4-model-behaviour. I made no edits, commits or pushes
and called no provider. The worktree has been removed. /home/user/wt/prompt-candidate is clean at f848de27. Python
came from the scratch venv with provider keys unset, and app imports used the mock key.

Scope:
- `git diff 198d0e78 f848de27` touches only the evidence folder (9 files).
- `git diff --quiet 198d0e78 HEAD -- backend .github` exits 0.

SHOULD-FIX R3-1 is resolved.
- composed_quotes.py folds with the audit's FOLD and pairs quotations in order with `"([^"\n]+)"`, with no floor. It
  runs `verdict` on every pair, flagged or not.
- An audit span that is not a pair is classed as an audit pairing difference, which is not composed. Unflagged
  composed pairs count toward the exit status.
- The located spans are re-derived and asserted equal to the audit's spans.
- `paired` (count == 2 × pairs) does imply that every mark is paired in order.

Reruns:
- composed_quotes.py on the same 23 retained runs reproduces composed_quotes.txt byte for byte, exit 1.
- The diff against the round-2 txt changes only the summary lines, adding the new counts, all 0. Span lines and exit
  status are unchanged.
- On 37072989252 it exits 0, all counts 0.
- composed_quotes_probe.py reproduces composed_quotes_probe.txt byte for byte, exit 0, with 28 agree, 1 F-withheld
  (nested, disclosed) and 1 false failure (markdown, disclosed).

My own probe ran 20 cases against the product's unsupported_prose_quotations.
- The reviewer's three answers (BABA native label then MD&A sentence, BABA viewed with "Revenue" twice, the curly
  variant): F publishes all three, and the reading finds 0 composed (sub-floor label, pairing difference, verified or
  sub-floor).
- These were all still classed composed, with F withholding:
  - label plus cell (ASML `Total net sales 32,667.3`, BABA after a preceding label);
  - interior ellipsis (`...`, `. . .`, `…`, also after a label);
  - glued `Revenue996,347`;
  - two labels then a composition;
  - a two-line markdown list;
  - a composition then a label.
- short-long-short, a curly label then straight quotes, a bold label, and a label with a comma inside or a marker all
  agree with F.
- Residual false failures, all NITs: label plus a line-break quotation, an empty quote first, ＂ or „ mixes, and
  backslash-escaped quotes.
- An alternative `"([^"]*)"` pairing on a copy leaves the 23-run output byte-identical and fixes the line-break and
  empty-quote cases.

I checked the frozen-file claims over the 23 runs with F's own `_rendered_text` and `_quotation_reading`. All of them
hold:
- 402 published answers, 27 with marks;
- 0 with unpaired marks, 0 nested, 0 with a sub-floor label followed by another quote;
- 15 audit spans, all of them pairs;
- F's pairs equal the in-order pairs on all 27;
- "Revenue" quoted in 13 of 69 BABA-viewed draws across 9 runs;
- 0 answers containing `*`, `_` or `~`.

Across 432 rows (24 runs, including withheld candidates), 0 have a backslash, an entity or an unpaired mark.

The PREREG, README and docstring describe the class and the shape (a sub-floor quoted label such as `"Revenue"`
followed by another quotation) accurately, and the strict alternative names the pairing shape.
design-history/exact-head-review-r3.md matches rereview-r3.json, 36 of 36 texts with whitespace normalized.

Also run: test_review_evidence_links.py and test_copilot_prose_quotations.py, 765 passed. run_validity.py changed in
its docstring only.

### rules-gates-custody (APPROVE)

I reviewed the round-3 commit f848de27052fdc9815c5c6324db9f54b70834145 (parent 198d0e78). The computed task text
names 198d0e78 as both the 'new head' and the worktree target, but the round-3 commit described in the implementer
report is f848de27. The literal `git diff --quiet 198d0e78 198d0e78 -- backend .github` is trivially 0. The
meaningful check, `git diff --quiet 198d0e78 f848de27 -- backend .github`, also exits 0.

I worked in a scratch worktree at f848de27 (…/scratchpad/prompt-candidate/rr4-rules-gates-custody), since removed
with `git worktree remove --force`. /home/user/wt/prompt-candidate was not touched and is still clean at f848de27.
Every Python run had OPENAI_API_KEY, DEEPSEEK_API_KEY and OPENAI_BASE_URL unset. I made no provider calls and no
GitHub writes; I only read through `gh api` GETs.

Scope and trailers:
- `git diff --name-only 198d0e78 HEAD` lists 9 files, all under tasks/review-evidence/prompt-candidate-2026-10-02/.
- The commit is not pushed (ls-remote is empty).
- The trailers on f848de27, 198d0e78 and 61cce875 are exactly `Co-Authored-By: Claude Opus 5.5
  <noreply@anthropic.com>` and `Claude-Session: …session_01XCLCs7hHjZamJ3x4bQMaCL`.
- PREREGISTRATION.md sha256 is b309a62f…496a, matching the report.
- `scope_hashes.py b40fa703 HEAD`: PASS. It differs from the committed file only in the head line and the folder's
  new files.
- `prompt_identity.py backend b40fa703`: exit 0, identical apart from the HEAD line.

Post-#1066 validity control, re-run:
- With `run_validity.py --control-prompt a88b6fb1…:5057` on scratchpad/copilot-37072989252: VALID, 18 rows, openai
  3.20.0, fingerprint aeb56401 x28, exit 0.
- Without the control: INVALID with exactly 18 MISMATCH lines, all on the system prompt, exit 1.
- The copilot-eval.json and runner.log sha256 values match the record.
- `git fetch origin bc0a96c3` by SHA succeeded. Its ^1 is 3084c024 and its ^2 is b7bd5d19. #1066's 432fa5df is an
  ancestor of ^1, and `git diff --quiet b40fa703 bc0a96c3 -- backend .github` is 0.
- The Actions API confirms run 37072989252 is 'Copilot filing fidelity' on head b7bd5d19
  (codex/wave3-optional-anthropic-refresh). The artifact digest is fe4b718ef8be6907…5b0c.
- Across the retained runs, openai is 3.19.2 x23 and 3.20.0 x1, as the PREREG states.

Nit fold-ins:
- Steps 2/3: three checks, and a failed check gives a validity stop that is reported and Incomplete. The Validity
  paragraph is reworded. Verified.
- Custody fetch by SHA, with ^1/^2 and the compare-API fallback. Verified.
- Unknown-cost bounds. Numbers verified against llm_pricing.py, config.py and extraction.py; wording nits above.
- 20-F 2-of-3 clause. Matches g_decide.py (`sum(v) >= 2`).
- PR body: the Review section, the M0–M4 tails, and a window-limited `Review override:`. review_gate.py accepts
  reasons of 10 or more characters. Editing the body fires only review-gate; neither copilot-eval nor ci.yml listens
  for `edited`.
- Precondition 4 names #1035, #1069 and #1070. Checked against the live open-PR file lists.
- run_validity.py docstring. Fixed.
- design-history/exact-head-review-r3.md: all 36 texts from rereview-r3.json are present with whitespace normalized.
- The Codex decision copy equals live comment 5958742492 (never edited) apart from a trailing newline.

Reproductions:
- composed_quotes.py on the 23 runs (excluding 37072989252): byte-identical to the committed output, exit 1.
- composed_quotes_probe.py: identical, exit 0 (28 agree, 1 F-withheld, 1 disclosed false failure).
- BABA-viewed draws: 13 of 69 quote "Revenue", across 9 runs. Verified.

Tests:
- The 14 backend tasks readers: 386 passed.
- frontend testHomesAllowlist.spec.ts, run via vitest with borrowed node_modules: 6 of 6 passed. The only stray
  test_*.py is the sealed fable-e8 fixture, and its hash matches.
- Owner test with the five RUNBOOK files: 1050 passed. The first run gave 1 failure while my full pytest ran at the
  same time; reruns gave 1050 twice.
- Mutations: M0 passed (7). M1, M2, M3 and M4 fail at :68, :70, :74 and :69, and the file was restored each time.
- Full gate on f848de27: ruff 0, bandit 0, pytest 5565 passed, 39 skipped, 2 deselected, exit 0 on a clean rerun (one
  unrelated flaky failure in the first, concurrent run).

Main: origin/main is e969e4ab (#1073). `git diff --quiet b40fa703 origin/main -- backend .github` is 0, merge-tree
with HEAD is clean, and the merged tree's backend equals HEAD's.

I re-checked the PREREG against Codex decision 5958742492 items 1–7. The edits keep the 0.75 ceiling, stop on
validity and budget risk, allow no retry or replacement, preserve the review findings, and keep all of the handback
limitations. Nothing was broken.
