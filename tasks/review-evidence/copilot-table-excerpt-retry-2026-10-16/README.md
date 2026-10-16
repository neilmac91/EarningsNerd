# Copilot table-text citations: why BABA withholds, and the one-retry fix (2026-10-16)

copilot-eval withheld BABA `viewed-native-revenue-2025` 3 of 3 times on #1350's head (run 38817393205).
The record of that run is [the attribution comment on #1350](https://github.com/neilmac91/EarningsNerd/pull/1350#issuecomment-6203868292).
Decision D's follow-up 1 ([`../../decisions-2026-10-09-design-followups.md`](../../decisions-2026-10-09-design-followups.md))
had left the root cause open: the model cites table text as a lone figure, a short label or an elided row. This
record measures that behaviour across every retained copilot-eval generation and gives the evidence for the change.

## The corpus

Every copilot-eval artifact from 2026-10-02 (after #1052's whole-excerpt check) to 2026-10-16 was read:
205 artifacts ([`corpus-artifacts.txt`](corpus-artifacts.txt)). One held no report, because its preparation failed
before any draw. Two were credential-less stubs. That leaves 192 distinct reports, 3,456 rows and 3,544 generations.

[`classify_corpus.py`](classify_corpus.py) feeds each generation's raw candidate through production's own scanner,
`_parse_citations` and `_verify_citations` (main `03fbf23e`). It records the verdict:
- published at this check;
- `regenerable`;
- `terminal`.

For each referenced citation that fails, it also records the reason:
- `missing`;
- `collision`, a number declared twice;
- `quoted_label`;
- `short`, under 24 normalized characters;
- `elided`;
- `mismatch`.

Its verdicts agree with the reason each run recorded on all 3,544 generations:
- every recorded "Unverified or ambiguous referenced citation" is regenerable (117) or terminal (12);
- every published generation passes;
- the 6 decision-F withholds pass this check and fail later, at the quotation check.

[`summarize_corpus.py`](summarize_corpus.py) produced [`corpus-summary.json`](corpus-summary.json), which holds every
number below. Prompt revisions are named by the SHA-256 prefix of the first generation's system message:
`a88b6fb1de5b` before #1111, `d46ef28f000a` after. Source kinds come from the prepared excerpt's hash: "sections"
(production's source while edgartools works) or the regex fallback (2026-10-06 to #1350).

## Findings

**1. Every citation failure is table text, on two questions.** 129 generations failed `_verify_citations`, all
BABA FY2025 or ASML:

| Reason | First generation | Retry generation | Example |
| --- | --- | --- | --- |
| elided (regenerable today) | 94 | 20 | `Revenue from third parties ... 996,347 ... 137,300` |
| short (terminal today) | 9 | 1 | `996,347`; `Consolidated\nTotal`; ASML `€32.7bn\nTotal net sales` (23) |
| collision + short (terminal today) | 2 | 0 | `996,347` and its row, both declared as `[1]` (2026-10-15, sections) |
| mismatch (regenerable) | 3 | 0 | a table header copied with its blank cells |

**2. When the model cites a table and succeeds, it cites the whole row.** After #1111 the verified text excerpts
were:
- **ASML:** 184 times the statement row `Total net sales 28,262.9 100.0 32,667.3 100.0 15.6` (with or without line
  breaks).
- **BABA:** 85 times the label `Revenue from third parties` (26 characters), and the full consolidating-schedule row
  about 30 times.

[`../../../backend/tests/unit/test_copilot_table_excerpts.py`](../../../backend/tests/unit/test_copilot_table_excerpts.py)
pins every one of these shapes against real slices of the prepared sources.

**3. #1111's prompt raised text-citation use, and on BABA's sections source every such citation failed.** The table
shows first generations that carry a text marker:

| Question, source | Before #1111 (`a88b6fb1de5b`) | After #1111 (`d46ef28f000a`) |
| --- | --- | --- |
| ASML (always the regex fallback) | 7/123 and 3/33 (6–9%) | 289/390 (74%), still 387/390 verified |
| BABA FY2025, regex fallback | 12/33 (36%) | 157/387 (41%) |
| BABA FY2025, sections | 12/123 (10%), 1 terminal | 3/3, all 3 terminal |
| BABA FY2026, regex fallback | 0/33 | 0/387 |
| BABA FY2026, sections | 2/123, all verified | 2/3, all verified |

#1111 was measured only on the regex fallback, so this did not show. The RUNBOOK's new "Copilot prompt revisions"
table and its gate (`tests/unit/test_copilot_prompt_revisions.py`) now record the source each revision was measured
on.

**4. The retry recovers about three in four, and a failed retry repeats the failure.** After #1111, a first
generation that failed with a regenerable mismatch got its one retry:
- **BABA:** 63 elided→published, 3 mismatch→published, 20 elided→elided, 1 elided→short. That is 66 of 87 recovered,
  or 67 of 88 with ASML's one recovery.
- **The 21 failed BABA retries:** 11 repeated the identical excerpt, 9 a shorter elided one, and 1 fell to a bare
  cell.
- **Comparison:** the retry fails about as often as a fresh first generation fails on that source (21/87 against
  92/387), so today's generic guidance ("failed source matching") adds little beyond a resample.

**5. On the production source the failures never reach the retry.** After #1111, rows were withheld at this check
as follows:
- **BABA regex fallback:** 21 failed twice, and 5 short rows had no retry.
- **ASML:** 2 short rows had no retry.
- **BABA sections:** 3 had no retry (2 collision+short, 1 short).

So every sections withhold was in a class #1111 made terminal.

## The change and its design

A judge panel ran three independent Opus designs (retry path only, first-generation prompt, unconstrained) and three
Opus judges (safety and rules, evidence, minimality and measurability). All three judges chose the retry-path design,
with the unconstrained design's cause-specific guidance grafted on:
- **Eligibility** (`copilot/envelope.py::_verify_citations`). A referenced excerpt that fails the matcher, whatever its
  length, or a referenced number declared twice may buy the one private regeneration. These stay terminal: a quoted
  section label, an undeclared referenced literal, and a source too short to verify anything. Publication is
  unchanged: the verifier, the 24-character floor, the payload, the two-generation cap, the shared deadline and
  charging quota once.
- **Guidance** (`copilot/prompt.py`). After a citation failure only, chosen by the owned exception class and never
  from candidate text, the retry's system message also carries `_CITATION_EXCERPT_RETRY_GUIDANCE`. It names the shapes
  in finding 1 and the two that verify (finding 2): no text citation for a figure that carries its `[F#]`, or one whole
  sentence or the whole row exactly as the filing shows it, or leave the figure out. The first generation's bytes
  (`d46ef28f000a`) and a decision-F retry's bytes (`f3b340db1e35`) are unchanged.

The first-generation design (a whole-row rule in `SYSTEM_PROMPT`) was not chosen, for three reasons:
- it changes what all six questions see on their first generation;
- #1111 shows such a change can move text-citation use several-fold;
- its residual failures on the sections source would still be terminal.

It stays the next candidate if the measurement in [`PREREGISTRATION.md`](PREREGISTRATION.md) shows the retry is not
enough.

## Verification (offline, no provider call)

- **Corpus re-verdict** ([`reverdict.py`](reverdict.py), output [`reverdict.txt`](reverdict.txt), exit 0). Main's and
  the change's `_verify_citations` were run over all 3,544 generations. Exactly 12 verdicts change, all terminal to
  regenerable: 11 first generations (7 BABA short, 5 of them on the regex fallback and 2 on sections; 2 ASML short; and
  the 2 collision+short sections draws of 2026-10-15) and 1 retry generation. A retry generation's verdict cannot change what the service does, since there
  is never a third generation. No generation moves between published and withheld, and no published payload changes.
- **Triage transition.** Under the change, `copilot-eval-triage-2026-10-09/f_attribution.py` replays run 38817393205's
  three BABA rows as UNEXPLAINED (exit 3), because it asks for a second generation the run never recorded. Under main
  the same rows reproduce (exit 0). Its `--self-test` passes on both trees. The RUNBOOK's replay paragraph records this.
- The PR body carries the tests, the gates and the mutation proofs.

## Draw 1 (pre-registered): run 38860895429, valid, 17 of 18

The PR head `1ccfa33f`'s copilot-eval draw met every validity condition in the pre-registration: preparation was
complete with sections on, the BABA FY2025 source hashed to `be4499769327`, every first generation to `d46ef28f000a`,
and the one retry to `ae01453ef90d`. The other five questions published 15 of 15 on their first generation.

BABA FY2025:
- **Run 0.** The first generation cited the whole income-statement row (`Revenue 5, 24 868,687 941,168 996,347
  137,300`), which verified and published.
- **Run 2.** The first generation used the XBRL fact alone and published.
- **Run 1.** The first generation cited the bare cell `996,347` beside its row, both as `[1]`. Main's code makes that
  terminal; the change gave it the retry. The retry followed the new guidance, dropping the cell and citing one whole
  sentence, the Note 2 convenience-translation sentence. That failed as a mismatch, for a reason the guidance did not
  cover. The extracted text breaks the line inside the rate (`US$1.00=RMB\n7.2567`), which normalizes to
  `RMB 7.2567`, and the model copied the displayed `RMB7.2567`.

The pre-registration's outcome 1 applied ("BABA rows withheld after their citation retry also failed"), so the PR
returned to draft and the first-generation candidate followed. On the sections source, BABA's first generation under
#1111's prompt has now failed 4 of 6 (3 of 3 on #1350's head, 1 of 3 here), against 1 of 123 under the prompt before
#1111.

## Addendum 1: the first-generation candidate

Four lines in `SYSTEM_PROMPT`, step 3's excerpt bullet, after the shortest-span sentence:
- **The whole-row exception, the panel's first-generation design.** A table figure's excerpt is its whole row, from the
  row label through the last cell; never a lone figure, a header or a partial row. Run 1's first generation already
  held the verifying row as a duplicate declaration.
- **An exact-copy sentence for the draw's own failure.** Copy every excerpt exactly as the supplied text shows it, never
  joining or splitting words, figures or currency signs that the text separates or joins. That covers both the
  `RMB\n7.2567` break and AAPL's glued labels (`Total net sales416,161`).

The retry inherits both, because its system message begins with `SYSTEM_PROMPT`. The eligibility change and
`_CITATION_EXCERPT_RETRY_GUIDANCE` are unchanged. `test_copilot_table_excerpts.py` pins the rule's place in step 3, and
the Note 2 sentence both ways: as the text shows it, published; with the rate joined, a retry. The measurement is
addendum 1 in [`PREREGISTRATION.md`](PREREGISTRATION.md).

## Draw 2 (pre-registered, addendum 1): run 38878772611, valid, 18 of 18

[Run 38878772611](https://github.com/neilmac91/EarningsNerd/actions/runs/38878772611) drew on `ff6836cf`, merged with
main at `0b52b86b`. The draw gate logged "No earlier draw on ff6836cfdd15: this run draws." Every validity condition
held:
- `preparation.json`: status `complete`, `USE_EDGARTOOLS_SECTIONS` true, edgartools `5.58.0`;
- BABA FY2025's source hashed to `be4499769327`, and the other five sources to their sections hashes;
- all 18 first generations hashed to `c221b7e3c5c2`;
- no row took a retry, so neither retry hash occurred.

`accepted: true`: 18 of 18 scored and passed, zero errors. Each question passed on its first generation. Classified with
`classify_corpus.py`:

| Question | First generations citing filing text | Excerpts (all verified) |
| --- | --- | --- |
| AAPL, TSLA, MSFT | 0 of 3 each | none; the new lines added no text citation |
| BABA FY2025 | 0 of 3 | none; each answer used the XBRL fact alone |
| BABA FY2026 | 2 of 3 | one whole sentence; the whole `Consolidated revenue` row |
| ASML | 2 of 3 | the whole `Total net sales` statement row, both times |

On BABA FY2025's sections source, the first generation under #1111's prompt (`d46ef28f000a`) failed 7 of 9 across
three draws on the identical source text:
- 3 of 3 on #1350's head (run 38817393205);
- 1 of 3 in draw 1;
- 3 of 3 in #1347's draw [38932983694](https://github.com/neilmac91/EarningsNerd/actions/runs/38932983694): two
  withheld, one recovered by its retry.

Under addendum 1 it failed 0 of 3. Where this draw cited a table, it cited the whole row. On BABA FY2025 it cited no
text at all. As the pre-registration's power statement says, one draw of three attempts sets a direction, not an
effect size.

Cost: USD 0.065977 across 34 calls, at peak hours. That is USD 0.006 over the USD 0.06 reserved. 184,933 of its
1,072,997 prompt tokens missed the provider's cache, which fits a system prompt the cache had not seen before.

## Main's #1347 and the merge (addendum 2)

#1347 (E28 option 1) merged after draw 2. It parses the summary's sections from the fetched primary document instead of
`Filing.obj()`, and it conflicted with this branch. Its last copilot-eval draw (run 38932983694, on `6546f9f8`)
prepared byte-identical sources for all six questions:

| Question | Source hash, #1347's draw | Source hash, draw 2 |
| --- | --- | --- |
| AAPL sales-gross-profit-2025 | `dfa1fbf6509b` | `dfa1fbf6509b` |
| TSLA sales-operating-income-2024 | `c672b174e4fc` | `c672b174e4fc` |
| MSFT sales-diluted-eps-2025 | `1a68ae488350` | `1a68ae488350` |
| BABA native-revenue-2026 | `5387d3a77820` | `5387d3a77820` |
| BABA viewed-native-revenue-2025 | `be4499769327` | `be4499769327` |
| ASML us-gaap-sales-net-income-2025 | `3d5c91eb152d` | `3d5c91eb152d` |

So draw 2 measured the change on the sources production prepares after #1347. #1347 also landed E25 (the eval
harnesses' `EDGAR_CACHE_DIR`), identically, so the merge takes main's copy and this PR no longer carries it.
`PREREGISTRATION.md`'s addendum 2 says how the merge head's own draw counts.
