# Test a trust mark blind against a quieter design and a no-mark design before proposing it; read competitors' silence as a baseline, not a gap

Date: 2026-10-24   Area: frontend, design system, analysis notation

**Context**: The Multi-Period Analysis coherence report (`docs/mpa-improvements/coherence.md`)
first proposed a louder notation:
- a ringed review letter;
- "needs a source check" in warning ink on the KPI cards;
- a key beside every mark.

Its evidence was three comprehension rounds that varied only the wording of that one marked
design, so they could not show it was overkill. The founder found it dramatic and
distrust-inducing, and pointed out that competitors mark nothing.

A blind test of four designs on one REGN data state settled it. The data already held a
known-wrong figure, REGN's restated FY2018 revenue, and a note was planted on it where the code
does not yet raise one
(`docs/mpa-improvements/verification/notation-variant-test.md`):
- **Routine marks off.** With the marks gone from correct figures, trust in a correct $4.1B rose
  from 3 and 4 (current page) and 3 and 3 (ring) to 4 and 4, and cleanliness from 3 to 4, at no
  cost.
- **Every mark off.** With nothing marked at all, the one real error (FY2018 revenue −12.4%, which
  is +14.3% as filed) went unflagged. Both readers caught it only by cross-checking rows and from
  memory.
- **Quiet design.** A small neutral letter on that figure alone kept it visible at the cleaner
  design's calm.

**Rule**:
- Before proposing a mark, label or warning on figures, render at least three designs on one data
  state: the proposal, a quieter one, and none. Then have fresh readers judge them blind, with
  neutral labels and fixed questions:
  - trust in a correct figure;
  - trust in a wrong one;
  - whether the page itself flagged the wrong one;
  - cleanliness;
  - whether the product feels trustworthy.
- Use a data state that holds a known-wrong figure, so the test can tell a calm page from one that
  hides problems. Plant its note where the code does not raise one yet.
- Treat what paid competitors do as the baseline the proposal must beat with that evidence, not as
  an omission to fill.
- Before the first run, check that the variant switch reaches every surface that renders the mark.
  Here, letters leaked into the narrative's citation chips, and the quiet and no-marks designs were
  re-run.
- A wording test that varies one design does not test the design. Run it after the design has won.

**Evidence**:
- `docs/mpa-improvements/coherence.md` §2.8 and §2.9, and `verification/notation-variant-test.json`.
- The ring design: `docs/mpa-improvements/prototype/notation-prototype.diff`.
- The quiet design: `docs/mpa-improvements/prototype/notation-quiet.diff`.

The test method is review-checked. The marking rule it led to gets its own gate with the notation
change (`coherence.md` §2.3).
