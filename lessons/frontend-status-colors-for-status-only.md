# Reserve loud status colors for genuine status messages

Date: 2026-06-23   Area: frontend

**Context**: Mapping `StateCard`'s default `info` variant to the blue `info` token turned every guidance box (e.g. "Start a comparison") loud blue — off-brand against the sage/slate identity. (The sage/slate split has since been consolidated to one Sage accent; the rule is now encoded in the GuidanceCard/Notice components and still applies.)

**Rule**: Brand accents are for actions/accents; loud status colors (blue/green/red) are for real state messages. A default guidance/empty-state container should be subdued or brand-tinted, never mapped to a loud status token. Activity (a run in progress, a loading quip) is never a status notice of any variant: it is the progress indicator in sage with its words in the ink. A status variant is written at every call site, never defaulted.

**Evidence**: `StateCard` default `info` variant → blue `info` token; "Start a comparison" guidance box rendered loud blue. Its replacement `Notice` shipped with the same default (`variant = 'info'`, 2026-07-02), and the generating card's whimsy line sat in a blue `<Notice variant="info">` from 2026-07-04 (`f0afb4de`) to 2026-10-24, re-blessed by #1293's glyph pass as "DS-sanctioned" (the nesting rule, never the content); a reviewer saw it as "this blue section". Gates since 2026-10-24: `Notice.variant` is required, and `frontend/tests/unit/statusTintResidue.spec.ts` pins every status tint class outside `components/ui/` and every Notice's written variant, shrink-only.
