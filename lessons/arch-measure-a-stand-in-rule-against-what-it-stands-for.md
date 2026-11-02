# Measure a stand-in rule against what it stands for before it ships

Date: 2026-11-01   Area: arch

**Context**: MPA WP5a-B's growth rule read n/m wherever a YoY's two years sat on different shown-to-first-reported
ratios, standing in for "the two values shown sit on different bases". Its thresholds were chosen (D1), but the rule
was never measured against that property. D3's census asked each comparison the property's own question: does the
filing behind the earlier year's value shown give the later year the value shown? Of the 363 reported comparisons the
rule read n/m, 256 were like-for-like (155 of 158 leading edges, 88 of 123 runs), and at a leading edge the growth
it printed "as first reported" mixed two bases. The founder chose crossings only (2026-11-01).

**Rule**: Before a rule that stands in for a property ships, measure it on real data against that property's ground
truth, for every kind of case the rule treats alike, and keep the measurement in the rerunnable tool that counts the
rule, beside the rule's own count, with a test that holds the tool's count to the code's.

**Evidence**: `backend/scripts/restatement_census.py` (`basis_comparisons`: kind, basis and n/m per comparison;
`calculated_comparisons`; `_basis_table`); `backend/tests/unit/test_first_reports.py`
(`TestTheCensusCountsTheAnalysissNM`: the census's n/m equals the dataset's, reported and calculated, over every shape;
`test_d3_growth_reads_n_m_at_a_crossing_alone`); `docs/mpa-improvements/coherence.md` §1.6 "The census by kind (D3)";
#1888.
