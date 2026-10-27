# Load an e2e spec you changed before you push it: the typecheck leaves the tests out, and lint passes a duplicate declaration that stops the whole run

Date: 2026-10-27 · Area: testing / frontend e2e

**Context.** E220's second head (`665fa982`, #1686) added a `headerAt` helper to
`frontend/tests/e2e/header-covers-nothing.spec.ts`, which already declared one. The full frontend gate passed on that
head: `frontend/tsconfig.ci.json` excludes `tests/` and every spec, and `eslint .` reports no second `const` of one
name. Playwright then refused the whole run ("Identifier 'headerAt' has already been declared"): CI's e2e job stopped
after four seconds with no test run, in that spec or any other, and so did the local run. `8b30ef0e` dropped the
duplicate.

**Rule.** After you edit an e2e spec, load it before the push: from `frontend/`,
`npx playwright test --list <spec>` must list its cases, with no build or server needed. Better, run the changed cases
against a local build of the head first.

**Gate.** CI's e2e job, after the push: a spec that does not load fails it, and runs no other spec either. Nothing
before the push catches it, because the typecheck's CI config leaves the tests out by design.

**Evidence.** #1686: `665fa982` (the duplicate) and `8b30ef0e` (the fix); `frontend/tsconfig.ci.json`'s `exclude`.
