# Source member ledger: evidence, 23 September 2026

Draft engineering evidence for [the member-disposition ledger](../../readiness-2026-09-21/acceptance/source-review-members.md). This is not an E7 evidence schema and admits nothing. Measured implementation: `5b2c848e0e62794e183e46c22e50503d8919aeb4`, stacked on main `9ec55f70`.

## Verification

Gate from `backend/` on committed `5b2c848e` under Python 3.11.15, pinned ruff 0.16.8 and bandit 1.9.4 ([log](full-gate.log)):

- `ruff check .` passed; `bandit -r app -ll` passed.
- `python -m pytest`: **3695 passed, 2 deselected, 40 warnings in 211.56s**, with zero failures, errors or skips.
- The four PostgreSQL concurrency lanes ran against a scratch local `postgres:15`, never production.
- The 2 deselected cases are the `pytest.ini` performance marker. Hosted CI runs that lane.

An earlier attempt on the same commit showed 39 errors in those lanes because the local Docker daemon had stopped. That attempt is superseded by the clean rerun and is not claimed as a pass.

The regression home `backend/tests/unit/test_acceptance_source_members.py` builds its synthetic complete submission through the real `map_submission`, and links members to real `acceptance_source_units` manifests. It exercises every documented rejection:
- exact-duplicate proof, including chains, self-links and targets that are unresolved;
- packet linkage and single-claim packets;
- member identity fields, span bounds, ordinals, filenames and declared text;
- attestation flags, limitations, version and kind;
- manifest shape and accession;
- five strict-uuencode failure forms and the EDGAR `<PDF>` wrapper;
- no mutation of inputs.

## Single mutation proof

Exactly one proof ran on committed `5b2c848e` ([receipt](mutation-proof.json)). It disabled only the exact-duplicate byte-identity check. The mutated gate failed with `1 failed … DID NOT RAISE ValueError`; after byte-identical restoration (`884a5338…`, clean tree) it passed with `1 passed`. No E7 spend or required-brief guard was touched.

## Independent review

An independent adversarial review of the first commit `76188d6` found no blockers. It could not make the validator accept an omitted member, an unproven duplicate, a mismatched packet link or a forged identity. Its findings are fixed in `5b2c848e`:
- `binascii.a2b_uu` silently zero-padded truncated or mis-sized lines.
- EDGAR `<PDF>`-wrapped uuencoded members were recorded as unencoded.
- A malformed manifest raised `TypeError`.
- Declared packaging did not hold completion.
- Several checks had no test.
- Type identity was not exact for subclasses.

A member that fails decoding is now recorded as `invalid_uuencode`, rather than aborting the whole ledger.

## Not established

No real EDGAR submission was used. The frozen snapshot is outside Git and nothing was refetched from SEC. Before relying on the decoder, run it over the H01, H02 and H25 complete submissions (980 members) to confirm that real uuencode variants decode rather than landing in `invalid_uuencode`. Modality inventories, the review graph, issue ledgers and admission remain later slices. No E7 generation, Fable or judge call, provider spend, flag, migration or deployment occurred.
