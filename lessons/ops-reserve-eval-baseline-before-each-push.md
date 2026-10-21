# Reserve for `eval-baseline` before opening, and before each push to, a pull request whose diff touches `backend/app/`, `backend/evals/` or `backend/prompts/`: it draws on every push, drafts included

Date: 2026-10-21   Area: ops / evals / spend

**Context**: #1451 (E137's second half: the logout route and `refresh_token_service.py`) was pushed
three times as a draft, at 03:07Z, 03:48Z and 04:16Z on 2026-10-21. Its session counted one paid run,
the ready mark's `copilot-eval`, and planned its balance read and reservation for the ready mark.

CI's `eval-baseline` job also draws. It runs the full verified set against DeepSeek on every
`pull_request` event, draft or not, whose diff against its base touches `backend/app/*`,
`backend/evals/*` or `backend/prompts/*`. It was measured at USD 0.35–0.36 a run. Each of the three
pushes ran it to the end, and no reservation was written for any of them. The balance went from USD
12.54 (00:31Z) to 12.21 (03:51Z) to 11.88 (04:19Z), about USD 0.33 a run.

The same session's two pushes to #1437 the evening before (20:56Z and 21:58Z, a notable-filings
service change) had run it too, and #1437's spend comments counted only `copilot-eval`. That makes
five runs, about USD 1.7, with no reservation.

`AGENTS.md` §3 authorizes bounded measurement spend after a balance read, and it prices an
`eval-baseline` run. But `AGENTS.md` §6 and the ready-mark section of
`ops-keep-moving-under-standing-authorization.md` name only `copilot-eval` and the ready mark, and
that is where the session looked.

**Rule**:
- **Opening the pull request.** Read the balance first (`deepseek-balance.yml`, which makes no inference
  call). Then state the reservation in the body as you open it: USD 0.73 for each push you expect (the
  dearest measured run × 2), plus USD 0.06 for the ready mark's `copilot-eval` when the diff matches its
  `paths:`. The scope is the pull request's whole diff against its base, so it covers:
  - a later push that changes only tests or records;
  - a merge of `main`.

  A branch with no pull request runs no `pull_request` CI, so opening the pull request is the first
  paid event.
- **Each push.** Every push to such a pull request runs `eval-baseline` again, draft or ready. Before a
  push beyond the count you reserved, reserve again. Put a review round's fixes in one push, since each
  push costs a run.
- **A superseding push.** It cancels a run still in progress (`concurrency: eval-baseline-<number>`), but
  the cancelled run has already drawn for the minutes it ran. Count it.
- **The after-draw reading.** It counts the `eval-baseline` runs beside the `copilot-eval` draw, with the
  run links, so the reading is not read as one draw's cost.

**Evidence**:
- `.github/workflows/ci.yml:444-453`: the job, its `pull_request` trigger with no draft condition, and
  its concurrency group.
- `.github/workflows/ci.yml:493`: the paths that arm it.
- `tasks/refactor-plan-2026-10.md:327,329`: the measured cost and the USD 0.73 reservation rule.
- `AGENTS.md:67`: the §3 authorization.
- #1451's spend comment [6308009782](https://github.com/neilmac91/EarningsNerd/pull/1451#issuecomment-6308009782):
  the three runs and the readings.
- #1437's CI runs [39496203700](https://github.com/neilmac91/EarningsNerd/actions/runs/39496203700)
  and [39504563191](https://github.com/neilmac91/EarningsNerd/actions/runs/39504563191): their
  `eval-baseline` jobs each ran the eval for nine to ten minutes.

**Gate**: none; review-checked. A push hook cannot see a reservation. Running `eval-baseline` only on
the ready mark, as `copilot-eval` does, would save about USD 0.35 a draft push and give up the
draft-time signal. That is a CI workflow change and the founder's call.
