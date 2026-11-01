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

**Recurrence (2026-10-14, the ticker route, #1293)**: the /filing/AAPL picker's row link showed "Open
filing" and carried `aria-label="Open 10-K 0000320193-25-000079"`, so the visible words were not in
its name (WCAG 2.5.3, label in name); the founder's design review caught it. An `aria-label` replaces
a control's text, so a control with visible words takes none: it keeps them and extends its name
with a hidden tail, here `Open filing{' '}<span className="sr-only">(10-K, accession …)</span>`.
`frontend/tests/unit/filing-supersession.spec.tsx` asserts both rows' whole names with
`toHaveAccessibleName`; the app-wide gate is `frontend/tests/unit/labelInName.spec.ts` (E68 (3)), which no control
fails: the residue it opened with on #1884 was fixed with the words chief design ruled there.

**Recurrence (2026-10-29, the invite share panel, E243)**: chief design's review of #1784 found "Copy for
DM/LinkedIn" named "Copy invite message and link for a DM or LinkedIn" and "Copy message" named "Copy invite
message and link", and the panel's toggle, which shows "Share invite" or "More", was named "Show share options"
or "Hide share options". Every control in `frontend/features/admin/components/ShareInvite.tsx` now takes no
`aria-label`: it keeps its words, the toggle's state is its `aria-expanded`, and "More" extends its name with a
hidden tail, "More{' '}<span className="sr-only">share options</span>". `frontend/tests/unit/shareInviteNames.spec.tsx`
holds each control's whole name to begin with the words it shows, with the platform share sheet and without.

**Exception (E281, 2026-11-01, #1921)**: where a link's text must stay exactly as written, or where the link sits
inside running text with words after it, an `aria-label` that repeats its words first and ends in the tail's words
stands in for the tail. Inside running text the tail's written `{' '}` paints inside the link's box, under its
underline and focus ring (4.45px at 16px, chief design's measure on #1921); the space before a span that ends its
line is dropped. So the footer's Logo.dev attribution (its text the attribution's phrase alone), a feedback
message's links (read literally, in a `whitespace-pre-wrap` paragraph) and the terms page's "SEC EDGAR" link
(mid-sentence, once the founder's go-ahead comes) take the label form. The visible words open the label, so label
in name holds (`frontend/tests/unit/labelInName.spec.ts`). A link whose `aria-label` already named it ends that
label in the same words; every other new-tab link keeps its words and takes the tail.
`frontend/tests/unit/newTabCue.spec.ts` reads both forms and fails a tail with words after it in its parent, and
DESIGN_SYSTEM.md's "A link that opens a new tab" states the rule.

**Evidence**: found on this branch's CLEAN-R2 links (`e97f70ff`, in
`frontend/app/company/[ticker]/page-client.tsx`, since replaced by #1147's filings index): the first
run of `tests/e2e/company-filing-rows.spec.ts` against the colon tail found no link named "Open
filing: 10-K filed Oct 31, 2025", and its aria snapshot showed `link "Open filing : 10-K filed Oct
31, 2025"`. The rule holds in today's `frontend/features/filings/components/FilingIndex.tsx`, whose
"Report year" and "Filed" hidden spans keep the space outside the span.
