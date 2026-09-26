# E7 graph custody: bounded independent review

Reviewed PR head `c8c90ace48b0d199f200f5cccf3919f01cf18058` and its main merge
`b53455bb3b13817d44cf089f3280ced143998583`. Both accept all three synthetic counterexamples in
the retained [replay runner](e7-graph-reproductions.py.txt). Codex independently replayed the
runner against the main merge. It reads committed fixture/code with `git show`, imports only
the local offline custody dependency and runs no pytest/provider/network/guard operation.

Use an otherwise clean checkout of the stated revision so the imported unit-validator dependency
matches it. Save the attached text as a temporary `.py` file and run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/e7-graph-reproductions.py /path/to/EarningsNerd b53455bb3b13817d44cf089f3280ced143998583
```

Exit 0 means the three invalid evidence constructions are still accepted. This is a reproduction
of missing rejection, not a passing acceptance test. The runner is retained audit evidence, not
a new CI test home.

## 1. Prompt construction is not verified

`backend/evals/acceptance_source_review_graph.py:270` onward compares independently declared
input and template hashes, and verifies that some bytes match the declared rendered-prompt hash.
It never derives those bytes from the frozen template and complete input. Replacing leaf `l2`'s
prompt with `ARBITRARY PROMPT THAT DOES NOT RENDER TEMPLATE OR INCLUDE UNIT INPUT`, changing
only its prompt hash/artifact entry, still validates.

Refutation checks: a static trace of the validator and all rendering references found no renderer
or equivalent canonical-input construction; the executed counterexample independently confirms
the gap. This conflicts with the existing
[integration requirement](../../readiness-2026-09-21/acceptance/source-review-hierarchy-integration.md)
that arbitrary prompt bytes beside a template label are insufficient.

Minimum repair: bind and recompute a versioned deterministic prompt/envelope from the frozen
template and all declared inputs. Account for every separately supplied modality/source input.
Reject omitted, altered, reordered or additional input content where it violates that contract.
This proves submitted construction, not that the model attended to every byte.

## 2. Caller-declared history cannot prove complete attempt custody

The registry fields at `acceptance_source_review_graph.py:59` describe only context, node,
attempt number and status. The validator has no trusted previous registry or external expected
history. Delete compacted `ctx-l1-a`, renumber successful `ctx-l1-b` from attempt 2 to 1, and the
graph validates with `ctx-l1-a` missing from its returned `source_context_closure`.

Refutation checks: the schema/consumer trace found no independently retained history authority;
the executed deletion/renumbering case passes. The planned output-review exclusion would miss
that earlier source context if it trusted this closure.

Minimum repair at admission: compare against an independently retained, frozen attempt inventory
that records each attempt's contract/input/prompt identity, context and outcome, including adverse
or partial artifacts when present. Reuse an existing operator execution ledger where possible.
A hash chain whose entire history and root are supplied afresh by the same caller cannot by itself
detect deletion. Until that boundary exists, describe this output as a caller-declared context
list and keep it unavailable as an authoritative admission/exclusion closure.

## 3. Unused allowed templates escape alias checks

At `acceptance_source_review_graph.py:289` the alias checks cover templates encountered while
visiting instantiated nodes. In a valid graph with no reducer node, declare the optional reducer
template hash equal to leaf `l1`'s output hash and omit the original reducer-template bytes. The
graph validates with zero reducers.

Refutation checks: contract validation only syntax-checks that unused declaration; the executed
unused-kind fixture accepts the alias. The earlier later-template/earlier-output fix in `c8c90ac`
does not cover a node kind never visited.

Minimum repair: freeze and verify the bytes of every template declared by the role contract before
traversing nodes, and compare all node output hashes against that full set. A targeted change to
the existing artifact rule is sufficient; another general validation framework is unnecessary.

## Impact, evidence and handback

The module is deliberately offline and non-admitting. Repository search found imports only in
custody code/tests/documentation and no serving or paid-generation call site. These are blockers
to trusting future E7 hierarchy admission, not an observed production incident or a reason to
roll back a healthy service.

The exact merged head has green hosted backend/PostgreSQL gates. The retained local log is for
`fe03cd0`; request any missing final-head local receipt from the owner, without relabeling the old
log or repeating hosted checks just to recreate a report.

The current owner should return a small corrective PR, exact-head gate evidence and focused
regression/fault-restoration proofs. Independent review should try to refute the corrections,
then move to the real H29 source pair and reconciliation. Actual source reviews, issue propagation,
modality composition and readiness/decision integration remain separate outstanding outcomes.
