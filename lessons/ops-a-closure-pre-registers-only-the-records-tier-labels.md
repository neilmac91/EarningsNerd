# Pre-register only a survey, a fact-check and one reviewer for a records pull request's own review, each once

Date: 2026-10-30 · Area: ops / CODE RED records / review tiers

**Context.** Every CODE RED decision record's pull request opens with a closure, an append-only JSON file under
`tasks/code-red-20261004/runtime/control/` that registers the contexts the chief launched and pre-registers, before any
launch, the labels of the contexts it launches next. A records pull request is reviewed at the records tier of
`AGENTS.md` §5, and for its own review the CODE RED records allow three contexts per record N: a read-only survey of
the window, a fact-check workflow and one reviewer, which runs its own same-context delta checks. Refuters, review
lenses, delta reviewers and second reviewers belong to the routine and high tiers. The chief checked each
pre-registered context against its pull request's tier by hand, and the closures from before the gate carry 23 labels
the rule refuses: review lenses, refuters and independent or delta reviewers for records 02 to 08 (`decisions-NN-…`,
closures 139 to 153), delta reviewers for records 09 and 17, second reviewers for records 21 and 45, and an others
check for record 36 (closures 157 to 196). The founder approved a machine gate for the hand check (CLAUDE.md rule 12).

**Rule.** For a records pull request's own review, pre-register only `record-N-survey-01`, `record-N-factcheck-01` and
`record-N-reviewer-01`, each in one closure and by one context. Any other pre-registered label that names a record (one
starting `record-N-` or `decisions-N-`, in any case) fails the records gate, which names the closure and the label: a
refuter, a review lens, a delta or second reviewer, or one of the three again, in a later closure or on a second
context. A `new_provisional_contexts` entry without the `:launched-after-this-record:` marker fails too, since its label
cannot be read. Closures are never edited, so the labels from before the gate stay, pinned as exact (closure, label)
pairs: a new violation fails, an exempt label used in any other closure fails, and an exemption that no longer matches
its closure fails. Engineering labels (`…-pr-01`) name code pull requests' contexts, which have tiers of their own, and
are outside this rule.

**Sources.** `backend/tests/unit/test_code_red_runtime_records.py`: `_record_label_violations` (the pure check over
parsed closures), `PRE_GATE_RECORD_LABELS` (the frozen pairs), `test_closures_pre_register_only_the_records_tier_labels`
(the committed closures) and `test_records_tier_label_check_on_planted_closures` (the planted cases), run as "records
gate" by `tasks/code-red-20261004/runtime/tools/records-gate.sh` and by CI's backend suite; `AGENTS.md` §5 (the records
tier); `lessons/arch-gate-reference-values-are-themselves-gated.md` (why the exemption set is pinned in both
directions).
