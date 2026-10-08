# Independent custody and telemetry verification, 2026-10-08

This is the verification half of the evidence task Codex queued on #1029 (comment 5966195498). The four archives are those of the Copilot prompt-candidate measurement (#1074, handback 5965113700).

## Method

Four independent verifier agents each took one archive, and a fifth agent cross-checked the handback. They worked read-only and made no model calls.

Each verifier:
- downloaded a **fresh** copy of its archive through the Actions artifacts API, into a new empty directory;
- did not use the operator's analysis scripts, and read the archive contents only with its own code, run with `python -I`;
- compared:
  - the fresh zip with the API digest, and byte for byte with the operator's scratch copy;
  - the posted hashes with the members;
  - every posted figure with its own recomputation from the raw files.

The registered repository tools ran only as a second opinion. These were `prose_quote_audit.py`, `f_attribution.py` (also re-run against a `git archive` of the merge ref's backend) and `copilot_cost_runnerlog.py`.

The critic then checked each of 35 claims in the handback's outcome, evidence, telemetry and custody sections. It checked them against the four reports and, where a report was silent, against the fresh extractions.

## Custody: 4 of 4 match

| Archive | Fresh zip sha256 = API digest = scratch copy (byte-identical) | Members |
| --- | --- | --- |
| `eval-report-37092291865` (row R(i)) | `b2faabf1726d63c600ad469a08dec0647cda692ebd90f2a030ea1ba6f9959a65` | 3 |
| `copilot-fidelity-37092951315` (Q1) | `0280b6ec48e2f359972eec0d0fad2a4861e2b721a99059688fcb6a837294bfc9` | 76 |
| `copilot-fidelity-37093200860` (Q2) | `4dbdd9e450386d36f4cf07f58c87a276ec62b78e122a952d66a04f132aa029fe` | 76 |
| `copilot-fidelity-37093395884` (Q3) | `93748f158813046391cc9ec8da8bfa3d9a2d54dbcfcc900c63692aad698c8f42` | 76 |

- **Members:** all 231 member hashes are in [members.tsv](members.tsv). The posted member hashes (`eval_*.json`, `.md` and `ci-execution.txt`; `copilot-eval.json`, `runner.log` and `copilot-eval.md`) all match.
- **Safety:** no archive contains absolute paths, `..` entries or symlinks.
- **Q2 and Q3:** `preparation.database_sha256` matches `prepared-source.db`, and every `preparation.sources` hash matches its extracted file.

## Telemetry and outcomes: every posted run figure reproduces

| Run | Recomputed from the raw files | Posted |
| --- | --- | --- |
| eval-baseline | 70 rows / 70 scored / 0 errors / 0 retried, pass rate 1.0. 70 calls, 0 unknown. 2,755,570 prompt tokens (2,741,494 hit, 14,076 miss), 275,109 completion. The per-result usage sums equal the summary exactly. Cost exact 0.175401282. Regression-gate step: success. | 0.175401 |
| Q1 | 18 / 17 scored / 1 error (AAPL `sales-gross-profit-2025` d0, `quotation_not_in_source`, quoting `"gross profit,"`), `accepted` false. Checks 1–3 pass; 4 and 5 fail; R(ii) passes on 17 rows. 31 `ai_call` lines, 0 unknown, 0 peak. 782,976 hit, 184,141 miss, 4,008 completion. Fingerprint `aeb56401` on all 31. Cost exact 0.032374878. | 0.032375 |
| Q2 | 18/18/18, 0 errors, `accepted` true. Checks 1–5 and R(ii) pass. 33 calls, 0 unknown, 0 peak. 1,028,224 / 6,599 / 4,286. `aeb56401` on all 33. Cost exact 0.006646122. | 0.006646 |
| Q3 | 18/18/18, 0 errors, `accepted` true. Checks 1, 2 and 5 pass; 3 and 4 fail under the strict reading: raw `composed_quote_rows` holds AAPL d0, AAPL d1 and ASML d2, and decision F found all four spans in the source. R(ii) passes. 33 calls, 0 unknown, 0 peak. 1,034,880 / 6,549 / 4,444. `aeb56401` on all 33. Cost exact 0.00675339. | 0.006753 |

Supporting facts the verifiers also confirmed:
- **Prompt identity:** every one of the 54 rows carries the system prompt `a22fb4cd…09f5` (5289 characters).
- **Merge ref and tree:** every run used merge ref `3a5c5894`, whose parents are `82556d6e` and `437e245c`, and `git diff --quiet 437e245c 3a5c5894 -- backend .github` exits 0.
- **Tool-use strings:** they are as posted. 10-K: 27/27 across the three runs. 20-F tool-using question-runs: 1/3, 2/3 and 2/3.
- **Rates:** `llm_pricing.py` holds deepseek-flash at 0.003 / 0.15 / 0.60 USD per 1M tokens, and `config.py`'s `AI_PEAK_PRICE_MULTIPLIER` is 2.0. Both are identical at `3a5c5894`, at `437e245c` and on main.

**Lane total.** The exact total is 0.221175672. The sum of the per-run figures rounded to 6 decimals is 0.221175, which is the posted figure. If each call is rounded first, as the logs' own `estimated_cost_usd` does, the sum is 0.221181.

## Critic: 33 of 35 handback claims confirmed

- **UNVERIFIED: the DeepSeek balance readings.** No archive records them and no provider-side record was obtained; only the operator reported them.
- **CONTRADICTED: "Every gap is within cent resolution."** It is wrong per run. For each run, the balance drop and its known cost were:

  | Run | Balance drop | Known cost | Gap |
  | --- | --- | --- | --- |
  | eval-baseline | 0.16 | 0.175401 | −0.0154 |
  | Q1 | 0.02 | 0.032375 | −0.0124 |
  | Q2 | 0.02 | 0.006646 | +0.0134 |
  | Q3 | 0.01 | 0.006753 | +0.0032 |

  Three of the four exceed the ±0.01 that two cent-rounded readings allow. The pattern fits charges debited after the reading that followed each run: under-reads early, then catch-up. The handback's seven readings are 43.12 → 42.96 → 42.94 → 42.93 → 42.91 → 42.91 → 42.90. The four per-run drops above sum to 0.21; the remaining 0.01 is the 42.94 → 42.93 step between the Q1 and Q2 runs, which the table assigns to no run and which fits the same late-debit pattern. Over the whole lane the balance fell 0.22 against a known 0.221175, which is within resolution. The correction is posted on #1029 (comment 6054003539).

## Other clarifications to the handback

- **The eval-baseline archive records cost 0.0** (`total_cost_usd` and every row's `cost_usd`). Its 0.175401 is priced from the token telemetry.
- **Peak status of the 70 eval calls:** those calls carry no timestamps or peak flags. The off-peak status rests on the job's timestamps on Saturday 2026-10-03, because at 03:xx UTC on a weekday those calls would have been peak.
- **"0 table figures in quotation marks"** counts `quote_inventory.py`'s table-figure heuristic. Q3 ASML d2 quoted two figure-bearing MD&A sentences, which decision F's normalised check found in the source (it folds the source's space before each comma) and published.

## Merge ref reproducibility

Since #1074 closed, `3a5c5894` is no longer pinned by any GitHub ref, so it could be garbage-collected. That does not matter, because its tree is reproducible:

```
git rev-parse 3a5c5894^{tree}                                       # e8e617c1ec589b7ab775364844632bc20f95069c
git merge-tree --write-tree 82556d6ec232e8ae5f0dfa4c951aa6fb5c695e39 \
                            437e245c824516ec8a552c2fd6dced0e0bc0091f  # e8e617c1ec589b7ab775364844632bc20f95069c
```

Both parents stay reachable: `82556d6e` is on main, and `437e245c` is the head of the branch `claude/copilot-prompt-candidate` (kept by the founder's decision of 2026-10-08) and of `refs/pull/1074/head`. The validity diff can be rerun as `git diff --quiet 437e245c $(git merge-tree --write-tree 82556d6e 437e245c) -- backend .github`.

## Limits

- The balance readings are not checked against a provider invoice. The ledger's 7.346893 base is historical and unreconciled, as Codex's disposition says (#1029 comment 5964926509).
- The regression-gate step's log was not read, only its `success` conclusion.
- The arm-B comparison and the pre-window gates (5565 passed, M0–M4, three-lens APPROVE) were not re-derived from archives. The 5565-passed gate is on record in #1029 comment 5964670480 and the handback, the mutations in the evidence folder's `mutations.txt`, and the final review in [final-review-437e245c.md](final-review-437e245c.md) for the final review round.
- `f_attribution.py` reproduces against a backend export of `437e245c` or `3a5c5894`. The current main's `copilot_service.py` differs.
- The verifiers' own scripts and fresh extractions stayed in the session's scratch space, which is not durable. [recompute_archives.py](recompute_archives.py) re-derives the headline figures from preserved zips without them.
