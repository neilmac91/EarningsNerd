**Verdict: NEEDS CHANGES.** The prompt diff does exactly what Codex 5958742492 authorized. The pre-registration misses or contradicts several of the decision's numbered requirements, so it should not be frozen as written.

Evidence notes: I read the decision verbatim through the public API and saved it at `/tmp/claude-0/-home-user-EarningsNerd/4aaef390-9924-5295-aa90-251d71b700b2/scratchpad/prompt-research/fidelity/codex.md`. Citations of the form `design.md:N` refer to the brief at `.../scratchpad/prompt-research/design.md`. No provider call and no GitHub write were made. In the worktree I only ran `git fetch`; it is still clean at `153cfc46`.

**What is faithful (checked):**
- **Prompt hashes.** I recomputed them on my own, with dummy non-calling credentials.
  - Main is `a88b6fb1` (5057 characters). The clause occurs once, at offset 2914.
  - Removing it gives `16457055` (5006 characters), which is arm B.
  - Inserting rule A gives `cd7a6208` (5367 characters). The rule starts at offset 2233, after the tool MUST (674) and before OUTPUT FORMAT (2595).
- **Content stays in scope.** There is no #1023 example and no edit to the `copilot_service.py:90` rule ("Every factual claim MUST be supported by a verbatim excerpt"). The byte-identity table covers the scorer, runner, golden set, baseline, flags, locked tests and floors (`design.md:186-199`). No merge happens, and the PR ends as a draft (`design.md:233,246`).
- **Trigger costs are correct.**
  - `ci.yml:3-6` uses the default `pull_request` types and pushes only to main, so a ready transition or a branch push does not re-run eval-baseline.
  - `copilot-eval.yml:20` skips drafts.
  - So only the draft opening triggers eval-baseline. Worst case is 0.19 + 3 × 0.1725 = 0.7075, under the 0.75 ceiling.
- **Run rules are covered.** These are present at `design.md:239-304`: three fresh runs of 18 attempts each, an absolute (not comparative) claim, inspecting Q1 first, no retry or replacement run, invalid runs stop the lane, a failed check stays a failure, the #1056 triage rule excluded, uncited figures reported separately, the MSFT advisory not made a threshold, and not-disclosed left unmeasured live.

## Issues (most severe first)

**1. HIGH: RUNBOOK aggregate evidence is missing from acceptance.** Step 6 of the decision says "Require all three runs and the RUNBOOK aggregate evidence".
- `RUNBOOK.md:817-818` says: "Acceptance still requires its separate full summary artifact against the sole unchanged baseline."
- The brief treats eval-baseline only as a cost (`design.md:243-244,299`).
- The TRUST veto (`RUNBOOK.md:888-890`) is folded into check 5's measurement (`design.md:265`), so check 5 is no longer the unchanged check from `copilot-tool-nonexecution-2026-09-30.md:271`.

Fix: add a separate row "R. RUNBOOK aggregate evidence", after checks 1–5 and with checks 1–5 left untouched, containing:
- (i) the eval-baseline run from opening the draft on the frozen head passes against the unchanged `baseline_scores.json`, and its artifact is retained. A red result means not qualified, with no rerun.
- (ii) every scored row has `score.fact_adjacency == 1.0` in each run and across all 54 rows.
- (iii) a statement that the rule makes no density or marker demand, so the `--runs 5` requirement in `RUNBOOK.md:891-896` does not apply.

**2. HIGH: the pre-registration file refers to things that can't exist when it is committed.** The text that goes into the frozen head contains `<HEAD_SHA>`, `<BRANCH>`, `PR #<N>`, "Exact-head review: <…>" and "Offline gate: <counts>" (`design.md:234,237,239`).
- Filling the review or gate results changes the head, which breaks the exact-head review required by step 3.
- The PR number exists only after the paid draft opening, which comes after "before any paid trigger" (step 4).

Fix: in the file, write "the commit containing this file". Put the head SHA, branch, file sha256, review verdict and comment id, and gate counts in the step-0 #1029 comment, posted before step 1. Post the PR number afterwards as a non-registration note. The independent review must cover the head that includes the pre-registration file.

**3. HIGH: the runtime-validity rule contradicts itself, and the backend freeze isn't coordinated.**
- The identity table requires "`source_sha` identical in Q1–Q3" (`design.md:220`). The precondition instead allows differing merge commits when `git diff --quiet -- backend .github` holds (`design.md:253`).
- The merge ref is recomputed at every ready transition (`design.md:328`). Frontend PRs #1042–1048, #1058, #1059 and #1064 are merging now; none touch `backend/` or `.github`, but they will change `source_sha`. Which rule applies would be chosen after seeing the data.
- #1050 changes `backend/requirements.txt` (OpenAI, PyJWT and Sentry bumps). Another Codex owner holds it, with a USD 1.00 reservation (#1029 comments 5960271054 and 5960418625). Merging it mid-window would invalidate Q2 and Q3.
- "Hold other backend merges" (`design.md:312`) names no mechanism. Steps 1 and 7 of the decision require no parallel backend release and coordination before freeze.

