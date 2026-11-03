# Compare the merge candidates two eval draws ran, not their heads, before calling their runtime unchanged

Date: 2026-11-03 (PB-02, #1955)   Area: evals / paid runs

**Context**: On #1955 the ready mark's `copilot-eval` draw (run 41609164901) went red on two provider timeouts, and
the chief predeclared one more full draw on a head whose only change was its evidence folder. Its preregistration
(`tasks/review-evidence/pb02-copilot-redraw-2026-11-03/PREREGISTRATION.md`) listed the runtime as unchanged. The check
behind that claim compared only the new head's `backend/`, `frontend/`, `docs/`, `lessons/` and `.github/` trees with
the first draw's head. But `copilot-eval.yml` and `ci.yml`'s `eval-baseline` both check out with `actions/checkout`
and no `ref:`, which on a `pull_request` event is the PR's merge ref, not its head. The first draw ran
`Merge ff15b23e into 86479c66`, and the re-draw (run 41613482231) ran `Merge ef786cb8 into 7523d61c`. Between those
bases main had changed `backend/requirements.txt` (#1945: pydantic, pydantic-core, stripe and posthog) and four facts
and EDGAR services (#1962), inputs that `copilot-eval.yml` names. The omission was disclosed before the result. The
chief then directed that the next verification record the exact merge candidate it executed and not be described as
an identical-runtime comparison.

**Rule**:
- A pull request's CI eval draws run its merge candidate: the head merged into main as main stands when the run checks
  out. Before a preregistration or a report calls two draws' runtime unchanged, compare their merge candidates' bases
  over the inputs the workflow names (its `paths:`, the requirements, `.github/ai-model.env`), not only the heads' trees.
- When main has moved between the draws, say so, and do not call them an identical-runtime comparison.
- Record each draw's executed merge candidate from its own log: `HEAD is now at <sha> Merge <head> into <base>`
  (`eval-baseline` also writes `source_sha=` to its `ci-execution.txt`).

Review-checked: AGENTS.md §4 writes no test for prose.

**Evidence**: #1955. The two draws: runs 41609164901 and 41613482231. The disclosure: issuecomment-6600366973. The
chief's direction: issuecomment-6601934314. The post-recovery verification recorded its merge candidate as this rule
says (`Merge 56a6b3eb into 285f494b`): `copilot-eval` run 41627782284 and `eval-baseline` job 125889420257, reported
in issuecomment-6602985697. `lessons/ops-copilot-eval-red-is-triaged-never-rerun.md` covers the draws themselves.
