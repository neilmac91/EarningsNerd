# Complete quarterly tax-cause withholding — engineering record

The implementation and correction records below preserve their original stage. The current
integration is recorded at the end; publication and deployment status belong to the pull request.

Base: `0863a4b299b9f066b12a98852caa205857628656`. Implementation: `c8a0011fe4252d0ee0cfe31a243f87da997ce0a5`.
Namespace correction: `d0d44929790d723990cc44187e0bb7790385032a`. No publication authorization is implied.
Evidence-consumer correction: `137b56906994c884de93402752662a980f420aa0`.

The retained FIGS run-1 impact transfers a statutory-rate explanation to a year comparison. The
new owner replaces only the complete admitted authored sentence with:

> This summary could not independently verify the explanation of the tax-rate change.

It does not say the claim is false, the filing lacks disclosure, or a different cause is correct.
The previously held reconciliation/sign commit `1d65925712f13266130f954b2b768e80b07c68c2` and
the complete-note quotation proposal remain held. The latter omitted governing withdrawal or
hypothetical context outside the tagged chain; this candidate never renders that chain.

## Finite contract

The authored value must completely match the case-sensitive grammar in
`app/services/ai/tax_rate_explanation.py`: a three-month current/prior rate comparison with a
valid English-month date, year 1900–2099, bounded one-decimal rates, and the exact driver phrase
"limitations on the deductibility of officer compensation and state taxes." There is no ticker,
issuer, accession, numeric-value selector or wildcard cause. Any other prefix, tail, qualification,
date, operand or driver stays authored. The phrase's limited coverage is deliberate.

The independent evidence must have one exact normalized occurrence in one complete tagged tax
note/continuation chain. Recognized namespace bindings, no local rebinding, actual qualified
tags, unique IDs, same issuer/report end, complete nondimensional durations, exact current and
prior three-calendar-month windows, pure units, scale -2, decimals 3 and bounded lexical rates
are required. These identify source operands; `assertion_scope` remains `not_established`.
The supported transformation namespace is the retained 2020-02-12 registry; unsupported
namespaces/layouts abstain. The annual disclosure parser is unchanged.

A complete source paragraph matching the same closed explanation and operands excludes
withholding. This exclusion does not certify that paragraph's truth. Unknown source formulations
may still produce the capability limitation, which must not be presented as a source-absence
finding. Missing, malformed or ambiguous source stays authored.

Only canonical `impact` is rendered by production. Both real independent-evidence aliases are
supported with the same truthy fallback as read-time provenance; two populated conflicting
`supporting_evidence`/`supportingEvidence` values abstain. Whitespace remains truthy. No unsupported
section/impact alias was added. Evidence bytes, source references and other notes survive.
Application audit records are stripped from model payloads at every depth. The new audit is
constructed only in the final outer envelope and has no render authority. The source selector
and audit do not enter provider requests, canonical judge payloads or Copilot context.

Admission uses originally authored evidence before evidence snapping, in both preview and final.
A near-match repaired to a real source sentence by the existing armed snap gate cannot newly admit
the impact. That independent gate retains its existing evidence behavior; the tax owner changes
only impact and does not use repaired evidence as original source selection.

Recovery notes use the same independent complete-native-source contract. They need no assumption
about the primary prompt excerpt. The primary preview does not display a note that has not yet
been recovered. Retained authored denials and absent native sources still abstain after recovery.

## Existing gates and actual fault/restoration

Extend the existing disclosure and statement-integration gates, using the pinned retained source
and output under `backend/tests/fixtures/tax_rate_comparison`. Raw source SHA-256:
`513789f462c784068a92153e69ccfd46a1f1029b4e449f284de34e463b3c2272`.
Retained output report SHA-256:
`deaa1b52c85bbab1bbcd19b7e55ab483b58ec465d6523272931cbd67e6c7f80b`.
The historical generation raw differed by ten characters; this is an offline retained-source
application replay, not an exact historical raw replay or a fresh evaluation.

The actual streamed provider mock, final assembly, persisted/read enrichment, shared Markdown,
PDF HTML and CSV consumers are exercised. The positive rates and issuer are changed together in
a generic control. Authored denial/hypothesis/unknown prefix/tail, exact source explanation,
wrong operands, alias conflicts, forged audits, inside/outside source qualifications and recovery
are included. Expanded committed source/consumer gate: **137 passed**.

One replacement-boundary mutation on committed `c8a0011f` changed only authored
`_CLAIM.fullmatch(text)` to `_CLAIM.search(text)`. Actual result:

```text
3 failed, 1 passed, 47 deselected
FAILED ...[denial]
FAILED ...[tail]
FAILED ...[recovered_denial]
restored: 4 passed, 47 deselected
```

