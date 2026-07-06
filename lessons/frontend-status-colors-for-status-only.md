# Reserve loud status colors for genuine status messages

Date: 2026-06-23   Area: frontend

**Context**: Mapping `StateCard`'s default `info` variant to the blue `info` token turned every guidance box (e.g. "Start a comparison") loud blue — off-brand against the sage/slate identity. (The sage/slate split has since been consolidated to one Sage accent; the rule is now encoded in the GuidanceCard/Notice components and still applies.)

**Rule**: Brand accents are for actions/accents; loud status colors (blue/green/red) are for real state messages. A default guidance/empty-state container should be subdued or brand-tinted, never mapped to a loud status token.

**Evidence**: `StateCard` default `info` variant → blue `info` token; "Start a comparison" guidance box rendered loud blue.
