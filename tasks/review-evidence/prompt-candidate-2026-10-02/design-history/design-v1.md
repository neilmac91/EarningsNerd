# Copilot prompt fix candidate: design brief

Read-only design work, 2026-10-02 ~21:00Z. Worktree `/home/user/wt/prompt-research`, detached at origin/main
`153cfc46`; `git status` was clean before and after. No provider call, no GitHub write.

Scratch tools in this directory:
- `compose.py` applies each source edit in memory and evaluates the edited `SYSTEM_PROMPT` f-string with the real module's globals. The hashes below are therefore the bytes a real edit would produce.
- `mkcand.py` builds a candidate file, which `svc_scope_check.py` then checks. The candidate file was deleted afterwards.

**Authorization (Codex, #1029 comment 5958742492):** exactly one candidate, made of (a) arm B's deletion and (b) a short contiguous-quotation rule for prose. Out of scope:
- citation JSON rules;
- decision F's boundary and floor (`_MIN_QUOTED_LEN = 8`, `copilot_service.py:512`);
- the citation floor of 24 (`provenance_service.py:31`);
- the scorer, runner, golden set, baseline, locked tests and flags;
- #1023's worked example;
- general prompt tuning.

---

## 1. The proposed `SYSTEM_PROMPT` diff

### (a) Arm B deletion, verbatim (`backend/app/services/copilot_service.py:122`)

```diff
-   after the citations line, including when all cited figures use tool markers. Example:
+   after the citations line. Example:
```

- The deletion is exactly `", including when all cited figures use tool markers"`: 51 characters, at offset 2914 of main's composed prompt. The clause occurs once.
- main `a88b6fb1de5b…` (5057 characters) minus the clause gives `164570555f40…`, which is arm B (5006 characters). This equals `str.replace(CLAUSE, "", 1)` and G stage 2's arm B (`tasks/copilot-tool-nonexecution-2026-09-30.md:291-293`).
- The sentence "If there are no filing-text markers, output []" (`:121`) stays. A tool-only answer is therefore still told to emit `[]`, which keeps `RUNBOOK.md:758-761` true and preserves acceptance check 1's basis.
- The five step-3 sub-bullet pins in `test_copilot_live_regressions.py:62-66` sit at `:124-130`, which this candidate does not touch.

### (b) The contiguous-quotation rule: three wordings

Design constraints that all three wordings follow:
1. **No #1023 content.** I read #1023's actual diff (PR #1023 files, hunk `@@ -77,7 +77,14 @@`). It rewrote the lead rule at `:90` ("Every factual claim MUST cite its own source: use the returned [F#] marker…"). It also added a figures-only directive: "Do not append a narrative cross-check or text citation solely to repeat them", with a worked answer, "Revenue was €10.0 million [F1] and net income was €2.0 million [F2]." Then use [] …". That run made 0 of 18 tool calls (`copilot-tool-nonexecution-2026-09-30.md:41`, `:155-160`). The candidate therefore:
   - does not edit `:90`;
   - says nothing about tools, `[F#]`, `[]`, tool-only answers or cross-checks;
   - contains no worked answer;
   - uses no golden-set figures.
2. **Hypothesis 1** (`:155-160`): wording that describes the shape of the finished answer made skipping tools look compliant. The rule therefore governs only quotation marks. It sits after every tool directive, never before or between them.
3. **The rule targets the composition, not figures as such.** Two genuine sentence quotations that carry figures publish today and must keep publishing (§2): BABA's "further increased by 3% to RMB1,023,670 million…" and ASML's "Net income for 2025 amounted to €9,609.4 million…". So the rule says "table figures", not "figures".
4. **Mechanics.** No `{` or `}` (the prompt is an f-string, `:84`). ASCII only, so the em dash stays the only non-ASCII character. Straight wording, with no curly quotes in the rule.
5. **Voice.** It mirrors step 3's own vocabulary ("contiguous span", "verbatim", "cells", "ellipsis", `:124-128`) and the RULES bullet style, with a `\` continuation in the source.

**A. RULES bullet at the end of RULES**, after the `[F#]` bullet (`:106-111`) and before `OUTPUT FORMAT` (`:113`). 63 words, 361 characters. *Recommended.*

```
- Quotation marks in your answer may enclose only one contiguous span copied verbatim from the filing, such as a sentence or phrase. Never quote a table row with cells left out, a label joined to its value, or text with an ellipsis inside it; state table figures without quotation marks. When you say the filing lacks a metric, name it without quotation marks.
```

**B. Sub-bullet under OUTPUT FORMAT step 1** (`:114-115`), indented like step 3's sub-bullets. 59 words.

```
   - In the prose, put quotation marks only around one contiguous span copied verbatim from the
     filing. Never quote a table row with cells left out or a label joined to its value, and never
     put an ellipsis inside a quotation; state table figures without quotation marks. When you say
     the filing lacks a metric, name it without quotation marks.
```

**C. Split.** The bullet from A without its last sentence (50 words, same place), plus the not-disclosed placeholder (`:143`) extended to:

```
<one sentence stating what is missing and why this filing would not contain it; name the missing metric without quotation marks>
```

| | A (recommended) | B | C |
|---|---|---|---|
| Composed sha256 | `cd7a62086778b2a47c9d6f7d8af5e7a4b6c910ee08a50223486d35ccc6e204a7` | `21a837dce527…` | `dc1cd0cb2934…` |
| Characters / bytes | 5367 / 5391 | 5365 / 5389 | 5343 / 5367 |
| Rule block(s) removed → `16457055` | yes (one block) | yes | yes (two edits) |
| Rule offset vs. the tool MUST (674) and OUTPUT FORMAT | 2235: after all tool directives | 2458: inside the output-shape steps | 2235, plus the not-disclosed template |
| Covers the not-disclosed sentence | yes, by the conditional sentence | weakly: step 1 is "prose", and the not-disclosed block says "do NOT write prose" (`:141`) | yes, at the template itself |
| Step-3 pins intact; clause gone | yes | yes | yes |

**Why A:**
- **Authority.** It sits in RULES, at the same level as `:90` ("…verbatim excerpt quoted directly from the filing"), the directive that plausibly invites prose quoting. `lessons/arch-edit-causal-directive-add-example.md:7` warns that weaker-placed caveats lose to stronger nearby directives, and scope forbids editing `:90`.
- **Hypothesis 1.** It leaves the OUTPUT FORMAT steps, where the clause effect lived, unchanged apart from the deletion. B adds new answer-shape text in exactly that region.
- **One contiguous block.** The identity proof is simple: candidate minus BLOCK equals arm B, and arm B plus CLAUSE equals main.
- **Scope of "answer".** "Quotation marks in your answer" reaches the prose and the not-disclosed sentence. It does not literally reach the JSON string delimiters of the citations and followups arrays; "you write" would have.
- **The absence clause is conditional** ("When you say the filing lacks a metric…"). It does not invite omission announcements, which `:100-102` forbids. If reviewers still see tension with `:100-102`, **C** is the fallback, because it moves that clause into the not-disclosed template.

**Cache cost is the same for all three.** `messages[0]` precedes the filing context (`:349-350`), so any system-prompt edit misses the provider prefix cache for the whole context. B1's cold first run (184,219 miss tokens) is the expected cost whatever the offset. The insertion offset changes only about 100 tokens per first draw.

**Trim option.** Dropping "such as a sentence or phrase" brings A to 57 words. I do not recommend it: that phrase is the explicit signal that genuine quotations are still allowed.

**Source form of A** (simulated; `svc_scope_check.py`: 120 of 120 non-prompt top-level statements are AST-identical):

```diff
@@ -111,0 +112,4 @@
 filing-text excerpt marker ([1], [2], ...) backed by a verbatim excerpt — never an [F#] marker.
+- Quotation marks in your answer may enclose only one contiguous span copied verbatim from the \
+filing, such as a sentence or phrase. Never quote a table row with cells left out, a label joined \
+to its value, or text with an ellipsis inside it; state table figures without quotation marks. \
+When you say the filing lacks a metric, name it without quotation marks.
@@ -122 +126 @@
-   after the citations line, including when all cited figures use tool markers. Example:
+   after the citations line. Example:
```

Candidate `copilot_service.py` sha256 begins `7fc668aed12df8d4`; main's begins `7262596ebd09c830`. Hash the `copilot_service.py` on the real head before freezing; it should match `7fc668aed12df8d4` if the edit is byte-exact.

---

## 2. Failure and legitimate shapes against rule A

Sources: `failure_shapes.md` §1–3, `rows.json` and `rows_pre.json`. F's predicates are at `copilot_service.py:881-902`; its ellipsis regex is at `:508`.

| Retained failure shape | Where | F verdict today | Clause of A that addresses it |
|---|---|---|---|
| Label plus one cell, other cells removed: `"Total net sales 32,667.3"`, `"Net income 9,609.4"` (7 rows, 13 spans) | ASML A1 d0, C1 d0, C2 d0/d2, B1 d1/d2, B2 d2 | `quotation_not_in_source` | "Never quote a table row with cells left out, a label joined to its value"; and "state table figures without quotation marks". Three independent hooks |
| Ellipsis or elision inside a quotation: `"Total net sales 28,262.9 ... 32,667.3"`, `"Revenue ... 996,347"` (4 rows, 6 spans) | ASML C1 d1/d2; BABA viewed C2 d1, B2 d1 | `elided_quotation` | "or text with an ellipsis inside it"; also "cells left out" and "state table figures without quotation marks" |
| Label plus value where the source has no separator: `"Total net sales 416,161"` (source reads `Total net sales416,161`) | 36870677818 AAPL d2 (pre-G) | `quotation_not_in_source` | "copied verbatim"; "a label joined to its value"; "state table figures without quotation marks" |
| Near-miss that F lets through: `"Net income 7,571.6"` (label plus first cell, the wrong year for the claim) | C1 ASML d0 | verified (passes) | "state table figures without quotation marks" and "a label joined to its value". The rule is stricter than F here, deliberately |
| Bare cell under the floor: `"9,609.4"`, `"996,347"` | C1 ASML d0; BABA viewed C2 d0, B2 d2 | exempt (7 < 8) | "state table figures without quotation marks". Complying loses nothing, because the figure is still stated, just without quote marks |
| Quoted absent-metric name in a not-disclosed reason (`"Adjusted EBITDA"`, `"iPhone unit sales"`) | not observed live (no not-disclosed golden question); pinned at `test_copilot_prose_quotations.py:1094-1109` and `:962-986` | withheld (8 characters or more) | "When you say the filing lacks a metric, name it without quotation marks." The live effect is **unmeasurable**: the golden set holds no live not-disclosed case (`copilot_golden_set.json` `pending_cases`) |
| Paraphrase in quotes | none retained | would be `not_in_source` | "one contiguous span copied verbatim from the filing" |

| Legitimate shape (publishes today) | Example | Why A preserves it |
|---|---|---|
| Contiguous sentence fragment carrying figures | BABA `"further increased by 3% to RMB1,023,670 million (US$148,401 million) in fiscal year 2026"` (5 G rows plus 36800236360) | One contiguous span, copied verbatim, from a sentence and not a table: allowed under "such as a sentence or phrase" |
| Contiguous MD&A sentence | ASML B2 d1 `"Net income for 2025 amounted to €9,609.4 million, representing 29.4% …"` | Same as above |
| Quoted line-item label | `"Gross margin,"` (AAPL C1 d0) | A phrase with no value joined to it |
| Labels quoted, figures outside the quotes | `shows "Total net sales" of €32,667.3 million and "Net income" of €9,609.4 million` (36870677818 ASML d0) | This is exactly the shape A asks for |
| Short label | `"Revenue"` (13 BABA-viewed rows) | A phrase; also exempt from F |
| Unquoted cross-check, the target shape | A1 ASML d2 `shows total net sales of 32,667.3 and net income of 9,609.4 (in € millions) for 2025 [3]` (also A2 d1, C2 d1, B1 d0) | "state table figures without quotation marks". A says nothing against the cross-check itself, which keeps Codex's quotation-only scope |
| Edge ellipsis | `"...amounted to €9,609.4 million, representing 29.4%…"` (pinned to publish, `test_copilot_prose_quotations.py:110`) | "inside it" names only interior ellipses, matching F's edge stripping (`:507`) |
| Unquoted not-disclosed reason | `This 10-K does not disclose forward revenue guidance.` (`test_copilot.py:597-611`) | This is exactly the shape A asks for |

---

## 3. Offline verification plan

**Prompt-byte pins: no STOP.**
- The only test that pins prompt text is `test_copilot_live_regressions.py:59-66`. It is an ordinary owner test (#808 precedent `f0a81fff`), not a locked one. Locked tests are listed at `CLAUDE.md:79` (rule 6) and `docs/summary-quality-improvement-plan.md:130`.
- No test names `SYSTEM_PROMPT` or any prompt hash.
- Its five substrings sit at `:124-130`, which A does not touch. All five are present in A, B and C (`compose.py`).

**Test change: extend the existing owner, with no new function or file.** Add these to `test_contiguous_citation_instruction_reaches_actual_service_messages`, reading `messages[0]['content']` as it already does:

```python
assert ', including when all cited figures use tool markers' not in instruction   # G stage 2 cause
assert 'If there are no filing-text markers, output []' in instruction           # namespace rule kept
rule = 'Quotation marks in your answer may enclose only one contiguous span copied verbatim from the filing'
assert instruction.count(rule) == 1
assert 'state table figures without quotation marks' in instruction
assert 'When you say the filing lacks a metric, name it without quotation marks.' in instruction
```

Optional, if reviewers want it: assert the placement, `find('you MUST call the provided') < find(rule) < find('OUTPUT FORMAT')`.

- I checked these assertions in memory:
  - they pass on candidate A (`cd7a6208`);
  - they fail on main (`a88b6fb1`: clause present, no rule);
  - they fail on arm B (`16457055`: no rule).
- `_build_messages(...)[0] == {'role': 'system', 'content': candidate}` holds.
- **Do not pin the full sha256 in a unit test.** It would only mirror the implementation (`AGENTS.md:60-61`), and the pre-registration carries the hash instead.
- **Do not add a test to the decision-F owner.** Rule 12 (`CLAUDE.md:100`) is already enforced by F's withholding. Both not-disclosed shapes are already pinned: unquoted publishes (`test_copilot.py:597-611`), quoted is withheld (`test_copilot_prose_quotations.py:1094-1109`). `AGENTS.md:60` says not to add a second test for a gated rule.
- Keep `test_copilot_prose_quotations.py` byte-identical (sha256 begins `3612d6bd`). Its docstring at `:1097-1101` stays true: the follow-up is gated by the RUNBOOK.

**Mutation proofs** (run against the owner test file only, record the result, then restore):

| Mutation | Expected result |
|---|---|
| M1: restore the 51-character clause | fails `clause absent`; checked in memory, composed hash `81f826dd` |
| M2: delete the rule block | fails `rule count == 1` and the following assertions; checked in memory, `26ec5d74` |
| M3 (only if the placement assertion is added): move the block to just after `:90` | fails the placement assertion |
| M0: unmutated tree | the five original pins still pass |

**Gates on the frozen head** (from `backend/`, with provider keys unset):
- **RUNBOOK offline set** (`RUNBOOK.md:808`): the five Copilot files.
- **Every other Copilot, provenance and verbatim owner**: 15 files, which passed 1495/1495 on a placeholder-rule simulation (prompt-and-owners finding).
- **Full gate** (`AGENTS.md:99-101`): `ruff check . && bandit -r app -ll && python -m pytest`.
  - Expected test count: 5558 at `153cfc46`, or 5565 after #1065 (`returns-current-period-guard` README, "Gate"). The candidate adds assertions but no test cases.
  - **Disk is the blocker.** `/` has 83 MB free (100%). An earlier full-suite simulation died with ENOSPC. Free space before running the gate.

**Identity and scope proofs.** Commit a small `prompt_identity.py` in the evidence folder before any spend. It should do the following:
1. Import the head's `copilot_service`. Assert that `_build_messages(...)[0]['content'] == SYSTEM_PROMPT`, its sha256 is `cd7a6208…` and its length is 5367.
2. Assert that `SYSTEM_PROMPT.replace(BLOCK, '', 1)` hashes to `16457055`.
3. Assert that inserting CLAUSE after "output []\n   after the citations line" yields `a88b6fb1`.
4. Assert `cs._MIN_QUOTED_LEN == 8` and `provenance_service._MIN_VERIFIABLE_LEN == 24`.

`BLOCK` is the 361-character string beginning `'\n- Quotation marks in your answer'` (exact `repr` in `compose.py` output).

**Byte-identical to base.** Use `git diff --exit-code <BASE> <HEAD> -- <path>` and a sha256 table. Prefixes at `153cfc46`, from the gating-and-acceptance reader; re-hash them at the post-#1065 base, since #1065 touches none of these paths.

| Component | Paths and sha256 prefixes |
|---|---|
| Scorer | `evals/copilot_scorers.py` `4b70c52f09bf8bec` |
| Runner | `copilot_runner.py` `f35ecd3cb68099e7`; `copilot_bootstrap.py` `abb2ba4fb57664cd`; `copilot_schema.py` `b6650382ee809b76` |
| Golden set | `copilot_golden_set.json` `15f8e7f92f934a5b`; `copilot_sources.json` `8960e1bbeaa95680` |
| Baseline | `baseline_scores.json` `6ca0f4a8654b4911`; `golden_set.json` `f165468c3161a5de`; `regression_gate.py` `ed8d08b8566cd903`; `evals/baselines/` (6 files) |
| Flags and model | `.github/ai-model.env` `95c580400a7ff145`; `app/config.py` `bccbaf90c9e67794`; `ci.yml` `a73b7757d8ec3867`; `copilot-eval.yml` `bb7ecee1b16be7d9` |
| Model-facing tool path | `copilot_tools.py` `442ae5f147272bfe`; `ai/copilot_chat.py` `2f7ca99c904e4509`; `citation_markers.py` `1042db3962a8e694` |
| Citation floor | `provenance_service.py` `b7af6468e21e8fcc` |
| F boundary, F floor, quote marks, `_build_messages`, resolver | `svc_scope_check.py <base> <head>` must print `identical: True (120 vs 120)`, with the only diff being the two hunks above |
| Locked tests | `test_summary_stream_contract.py` `4b10582387ed68ad`; `fixtures/summary_stream_frames.json` `5dcc29d7e482ca0f`; `support/summary_stream_harness.py` `6b6d4c3a2e971825`; `test_summary_stream_heartbeat.py` `26f454699e00db07`; `test_auth_flow.py` `4a927487d44c7754`; `test_auth_cookies.py` `1299c8444c3e8955`; `test_background_generation_characterization.py` `5a6b7024605bfe71`; `test_stripe_webhook.py` `ca02207aaa71e884`; `test_subscription_webhook_sync.py` `a00853b94d4bb712` |
| Measurement tools | `f_attribution.py` `a88162d7776dc3d0`; `prose_quote_audit.py` `8716c4729e1a8f15` |

**Allowed diff:** `git diff --name-only <BASE> <HEAD>` lists exactly these files:
- `backend/app/services/copilot_service.py`
- `backend/tests/unit/test_copilot_live_regressions.py`
- the new `tasks/` pre-registration file and evidence folder
- `tasks/todo.md` (optional)

No `backend/evals/**` change is needed:
- `RUNBOOK.md:758-761` stays true, because "If there are no filing-text markers, output []" remains.
- Use a new pre-registration file rather than editing `tasks/copilot-tool-nonexecution-2026-09-30.md`, which #1065 edits at `:169`.

**Identity table for the pre-registration:**

| Item | Required value (every row of every run) | Checked by |
|---|---|---|
| System prompt | sha256 `cd7a62086778b2a47c9d6f7d8af5e7a4b6c910ee08a50223486d35ccc6e204a7` (prefix `cd7a6208`), 5367 characters | `g_precheck.py` (`tasks/review-evidence/g-stage1-2026-10-02/g_precheck.py:13-23`) |
| Contexts (`initial_messages[1:]`) | AAPL `db033e5a13d4`, TSLA `3babd16a34cf`, MSFT `b552352b2af3`, BABA native-2026 `6db10712e780`, BABA viewed-2025 `be263a712053`, ASML `09e857dbd1b9` | `g_precheck.py` |
| Tool schema | `b6958973` | `g_precheck.py` |
| Generation options | `{"max_tokens": 2400, "model": "deepseek-flash", "temperature": 0.2}` | `g_precheck.py` |
| Report fields | `golden_sha256` `15f8e7f9…`; `requested_model` deepseek-flash; `requested_flags` `{COPILOT_MAX_TOKENS: 2400, USE_STATEMENT_FINANCIALS: true}`; `planned_attempts` 18; runs 3 | read from `copilot-eval.json` |
| Runtime | `source_sha` identical in Q1–Q3 | read from `copilot-eval.json` |
| Fingerprint | `aeb56401…` expected. Any other value is **reported, not invalid**. A stable fingerprint does not prove unchanged provider state (#1065's wording correction) | `grep -o '"system_fingerprint": *"[^"]*"' runner.log \| sort \| uniq -c` (the method of `g2_precheck.txt`; `g_precheck.py` prints `{}` for fingerprints) |

---

## 4. Draft pre-registration (commit in the frozen head before any paid trigger)

> **Copilot prompt candidate: qualification pre-registration.** Authorized by Codex's decision on
> #1029 (comment 5958742492, 2026-10-02 18:27Z, under the founder's delegation). Ceiling: **USD 0.75
> in total, including the automatic eval-baseline and ready jobs; hard stop.** No merge and no
> production prompt release follow from this measurement. These are absolute qualification runs:
> historical A/B results (G stages 1–2) are context only, and no comparative effect is claimed.
>
> **Candidate identity.**
> - Base: main `<BASE_SHA>` (after #1065 merged and its deploy was verified). Head: `<HEAD_SHA>` on `<BRANCH>`, PR #`<N>`, opened as a draft.
> - The diff is exactly the two `copilot_service.py` hunks: arm B's 51-character deletion at main offset 2914, and BLOCK (361 characters) inserted after "never an [F#] marker.". It also contains the owner-test assertions and `tasks/` only.
> - Composed `SYSTEM_PROMPT` sha256 is `cd7a6208…` (5367 characters). Removing BLOCK gives `16457055` (G's arm B), and adding back the clause gives `a88b6fb1` (main). Proof: `prompt_identity.py` (sha256 `<…>`).
> - Exact-head review: `<three lenses, verdict, comment id>`. Offline gate: `<counts>`.
>
> **Runs.** Q1, Q2 and Q3 are three fresh `copilot-eval` runs, each `--runs 3` (6 questions × 3 draws = 18 attempts), on the unchanged head `<HEAD_SHA>`. Each run starts only after the previous one completes and has been inspected, off-peak.
>
> **Trigger sequence:**
> 0. *(free)* Push the branch without a PR. Post a #1029 comment that names `<HEAD_SHA>` and this file's sha256.
> 1. *(about 0.18)* Read the balance and the ledger, then open the PR as a **draft**. This runs `ci.yml` with `eval-baseline` once; `copilot-eval` is skipped while the PR is a draft (`copilot-eval.yml:20`).
> 2. After `eval-baseline` completes, record its cost, read the balance, apply the spend rule, then mark the PR ready. This starts **Q1**.
> 3. After Q1 completes, inspect it (validity, cost and checks 1–5) **before continuing**. Then convert to draft (free), read the balance and ledger, apply the spend rule, and mark ready. This starts **Q2**.
> 4. Repeat step 3 for **Q3**. Then convert the PR back to draft.
>
> Never push, rebase, close or reopen the PR during the window, and never toggle it while a run is in progress (`cancel-in-progress`, `copilot-eval.yml:13-15`). Results go in PR or #1029 comments, not in commits to this branch.
>
> **Validity precondition** (checked on every row of each run before any rule is applied):
> - the identity table above, checked with `g_precheck.py` unchanged;
> - the report fields;
> - `source_sha` identical across Q1–Q3. No other backend merge to main during the window. If the merge commits nevertheless differ, the run is valid only if `git diff --quiet <s1> <s2> -- backend .github` holds.
>
> Any mismatch, a cancelled run or a missing artifact makes the run **invalid**: stop, record, apply no rule, and run no replacement without new authorization. Fingerprints are reported.
>
> **Acceptance: checks 1–5, applied to EACH run** (verbatim from `tasks/copilot-tool-nonexecution-2026-09-30.md:264-271`):
>
> | # | Check (verbatim) | Measured by | Q1 | Q2 | Q3 |
> |---|---|---|---|---|---|
> | 1 | MSFT string-ID rejections: 0 (no withheld MSFT row; no string or `F#` identity in the citation array). | MSFT rows have no `error`. Every object in the declared `===CITATIONS===` JSON in `tool_trace.candidate_deltas` has a positive integer `n`. No "Invalid citation declaration" reason | | | |
> | 2 | AAPL/TSLA/MSFT tool use: every draw (18/18 across both runs). | `g_decide.py`: `TTT` for each 10-K question, i.e. 9/9 per run and 27/27 overall | | | |
> | 3 | ASML: no stitched or unverified citation excerpt, no withheld ASML row, and no composed prose quotation; redundant cross-check citations are counted and reported. | 3/3 ASML rows completed and scored, with `unverified_excerpts == []` and `citation_faithfulness == 1.0`. `f_attribution`: 0 ASML F-withheld. `prose_quote_audit`: 0 composed on ASML. The cross-check count uses the method below | | | |
> | 4 | Composed-quote audit clean: 0 composed or absent quotations across all rows. | `f_attribution.py --out …` exits 0, with 0 UNEXPLAINED and 0 F-withheld rows on any surface (answer, reason, chip). `prose_quote_audit.py` does not exit 1. The floor is decision F's: 8 or more normalized characters, or any interior ellipsis | | | |
> | 5 | Formal acceptance 18/18 with 0 errors, and 0 answers without any citation; uncited figures reported. | `summary` 18/18/18, `errors` 0, `accepted` true, `failures` []. Fact adjacency is 1.0 on every row (the RUNBOOK TRUST veto, `RUNBOOK.md:888-890`). `prose_quote_audit` `uncited_answer_rows` = 0 | | | |
>
> **Uncited figures are reported separately**, as the sum of `score.uncited_figures` per run and per question. The existing MSFT advisory (1 per draw) is reported and not made into a threshold.
>
> **Redundant cross-check method** (declared now, with its script committed in the evidence folder):
> - **Published rows:** on each row with non-empty `tool_results`, count the final citations whose `section_ref` does not start with `XBRL`.
> - **Withheld rows:** count the integer-`n` objects in the declared JSON.
> - **List:** each excerpt, and whether it restates a figure that carries an `[F#]` chip on the same row.
>
> **Reported as context, outside the rules:**
> - 20-F tool use, from `g_decide.py`: question-runs and draws;
> - every quoted span, classified as verified, sub-floor, or table figure in quotes;
> - non-F withholds;
> - not-disclosed rows (expected 0; this case is unmeasured live);
> - per-run cost from `copilot_cost_runnerlog.py`, including cache-miss tokens;
> - fingerprints;
> - elapsed time.
>
> **Outcome.**
> - **Qualified:** all three runs are valid and each passes checks 1–5.
> - **Not qualified:** any check fails in any run. A failed quality check does not stop the predeclared set while validity and spend permit, but it remains a failure. No retry, selective rerun, replacement run or silent candidate edit. Diagnostic withhold reasons do not turn withheld rows into passes, and the #1056 triage rule (`RUNBOOK.md:869-882`, condition 2) does **not** apply, because this PR changes model-facing bytes.
> - **Incomplete:** a validity or spend stop. Report the early stop.
>
> **Spend.**
> - Before each paid trigger, read the actual DeepSeek balance and the current shared ledger.
> - Count every physical provider call, including withheld and error rows and unknown charges, from `runner.log` `ai_call` lines.
>
> **Off-peak.** Trigger only outside 01:00–04:00 and 06:00–10:00 UTC, Monday to Friday (`llm_pricing.py:25`), and never within 45 minutes of a peak start (the job timeout is 40 minutes).
>
> **Spend rule (budget risk stops the lane):** before each ready transition, stop unless
> spent-so-far + remaining runs × USD 0.1725 ≤ 0.75. USD 0.1725 is the off-peak cost of one run with no cache hits.
>
> | Item | Measured basis | Expected | Conservative | Off-peak worst |
> |---|---|---|---|---|
> | eval-baseline (opening the draft) | 0.173515–0.181062 off-peak (8 runs) | 0.181 | 0.19 | 0.19 |
> | Q1 (cold prefix) | B1 0.033333 | 0.033 | 0.04 | 0.1725 |
> | Q2, Q3 (warm) | 0.005022–0.007807 (18 runs) | 0.008 each | 0.04 each | 0.1725 each |
> | **Total** | | **≈ 0.23** | **≈ 0.31** | **≈ 0.71 (< 0.75)** |
>
> Peak pricing could reach about 1.40 with no cache, so a peak trigger is forbidden. A red check is recorded and never re-run.

---

## 5. Risks and decisions needed before freezing

**Decisions:**
1. **Wording.** A is recommended; C is the fallback if reviewers see tension between A's absence sentence and `:100-102`. A is 63 words against Codex's "SHORT"; it trims to 57 by dropping "such as a sentence or phrase", which I do not recommend.
2. **Base and γ.** #1065 (γ) moves `backend/app` (`markdown_render.py`, `summary_versioning.py`) and edits `tasks/copilot-tool-nonexecution-2026-09-30.md:169` and `tasks/pr-disposition-2026-09-30.md`. It does not touch `copilot_service.py` or the owner test. Cut the candidate from post-γ main after γ's deploy is verified, and hold other backend merges until Q3 completes. Otherwise `source_sha` and the merge base move.
3. **Test footprint.** Choose between the four to five assertions above and the minimum (clause-absent plus one rule-presence assertion), given `AGENTS.md:60-61`. Also decide whether to include the placement assertion.
4. **Pre-registration custody.** The proposal is a `tasks/` file inside the frozen head plus a #1029 comment naming the head SHA before the draft opens. Both need the lane's GitHub write.
5. **Continue after a failed run?** Codex's text implies runs 2 and 3 still execute after a quality failure, at about USD 0.016 extra. Confirm this, then state it in the pre-registration.
6. **20-F tool use is context only.** Checks 1–5 could pass with 20-F tool use back at arm-A levels, because tool-less ASML draws never quote (0/59). The candidate would then "qualify" without fixing its motivating defect. The proposal is to report it prominently with no threshold, per Codex's "unchanged checks" and "no comparative claim". The founder could decide otherwise.
7. **Draft/ready toggles.** `gh` is not installed. Confirm the mechanism, for example a GitHub MCP `update_pull_request` draft flag, before step 1.

**Risks:**
- **Hypothesis 1 recurrence.** "state table figures without quotation marks" could read as license to take figures from the excerpt instead of calling tools. Mitigations: the rule's position after every tool directive, and no mention of tools or markers. Check 2 covers the 10-K side; 20-F tool use is visible only as context (decision 6).
- **Conserved-fabrication lesson** (`arch-edit-causal-directive-add-example.md:7`). Suppressing quoted cross-checks may move the model to other modes: stitched citation excerpts (the #1021 KPI-tile shape, a non-F withhold) or more redundant text citations. Check 3 and the context report measure all modes.
- **Small denominators.** Failures concentrate on about 6 tool-using ASML and BABA-viewed draws per run. A clean three-run pass bounds the composed-quote rate at roughly ≤ 15% per relevant draw over about 18 draws, or ≤ 5.6% per row over 54 rows (rule of three). Do not overstate it.
- **Not-disclosed path.** The absence clause cannot be validated live; offline pins exist only for F's behaviour.
- **Mechanics hazards:**
  - any push, close/reopen or rebase adds an `eval-baseline` (about 0.18) and changes the head;
  - toggling during a run cancels it;
  - an evidence commit to the branch costs one more `eval-baseline`.
- **Main mid-window.** `GITHUB_SHA` is the PR merge ref, which is recomputed at each `ready_for_review`.
- **Disk.** 83 MB free, so the full backend gate will ENOSPC until space is freed.
- **Cache.** If DeepSeek evicts the prefix between runs, each run is cold. That is still within budget off-peak (≈ 0.71 worst case), but leaves little margin.
