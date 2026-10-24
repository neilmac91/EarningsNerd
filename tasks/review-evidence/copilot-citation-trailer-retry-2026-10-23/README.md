# Copilot citation trailer: the one private regeneration (2026-10-23)

copilot-eval withheld BABA `viewed-native-revenue-2025`, draw 2, on #1377's head `d84e07b` (run 38942183029:
18 completed, 17 passed, 1 execution error) with `publication withheld: Unexpected citation trailer`. The
attribution is [#1377's comment](https://github.com/neilmac91/EarningsNerd/pull/1377#issuecomment-6221481880). The
records PR #1504 queued the fix.

## The recorded candidate

The row's only generation, read from the run's artifact (`copilot-fidelity-38942183029`, `copilot-eval.json`),
holds two `===CITATIONS===` lines. After the first array it wrote a note and a second array:

```
===CITATIONS===
[{"n": 1, "excerpt": "996,347", ...}, {"n": 1, "excerpt": "137,300", ...}]

Note: the excerpts above are too short to meet the minimum length requirement, so I'll provide a proper contiguous span instead.

===CITATIONS===
[{"n": 1, "excerpt": "Revenue 5, 24 868,687 941,168 996,347 137,300", ...}]

===FOLLOWUPS===
[...]
```

`_parse_citations` (`backend/app/services/copilot/envelope.py`) admits one array, then only the followups block,
so the text after the first array was rejected before any excerpt was checked. On main `8b6f1bd8` that reason
was terminal: the question ended in the generic publication error, with its quota unit refunded.

## The change

The trailer rejection is now `_RegenerableCitationTrailer`, an owned class with the same logged reason. It buys
the one private regeneration, under the same rules as the other two retries: a fresh generation from the original
filing and question, the same source, usage accounting and 75-second deadline, every admission check on the
replacement, and the rejected candidate never published or put into a prompt. Unlike the other two it adds no
guidance text. The candidate was never source-matched, so `_retry_guidance` returns `""` for it: the
regeneration re-samples with `SYSTEM_PROMPT` byte-identical, the composition every first generation already runs.
A terminal rejection now returns `None`, so an empty guidance and "no regeneration" are distinct values.

| Composition | SHA-256 prefix |
| --- | --- |
| First generation (`SYSTEM_PROMPT`) | `c221b7e3c5c2`, unchanged |
| Retry after a decision-F rejection | `34d01dadbac0`, unchanged |
| Retry after a citation failure | `bf240eb01f4c`, unchanged |
| Retry after a trailer rejection | `c221b7e3c5c2`, the first generation's bytes |

Fed through this checkout's parser and chooser offline, the recorded candidate above (`results[14]` of the
artifact's `copilot-eval.json`, generation 0, its 185 deltas joined, SHA-256 `46ce40bcfcb0`; the text after its
first `===CITATIONS===` line through `_parse_citations`, then `_retry_guidance`) raises
`_RegenerableCitationTrailer('Unexpected citation trailer')`, selects `""`, and the regeneration's system message
hashes to `c221b7e3c5c2`. On main it raises `_UnpublishableAnswer` and selects no regeneration.

A re-sample can repeat the trailer, or, for a generation cut off by its output length (`===FOLLOWU`), the cut.
A second rejection is terminal, which is what main does with the first one, so this is never worse than main.

## The withdrawn guidance, `863fb9b91a4e`

