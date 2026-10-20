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
Google or Apple does not have and which a lost first-sign-in race does not call for. Its rewrite
then said "Google will link once both sides have verified it", which reads as automatic: verifying
links nothing, and the provider links only on a later sign-in through it (the principal review).

**Rule**:
- Before writing "withheld", "verified", "the filing's own words", "every", "any company" or a
  count, list every surface the sentence covers and find, for each, the code that enforces it.
- Read the flag behind each enforcement. A gate that ships off (advisory) means the behaviour is
  measured, not enforced; the sentence covers only what runs with the deployed defaults.
- Read the write behind each enforcement too. A check-then-write (a read with no row lock, then a
  write) holds for one request at a time: before writing "once", "every" or "within", ask what two
  overlapping requests do, and scope the sentence to what still holds.
- Scope the sentence to the enforced surfaces ("risk excerpts … or withheld"), in plain words, and
  add the scope to `frontend/tests/unit/brandCopyRules.spec.ts`, or for a legal page to
  `legalTruth.spec.tsx`, in the same PR (CLAUDE.md rule 12).
- When a flag is armed later, the claim may widen in that PR, with the gate's scope widened beside it.
- An exclusive or negative claim ("only checkout", "never waits on it", "the one gate") is a promise
  too, in a comment or a record as much as on a page: grep every read of the field or flag it names
  (`email_verified`) and scope the claim to what those reads do.
- When a correction rewrites one sentence, grep for the same claim elsewhere (another component, a
  comment, a record, a mail) and fix or hand off every copy in the same change.
- An error's remedy is a promise for every path that sends its code: read each raise site before
  naming what the reader should do.
- A remedy names the reader's next action. When the code acts only on a later request (a provider
  links on the next sign-in through it), say that request ("try Google again"), never that the
  change happens by itself.
- A visual signal that means a server fact is a promise too (the device means "the server located
  this", D-044). Trace every path that paints it, a fallback riding the same channel included, and
  carry the fact with the fallback rather than the chip's own flag: a chip with no excerpt sent its
  section heading as the request's passage under the chip's `verified`, so the reader painted a
  heading the server never located. The request now says located only with the excerpt the server
  checked, and the reader paints anything else in a neutral find highlight.

**Evidence**: founder review 5484603342 on PR #1226 (P2, quote guarantee);
`backend/app/services/ai/forward_quote_gate.py`, `backend/app/config.py` (`AI_FORWARD_QUOTE_GATE`),
`backend/app/services/provenance_service.py` (`_enrich_forward_quotes`, the risk projection);
`frontend/features/marketing/components/MeasuredClaims.tsx`, `TrustStrip.tsx`, `EvidenceSection.tsx`;
`brandCopyRules.spec.ts` rule 1c, which fails on the three reviewed sites. Founder review 5511059785 on
PR #1310 (P2, the banner's generation gate; P3, the account-conflict remedy) and that PR's second
review (the dialog's sentence, the "only checkout" records), and the principal review's P3 of
2026-10-14 on the same PR (the conflict sentence's automatic linking); `backend/app/routers/subscriptions.py`
(the one 403), `backend/app/services/oauth_account_service.py` (linking waits on both sides);
`frontend/tests/unit/authPagesCopy.spec.tsx`, whose dialog and 403 cases hold the scoped lines to
that route. Chief design's review 6255015740 on PR #1396 (the blocker: the Source pane painted the
device on a Cited metric chip's heading, a verified XBRL chip's and a Cited quote's);
`frontend/features/filings/components/SourceTrace.tsx` (`jumpToSource`), `FilingViewer.tsx`
(`isLocated`), and `frontend/tests/unit/sourcePanePaint.spec.tsx`, which holds the paint each jump
registers. The high-tier review of PR #1397 (2026-10-19): /security said a refresh token works once
and that logging out of all devices ends every session within 30 minutes, while
`backend/app/services/refresh_token_service.py` (`rotate_refresh_token`, a plain `.first()` and the
rotation written after the successor) let two overlapping renewals both succeed and a renewal racing
a logout keep a live token (E127, fixed by #1422; `tasks/todo.md` E96); `legalTruth.spec.tsx`
(`E127_PROMISES`) holds the two items to what still holds on every run, timed or not: #1431 then
fixed a login that straddled a password reset, but a session token already issued runs to its
expiry and E96 and E133 are open, so the stronger wording returns only with the founder's go-ahead.