Fix: put the `git diff -- backend .github` tolerance in the identity table and drop "identical". Add to step 0: ask the named owners for a backend-merge freeze covering the window (the #1050 successors and the #1060 deploy owner), record their acknowledgement, and don't open the draft without it.

**4. MEDIUM: step 1 prerequisites of the decision are absent.** Step 1 says "First finish and record any outstanding actual #1036 deployment verification … reuse an already active successor if one exists."
- #1036 (`a541c3c8`) changed `backend/tests/unit/test_copilot.py`, so it deployed. I found no #1036 deploy receipt in `tasks/` at `153cfc46` or in the #1036 or #1029 comments; only #1056's revision 00434-nbg was verified (5959897697).
- #1060's own deploy receipt (it changed `copilot_service.py` and `copilot_scorers.py`) is still pending (5960505399).
- The brief names only #1065 (`design.md:312`).

Fix: add these as preconditions before branching:
- record #1036's deploy verification, or record explicitly that the 00434-nbg verification covers it, with run ids;
- the #1060 and #1065 deploy receipts;
- a recorded "no active prompt-candidate successor" check (at 21:09Z there was no open PR for it).

**5. MEDIUM: the spend section is incomplete.**
- (a) Step 5 of the decision requires every physical call and unknown charge to be counted for the automatic baseline too. The method given (`runner.log` `ai_call` lines, `design.md:290`) covers only the Copilot runs. For eval-baseline the brief just says "record its cost" (`design.md:244`); name the telemetry source and the unknown-cost count.
- (b) The spend rule runs only "before each ready transition" (`design.md:294`). Also apply it before step 1 as 0.19 + 3 × 0.1725 ≤ 0.75.
- (c) The 45-minute off-peak buffer rests on copilot-eval's 40-minute timeout (`design.md:292`). eval-baseline has no `timeout-minutes` (`ci.yml:254-264`), so base step 1's buffer on measured eval-baseline durations.
- (d) Before step 1, record the shared-ledger starting point: last posted remainder USD 7.712591 (5960408518), other reservations, and #1056's still unreconciled eval-baseline charge (5959159895). Then debit the 0.75 reservation.

**6. MEDIUM: there is no plan for keeping the raw run artifacts.** Step 5 says to retain every attempt, but the brief only puts results in comments (`design.md:248`). The eval-baseline artifact expires after 14 days (`ci.yml:397`). Fix: after each run, download the artifact and record the sha256 of the zip, `copilot-eval.json` and `runner.log` (the D20–D27 pattern, `tasks/pr-disposition-2026-09-30.md:50-58`), then keep a durable private copy.

**7. MEDIUM: wording A reaches beyond the authorized text.**
- (a) "a label joined to its value" is not in Codex's wording and is not limited to tables. It can suppress genuine contiguous MD&A quotations, which step 2 says to preserve (for example, ASML's "Net income for 2025 amounted to €9,609.4 million…", `design.md:123`). Each failure shape it targets is already caught by another clause (`design.md:112-115`).
- (b) "Quotation marks in your answer" is broader than the authorized "in answer prose". It literally covers the JSON string quotes in the citations and followups arrays (`copilot_service.py:118-137`), which brushes against "keep citation JSON requirements unchanged".
- (c) "state table figures without quotation marks" is stricter than "State figures without quoting reconstructed table cells". The brief discloses this only as "stricter than F" (`design.md:115`).

Exact fix: use this bullet, which is 58 words, ASCII, brace-free, and still a single block (removing it leaves `16457055`). It composes to `7722ac001d4e0970084fa39a6b8c58776d62c6334630576182d8b252843489b0` (5344 characters):

> - In your answer prose, quotation marks may enclose only one contiguous span copied verbatim from the filing, such as a sentence or phrase. Never quote a table row with cells left out or text with an ellipsis inside it; state table figures without quotation marks. When you say the filing lacks a metric, name it without quotation marks.

Also disclose (c) as deliberate in the pre-registration, and update the owner-test strings (`design.md:145`).

**8. LOW: the checks are labelled "verbatim" but need adapting.** The quoted text says "(every run, both runs)" and "18/18 across both runs" (`copilot-tool-nonexecution-2026-09-30.md:264,267`). Add a note that it is applied per run (9/9 draws), as Codex's "each qualification run" requires.

**9. LOW: the audit tool's exit code 2 is treated as a pass without saying so.** `prose_quote_audit.py:4-6` says exit 2 means "founder decides, never an automatic pass". The brief's "does not exit 1" (`design.md:264`) silently passes exit 2, which will always occur here (MSFT `uncited_figure_rows` and 20-F `tool_less_rows`). Cite the precedent policy (D14 and D17 at `pr-disposition-2026-09-30.md:44,47`: composed 0 and uncited answers 0 means PASS), and report the other exit-2 categories without thresholds.

**10. LOW: decisions left open in §5 invite choices made after seeing data.**
- Items 5 and 6 are already settled by the decision: step 5 says "Complete the predeclared set only while its validity/spend conditions permit", and step 6 says the checks are unchanged.
- Items 1, 3, 4 and 7 are routine implementation choices (CLAUDE.md: "Resolve routine implementation choices directly").
- Settle all of them in the pre-registration before freeze, and drop the "founder could decide otherwise" fork.

**11. LOW: there is no handback specification.** Add the step 7 list: frozen head, all three outcomes or the explicit stop, actual telemetry and unknowns, the exact-head review, normal gates, and remaining limitations. Also add step 3's "Preserve earlier failures and review findings", which means keeping this brief's review findings in the evidence folder.

**12. LOW: mapping and checking-tool precision.**
- Step 3 names specific offline controls. Map each to its owner test:
  - not-disclosed cost: `test_copilot_prose_quotations.py:1098`;
  - table fragments: `:483` and `:932`;
  - legitimate quotations: `:105-112`;
  - MSFT identity: the test driving `copilot_service.py:411-417` with a string `n`, which the brief should name.
- `g_precheck.py:14` prints only an 8-hex prefix and no length, so "sha256 `cd7a6208…`, 5367 chars, checked by `g_precheck.py`" (`design.md:215`) is in fact a prefix check. Say so, or check the full hash on `initial_messages[0]`.