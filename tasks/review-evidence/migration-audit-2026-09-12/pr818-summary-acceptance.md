# PR #818 summary accounting acceptance — September 12

CI run 34686113163 / evaluation job 103533271228 passed on synthetic merge f2c8a635c681fe106bb84d88d036d51a6713083f, whose parents are main bf0ff3bf2dbbacef25f97945d470430ce0b5e26b and reviewed head 208767ff4ae2016b55cb834316b88a3eb18649be. Root fetched the merge and verified its whole tree identical to the fully gated head. Report SHA256: 0af78f2034d2695fbbf788510f1ebec1f62fad2101cebb47c746d268e819f415.

All 52 expected identities (26 verified filings, two repeats) are present exactly once; the golden-file hash matches committed bytes. All 52 completed without error and passed the existing hard scorer gates. Actual calls all returned deepseek-flash. No judge or fallback was enabled.

Independent offline reconciliation of every final/retry record, candidate summary and actual ai_call log found no discrepancy: 52 calls, zero unknown calls, 2,166,940 prompt tokens and 195,399 completion tokens; cache hits 2,157,050 and misses 9,890. Reasoning tokens are unavailable, not zero. There were no outer retries in this assessment, so actual failure-path evidence comes from the retained committed mutation and local invariant tests, not an invented live failure. The accounting report and log agree exactly; this is not an invoice or proof that historical missing records can be recovered. The legacy $cost column remains a placeholder and must not be read as free generation.

No prompt, application, source acquisition, normalization, preview or scorer implementation changed in this PR. This is acceptance of usage conservation and the existing regression gate, not a fresh manual financial review or a world-class quality claim. The report still contains advisory figure-trace observations. Existing Fable/Codex narrative findings and source-coverage limits remain in the quality queue.

Evidence: pr818-summary/eval_20260912T094019Z.json, its paired Markdown and ci-execution.txt; pr818-summary.log; pr818-summary-conservation.json. Offline checker check-pr818-usage.py imports no application code and makes no calls.
