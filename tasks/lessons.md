# Lessons

## 2026-06-11 — Adjacent-line edits conflict on merge
While draining the dependabot queue: assumed PRs touching *different lines* of
`backend/requirements.txt` could merge back-to-back without conflicts. Wrong —
git's 3-way merge conflicts when hunks fall within ~3 lines of each other
(context window), not only on identical lines. PR #224 (pydantic, line 4)
conflicted after #222 (python-multipart, line 3) and #223 (email-validator,
line 6) merged.

**Rule:** treat any two PRs editing the same file within a few lines of each
other as conflicting; plan serial merge + rebase between them. Only file-level
disjoint PRs are safely parallel.

## 2026-06-16 — Backend CI runs bandit, not just ruff
The `backend-tests` CI job runs `bandit -r app -ll` as a gate. I verified locally with
ruff + pytest only, so a `hashlib.sha1()` call (legitimately required by the HIBP
k-anonymity protocol) tripped bandit B324 (weak hash, High) and failed CI on the first
push. Fix was `usedforsecurity=False` (bandit's own suggested remedy + semantically correct).

**Rule:** before pushing backend changes, run the full local gate — `ruff check .` AND
`bandit -r app -ll` AND `pytest` — not just ruff + pytest. For intentional weak-hash use
(SHA-1/MD5 required by an external protocol), pass `usedforsecurity=False`.

## 2026-06-16 — Verify against the actual code before "implementing" a plan item
While executing the auth/privacy plan I almost rebuilt analytics consent-gating, the
Privacy Policy, and the GDPR export/delete UI — all three already existed and were
well-built (`posthog-provider.tsx` gates on consent; `/privacy`; `/dashboard/settings`).
The audit/plan flagged them as gaps from a distance; the code said otherwise.

**Rule:** re-read the relevant files immediately before implementing any plan item, even
one the plan marked "missing". Confirm the gap is real before writing code — re-implementing
working code is wasted effort at best and a regression risk at worst.

## 2026-06-23 — A theme/token migration is app-wide, not "the page in the screenshot"
Adopting the new design system, I converted the landing page + chrome and called it done. The
user then found the *same* class of issues (legacy mint/emerald/`primary`/blue/sky/teal as brand,
unthemed surfaces) on Contact, Compare, Pricing, Search — and a codebase sweep surfaced ~37 more
files (compare/result, the copilot workspace, charts, modals, auth/legal pages). They only came to
light page-by-page via the user's screenshots.

**Rule:** treat a design-token/theme migration as **app-wide by default** (public *and*
authenticated). Enumerate the blast radius up front with a repo-wide grep for the legacy tokens and
make that grep the done-gate — never scope to the page that prompted the change. (Conventions +
the grep live in `frontend/DESIGN_SYSTEM.md`.)

## 2026-06-23 — Don't set global element-level colors that fight the surface
A global `h1–h6 { color: var(--heading-color) }` (warm brown in light) painted brown ink on the
always-dark hero when the site was in light theme — the "brown heading" bug. Element-level global
colors override the color a heading would otherwise inherit from its (dark) surface.

**Rule:** never set a global element-level *color* that surfaces opt out of. Keep global rules to
non-conflicting properties (font-family) and give each heading an explicit theme-pair color.

## 2026-06-23 — Theme-paired ≠ readable; check luminance against the actual background
A CTA/card used `bg-brand-weak` (#ECF2EE) as its fill on the cream page (#F4F3EE) — a ~1.02:1
surface contrast (brand-weak is actually *darker* than cream), so the card was invisible. It was a
valid token and a valid dark pair, but unreadable.

**Rule:** for surfaces, verify the **luminance delta vs the background it sits on**, not just that a
token exists. Lift cards with a *lighter* fill (`panel-light`) + a soft `shadow-e*`; brighten on
hover, never darken. `brand-weak` is an accent/tint, not a card fill.

## 2026-06-23 — Reserve loud status colors for genuine status
Mapping `StateCard`'s default `info` variant to the blue `info` token turned every guidance box
(e.g. "Start a comparison") loud blue — off-brand against the sage/slate identity.

**Rule:** brand sage/slate is for actions/accents; loud status colors (blue/green/red) are for real
state messages. A default guidance/empty-state container should be subdued or brand-tinted.

## 2026-06-23 — Green CI ≠ correct visuals; eyeball both themes
Every visual regression this round (brown heading, clashing gradients, invisible cards, blue info
box) passed typecheck/lint/build/tests and was caught only by the user looking at the preview.

**Rule:** for any visual/theme work, "tests pass" is necessary but not sufficient. Review the
deployed preview in **both light and dark** (or get a preview review) before declaring done.

## 2026-06-23 — A frontend gate is not a gate; enforce access server-side
While planning the closed beta I assumed `WAITLIST_MODE` kept the public out. It does not: it's read
**only** in `frontend/middleware.ts` (redirects `/`→`/waitlist`), while the backend register endpoint
(`backend/app/routers/auth.py:608-676`) accepts **anyone** — no allowlist, no invite check. Flipping
`WAITLIST_MODE=false` would have silently opened registration to the entire internet. The "gate" was
cosmetic; a curl to `/api/auth/register` walks straight past it.

**Rule:** any access/gating requirement (waitlist, invite-only, beta cohort, role) must be enforced
in the **backend** at the mutation endpoint — the frontend middleware/redirect is UX only and is
trivially bypassed. Before trusting an existing gate, grep for where the *server* validates it; if the
check lives only in `middleware.ts`/route guards, treat the resource as ungated.

## 2026-06-24 — Don't run schema-altering migrations in the serving container's startup path
To make deploys "self-safe" I added a startup migration runner that applied `migrations/*.sql` in the
FastAPI lifespan. It broke the prod deploy: `ALTER TABLE users ADD COLUMN is_beta` needs an
`ACCESS EXCLUSIVE` lock on `users`, but during a Cloud Run **rolling deploy the old revision is still
serving** and holds `AccessShare` locks on `users` — so the ALTER blocked/timed-out and crashed the
new revision's startup ("failed to start and listen on PORT within the timeout"). CI never caught it:
CI runs on **SQLite**, where the Postgres-only runner is skipped, so the PG path was completely
unexercised. (Prod stayed up — Cloud Run keeps the last healthy revision when a new one fails.)

**Rule:** never run schema-altering DDL (ADD COLUMN/constraint/index on a hot table) inside the
serving container's startup/health-check path on a rolling-deploy platform — it races the healthcheck
and contends with the draining old revision. Apply column/table ALTERs **out-of-band**: manually
before the deploy (psql waits patiently for the lock), or via a dedicated pre-deploy migration job —
never in `lifespan`. And remember: a Postgres-only code path that CI exercises only on SQLite is
**effectively untested** — treat it as such before shipping it to prod.

## 2026-06-30 — Ran pytest but not ruff; CI lint failed on F401
Pushed a new test file importing `pytest` without using it; `pytest` was green locally so I shipped
it, but the `backend-tests` job runs `ruff check .` FIRST and failed on F401 (unused import). This is
a repeat of the 2026-06-16 lesson in spirit.
**Rule:** run `ruff check .` (and `bandit`) before every push, not just pytest — the lint gate runs
before the tests and a trivial unused import will red the build.

## 2026-06-30 — LLM-judge (claude-opus-4-8) API quirks
Getting the eval judge working took four separate fixes, each surfaced only by actually calling it:
(1) the `anthropic` SDK isn't in core requirements (judge is off by default) — `pip install anthropic`;
(2) the env key had no credits (`credit balance too low`) — verify with a 1-call test before a full run;
(3) `claude-opus-4-8` rejects the `temperature` param as deprecated (400); (4) it also rejects
assistant-message **prefill** ("conversation must end with a user message"), the usual JSON-pinning
trick — so reliability came from generous `max_tokens` (opus prepends a rationale before the JSON and
a tight cap truncated it → unparseable on ~30% of calls) + a `json_repair` fallback + one retry.
**Rule:** before a long/expensive model run, smoke 1–2 items and INSPECT the raw result (not just
exit code) — auth, credits, params, and parse-rate all fail silently as "0 score" otherwise. Don't
assume params/features (temperature, prefill) carry across model generations.

## 2026-06-30 — Mid-session env var updates don't reach the running shell
The user updated `ANTHROPIC_API_KEY` in the environment, but my shell kept seeing the old value
(env is captured at session start; updates don't propagate to a live session). Confirmed via a
non-secret fingerprint (prefix + length + last-2 charcodes) that the value hadn't changed.
**Rule:** when an env/secret is "updated" mid-session, verify the running process actually sees the
new value (fingerprint it) before debugging downstream; a fresh key may need a session restart, or
use the pasted value directly (write to a sourced scratch file, never echo it; recommend rotation).

## 2026-06-30 — FK enforced in Postgres, not in SQLite tests
`saved_summaries.summary_id → summaries.id` has no `ondelete`, so in **Postgres** a bulk
`DELETE FROM summaries` referenced by a bookmark RAISES (NO ACTION). SQLite (the test DB) doesn't
enforce FKs by default, so a test would NOT surface it. The bulk reset-all endpoint therefore skips
pinned rows by design (FK-safe) regardless of the test DB's leniency.
**Rule:** a destructive bulk delete must be FK-safe by construction, not by trusting the test DB —
SQLite-green ≠ Postgres-safe for referential integrity.

## 2026-06-30 — Eval ergonomics that saved rework
- `prompt_loader` caches prompts at import, so editing a prompt file mid-run is safe for an in-flight
  eval (it uses the cached copy); the candidate/after run picks up edits via a fresh process.
- The golden-set builder re-resolves each entry to the *latest* filing (drift). To re-verify ONE
  entry after an extraction fix, re-extract by its PINNED accession — don't run the full builder.

## 2026-07-01 — An LLM judge must see the SAME source the generator did, or it invents "hallucinations"
The judge scored faithfulness 1.96 with 633 "G3 hallucinated_facts" flags across all 78 runs and
judge_pass=0 — alarming, and it looked like the product was fabricating figures. It was NOT: the judge
was fed `excerpt[:60000]` while the generator grounds on the FULL critical-sections excerpt
(`filing_sample = filing_excerpt`, ~124–165k chars). On a 10-K, capital-return / dividend / purchase-
obligation / segment disclosures sit LATE in the document (AAPL FY25: $100B buyback at char 73,895,
$0.26 dividend at 73,701 — all past the 60k window). Told to "fail when in doubt," the judge flagged
real facts it simply couldn't see. Deterministic `numeric_precision` was 1.0 the whole time and was
right. Raising the cap to 200k recovered faithfulness 2→4 and insight 3→4 on the *identical* summary.
**Rule:** when an LLM-judge verifies claims against a source, it MUST receive the same (or a superset
of the) context the generator used — a smaller judge window manufactures false "unsupported claim"
failures. Cross-check any judge gate against the deterministic scorers: when they disagree sharply
(judge says fabricated, precision says clean), suspect the judge's context/instructions before
believing a product regression. Verify by locating the flagged fact's char-offset in the actual
grounding, not by trusting the judge's phrasing.

## 2026-07-01 — Bake off a model swap the way production runs it (thinking mode matters)
Baking off GLM-5.2 vs DeepSeek: a 1-call smoke showed GLM returned EMPTY `content` under a normal
token budget because it's a reasoning model that spent the whole allowance on `reasoning_content`
first. DeepSeek-v4-pro is also a reasoning model, but the pipeline already disables its "thinking" for
deterministic extraction — gated on a `"deepseek" in model/base_url` check that GLM didn't match. Left
as-is, the bake-off would have compared DeepSeek-thinking-off against GLM-thinking-on (conflating model
with mode, plus truncation). Fix: generalize the gate to any reasoning model that accepts the z.ai-style
`extra_body={"thinking":{"type":"disabled"}}` switch. **Rule:** before an apples-to-apples model
bake-off via env-swap, smoke ONE real call and inspect the raw message (content AND reasoning_content);
hold every knob constant (thinking mode, max_tokens, temperature) so the only variable is the model.
Verdict: GLM-5.2 matched DeepSeek on quality but was ~48% slower and ~3.5× costlier → no adoption case;
kept as a validated env-swap failover.

## 2026-07-01 — Currency-agnostic scorers are blind to a ~7x correctness bug; the aggregates hid it
Wave 3's 20-F prose looked clean on every aggregate (recall +0.012, no regression, judge dims flat).
Only drilling into the judge's recorded per-run gate_failures surfaced it: one NVO (Novo Nordisk / DKK)
run rendered its figures as bare `$` ("$309,064M" where the source is DKK) — a ~7x distortion. Root
cause was NOT extraction (DKK was captured in the XBRL grounding) — the model *intermittently* (~1/3
of NVO runs) ignored the "never render non-USD as `$`" directive. Critically, `numeric_precision`
stayed 1.0 the whole time because it matches the VALUE and is **currency-agnostic** — it never checks
the unit — so the deterministic gate literally cannot see a currency mislabel; only the judge/eyeball
can. **Rule:** (1) when a class of error is invisible to the deterministic scorers (currency label,
units, sign-on-derived-metrics), add a dedicated deterministic guard — don't rely on the LLM judge as
the only catcher. (2) Aggregate metrics + "no regression" can hide a rare, severe per-item defect; for
go/no-go on a user-facing launch, inspect the worst per-item cases, not just the means. Added
`score_currency_consistency` (bare-`$` on non-USD filers; US$/NT$/HK$ excluded via letter-lookbehind;
native counted via a currency-alias map since CNY renders "RMB", TWD renders "NT$"). WARN-gated, not
hard — the slip is intermittent and a hard gate would flake CI until the underlying model slip is fixed.

## 2026-07-01 — The judge's XBRL view was ALSO truncated (json.dumps[:8000]) — a second blind-spot
Wave 4a judged spot-check FAILed AAPL with faithfulness 2 and G3 "hallucination" flags on Free Cash
Flow, ROE/ROA, working capital and current ratio — all figures the model legitimately grounds on. A
probe settled it: the full standardized-metrics JSON is 12,244 chars, but `evals/runner._xbrl_to_text`
capped the judge's XBRL view at 8,000 (`json.dumps(metrics)[:8000]`), so ~1/3 of the metrics (the
*late* dict keys — FCF/ROE/ROA/WC/current ratio) fell out of the judge's view and were flagged as
unsupported. Same class of bug as the 60k-excerpt truncation, different channel (the XBRL block, not
the filing excerpt). Fix: raised the cap to 40,000 (`_XBRL_TEXT_CHAR_CAP`); the metrics JSON is small
and the judge already carries a 200k excerpt budget. **Rule:** the judge-context lesson applies to
EVERY channel the generator grounds on, not just the filing text — audit each source the generator
sees (excerpt AND XBRL AND any tool output) for its own truncation cap. When the judge flags a figure
you *know* is in the grounding, dump exactly what the judge received and check for a truncation
boundary before believing a regression.

## 2026-07-01 — Feeding the model pre-computed deltas (YoY%) induced FABRICATED causal drivers
Wave 4a trialled appending an explicit "YoY: +X%" to each monetary grounding row (derived from the two
SEC-verified current/prior values — genuinely grounded). A judged before/after on AAPL (with the
now-fixed judge view, so the comparison was clean) was unambiguous: WITHOUT the YoY suffix faithfulness
was 4 and the cash-flow narrative was clean; WITH it faithfulness dropped to 2 and the model produced
two *fabricated* cash-flow causal attributions ("OCF fell due to higher tax payments"; "investing CF
turned positive as maturities increased") that directly contradicted the source cash-flow statement.
Mechanism: the salient delta (esp. investing CF +417.7%) + the Wave-2 "state the driver" directive =
the model invents a driver to explain the number. `numeric_precision` stayed 1.0 (no wrong *number*),
so only the judge caught it. **Rule:** a "figure amplifier" that surfaces a DERIVED comparative is not
faithfulness-neutral when the prompt also asks the model to explain changes — it manufactures
explanations. Ship the raw current/prior figures (let the reader/model see the trend) but DON'T
pre-chew deltas into the grounding unless paired with a groundedness guardrail ("attribute a cause
ONLY when the filing states it"). Dropped YoY for Wave 4a; kept the FCF relabel + working-capital
fallback (pure grounding, no delta-to-explain) + the judge-view fix. The driver-guardrail (which would
let YoY return safely) is the real prize — queued as a prose-wave item.

## 2026-07-01 — Faithfulness guardrail: appended caveats fail; conditional directive works — but fabrication REDISTRIBUTES
The driver/outlook guardrail wave, gated with judged before/after (3 filings × 3 runs, subscription
`cli:sonnet`). **V1** (append two caveat bullets after the existing "state the PRIMARY driver"
directive) did NOTHING: mean faithfulness 3.00→3.11 (flat), causal-driver fabrications 6→8 — a buried
caveat loses to the unconditional lead directive it contradicts. **V2** (reword the LEAD directive to
be conditional — "give the driver ONLY as management states it; when the filing gives no cause, report
the movement alone" — + a prominent DO-NOT prohibition) cut the egregious source-contradicting causal
fabrications to ~1, held faithfulness, no deterministic regression, prose stayed decisive (2 PASS vs 1).
BUT the *mean* stayed flat (3.11) because the model's fabrication **redistributed** to modes the
guardrail doesn't touch: presenting derived figures as reported ("Services now 26.2% of sales"), debt
aggregations, inferred "tone: positive/cautious". **Rules:** (1) to change model behaviour, edit the
DIRECTIVE THAT CAUSES IT (make the lead conditional), not an appended caveat — caveats that contradict
a stronger nearby instruction are ignored. (2) A model has a roughly conserved "fabrication drive":
suppressing one mode (invented causes) surfaces others (derived-as-reported, tone) — expect whack-a-mole
and measure ALL modes, not just the one you targeted; the headline mean can stay flat while a specific
egregious pattern is genuinely fixed. (3) Ship the targeted, no-regression win anyway (precedent: Wave 2
shipped a no-regression refinement on a judge-visible gain) and make the redistributed modes the next
target: a "don't present a derived/aggregated figure as if reported; don't infer tone" guardrail.
**V3 UPDATE — a concrete negative EXAMPLE was the real unlock (show, don't just tell).** A reviewer
suggested pairing the existing with-cause example with a no-cause one — `report the movement alone
(e.g. "Capex rose 12% to $1.2B")`. Adding that single parenthetical to the (V2) conditional directive
moved the mean from 3.11 to **3.78** (before 3.00), took OUTLOOK fabrications to **0**, and HALVED the
runs with any fabrication (8/9→4/9) — NVDA went fully clean. So the rewritten directive (V2) reduced the
egregious pattern but the *example* (V3) is what lifted the headline: the model imitates a modeled
output far more reliably than it obeys an abstract rule. **Rule:** when a directive tells the model to
sometimes-omit something, give a concrete example of the omitting-output — a rule + its worked example
beats the rule alone by a wide margin. (Cost: it took a 4th judged sweep to see it; worth it.)

## 2026-07-01 — Redistribution guardrail did NOT pan out — know when to stop tuning prose
After the driver/outlook win, I tried a follow-up guardrail for the modes fabrication redistributed
into: derived-figure-as-reported (a segment's % of total, a "total debt" summed from components) and
inferred "tone". Added two DO-NOT bullets + worked examples to all three prompts, judged before(V3=3.78)
/after(redist). Result: **no improvement** — OTHER-mode flags unchanged (12→12), mean faithfulness
3.78→3.56 (noise/slight drag), runs-with-G3 4/9→6/9. The targeted modes PERSISTED verbatim ("total
debt (term + commercial paper) = $98.7B", "26.2% of total sales"). Reverted; did not ship. **Why it
failed / lessons:** (1) unlike the driver directive (which I moved into the salient LEAD instruction), a
DO-NOT bullet is buried and loses to the model's pull to synthesize — the same V1 failure mode. (2) The
category is HETEROGENEOUS (debt roll-ups, segment %, dividend-per-quarter, liquidity, plus genuine
arithmetic errors) — no single guardrail moves a grab-bag, and "mark as derived" can't fix a wrong sum.
(3) CRUCIAL: the 10-K prompt itself INSTRUCTS "Total Debt = current portion + long-term debt", so the
model's debt roll-up is prompt-COMPLIANT and useful — the judge just dings it on provenance. Suppressing
prompt-requested, correct derivations is not a clear quality win. **Rule:** not every judge-flagged
category is a prompt-prose problem. When (a) the flags are heterogeneous, (b) some are the model
correctly following instructions the judge is merely strict about, and (c) a lesson-shaped fix (salient
+ example) would still only cover part — STOP tuning prose (CLAUDE.md: don't keep pushing). The residual
belongs to a different lever (a deterministic "summary figure not traceable to XBRL/filing" provenance
check, Wave 5) or is simply the floor. The driver/outlook guardrail captured the high-leverage,
coherent fabrication category; faithfulness 3.00→3.78 is the banked win.

## 2026-07-01 — Revived the YoY amplifier under the guardrail, re-judged, and DROPPED it again
The Wave-4a YoY% amplifier (append "YoY: +X%" to grounding rows) was dropped for inducing fabricated
cash-flow drivers. Hypothesis: now that the driver-groundedness guardrail is merged, YoY is safe to
revive. Tested it hard (subscription cli:sonnet, 3×3), before(guardrail,no-YoY) vs two variants:
- **full YoY** (all rows): faithfulness held at 3.78 (the guardrail DID prevent the old 4→2 crash), but
  causal fabrications rose 2→4 — incl. a capex "reflecting investment in manufacturing" the YoY delta
  invited. Runs-flagged 4/9→6/9.
- **Option B** (YoY off the 5 cash-flow/capex rows — the volatile, filing-unexplained deltas): 3.44,
  causal 3 (incl. a geographic "reflecting export controls" fabrication), 7/9 flagged.
At n=9 the faithfulness numbers (3.78/3.78/3.44) and causal counts (2/4/3) all overlap within noise —
so the robust reading is: **YoY gives NO measurable faithfulness or deterministic gain** (a YoY% isn't
a scored fact; the block already shows current+prior so the reader sees the trend), while it reliably
tempts the model to attribute a CAUSE to whichever delta it makes salient — a risk the guardrail only
partly catches. **Rule:** an amplifier that adds no measurable quality but adds any fabrication risk is
a bad trade for a trust-critical product — don't ship it, however "nice" it seems. The guardrail
prevents the catastrophe but doesn't license reintroducing the trigger. Reverted; recorded. (Founder
call, reputation-first: neutral-with-downside ⇒ no ship.)

## 2026-07-02 — Batch class-string replaces need per-site asserts
During the PR-5 banned-utility sweep, two blind string replaces caused regressions
that only Gemini's review caught: (1) a targeted `transition-all ->
transition-[stroke-dashoffset]` replace missed the SVG ring because its classes
live in a TEMPLATE LITERAL (``className={`transition-all ... ${isError ...}`}``),
so the blanket `transition-all -> transition` fallback silently killed the
animation; (2) `replace('bg-amber-400', 'bg-warning-light dark:bg-warning-dark')`
also matched `bg-amber-400/10` and `hover:bg-amber-400/20`, producing a solid
fill, a dead hover, and a conflicting un-prefixed dark class on a banner I did
not know existed.

**Rules:** (a) every targeted replace in a sweep script must `assert old in s` —
a silent no-op means the fallback rewrites the site wrong; (b) before replacing
any token, grep ALL its variants first (`/opacity` suffixes, `hover:`/`dark:`
prefixes, template literals) and handle each explicitly; (c) after a sweep, grep
the RESULT for impossible combinations (e.g. a solid fill next to a `/10` dark
pair) — the bug shows up as nonsense class adjacency.

## git add is atomic across pathspecs (2026-07-03)
A multi-path `git add a b c` stages NOTHING if any single pathspec is invalid — the
summary-layout commit shipped docs without its actual CSS because a bad root-relative
path poisoned the whole add (caught by the stop hook, not by me). Rule: after every
commit intended to complete a change, run `git status --short` and require EMPTY
before pushing or opening/updating a PR; never chain `git add bad-path || true`-style
recovery — fix the path.

## 8-K Item 2.02 ≠ earnings release (2026-07-04)
The calendar showed BIIB as "reported 7/1" (real date 7/29) because ingest treated ANY 8-K
carrying Item 2.02 as an earnings release. 2.02 is "Results of Operations and Financial
Condition" — it also covers pre-announcements (BIIB), delivery/production numbers (TSLA), and
royalty-trust distribution notices (MVO), so a regulatory *category* was silently treated as a
semantic *event*. Worse, the unguarded flip was terminal (reported rows are never overwritten),
so one false positive froze the row wrong AND discarded the later genuine 8-K.

**Rules:** (a) never derive a semantic event from a regulatory category alone — require an
independent corroborating signal (here: timing plausibility vs the fiscal quarter and the
expected date); (b) when a state transition is terminal, the guard belongs ON the transition,
shipped WITH the feature — reconciliation added "after launch" arrives after the data is already
poisoned; (c) for market-wide sweeps, prefer flip-only over insert: acting only on entities you
already track bounds the blast radius of a misclassified signal.

## buttonVariants() is a client export — can't be called in a Server Component (2026-07-04)
During the DS realignment I swapped a hand-rolled CTA on app/waitlist/page.tsx (a Server
Component) to `buttonVariants({variant:'secondary'})`. `tsc`/`eslint` passed but `next build`
failed at prerender: "Attempted to call buttonVariants() from the server but buttonVariants is on
the client." `buttonVariants` is a pure function, but it lives in the `'use client'` Button.tsx, so
Next marks it a client-only export — importing it into a server component and *calling* it throws.

**Rules:** (a) `<Button>`, `buttonVariants`, `useCountUp`, and anything from a `'use client'`
module can only be used in components that are themselves `'use client'`; a page with
`export const metadata` (no `'use client'`) is a Server Component. (b) For a link-styled CTA in a
Server Component, either keep a token-clean hand-rolled `<a>` or extract a small client wrapper —
you cannot call `buttonVariants()` there, and `<Button>` renders a native `<button>` (not an
anchor) so it can't be a link. (c) `tsc` + `eslint` do NOT catch the server/client boundary —
always run `next build` before shipping a change that moves DS primitives across page files.

## `<Button loading>` sets aria-disabled, NOT native disabled — forms need a handler guard (2026-07-04)
Recomposing the waitlist forms, I replaced `<Button disabled={isSubmitting}>` + a manual spinner with
`<Button loading={isSubmitting}>`. The DS Button keeps its resting fill while loading and uses
`aria-disabled` + an onClick guard — it does NOT set the native `disabled` attribute (by design). But
a form's implicit submit (Enter in a field) bypasses the button's onClick and fires `onSubmit`
directly, and a non-native-disabled submit button no longer blocks implicit submission. Net: swapping
`disabled` → `loading` silently reopened concurrent/duplicate submits (Gemini caught it).

**Rule:** any form whose submit button relies on `loading` (not native `disabled`) MUST guard its
submit handler with an early return (`if (isSubmitting) return` / `if (loading) return`) right after
`preventDefault()`. Don't rely on the button's disabled look to prevent re-entry. (Also: `className`
on `<Input>` lands on the outer shell, and `text-sm` is already in the field defaults — don't re-pass
it.)

## Run the FULL test suite (vitest), not just `next build`, for user-visible copy/value changes (2026-07-04)
The pricing "show monthly cost" change flipped the displayed anchor ($390/yr → $32.50/mo). tsc,
eslint, and `next build` all passed, and the screenshots looked right — but I skipped `vitest`, and
`PricingPage.test.tsx` asserted the exact old strings ("$390"/"$290"), so CI's frontend-tests job
failed after I'd already opened the PR.

**Rule:** any change that alters rendered text, numbers, or copy MUST run `npx vitest run` before
push — those are exactly what component tests assert, and neither the typechecker nor the build
catches a changed string. Build + screenshot verifies rendering; only the test suite verifies the
contract. When a test legitimately needs updating (behavior changed on purpose), update it to the
new expected value in the same PR — don't just delete the assertion.
