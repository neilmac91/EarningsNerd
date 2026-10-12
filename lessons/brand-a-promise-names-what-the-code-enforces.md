# Before a public sentence promises a behaviour, trace each surface it covers to the code that enforces it

Date: 2026-10-11   Area: frontend, brand, copy

**Context**: The brand studio's claims strip said quotes are "located in the filing text, in the
filing's own words, or withheld", and the trust strip that "quoted excerpts are the filing's own
words". The founder's review of PR #1226 showed a Forward Signals quote the filing does not contain
surviving the generation gate, provenance enrichment and the response model, then rendering as a
quotation with a Cited chip: `AI_FORWARD_QUOTE_GATE` ships off, so `forward_quote_gate.py` measures
an unmatched quote and keeps it. Of a summary's quotes, only risk excerpts are projected from a
matched span and withheld otherwise. The same branch had already lost scope three other ways (every
figure, search coverage, nine parts for every filing), each caught in review rather than at the
keyboard.

**Rule**:
- Before writing "withheld", "verified", "the filing's own words", "every", "any company" or a
  count, list every surface the sentence covers and find, for each, the code that enforces it.
- Read the flag behind each enforcement. A gate that ships off (advisory) means the behaviour is
  measured, not enforced; the sentence covers only what runs with the deployed defaults.
- Scope the sentence to the enforced surfaces ("risk excerpts … or withheld"), in plain words, and
  add the scope to `frontend/tests/unit/brandCopyRules.spec.ts` in the same PR (CLAUDE.md rule 12).
- When a flag is armed later, the claim may widen in that PR, with the gate's scope widened beside it.

**Evidence**: founder review 5484603342 on PR #1226 (P2, quote guarantee);
`backend/app/services/ai/forward_quote_gate.py`, `backend/app/config.py` (`AI_FORWARD_QUOTE_GATE`),
`backend/app/services/provenance_service.py` (`_enrich_forward_quotes`, the risk projection);
`frontend/features/marketing/components/MeasuredClaims.tsx`, `TrustStrip.tsx`, `EvidenceSection.tsx`;
`brandCopyRules.spec.ts` rule 1c, which fails on the three reviewed sites.
