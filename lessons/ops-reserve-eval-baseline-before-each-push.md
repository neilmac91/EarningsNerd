# Reserve for `eval-baseline` before marking a pull request ready and before each push while it is ready; a draft draws nothing

Date: 2026-10-21 (gate: 2026-10-25, F55)   Area: ops / evals / spend

**Context**: CI's `eval-baseline` job runs the full verified set against DeepSeek. Until F55 it ran on
every `pull_request` event whose diff against its base touched `backend/app/*`, `backend/evals/*` or
`backend/prompts/*`, draft or not, and on any dispatch of CI. Record 18 measured four runs at USD
0.35–0.36 each, all at peak pricing, and reserves USD 0.73 a push: the dearest run × 2, rounded up.
`AGENTS.md` §3 prices a run at "about USD 0.30". No file a session reads at start said when it ran.

On 2026-10-20 the principal session read the balance before #1325's push and before its own second
push to #1437, and reserved for both `eval-baseline` runs at §3's figure. Its first push to #1437, at
20:56Z (the pull request's third; another session made the first two), had no reservation of its own,
and #1325's after-draw reading named that run but counted it inside #1325's own reservation. Those
evening runs read about USD 0.16 each.

Hours later the same session drove #1451, the logout route and `refresh_token_service.py`. It counted
only the ready mark's `copilot-eval`, and pushed the draft three times (2026-10-21 03:07Z, 03:48Z and
04:16Z). Each push ran `eval-baseline` to the end, and no reservation was written for any of them. The
balance went from USD 12.54 before them to 11.71 after the third and the ready mark's `copilot-eval`
draw, about USD 0.27 a run. The readings cannot separate production traffic.

F55 (2026-10-25) took the drafts out, as founder row F55's option (b) recommended: a pull request's
`eval-baseline` draws only while it is ready, as `copilot-eval`'s draws do, and CI's `ready_for_review`
event starts the mark's run. The job reads the pull request's live draft flag, not the event's, since a
payload can still say draft after the mark (#1315). A draft's run still classifies its head and spends
nothing; its notice says when the ready mark would draw. Unlike `copilot-eval`, nothing limits a head to
one draw.

**Rule**:
- **The ready mark.** If the diff touches those paths, read the balance first (`deepseek-balance.yml`,
  which makes no inference call). Then state the reservation in the body before you mark it ready:
  USD 0.73 for the mark's run and for each push you expect while it is ready, and USD 0.06 for each
  `copilot-eval` draw (the ready mark, and each push while ready) when the diff matches that
  workflow's `paths:`. Opening a pull request as ready counts as its mark. Opening a draft and pushing
  to it draw nothing. A dispatch of CI on the branch runs `eval-baseline` whatever the diff, draft or
  not.
- **Each push while ready.** Every push re-runs it on the whole diff, including:
  - a commit that changes only tests or records;
  - a merge of `main`.

  So does a close and reopen while ready, a re-run of CI while it is ready (whatever state the
  original run saw), or a second ready mark on an unchanged head after a return to draft:
  `eval-baseline` has no once-per-head gate, as `copilot-eval` has. Reserve again before any run beyond
  the count you reserved. Put a review round's fixes in one push.
- **A superseding push or ready mark.** Either cancels a run still in progress (`cancel-in-progress`),
  a push made after a return to draft included; converting to draft alone cancels nothing. A run
  cancelled after its `Run baseline eval` step started has drawn for the minutes that step ran: count
  it. One cancelled before that step drew nothing. When its log does not show which, count it in full.
- **The after-draw reading.** Name the `eval-baseline` runs beside the `copilot-eval` draw, with their
  links, so the reading is not taken for one draw's cost.

**Evidence**:
- `.github/workflows/ci.yml`, `on:`: `pull_request`'s types, the default three and
  `ready_for_review`, and the dispatch.
- `.github/workflows/ci.yml`, job `eval-baseline`: its `if:` and its `concurrency:` group; its
  `Detect AI-relevant changes` step, with the paths that start it on a pull request and the live
  draft read (only an exact `false` draws; a failed read fails closed).
- `backend/scripts/review_gate.py`'s module docstring: #1315, where an event with a draft payload ran
  after the ready mark and cancelled its run.
- `.github/workflows/copilot-eval.yml:5,54`: `copilot-eval`'s events, and its skip of drafts.
- `tasks/code-red-20261004/runtime/control/DECISIONS-18.md:119-127`: the measured cost and the USD
  0.73 rule.
- `AGENTS.md:67`: §3's authorization and its figure.
- #1325's comments 6301441477 and 6302848458, and #1437's 6302657918 and 6303149706: the evening's
  reservations and readings.
- #1451's comments
  [6308009782](https://github.com/neilmac91/EarningsNerd/pull/1451#issuecomment-6308009782) and
  [6308352547](https://github.com/neilmac91/EarningsNerd/pull/1451#issuecomment-6308352547): the
  three runs and the readings.
- #1673's comment
  [6429626919](https://github.com/neilmac91/EarningsNerd/pull/1673#issuecomment-6429626919): five full
  and two partial draws, none reserved beforehand, three of them from ready marks after a return to
  draft made to request a Codex review (runs 40391708791, 40404785109 and 40418689755); the last
  cancelled its push's run 3 minutes into the paid step.

**Gate**: partly gated since F55. `backend/tests/unit/test_eval_parity.py` runs the scope step against a
stubbed live draft flag and fails if a draft, a failed read or any answer but `true` or `false` would
draw, or if a paid step stops waiting on the key check; `backend/tests/unit/test_ci_cost_controls.py`
fails if the ready mark stops starting a run, and its cancellation test pins the groups that let one
pull request's runs supersede one another. The reservation itself is review-checked: a hook on
the GitHub write that marks a pull request ready could look for one in its body, but it would miss
each later push, a dispatch of CI, and a session that loads no repository hooks.
