# Before a push that changes `backend/`, run the frontend unit suite as well as the backend gate: some frontend specs read backend files

Date: 2026-10-23 · Area: ops / verification

**Context.** Twice on 2026-10-23 a change with no frontend file in its diff passed the full backend gate
and then failed CI's `frontend-tests`. Both times the failing spec was
`frontend/tests/unit/authPagesCopy.spec.tsx`, which reads `backend/app/` and names every read of
`email_verified` by the nearest `def` above it:
- **#1529 (E144)** moved checkout's reads into a function nested in the route. Its 403 and its check of
  the snapshot then read as the nested function's, and `405abe0b` failed both cases. `5eaa0797` made the
  unit a module-level function.
- **#1535 (F60)** moved resend-verification's read into `account_mail_service._issue_link`, and
  `e981dd50a` failed (CI run 40025627889). `ab3cda166` named the new site.

Each red push cost a CI cycle and one more paid `eval-baseline` draw, since every push that touches
`backend/app/` draws one. Before #1535's push this session ran only the backend gate, because no frontend
file had changed.

**Rule.** Before a push whose diff changes any file under `backend/`, its tests included, also run the
frontend unit suite from `frontend/`:

```bash
npm run test -- --run
```

At least 17 unit specs build a path into `backend/` and read its files, for parity checks, inventories
and contracts. They include `authPagesCopy`, `planLimitsLockstep`, `passwordRulesLockstep`,
`summaryStream.contract`, `contactValidationParity` and `legalTruth`, and `testHomesAllowlist` checks
where backend test files live. So a backend edit can fail one with no frontend file in the diff.

Run the whole suite, not a subset picked by grep: two selection patterns tried on 2026-10-23 each missed
specs that read backend files. The suite takes about four minutes in CI. In a worktree with no
`node_modules`, link the main checkout's for the run and remove the link afterwards.

**Gate.** Review-checked. CI's `frontend-tests` runs these specs on every pull request, so a miss never
reaches main; the rule saves the red cycle and its paid draw. A machine gate on the cost alone would make
`eval-baseline` wait for `backend-tests` and `frontend-tests` (`needs:` in `.github/workflows/ci.yml`),
so that a red unit test skips the paid run. That is a high-tier CI change, and founder row F55 already
holds how `eval-baseline` spends.

**Evidence.**
- #1529: `405abe0b`, then `5eaa0797`.
- #1535: `e981dd50a` (CI run 40025627889), then `ab3cda166`.
- `frontend/tests/unit/authPagesCopy.spec.tsx`: `EMAIL_VERIFIED_READS` and the nearest-`def` scan.
- This rule adds the unit step of the frontend gate in CLAUDE.md's Commands to the backend gate, for a
  backend change.
