# Multi-Period Analysis depth harness

An offline research harness for the "AI trend analysis" section. It builds evidence packs from SEC
filings, generates analyses with a proposed prompt on several models, checks every number with a
deterministic gate, judges outputs pairwise with a model from neither output's family, audits causes and
number attribution, and writes a report. None of it runs in production or CI; its unit tests do
(`tests/unit/test_trend_depth_*.py`).
The findings and recommendation are in `tasks/analysis-depth-2026-10/REPORT.md`.

## Arms pin their prompt and their evidence packs

A generator arm (`providers.ARMS`) names the prompt it runs (`prompt`, a repository-relative path) and the pack
directory it reads (`packs`, under `tasks/analysis-depth-2026-10/`); `providers.prompt_path` and `packs_dir`
resolve them. An arm that names neither runs the frozen prompt on `packs/`: the frozen prompt is
`tasks/analysis-depth-2026-10/prompts/frozen-d558d371.md`, the prompt eval-v1 and dev-v4 ran (sha256 `d558d371…`),
archived byte for byte, so eval-v1's records still match their arms. The experiment of `DEEPSEEK-ERRORS.md` §3
adds three arms with deepseek-flash's model and settings, each differing from the control only in what it reads:

| Arm | Role | Packs | Prompt |
|---|---|---|---|
| `deepseek-flash` | K0, the control | `packs/` | frozen |
| `deepseek-flash-p` | P: the pack fixes alone | `packs-v2/` | frozen |
| `deepseek-flash-q` | Q: the prompt fixes alone | `packs/` | candidate, `backend/prompts/trends-depth-analyst-agent.md` |
| `deepseek-flash-c` | C, the candidate | `packs-v2/` | candidate |

