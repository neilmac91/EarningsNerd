# Copy verbatim fixtures from the source payload and assert them on textContent

Date: 2026-10-08   Area: test

**Context**: A risk heading is a verbatim prefix of its row's projected filing excerpt.
Its unit spec was first written with the four production filing-3 spans typed in by hand, and it
passed. The Playwright check, which serves the spans copied from the cached production payload,
failed on one of them: the filing joins "September" and "27" with a U+00A0 no-break space, and
the retyped string had a plain space. A rule that normalised that space would have passed every
unit case while rewriting the filing's text. Fixing the expectation exposed a second trap: in
jsdom, Testing Library's default normaliser turns the no-break space in the rendered node into a
plain space, but a string matcher passed with `exact: false` is not normalised, so a correct
render failed `getByText(span, { exact: false })`.

**Rule**: Build a verbatim fixture by copying it from the source payload with a script, never by
retyping it, and write invisible characters as escapes (`\u00a0`) so a reader sees them. Assert
verbatim content on `textContent` with `startsWith` / `toContain`, not with Testing Library's
whitespace-normalising text matchers.

**Evidence**: `frontend/tests/e2e/fixtures/filing-3-risks.json` (copied from
`raw_summary.sections.risks` of the critique harness's cached `GET /api/summaries/filing/3`, body
sha256 `1412895e…`), which `frontend/tests/unit/riskHeadline.spec.ts` and
`frontend/tests/unit/SummaryRisks.spec.tsx` now import rather than retype; the third span's
`September\u00a027`; `SummaryRisks.spec.tsx` compares each row's blockquote by `textContent`. Main's
first evidence-row headings (#1146) collapsed whitespace and rewrote that span's no-break space; the
rule that replaced them keeps it.
