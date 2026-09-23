# E7 source-view implementation evidence — 23 September 2026

The source-review helper is implemented at `696bf214`, following integration of verified
main `ebdc4c44`. It is an offline aid, with no readiness, generator, judge or production
activation path. [Usage and limits](../../readiness-2026-09-21/acceptance/source-review-views.md).

The final local gate ran under Python 3.11.16 with the updated dependency locks:
**3,655 passed, 40 warnings in 163.74 seconds**, zero failures/errors/skips. Ruff, Bandit,
package consistency, all four PostgreSQL concurrency lanes and both performance cases passed.
The known interpreter-shutdown logging warning followed successful pytest completion.
[Parsed JUnit receipt](full-gate-receipt.json).

The new invariant test was proved on committed state: deleting one parsed text unit before
normalization caused `1 failed, 2 warnings in 0.92s`; byte-identical restoration produced
`1 passed, 2 warnings in 0.99s`. The source hash was verified restored. This mutation did not
change a readiness or budget guard. [Proof receipt](mutation-proof.json).

The H29 pilot dossier preserves four approved source packets and all five embedded members,
including EX-99.2 and both decoded graphics. All six HTML views match an independent parser's
normalized text; structural reader table/row/image/exclusion markers match their complete
inventories. The three members retain 94 tables and 14 image references. The six readers total
300,432 bytes. [Actual-input audit](reader-pilot-audit.json). The independent reviewer rebuilt
all six views and reproduced their artifacts byte-for-byte.

[Independent review](source-view-review.md) records correctness, rule and gate scope and two
refutations per candidate issue. It approves bounded H29 preparation, not general browser
rendering or untested large-file capacity. Real source-only A/B reviews were dispatched to
separate fresh contexts after this input audit. Their conclusions are separate evidence;
this implementation receipt claims no complete reference or quality acceptance.

The two earlier automatically denied E7 mutation proofs remain unresolved and were not retried.
The founder marked #940 ready for review during this tranche; that UI state is preserved.
The PR remains unmerged and its outstanding evidence requirements remain in force.
