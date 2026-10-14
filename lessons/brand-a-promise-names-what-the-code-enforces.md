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

PR #1310 repeated it on the auth pages. The verification banner said "Verify your email to generate
summaries and subscribe." though only checkout refuses an unverified email (the founder's review
traced the gate). The fix round then wrote the opposite absolute into a comment and three records
("only checkout checks email_verified", "signing in never waited on it"), though linking a Google or
Apple sign-in to an existing account waits on both sides' verification, as the same PR's login
sentence said. The verification dialog kept the first claim, and its "We sent a link to" on an
action that sends nothing, because only its comment had been edited. The founder's review also found
the account-conflict sentence sending every reader to a password, which an account created through
Google or Apple does not have and which a lost first-sign-in race does not call for.

**Rule**:
- Before writing "withheld", "verified", "the filing's own words", "every", "any company" or a
  count, list every surface the sentence covers and find, for each, the code that enforces it.
- Read the flag behind each enforcement. A gate that ships off (advisory) means the behaviour is
  measured, not enforced; the sentence covers only what runs with the deployed defaults.
- Scope the sentence to the enforced surfaces ("risk excerpts … or withheld"), in plain words, and
  add the scope to `frontend/tests/unit/brandCopyRules.spec.ts` in the same PR (CLAUDE.md rule 12).
- When a flag is armed later, the claim may widen in that PR, with the gate's scope widened beside it.
- An exclusive or negative claim ("only checkout", "never waits on it", "the one gate") is a promise
  too, in a comment or a record as much as on a page: grep every read of the field or flag it names
  (`email_verified`) and scope the claim to what those reads do.
- When a correction rewrites one sentence, grep for the same claim elsewhere (another component, a
  comment, a record, a mail) and fix or hand off every copy in the same change.
- An error's remedy is a promise for every path that sends its code: read each raise site before
  naming what the reader should do.

**Evidence**: founder review 5484603342 on PR #1226 (P2, quote guarantee);
`backend/app/services/ai/forward_quote_gate.py`, `backend/app/config.py` (`AI_FORWARD_QUOTE_GATE`),
`backend/app/services/provenance_service.py` (`_enrich_forward_quotes`, the risk projection);
`frontend/features/marketing/components/MeasuredClaims.tsx`, `TrustStrip.tsx`, `EvidenceSection.tsx`;
`brandCopyRules.spec.ts` rule 1c, which fails on the three reviewed sites. Founder review 5511059785 on
PR #1310 (P2, the banner's generation gate; P3, the account-conflict remedy) and that PR's second
review (the dialog's sentence, the "only checkout" records); `backend/app/routers/subscriptions.py`
(the one 403), `backend/app/services/oauth_account_service.py` (linking waits on both sides);
`frontend/tests/unit/authPagesCopy.spec.tsx`, whose dialog and 403 cases hold the scoped lines to
that route.
