# Before a push that changes `backend/`, run the frontend unit suite as well as the backend gate: some frontend specs read backend files

Date: 2026-10-23 · Area: ops / verification

**Context.** Twice on 2026-10-23 a change with no frontend file in its diff passed the full backend gate
and then failed CI's `frontend-tests`. Both times the failing spec was
`frontend/tests/unit/authPagesCopy.spec.tsx`, which reads `backend/app/` and names every read of
`email_verified` by the nearest `def` above it:
- **#1529 (E144)** moved checkout's reads into a function nested in the route, so the scan named its 403,
  and the check after it, as the nested function's. `405abe0b` failed both cases, and `5eaa0797` made the
  unit a module-level function.
- **#1535 (F60)** moved resend-verification's read into `account_mail_service._issue_link`, and
  `e981dd50a` failed (CI run 40025627889). `ab3cda166` named the new site.

Each red push cost a CI cycle, and its fix push one more paid `eval-baseline` draw: every push to a pull
request whose diff touches `backend/app/`, `backend/evals/` or `backend/prompts/` draws one
(`ops-reserve-eval-baseline-before-each-push.md`). Before #1535's push, the session that pushed it ran
only the backend gate, because no frontend file had changed.

**Rule.** Before a push whose diff changes any file under `backend/`, its tests included, also run the
frontend unit suite from `frontend/`:

```bash
npm run test -- --run
```

At least 17 unit specs read files under `backend/`, for parity checks, inventories and contracts. They
include `authPagesCopy`, `planLimitsLockstep`, `passwordRulesLockstep`, `summaryStream.contract`,
`contactValidationParity` and `legalTruth`. `testHomesAllowlist` also checks where backend test files
live. So a backend edit can fail one with no frontend file in the diff.

Run the whole suite, not a subset picked by grep: on 2026-10-23, `grep -l '../backend'` missed 6 of the
17 specs and `grep -l 'backend/app'` missed 2, since some build the path in parts or read through a
helper such as `deployMaps.ts`. The rule covers all of `backend/`, wider than what the specs read today,
so a new spec cannot slip past it. The suite takes about four minutes in CI. In a worktree with no
`node_modules`, link the main checkout's for the run and remove the link afterwards.

The reverse needs no new rule: CLAUDE.md already runs the backend gate before every push, and that gate
holds the backend tests that read `frontend/` files, `test_frontend_matchers_parity.py` among them.

**Gate.** Review-checked. CI's `frontend-tests` runs these specs on every pull request, and a miss cannot
merge, since main's ruleset requires the check (`docs/OPERATIONS.md`). The rule saves the red cycle and
its paid draw. A pre-push hook could run the suite, but it would add about four minutes to every push and
needs `node_modules` in every clone. A machine gate on the cost alone would make `eval-baseline` wait for
`backend-tests` and `frontend-tests` (`needs:` in `.github/workflows/ci.yml`), so that a red unit test
skips the paid run. That is a high-tier CI change. Founder row F55 holds the forms for gating
`eval-baseline`'s spend, and this one is not among them.

**Evidence.**
- #1529: `405abe0b`, then `5eaa0797`.
- #1535: `e981dd50a` (CI run 40025627889), then `ab3cda166`. Both pairs are branch heads from before the
  squash merges, so the pull request numbers are the lasting reference.
- `frontend/tests/unit/authPagesCopy.spec.tsx`: `EMAIL_VERIFIED_READS` and the nearest-`def` scan.
- CLAUDE.md's backend gate line and `AGENTS.md` §8 stand unchanged. This lesson, in every session's
  reading, adds the frontend unit step to them for a backend change.
