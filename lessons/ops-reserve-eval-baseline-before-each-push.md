# Reserve for `eval-baseline` before opening a pull request and before each push to it: it draws on every push, drafts included

Date: 2026-10-21   Area: ops / evals / spend

**Context**: CI's `eval-baseline` job runs the full verified set against DeepSeek. It runs on every
`pull_request` event whose diff against its base touches `backend/app/*`, `backend/evals/*` or
`backend/prompts/*`, draft or not, and on any dispatch of CI. Record 18 measured four runs at USD
0.35–0.36 each, all at peak pricing, and reserves USD 0.73 a push: the dearest run × 2, rounded up.
`AGENTS.md` §3 prices a run at "about USD 0.30". No file a session reads at start says when it runs.

On 2026-10-20 the principal session read the balance before #1325's push and before #1437's second
push, and reserved for both runs at §3's figure. #1437's first push, at 20:56Z, had no reservation of
its own; #1325's after-draw reading named its run. Those evening runs read about USD 0.16 each.

Hours later the same session drove #1451, the logout route and `refresh_token_service.py`. It counted
only the ready mark's `copilot-eval`, and pushed the draft three times (2026-10-21 03:07Z, 03:48Z and
04:16Z). Each push ran `eval-baseline` to the end, and no reservation was written for any of them. The
balance went from USD 12.54 before them to 11.71 after the third and the ready mark's `copilot-eval`
draw, about USD 0.27 a run. The readings cannot separate production traffic.

**Rule**:
- **Opening the pull request.** If its diff touches those paths, read the balance first
  (`deepseek-balance.yml`, which makes no inference call). Then state the reservation in the body as
  you open it: USD 0.73 for each push you expect, and USD 0.06 for each `copilot-eval` draw (the ready
  mark, and each push while ready) when the diff matches that workflow's `paths:`. A branch with no
  pull request runs no `pull_request` CI, so the opening is the first paid event. A dispatch of CI on
  the branch comes before it, though, and runs `eval-baseline` whatever the diff.
- **Each push.** Every push re-runs it on the whole diff, draft or ready, including:
  - a commit that changes only tests or records;
  - a merge of `main`.

  So does a close and reopen, or a re-run of CI: `eval-baseline` has no once-per-head gate, as
  `copilot-eval` has. Reserve again before any run beyond the count you reserved. Put a review
  round's fixes in one push.
- **A superseding push.** It cancels a run still in progress (`cancel-in-progress`). A run cancelled
  after its `Run baseline eval` step started has drawn for the minutes that step ran: count it. One
  cancelled before that step drew nothing. When its log does not show which, count it in full.
- **The after-draw reading.** Name the `eval-baseline` runs beside the `copilot-eval` draw, with their
  links, so the reading is not taken for one draw's cost.

**Evidence**:
- `.github/workflows/ci.yml:3-7`: CI's triggers, `pull_request` with the default types and the
  dispatch.
- `.github/workflows/ci.yml:444-454`: the job, its trigger with no draft condition, and its
  concurrency group.
- `.github/workflows/ci.yml:493`: the paths that start it on a pull request.
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

**Gate**: none yet; review-checked until founder row F55 picks the gate's form.
- A hook on the GitHub write that opens a pull request could look for a reservation in its body. It
  would miss each later push, a dispatch of CI, and a session that loads no repository hooks.
- Gating it at the workflow changes every writer's spend process, so F55 holds two forms:
  - the job skips its paid step unless the pull request's body states a reservation, while the
    CODE RED chief reserves in its ledger today;
  - it runs only while a pull request is ready, as `copilot-eval` does, which gives up the drafts'
    signal.