This PR's earlier pushed heads (`925b0799`, `d4d9c510`) appended a one-array guidance text,
`_CITATION_TRAILER_RETRY_GUIDANCE`, to the trailer retry: composition `863fb9b91a4e`. The
[owner review](https://github.com/neilmac91/EarningsNerd/pull/1551#issuecomment-6376378669) asked for an aggregate
gate on that composition, and a [measurement plan](https://github.com/neilmac91/EarningsNerd/pull/1551#issuecomment-6377081980)
was posted for it. Its step 0 (below) found no trailer at all in the current prompt's first generations, so the
guidance had nothing measurable to improve, and its forced arm would mostly have measured AAPL's quotation check
(see "Not run"). The guidance is withdrawn unmeasured. No live call ever sent it: both of the PR's copilot-eval
runs on those heads (40035743783 on `925b0799`, 40035787132 on `d4d9c510`) were skipped as drafts and have no
artifact (`step0-summary.json`, "caveats").

## Step 0: how often the first generation trips the trailer check

[Posted on the PR](https://github.com/neilmac91/EarningsNerd/pull/1551#issuecomment-6377395045) on 2026-10-24 from
every copilot-eval run created from #1360's merge (2026-10-16T18:54:49Z) to 2026-10-23T23:53:45Z: 181 runs listed,
89 with an artifact, 78 reports read, 76 used. Each first generation whose system message hashed to `c221b7e3c5c2`
was replayed offline through `d4d9c510`'s scanner, parser and `_verify_citations`; the later stages' verdicts are
the runs' recorded reasons.

| Question | First generations | Rejected | Rate | Reasons |
| --- | --- | --- | --- | --- |
| AAPL `sales-gross-profit-2025` | 228 | 34 | 0.1491 | decision-F `quotation_not_in_source` 33; citation collision 1 |
| ASML `us-gaap-sales-net-income-2025` | 228 | 0 | 0 | none |
| BABA `viewed-native-revenue-2025` | 228 | 0 | 0 | none |
| BABA `native-revenue-2026` | 228 | 0 | 0 | none |
| MSFT `sales-diluted-eps-2025` | 228 | 0 | 0 | none |
| TSLA `sales-operating-income-2024` | 228 | 1 | 0.0044 | citation mismatch 1 |
| All | 1,368 | 35 | 0.0256 | `Unexpected citation trailer`: **0** |

Zero trailers in 1,368 bounds the rate at about 0.22% (exact binomial, 95%). The motivating trailer came from run
38942183029, before #1360, under the earlier first-generation composition `d46ef28f000a`. 33 of the 35 rejected
first generations were published by their run's own retry (`34d01dadbac0` or `bf240eb01f4c`). The summary's
caveats (mixed head code, post-verify verdicts taken from the record, draws that are not independent) are in
`step0-summary.json`.

After that listing, nine more copilot-eval runs drew 18/18 on heads where a trailer is terminal, so none of
their 162 first generations was a trailer: 40043032806, 40043359889, 40043362321, 40045472164, 40060856633,
40061189712, 40075823956, 40075949031 and 40075956940 (all concluded `success` with a full `copilot-fidelity-<run>`
artifact, created 2026-10-24T00:03Z to 07:54Z). Two of their reports, 40075823956 and 40075956940, were re-read offline: all 36 first generations hashed
to `c221b7e3c5c2`. That makes 1,530 first generations under this composition since #1360 with no trailer. Of
those, 1,404 were hashed (step 0's 1,368 and these 36). The other 126 drew 18/18 where a trailer is terminal, so none
was a trailer, but their system messages were not hashed.

## Not run: the forced arm

The plan's forced arm would have replayed this incident's candidate as each row's first generation, so that every
row's retry ran under `863fb9b91a4e`, in three draws of 18. Each retry would have been its row's last generation,
so a harmless guidance still loses rows at the first-generation rates above: the chance that all 54 rows publish
is about 0.22 (0.8509^9 x 0.9956^9, AAPL and TSLA). The likely readout, "not recovered" on AAPL's quotation
check with no harm shown, leads to the same choice that is available without spending. Path R makes the
measurement unnecessary: the retry sends the composition the 1,530 first generations above already ran.

## Measurement

The trailer retry sends `c221b7e3c5c2`, measured on sections as the first generation (the RUNBOOK's revision row
for `c221b7e3c5c2`, run 38878772611). The eligibility half is a guard change and gates offline
(`backend/evals/RUNBOOK.md`, "Gating rule"): `backend/tests/unit/test_copilot_quotation_retry.py` and
`backend/tests/unit/test_copilot_prompt_revisions.py`. The ready mark's copilot-eval draw must still be 18/18,
with every first generation `c221b7e3c5c2` and every retry one of `34d01dadbac0`, `bf240eb01f4c` or
`c221b7e3c5c2`. Each retry's hash must match the previous generation's recorded `withheld_reasons`:
`34d01dadbac0` only after a decision-F reason, `bf240eb01f4c` only after `Unverified or ambiguous referenced
citation`, and `c221b7e3c5c2` only after `Unexpected citation trailer`. Its `preparation.json` and the rows' source
hashes must show that every source that should have sections was prepared with them
(`lessons/evals-measure-a-copilot-change-on-the-source-production-uses.md`).

**The ready-mark draw:** [copilot-eval run 40092955405](https://github.com/neilmac91/EarningsNerd/actions/runs/40092955405)
on head `f02ec4b6`, 2026-10-24T12:12Z to 12:14Z, concluded `success`. Its artifact `copilot-fidelity-40092955405`
(artifact 12559482529, SHA-256 `e03fc9ca514bf550e623582e68f4279a8f8458a2e902f485c1e21466c781e08e`) was re-read
offline. It meets all three checks:

- **18/18:** `expected 18, completed 18, scored 18, errors 0, passed 18`, accepted.
- **Hashes:** each of the 18 rows made one generation, and all 18 first generations' system messages hash to
  `c221b7e3c5c2` (`sha256(content)[:12]`, as `test_copilot_prompt_revisions.py` computes it). No generation recorded
  a `withheld_reasons` entry, so no retry was sent and the pairing check has no case.
- **Sections:** `preparation.json` reads status `complete` with no errors, over six sources of three rows each. Five
  were prepared with sections: the AAPL, TSLA and MSFT 10-Ks and BABA's two 20-Fs, whose `sections.json` files run
  from 85,506 to 564,670 bytes and match their recorded SHA-256. Their rows' source texts open with the sections
  excerpt's `ITEM 8 -` or `ITEM 18 -` heading. ASML's 20-F has a 4-byte `sections.json` (`null`). That is its
  documented regex fallback: its 20-F has no parsable item headings (`backend/evals/RUNBOOK.md`, "Huge document
  section parse slow or skipped"). Every row's source text hashes to its source's prepared `excerpt.txt`.

The draw adds 18 hashed first generations under `c221b7e3c5c2`, none a trailer.

## Step-0 files

Copied unedited from the session that posted step 0, so the posted hashes still verify. The tools ran against
`d4d9c510`'s app code (H). `step0-summary.json`'s `output_files` field and every `step0-generations.jsonl`
record's `report` field keep that session's absolute paths; editing either would change the posted hash.

| File | SHA-256 | What it is |
| --- | --- | --- |
| [step0-summary.json](step0/step0-summary.json) | `ebe6504739392644e73088922ad478ee140e809cef66513204705476f23b196d` | the result, method, classifier changes and caveats |
| [step0-summary.md](step0/step0-summary.md) | `4992d08369126ea5b1fb3577bed2e835badb5cecd78c811fdf23c73099305126` | the table above, as posted |
| [step0-generations.jsonl](step0/step0-generations.jsonl) | `bc8e989a98b5681c894e5ff3bca709109e622767ea1d5fe3a6b7b1aacb9702ba` | one classified record per retained generation (1,439) |
| [step0-artifacts.txt](step0/step0-artifacts.txt) | `be28e9b72039fea4721b16913dde322c44704da57deb638a4338037edd006047` | the artifacts read: run, artifact and head SHA |
| [tools/classify_corpus_h.py](step0/tools/classify_corpus_h.py) | `1fcda11d0976182aa64220d0cd6a4b22d934ab7c3fecbe3cb53dabd1f3d5d8d8` | the per-generation classifier |
| [tools/classify_corpus_h.diff](step0/tools/classify_corpus_h.diff) | `e70a12be65ad2a8661b8a6c744475b95a2e0144d177f30316cc9c9ad0ac315f1` | its diff from the 2026-10-16 classifier |
| [tools/summarize_step0.py](step0/tools/summarize_step0.py) | `39687dbdb7fd82047842d47ef7242657aba690ade8239f47e2ab193e80b61639` | builds the summary from the classified records |
| [tools/prescan.py](step0/tools/prescan.py) | `bbac6683561903ca32722fcbfe12a5248f78c9f573ffe6363fad2ae73d01ed00` | picks the usable reports |
| [tools/fetch_artifacts.sh](step0/tools/fetch_artifacts.sh) | `db0dfcba12df230afcf32d0d5ac750878084257da1359835e3f7e0a315a961fa` | downloads each artifact and extracts only its report files |
| [tools/head_code_diff.sh](step0/tools/head_code_diff.sh) | `3248aec77ff7c49b0795e06c5e9c985e33b500cb3a197986488c65d0efb226b0` | compares each run head's Copilot files with H |

The diff's base, `tools/classify_corpus.orig.py` in its header, is byte-identical to the committed
[2026-10-16 classifier](../copilot-table-excerpt-retry-2026-10-16/classify_corpus.py) (SHA-256 `42d102d4…71c8`),
so it is not copied again. `classify_corpus_h.py`'s `chooser` reads an empty guidance as "terminal", which was
H's meaning. Under this head an empty guidance is the trailer's re-sample and `None` is terminal, so the classifier
would label a trailer "terminal" if re-run here; step 0 found no trailer, so its counts are unaffected.
