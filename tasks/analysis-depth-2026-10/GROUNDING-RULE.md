# Grounding rule for the AI trend analysis: proposal for approval

Status: **proposed, not implemented in production.** The enforcement exists only in the evaluation
harness (`backend/evals/trend_depth/factcheck.py`), where it gates every output in the bake-off. Production
wiring waits for the founder's approval of the rule below.

## Why the rule has to change

The current rule makes depth impossible by construction. The model may only rank IDs of sentences that
code has already written, and its prompt forbids it to "infer causes … or relationships" (rule 4 of
`backend/prompts/trends-analyst-agent.md`). The census of 40 reproduced analyses
(`census/README.md`) shows the result. Of 705 sentences, 41.6% restate a figure and 58.4% are derived
comparisons; none states a cause and none is a judgement. In 95.7% of numeric sentences there is no figure
that the metrics table on the same page does not already show. The rule bought perfect numeric fidelity by
having nothing to say.

The proposal keeps the fidelity and lets the analysis say what the numbers mean, within a rule a machine
can check.

## The rule (four tiers)

Every sentence in a generated analysis has exactly one type, declared by the generator and shown to the
reader where it matters.

| Tier | Sentence type | May contain | Must cite | Checked by |
|---|---|---|---|---|
| 1 | **Fact**: states a filed or calculated figure | numbers | the ID of every figure (`F`, `X`, `S`, `D`) | gate: each number equals a cited value at its printed precision |
| 2 | **Comparison**: relates figures (growth, change, share, above/below, versus peers or the window) | numbers, including ones derived from cited inputs | the inputs (or the `D` value that already holds the result) | gate: each number equals a cited value or a derivation of cited values (growth, CAGR over the cited years, difference, ratio, share, percentage-point change, sum, mean); a direction word must match the sign; a named year must be the value's year |
| 3 | **Cause**: says why something moved | numbers as in tiers 1 and 2 | at least one filing passage (`P`) that states the cause, plus the figure it explains | gate: a `P` is cited and every number reconciles. Judge: the passage actually states the cause |
| 4 | **Judgement**: interpretation (what it means, how durable, what the risk is) | only numbers already cited in the same sentence | the figures it interprets | gate: no number that does not reconcile to a citation. Shown to the reader as *Analysis* |

The generator may not state any number that does not reconcile, and may not state a cause without a
passage. If no passage explains a move, it says so. Forecasts are allowed only as conditions ("if operating
margin falls below 24.9%…") or as guidance quoted from a passage.

The evidence the rule cites is assembled by code before the model runs (`evidence.py`). The metrics table
supplies `F`; companyfacts supplies the extended lines `X`; each 10-K's own XBRL supplies the disaggregated
revenue and segment profit `S`; code computes the driver metrics, window reference levels and peer
percentiles `D`; and code quotes 10-K MD&A and note passages, with their EDGAR locations, as `P`. The
model never computes a figure it cannot cite, because the useful derivations already exist as `D` values.

## Enforcement: the fact-check gate

`factcheck.py` runs on every output and fails the run on any of the following:

1. a citation to an ID the evidence pack does not contain;
2. a number that matches nothing the sentence cites, whether as a value, a derivation of cited values,
   or a figure printed in a cited passage;
3. a match only in a year the sentence does not name (a period mismatch);
4. a direction word that contradicts the sign of the change it states ("rose 3.2pp" for a fall);
5. a number with no citation at all;
6. a cause sentence that cites no filing passage.

Numbers are parsed with their units: dollars with scale, %, pp and basis points, x and times, days, years,
shares and per-share amounts. Qualifiers are honoured: "about" allows 5%, "more than" is a bound, and
"nearly tripled" means a ratio within 15% below 3. Matching uses the printed precision (half a unit of the
last printed digit), so "$14.3 billion" accepts $14,342.9 million but "320 basis points" rejects a
315bp move. Years, form names, item and note numbers, and citation markers are not figures. Counts of
periods ("four consecutive years") are logged as `unverified_count` and left to the rubric judge, because a
pack does not hold counts as values. This is the gate's one known gap.

In production the gate would sit where `scan_numeric_fidelity` sits now: after generation and before
anything is shown or cached. A failure gets one regeneration that names the failures. A second failure is
not published, and the page falls back to the current code-owned narrative, which already passes by
construction, with the failure logged.

The gate checks numbers, not the words around them, so two checks that read words run as model audits, in
the evaluation and as a weekly sampled audit in production (`backend/evals/RUNBOOK.md` already runs one for
Copilot citations):

- `causes.py`: does each cited passage state the cause its sentence gives? Each sentence is labelled
  supported, partial or unsupported.
- `semantics.py`: is each verified number said about the metric and period it was matched to? It catches a
  growth rate in cash called revenue growth.

In the evaluation (REPORT.md §7.3–§7.4), 1% of cause sentences were unsupported and 22–23% partial under
the Opus auditor. Between 3 and 10 of every 1,000 verified numbers were attributed to the wrong metric,
period or sign, depending on the model.

Known gaps, each measured in REPORT.md:

- counts of periods ("four years running");
- a fall printed as a bare rate with no direction word ("a 5.3% CAGR" for −5.3%);
- interpretation written into a fact or comparison sentence instead of a marked judgement.

A rule for unsigned falls was tried and rejected: all six claims it flagged were false positives. It needs a
better clause model before it can fail a run.

The gate's behaviour is pinned by `backend/tests/unit/test_trend_depth_factcheck.py`, which has one planted
case per failure class and one per accepted form.

## How sources are presented

The aim is trust without the sources outweighing the analysis. The current page shows 13 chips and a
13-row sources list for six short paragraphs, many of them restating the table.

- **Inline:** one small superscript number per clause, not per figure. Where a sentence cites several
  figures, the chip opens a popover listing them. Filing passages get a distinct chip style (a quote mark)
  so a reader can see at a glance which claims rest on the company's own words.
- **Judgements** are set apart typographically: an "Analysis" label and a left rule, never colour alone.
  This is the visible marker the rule promises. The reader always knows where the data ends and the
  interpretation begins.
- **Popover:** a figure shows its value, period and provenance (filed XBRL tag, or the formula and its
  inputs for a calculated figure). A passage shows the quoted text with the filing, the item or note, and a
  link that opens the 10-K at that paragraph (a text-fragment URL).
- **Sources list:** collapsed by default under the analysis ("Sources: 9 filed figures · 6 calculations ·
  5 filing passages"), grouped by kind, and expanded on request. The PDF export prints it in full.
- **Data checks** that affect a stated figure (a recast year, a basis break) appear inline in the sentence
  that uses the figure, not in a separate notes block the reader has to reconcile.

## What approval would authorise

1. Replace the selector prompt and the observation catalogue with evidence-pack generation and the
   four-tier rule, behind a flag, as a new `PROMPT_VERSION`.
2. Move `factcheck.py` into `app/services/trend_analysis/` as the gate, with the fail-closed fallback above.
3. Add the evidence-pack inputs to the facts layer: the extended companyfacts lines, 10-K XBRL
   disaggregation, and MD&A/note passages fetched through the existing SEC transports and cached per
   accession.
4. The presentation changes above (a separate UI change under the design-system rules).

None of these is done in this branch.
