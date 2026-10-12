# A visually hidden tail on a control's name brings its own space and starts with a word or bracket

Date: 2026-10-08   Area: frontend

**Context**: CLEAN-R2 gave every company filing link the visible label "Open filing" and a
visually hidden tail naming its filing, so the rows' links stop sharing one accessible name. The
first tail was `<span className="sr-only">: 10-K filed Oct 31, 2025</span>`, written to read
"Open filing: 10-K filed Oct 31, 2025". Chromium computed "Open filing : 10-K filed Oct 31, 2025":
`sr-only` positions the span absolutely, which blockifies it, and Chromium separates a block's text
from its neighbour's with a space when it builds the name. Other engines may join the two runs with
no space at all, so a tail that relies on either behaviour reads wrong somewhere.

**Rule**: When a hidden span extends a control's accessible name, (a) write the space yourself
before the span (`Open filing{' '}<span className="sr-only">…</span>`), so every engine gets at
least one and whitespace collapse keeps it at one; (b) start the tail with a word or an opening
bracket, never with punctuation that must touch the visible label (`(10-K, filed Oct 31, 2025)`,
not `: 10-K …`); (c) keep the visible label at the start of the name (label in name), and assert the
whole name in the browser with `toHaveAccessibleName` rather than reading `textContent`.

**Evidence**: found on this branch's CLEAN-R2 links (`e97f70ff`, in
`frontend/app/company/[ticker]/page-client.tsx`, since replaced by #1147's filings index): the first
run of `tests/e2e/company-filing-rows.spec.ts` against the colon tail found no link named "Open
filing: 10-K filed Oct 31, 2025", and its aria snapshot showed `link "Open filing : 10-K filed Oct
31, 2025"`. The rule holds in today's `frontend/features/filings/components/FilingIndex.tsx`, whose
"Report year" and "Filed" hidden spans keep the space outside the span.
