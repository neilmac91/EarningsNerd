# Source-capacity checkpoint — 27 September 2026

PR #970 is released. The next source work now has two measured blockers: the largest direct
primary does not fit the tested memory boundary, and the frozen submission representations do
not satisfy the strict encoded-member decoder. Neither result is a quality acceptance verdict. A [subsequent ASCII-offset correction](../source-view-ascii-2026-09-27/README.md) completed both direct primaries under the unchanged limits; the original failure below remains historical evidence.

## Verified release

PR [#970](https://github.com/neilmac91/EarningsNerd/pull/970) merged as
`5c8d0f40833a1d464a2fec9eb48bcea07ea10399`. Exact-head review cleared
`b424a1bbb66694e3be8eb21ede247951134b1f29`; its tree matches the measured synthetic merge and
the final squash. The [compact hosted audit](pr970-hosted-audit.json) records 70 summary outputs and 18 Copilot
outputs; identity completeness was checked against the retained underlying reports. There were no
output errors or hard-gate failures. It records 111 physical
provider attempts and USD 0.186447 in known application estimates. Five transient Copilot error
attempts have unknown usage/cost; provider-billed cost is unknown. Soft citation/figure warnings
remain in the underlying reports and are not semantic acceptance.

The [release receipt](pr970-release.json) and
[public closure](https://github.com/neilmac91/EarningsNerd/pull/970#issuecomment-5854115499)
record main CI `36305043219`, successful deployment `108580544432`, migrations `applied=0
skipped=39`, revision `earningsnerd-backend-00394-m56` at 100% traffic, and a subsequent independent
HTTP 200 healthy response. The bounded history interface can now be frozen for corpus execution.

## Actual member census

The released member API re-derived and validated every mapped member against the frozen complete
submissions. The [compact receipt](member-census-receipt.json) is a publication summary, not an
admission input or a replacement for the retained canonical ledgers.

| Filing | Members validated | Not uuencoded | Strict decode failures | Decoded |
| --- | ---: | ---: | ---: | ---: |
| H01 | 162 | 156 | 6 | 0 |
| H02 | 268 | 261 | 7 | 0 |
| H25 | 550 | 299 | 251 | 0 |
| Total | 980 | 716 | 264 | 0 |

All 980 dispositions remain explicitly unresolved, with no review-unit assignment. Three exact
payload-duplicate groups cover nine members, but no duplicate disposition or review coverage is
inferred. H25's byte-only worker completed in 3.55 seconds at approximately 474 MB peak RSS; this
was not structural projection, image inspection, semantic review, or provider-context measurement.

All 264 encoded-looking blocks contain a physical blank line immediately before `end`. The bytes
are present in the frozen submissions; the document mapper does not trim interior lines. A separate
diagnostic found that permitting only that terminal blank would decode five H25 GIFs and leave
259 members with additional strict line-width/alphabet defects. Across 2,057,973 encoded data lines,
none ends in a space. That pattern is consistent with trailing-space loss, but does not establish
where it occurred or authorize repair.

An explicitly separate, in-memory padding hypothesis produced structurally valid samples and
three CRC-valid XBRL archives. Those are reconstructed diagnostic results, not canonical decoded
source artifacts. No production decoder, frozen source, ledger, schema, or strict malformed-input
test was changed. The acquisition trace found the compatibility SEC service returning HTTPX decoded response text,
then an exact UTF-8 re-encoding/write; no line-trimming site was identified. EdgarTools was not the
capture route. The receipts explicitly do not claim raw-wire identity. Compare authoritative bytes
before choosing source recapture or a separately reviewed transport interpretation. Do not silently pad the
264 members or count them as covered.

The full three canonical ledgers, failure rows, original receipts, diagnostic code and hash
inventories remain in the operator workspace under `outputs/takeover-2026-09-26/corpus-member-census/`.

## Bounded Linux result

The [actual run](https://github.com/neilmac91/EarningsNerd/actions/runs/36306402349) verified the
frozen capsule and ran the released source-view module in a network-isolated Linux process with
no provider credentials. The [execution receipt](h25-linux-execution.json) and
[worker receipt](h25-capacity-receipt.json) record an enforced 3 GiB address-space limit and a
180-second wall limit. H25 failed with `memory_limit_exceeded` after 20.037433 seconds; peak RSS
was 3,182,571,520 bytes. H02 was held without execution. The limit was not raised and the failure
was not retried into a pass.

This input is the frozen 57,158,558-byte direct primary, SHA-256
`08f3a9c524be807db51302faffee034992d9c00c90013bb239b3a940e973539c`, which differs by 111 wrapper
bytes from the extracted SGML member. The run does not establish that member's coverage, minimum
required memory, provider-context capacity, or whether allocation failed during projection or its
subsequent verification. Two earlier jobs failed before measurement while accessing the temporary
draft asset; those failures remain separate in the execution receipt. The final unchanged 3.2 MB
capsule was read from the isolated diagnostic branch with read-only permissions. That branch is
not merged into main, and the unused staging draft release was removed after result retention.

## Next deliverables

1. Ingest the frozen PR #942 p/q judging results when Fable returns them; preserve its existing
   contract and queue. No result is inferred from the founder's handoff confirmation.
2. Compare authoritative source bytes to the retained decoded-text capture before changing the strict decoder. Preserve
   the 264 failures and any diagnostic reconstructions as distinct evidence.
3. The [bounded ASCII-offset correction](../source-view-ascii-2026-09-27/README.md) now has a successful H25/H02 direct-primary measurement at the original limits. Preserve exact source/unit identities, then measure the remaining readable members, decoded modalities and complete unsent role payloads.
4. Finish the 60 independent source briefs and 30 reconciliations, then execute E7 within the
   approved budgets and quality gates. These engineering measurements do not admit the programme.