Every stage reads the pack of the system it reads: the gate, the repair, the audits, the judge's sources and the
report's gate replay. `current` and the gold examples read `packs/`, as does the company header the judge shows
both drafts. Each record keeps the sha256 of the prompt it ran (`prompt_sha256`) and of the pack it read
(`pack_sha256`, beside `packs` and the dataset's `snapshot_id`, which a pack rebuilt over the same data keeps), and
a first pass is repaired or copied only beside both (`records.same_inputs`). The candidate is edited in place;
`TREND_DEPTH_PROMPT=/path/to/draft.md` stands in for it in the `-q` and `-c` arms only, never for the frozen prompt.
To run another model on the candidate, add an arm with `prompt=CANDIDATE_PROMPT` (and `packs="packs-v2"`).

## Re-run the DeepSeek experiment

```bash
cd backend
ARMS=deepseek-flash,deepseek-flash-p,deepseek-flash-q,deepseek-flash-c   # P and C need packs-v2/
V4PRO=deepseek-v4-pro  # judge and auditor only, under the ADR-0008 addendum
# 0. A like-for-like baseline: eval-v1's DeepSeek and Sonnet outputs re-audited under the auditor's view 2.
python -m evals.trend_depth.generate --label eval-v1-view2 --arms current,deepseek-flash,claude-sonnet-5-5 --split all --copy-from eval-v1
python -m evals.trend_depth.semantics --label eval-v1-view2 --systems deepseek-flash,claude-sonnet-5-5 --auditor claude-opus-5-5
# 1. Development half only, never reading held-out outputs: two independent runs of every arm, one label each.
#    --pipeline v2 gives every arm the same new gate and repair code (auto-citation, retyping, backstops, patch
#    repairs), so the arms differ only in pack and prompt; K0 on v2 measures the code fixes alone.
python -m evals.trend_depth.generate --label dev-v5-r1 --arms $ARMS --split dev --pipeline v2
python -m evals.trend_depth.generate --label dev-v5-r2 --arms $ARMS --split dev --pipeline v2
# 2. In each run: audits of K0 and C (Opus by default for a DeepSeek system, V4 Pro the second auditor), then the
#    judge, C against K0 in both orders (Opus, the first judge from neither output's family).
for label in dev-v5-r1 dev-v5-r2; do
  python -m evals.trend_depth.causes --label $label --systems deepseek-flash,deepseek-flash-c
  python -m evals.trend_depth.semantics --label $label --systems deepseek-flash,deepseek-flash-c
  python -m evals.trend_depth.causes --label $label --systems deepseek-flash,deepseek-flash-c --auditor $V4PRO
  python -m evals.trend_depth.semantics --label $label --systems deepseek-flash,deepseek-flash-c --auditor $V4PRO
  python -m evals.trend_depth.judge --label $label --systems deepseek-flash,deepseek-flash-c
  python -m evals.trend_depth.report --label $label --systems $ARMS
done
python -m evals.trend_depth.report --labels dev-v5-r1,dev-v5-r2 --systems $ARMS   # each measure per run, and the range
# 3. Freeze: stop editing the candidate and packs-v2/ (every record carries their hashes), then run K0 and C on
#    the held-out half, two runs each, with step 2's audits, judge and report.
python -m evals.trend_depth.generate --label eval-v2-r1 --arms deepseek-flash,deepseek-flash-c --split holdout --pipeline v2
python -m evals.trend_depth.generate --label eval-v2-r2 --arms deepseek-flash,deepseek-flash-c --split holdout --pipeline v2
```

`--copy-from eval-v1` still copies any arm on the frozen prompt and `packs/`, `current` and `deepseek-flash`
included. The packs in `tasks/analysis-depth-2026-10/packs/` are committed, so every step reads the same evidence
and needs no SEC access, except the `current` arm, which ingests companyfacts into the local store. A file that
exists is skipped, so use a new label per run. A record holding a provider error (a quota, an outage) is
retried by the next run with the same label. Judging other pairs: `--exclude-judges gemini-3.8-flash` when the
Gemini quota is spent (Gemma 4 31B then judges the Claude-vs-DeepSeek pairs), or `gemini-3.8-flash,gemma-4-31b`
for consensus panels; `--auditor <arm>` repeats an audit with one auditor for every system.

Keys are read by name: `DEEPSEEK_API_KEY`, `GEMINI_API_KEY` (or the cloud container's `OPENAI_API_KEY` with
a Google base URL), and `ANTHROPIC_API_KEY`. Without an Anthropic key, Claude runs through `claude -p` (the
repository's judge pattern), which bills the logged-in subscription; with the key, it runs through the
Anthropic SDK. A free-tier Gemini key reaches only the Flash models and Gemma: Pro and Gemini 4 Argon answer
with a quota of zero, Gemini 3.8 Flash allows 20 requests a day, and Gemma 4 31B is slow (about a minute per
judge call, with intermittent 500s).

Spend: `eval-v1` (20 companies, four proposed arms plus current, judging, and both audits under both
auditors) cost USD 42.3 in October 2026: Opus judging USD 23.4, Opus audits USD 10.7, Sonnet generation
USD 5.6, and everything else under USD 1 each. A run with only the default audits and without the Haiku arms
costs about USD 25. `tasks/analysis-depth-2026-10/REPORT.md` §8 has the per-analysis costs.

## Claude through the API (`eval-v2-api`)

`eval-v1` ran every Claude call through `claude -p`. With `ANTHROPIC_API_KEY` set, every Claude call goes to the
Messages API instead, the Opus judge and auditors included. Install the SDK with `pip install anthropic==2.3.0`,
the version its tests and this path were checked against (the app does not depend on it). The API makes two more arms possible, which the CLI cannot express:

- `claude-haiku-5-5-nothink`: thinking `disabled`;
- `claude-sonnet-5-5-nothink`: `between_tools`, Sonnet 5.5's lowest thinking setting.

Every Claude API attempt is in `tasks/analysis-depth-2026-10/runs/spend.jsonl`: its reservation, its own cost
or its worst case, and its release. A call on another backend is logged when it returns, so one that fails or
is interrupted is not; nor are the calls of `current`, whose production pipeline calls DeepSeek through the
app's own AI layer. The ceiling,
`TREND_DEPTH_ANTHROPIC_CEILING_USD` (default 75), is checked before each Claude API attempt, retries included. The
worst case is the prompt at one token per byte, plus a full `max_tokens` of output, at list price.

- **Reservations.** Before an attempt is sent, its worst case is appended as a reservation row, and the
  attempt is refused, with nothing sent, if the ledger's Anthropic total would then pass the ceiling. When the
  attempt settles, its own cost is logged, and only then is a row of the opposite sign (`released`) appended.
  An attempt stopped before its cost is on disk (a kill, an interruption before `message_start` or before its
  row is written) leaves the reservation counted.
- **A stream that fails after it starts** may be billed, but usage reports output only at the end. So it is
  logged at its worst case, marked `estimated`, before any retry. A reply that was whole before its connection
  failed is kept and logged at its own cost. The ledger can overstate what the key spent, never understate
  it.
- **One process at a time.** A process holds a lock on the ledger while it spends on the key, so a second one
  (two steps run at once) is refused. Run the Claude API steps one after another.
- **Other sessions.** A session in another checkout keeps a ledger of its own. So also set a spend limit on the
  key's workspace in the Anthropic Console: that is the stop that covers every session.
- **A torn ledger row.** A crash can leave a row whose cost was cut off. Such a row stops every Claude call
  until it is repaired by hand: give it the cost the Console shows, or delete it if it was not a Claude call.

Commit the ledger after a run: it is the record of what each run spent. Reservation and release rows net to
zero. A reservation with no release marks an attempt that a crash or an interruption stopped before its cost was
known; its own cost row may or may not follow it.

The plan reuses `eval-v1`'s `current` and `deepseek-flash` outputs, their audits and the verdict between them.
Costs are on the Anthropic key at list price, estimated from `eval-v1`'s measured tokens.

```bash
cd backend
ARMS=claude-sonnet-5-5,claude-sonnet-5-5-nothink,claude-haiku-5-5-low,claude-haiku-5-5-nothink
V4PRO=deepseek-v4-pro  # judge and auditor only, under the ADR-0008 addendum
# 1. Copy current and deepseek-flash from eval-v1 (USD 0).
python -m evals.trend_depth.generate --label eval-v2-api --arms current,deepseek-flash --split all --copy-from eval-v1
# 2. Generate the four Claude arms on all 20 companies (about USD 9). Repeat until no line reports an error
#    or a repair_error: each repeat retries only what a provider failure left undone.
python -m evals.trend_depth.generate --label eval-v2-api --arms $ARMS --split all --concurrency 3
# 3. Default audits. Claude systems are audited by DeepSeek V4 Pro (USD 0 on the key, about USD 0.75 on DeepSeek).
#    The --auditor runs copy those audits into the V4 Pro same-auditor folder, beside deepseek-flash's (USD 0).
python -m evals.trend_depth.causes --label eval-v2-api --systems $ARMS
python -m evals.trend_depth.semantics --label eval-v2-api --systems $ARMS
python -m evals.trend_depth.causes --label eval-v2-api --systems $ARMS --auditor $V4PRO
python -m evals.trend_depth.semantics --label eval-v2-api --systems $ARMS --auditor $V4PRO
# 4. Same-auditor Opus audits, for a like-for-like comparison with deepseek-flash (about USD 11).
python -m evals.trend_depth.causes --label eval-v2-api --systems $ARMS --auditor claude-opus-5-5
python -m evals.trend_depth.semantics --label eval-v2-api --systems $ARMS --auditor claude-opus-5-5
# 5. Judge each arm against current and against deepseek-flash, one opponent at a time, so no unrequested
#    Claude-against-Claude pairs run (consensus panels: about USD 23 of Opus, about USD 2 of DeepSeek V4 Pro).
for arm in ${ARMS//,/ }; do
  python -m evals.trend_depth.judge --label eval-v2-api --systems current,$arm --exclude-judges gemini-3.8-flash,gemma-4-31b
  python -m evals.trend_depth.judge --label eval-v2-api --systems deepseek-flash,$arm --exclude-judges gemini-3.8-flash,gemma-4-31b
done
# 6. Report, and the key's spend so far.
python -m evals.trend_depth.report --label eval-v2-api --systems current,deepseek-flash,$ARMS
python -c "from evals.trend_depth.providers import anthropic_spend; print(f'USD {anthropic_spend():.2f}')"
```

The whole plan comes to about USD 44 on the key. The scheduled Gemini follow-up adds about USD 8–10 of Opus
judging and audits once the key is set. The Opus audit figure is an estimate. The `eval-v1` audit records kept
no token counts, and the CLI's bill of USD 0.18 a sample includes writing each prompt to a one-hour cache, so
list price is about USD 0.13–0.15.

Several safeguards keep the spend to these figures and the results honest (`records.py` holds the shared rules):
- **Waiting outputs.** An output still waiting on generate, missing or holding an `error` or `repair_error`, is
  skipped by the audits and the judge and counted apart by the report. It is never recorded as a forfeit.
- **Changed outputs.** Each audit and verdict stores the hash of the output it read. One left beside an output
  that has since changed is redone, its cost carried forward, and the report leaves it out until then.
- **Failed calls.** A reply with no verdict on every criterion, or no label for any item asked about, or one
  that stops at its token cap, is recorded as an error with its cost and its reply's head and tail. The next
  run retries it and carries the cost forward. A judge retry reuses an order already paid for on the same
  drafts.
- **Interruptions.** Ctrl-C keeps what was already paid for. A judge order that returned is written to the
  record before the run stops. A first pass is written, marked as owed its repair, before the repair is sent,
  so a run killed during the repair retries only the repair. Records are written whole or not at all.
- **Replaced generations.** A generation replaced after a provider error keeps the replaced one's calls as
  `prior_attempts`, and the report's cost counts them.
- **Refusals.** A refusal is the model's own outcome and is not retried.
- **Pair orientation.** A pair is cached in one fixed orientation, whatever order `--systems` lists it in.
- **Shared audits.** An audit already made by the same auditor is copied between the default and same-auditor
  folders in either direction, never paid for twice. A copy is marked `copied_from`, and each record carries
  only what its own folder paid (`records.own_spend`), so every paid call is counted once.

## Rebuild the evidence

```bash
python -m evals.trend_depth.evidence REGN SNAP JPM            # packs (SEC traffic through the app's transports)
python -m evals.trend_depth.evidence --out ../tasks/analysis-depth-2026-10/packs-v2 --fulltext-end 2026-10-24 REGN  # version 2
python -m evals.trend_depth.replay                            # every recorded output under the old and new gate
python -m evals.trend_depth.drivers REGN SNAP JPM COST NVDA   # driver tree, common-size view, availability
python -m evals.trend_depth.census run && python -m evals.trend_depth.census report   # the current pipeline
python -m evals.trend_depth.gold check REGN SNAP JPM          # gold examples against the gate
```

Rebuilding a pack can renumber its IDs. `python -m evals.trend_depth.gold remap TICKER <old pack.json>`
moves a gold example's citations to the new IDs, and `gold check` then re-verifies every number.

## Modules

| Module | Job |
|---|---|
| `bootstrap.py` | environment, the private SQLite facts store filled by the production ingest, cached SEC inputs |
| `companies.py` | the 20-company evaluation set (10 development, 10 held out), the census set, peer groups, the human-pack companies |
| `sec_inputs.py` | 10-K list, documents (with the EX-13 and Item 7 fallbacks), XBRL dimensional facts, full-text search |
| `xfacts.py` | extended companyfacts lines (cost lines, cash uses, balances, bank and insurer lines), first-reported against latest |
| `dimensions.py` | revenue and segment-profit disaggregation from each 10-K's instance, subtotals, coverage |
| `derived.py` | the driver tree as values: common-size, margin bridge, operating leverage, cash conversion, net cash, capital returns, bank metrics, window levels, red-flag candidates |
| `passages.py` | MD&A and note passages that state causes or guidance, with EDGAR locations |
| `evidence.py` | assembles a pack, including data checks and peer percentiles from the store |
| `render.py` | the pack as the generator reads it |
| `factcheck.py` | the gate (`backstops=True` adds the probes' gate checks) |
| `probes.py` | backstop checks for the mislabels the gate misses (R1, R2a, R2c, R3, U1, unitless dollars) and logic measures |
| `replay.py` | re-checks every recorded output under the gate as it was at `b3ed8ef` and as it is now, with and without backstops |
| `autocite.py` | adds a figure's missing own ID by code before any repair (`generate --pipeline v2`); `python -m evals.trend_depth.autocite` runs its substitution test |
| `calibration.py` | judgement share outside the watch list, evaluative words in data sentences, watch-item forecasts, form |
| `providers.py` | model arms (each pinned to its prompt and pack directory), usage, latency and list-price cost, the spend ledger and its ceiling |
| `records.py` | the rules every stage shares over run records: when an output is final, the hash an audit or verdict keeps, whether a first pass came from this prompt and pack, the cost a first analysis would bill |
| `generate.py` | proposed and current generations, the one-repair step, the gate |
| `judge.py`, `readable.py` | pairwise position-swapped judging in a neutral reader format |
| `causes.py` | does each cited passage state the cause its sentence gives? |
| `semantics.py` | is each verified number said about the metric and period it matched? |
| `report.py` | the bake-off report |
| `human_pack.py` | the blind preference pack and scoring sheet |
| `gold.py`, `drivers.py`, `census.py` | gold examples, driver evidence, the census of the current pipeline |
