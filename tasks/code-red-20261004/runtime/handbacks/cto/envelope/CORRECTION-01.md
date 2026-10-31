# Correction 01 — CTO operating-envelope handback, revision 1 → revision 2 (2026-10-04T15:01:10Z)

**Defect (found by the COO disposition worker, recorded as an adverse finding in its output):** revision 1
of `CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md` and `CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` left
three generator placeholders unrendered in the *uncertainty* fields of B27, B32 and B40 (plain string
literals where f-strings were intended), while §0 asserted that all anchors were resolved. The bound
values, classifications, primary evidence anchors and the §5 determination were unaffected; the B32
resolving-observation mechanism (Ops `capacity-readout` step and window limit) was not fully anchored.

**Fix:** the three strings were made f-strings and both files regenerated from the same generator with
the same 93 anchors against commit `100fb7d6`. A field-by-field diff of the JSON shows exactly three
changed fields (B27, B32, B40 `uncertainty`), one added top-level field (`revision: 2`), and an
identical `determination` block.

| File | Revision 1 SHA-256 (evaluated by the COO worker; committed in `6cd23c3c`) | Revision 2 SHA-256 |
|---|---|---|
| `CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md` | `62a0f60cbff1df2bc9ec3f3225ba84168478636fb87336545d255a062612f041` | `ef22d1f5986c0b6f7165fc3e0f7b932f12a954ed74444a63bd3f09e6a4687a32` |
| `CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` | `2fc35be7e9c72fb9bbe5096f204227cf244c4d01bc11ed2448afba9c92db5f1b` | `9acb42fa5507a97cdb44d2195869c0bdb2c5897f289eb64d0bebdac86241c2ee` |

**Effect on the COO disposition:** none. `handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md`
(SHA-256 `d30bdd50125ae304ad5c4fd1c6559326d3767c0f17c1ca7ec41d895ab6fc13be`) evaluated revision 1, named
the placeholder defect, and reached HOLD on the `unknown` rows (B32, B37/B39, B56) and the spend HOLD;
revision 2 changes none of those rows' values or classifications. The dispatch manifest
`dispatch/COO-ENVELOPE-DISPOSITION-01.json` keeps the revision-1 hashes it bound at dispatch time; this
file supplies the chain to revision 2.

**Authorship note:** both revisions were authored in the chief context acting as CTO after the isolated
workflow launch was denied (§0 of the handback); the defect is the chief's and was caught by the
isolated COO worker, which is the kind of error an isolated adversarial lens would have been expected to
catch earlier.
