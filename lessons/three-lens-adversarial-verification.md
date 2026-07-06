# Verify a risky classification or deletion with N independent refute-first lenses, not one pass

**Area:** refactor · **Date:** 2026-07-06

A single read-through certifies what you already believe. For high-stakes mechanical work — a large 'pure move' classification (F3), or deleting a production code path (S1) — fan out several INDEPENDENT verifiers, each told to REFUTE a specific load-bearing claim (dead-symbol has no live caller; boundaries are exact; imports unused; no lost test coverage) and default to REFUTED on any doubt. F3's 3-lens pass caught 2 real domain misclassifications; S1's pre-delete verifiers confirmed the map and the post-commit review caught a MAJOR lost-coverage finding (the quota contract).

**Rule:** for a change that is hard to reverse (mass move, prod-path deletion), don't trust one review. Run independent adversarial lenses — classification, completeness/lost-coverage, stale-references, behavior-preservation — before AND after committing; a finding from any lens is cheaper than a prod regression.