The source bytes before and after were identical, SHA-256
`68d2a8d0a6c569c061655968b056abde3283564e856f9a648787092163ff48e4`.

Independent review then found namespace impostors. A distinct source-identity mutation on
committed `d0d44929` bypassed `_namespaces_valid(document)` at source admission:

```text
10 failed, 1 passed, 73 deselected
restored: 11 passed, 73 deselected
```

The restored source SHA-256 is
`5886b194314d1c38d79a2cea1796a70d610565a1f99b813ea6cf201054bddc13`.
Both mutations used fresh bytecode caches, restored byte-for-byte, and ended with a clean checkout.
Full logs, exact fault patches and replay artifacts are in the operator's
`outputs/overnight-2026-09-28/quality/figs-tax-withholding-candidate/`.

The later committed consumer gate on `137b5690` passed **143** cases. Replacing its actual
truthy alias fallback with `get(default)` failed both empty/null canonical controls:
`2 failed, 57 deselected`; byte-identical restoration: `2 passed, 57 deselected`.
Restored binder SHA-256: `860a9fa26a90831ab188e3caa8c445e613dbaba0111abd4e144412ccb78caaa4`.
Moving the eligibility call after the existing armed evidence snap failed the real near-evidence
control: `1 failed, 58 deselected`; restoration: `1 passed, 58 deselected`.
Restored facade SHA-256: `bf414c4815271f14d4db3214c3d4251f905c3d30c22d0f879faa3e656f83dea0`.
These faults and restorations also used fresh caches and ended with a clean checkout.

## Review and refutations

- Whole-impact deletion risk: first trace the sole mutation (`note["impact"]`) and complete
  matching condition; then challenge it through actual denial/tail/recovered-denial consumers.
  The faulty substring matcher fails those controls. The restored matcher preserves them.
- Selector identity risk: a correct root binding does not reject a local rebinding; independently,
  correct declarations do not reject another prefix with the same local name. Both reproduced
  refutations supported the review finding. The new checks and expanded gate address both.
- Authority risk: matching operands cannot establish a causal comparison. Independently, a
  complete tagged chain cannot establish absence of governing context outside the chain. The
  owner therefore emits only the capability limitation; the financial quotation stays held.
- Alias/recovery risk: first inspect the actual renderer/provenance selectors; then exercise sole,
  equal and conflicting real evidence aliases and actual recovery through final/preview/exports.
  Unsupported aliases remain outside the owner, and recovery supplies no new assertion authority.
- Empty-alias refutations: the actual provenance selector uses truthiness, not key presence;
  independently, JSON assembly preserves null/empty values rather than normalizing them away.
  Both attempts support matching the real fallback, including truthy whitespace conflicts.
- Repaired-evidence refutations: the real snapper can repair a near-match to the exact source
  sentence; independently, preview has no such repair, so post-snap admission would diverge.
  The actual ordered-consumer fault proves the final now decides on original evidence only.

At this initial candidate stage there was no flag/cache-stamp change, provider call, paid
evaluation, PR or deployment. Root owns subsequent independent review and publication.

## Integration with quarterly correction

Reconciled implementation `e33c2afef0c476edb32f8ddb660e389cd92c0757` includes main
`904ca43bb7079088e4de5d765e14396081c6fb04`. Only the additive lesson index needed conflict
resolution. Quarterly source, owner, renderer, judge and dedicated gate files remain byte-identical
to that main; removing the reviewed FIGS insertions from the shared facade reproduces main exactly.
The dedicated tax runtime remains `137b5690`; existing shared test function bodies are unchanged.

The shared four-file gates passed **235 cases**. Pinned Ruff 0.16.9 and Bandit 1.9.4 passed;
full pytest 9.1.1 passed **4,024 tests**, with 39 skipped, 2 deselected and 40 warnings (exit 0).
The existing Yahoo cleanup logger emitted a closed-stream diagnostic after the green summary.
Retained-source final, preview, shared Markdown and PDF HTML match the prior reviewed replay;
CSV differs only in its generated timestamp. An actual PDF was exported with zero network or
provider calls. Root's retained 70-row authored-grammar census selects row 13 alone; this is
not a 70-native-document consumer replay or a semantic judgment.

Root's correctness, repository-rules and gate reviews cleared the namespace, real evidence-alias
and pre-snap findings after their recorded refutations and committed fault/restoration proofs.
The annual parser, all locked contracts and the earlier held proposals remain unchanged. This
record does not establish E7 acceptance. Existing stored summaries are not regenerated by this
change; the content stamp and production flags stay unchanged.
