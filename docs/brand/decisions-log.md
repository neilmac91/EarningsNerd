# Brand studio decisions log

Running log from Phase 0. One line per decision: what was chosen, what was rejected and why, and
what waits on the founder. Later phases append; nothing is rewritten.

| # | Date | Phase | Decision | Rejected | Status |
|---|---|---|---|---|---|
| D-001 | 2026-10-11 | 0 | Audit the live deployment of `main` (`dd7b9ce`) rather than a local build, so the inventory shows what a stranger sees, cookie bar included. | A local `next start` with flags matched (the October critique's method): slower and not what visitors meet. | done |
| D-002 | 2026-10-11 | 0 | Keep captures in the repository as downscaled JPEGs under `docs/brand/audit/` and `docs/brand/battlefield/` (about 1.6 MB total); originals stay in the session scratchpad. | Committing full-resolution PNGs (about 40 MB). | done |
| D-003 | 2026-10-11 | 0 | Score the sameness test 0 to 3 per tell, fourteen tells, so Phase 9 can rerun it and show the delta. | A pass/fail list: hides partial progress. | done; score 36/42 |
| D-004 | 2026-10-11 | 0 | Re-verify the sample figures against SEC companyfacts before any mockup uses them; only the four FY2025 and FY2024 Apple figures (and dividends) listed in the audit §4 may appear in brand work until a product snapshot replaces them. | Reusing the FY2022 `landing-samples.ts` figures: verified, but they are the drift the audit records. | done |
| D-005 | 2026-10-11 | 1 | Treat the code's $39 / $390 as the price fact; the brief's $20 / $200 goes to the founder as a question; no price copy is authored by the brand work. | Writing $20 into mockups: would ship an unverified claim. | waits on founder (Q7) |
| D-006 | 2026-10-11 | 1 | Work under assumptions A1 to A9 ([01-interview.md](01-interview.md) §3) until the founder answers; label every use. | Blocking on the answers: the brief says continue. | in force |
| D-007 | 2026-10-11 | 2 | Describe Simply Wall St from the repository's research after two blocked captures, and say so; retry from a residential connection before Phase 9. | Omitting it: it is the nearest palette neighbour and the one competitor with a device. | partial |
| D-008 | 2026-10-11 | 2 | Keep Fiscal.ai's second-visit capture (the first visit met a Vercel checkpoint) and record both outcomes. | Treating the 429 as "blocked": the page did render. | done |
| D-009 | 2026-10-11 | 3 | The brand owns the act of checking (the receipt), not "citations" as a feature, because the feature is table stakes and the act is unclaimed ([02-battlefield.md](02-battlefield.md) §3). | Owning "what changed": real, shipped, and the council's JTBD, but it is a feature the Change Report already labels, and the battlefield shows diffing is where BamSEC and the institutional tools compete. | done |
| D-010 | 2026-10-11 | 4 | Show the three directions as rendered hero mockups in both themes at 1440 and 390, built from the real tokens and the verified figures, so the founder chooses between pictures, not paragraphs. | Mood boards or sketches: the brief forbids stopping there. | done |
| D-011 | 2026-10-11 | 4 | Recommend the Marked Copy (direction B); pause for the founder's choice before Phase 5. | Proceeding under an assumed choice: the brief names this as a founder pause, and Phases 5 to 8 would be thrown away if the choice differs. | waits on founder |
| D-012 | 2026-10-11 | 4 | Show the "catch" with two real figures from two fiscal years ("From memory $391.0B · In the filing $416.2B") rather than a fabricated wrong number. | Inventing a chatbot's wrong answer: unverifiable, and A4 forbids naming. | done |
| D-013 | 2026-10-11 | 4 | Commit the mockup sources (`directions/*.html`, `mockup.css`) beside the renders, with the fonts referenced relatively from the repository, so a direction can be re-rendered or edited without the session. | Renders only: the founder could not change a word. | done |
