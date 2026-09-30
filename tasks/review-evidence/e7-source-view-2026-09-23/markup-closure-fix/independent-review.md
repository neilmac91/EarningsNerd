# Independent review — fail-closed markup boundaries

**Disposition: no remaining actionable finding in commit `30dfce4c745d9e0b91d531fd10b7fe1ca003105b`.** The review covers the two backend files only and did not edit the repository, rerun PostgreSQL tests, or assess financial content. The final parser SHA-256 is `6bc13530f204d577bb2105226917da4d9ddeb0a8d3c5b5c41e6ee8239643a24f`; the test SHA-256 is `62f32e776f1d359e5d35efe61911b22d1fe0ad1a020c1a23fe7226a7b6face4c`.

## Start boundaries and scopes

The guard rejects start tags that would require browser-implied closure instead of silently rewriting ancestry. It covers the complete in-body `p` closure set used here; list items within the nearest `menu`/`ol`/`ul`; `dt`/`dd` within the nearest `dl`; current and legacy ruby implied-end cases within the nearest `ruby`; option and optgroup transitions within the nearest `select`/`datalist`; and cell, row, section, caption, and colgroup transitions within the nearest table. The scope scan stops at the nearest relevant container, preserving explicit nested lists, ruby annotations, selects, and tables.

Two fresh refutations support this result:

1. Direct projection rejected hidden `p` before `p` and `div`, consecutive `li`, `dt`→`dd`, `rtc`→`rb`, consecutive options, omitted cells, and the table section/caption/colgroup fixtures with `unsupported implicit HTML boundary`.
2. Direct controls accepted an explicitly closed `p` followed by a block, an outer hidden list item containing a nested list, a nested table inside an outer cell, explicit option/optgroup markup, and explicit `rtc` containing closed `rt`/`rp`. Hidden inheritance remained correct inside the explicit outer hidden element and stopped after its close.

This is deliberately fail-closed. It does not implement an HTML5 repair tree or alter source bytes. The relevant optional-tag behaviors follow the [WHATWG HTML optional-tag rules](https://html.spec.whatwg.org/multipage/syntax.html#optional-tags), while the projection continues to disclaim browser equivalence.

## End tags, EOF, and self-closing syntax

An end tag may now pop only the matching top element. Crossed closure and a parent close that would discard an open child fail before an event or stack mutation. EOF rejects every remaining non-void element except the narrow `html`/`body` wrapper combinations required by the retained index source. Non-void self-closing syntax fails before `handle_starttag`; void self-closing tags continue through the normal exact-byte path. Historical unmatched non-structural close tags remain accepted, as documented by the implementation, while unmatched table/script/style closes still fail.

Two fresh refutations support this result:

1. `<div><span>A</div></span>`, `<ul><li>A</ul>`, an EOF-open `section`, and `<div hidden/>B` all failed. These exercise crossed closure, optional child closure at its parent, non-wrapper EOF, and non-void self-close independently.
2. EOF-open `<html><body>A`, `<p>A<br/>B</p>`, and `A</span>B` passed. They exercise the permitted wrapper exception, void self-close, and the retained historical unmatched-formatting-close behavior without hidden-state leakage.

Rejecting self-closing foreign/custom non-void elements is conservative and may make a future source unavailable; it cannot silently mislabel that source. The six H29 inputs contain no non-void self-closing callbacks.

## Counter integrity and bounded performance

The first reviewed version used an unconditional full-stack search for every `p`-closing start tag. Two independent measurements refuted its scalability: balanced `div` projections grew from 0.0897 seconds at depth 2,000 to 1.1132 seconds at depth 8,000, while equivalent `span` projections remained near-linear; isolated repeated boundary checks grew from 0.1104 seconds at 2,000 to 7.0342 seconds at 16,000.

The final commit replaces that scan with `open_p_count`. The counter increments only after a non-void `p` is appended and decrements only when an exactly matched top-level `p` is popped. Rejected boundaries and unmatched closes do not alter it; EOF-open `p` still fails through the stack check. This keeps the counter synchronized with the only permitted stack mutations.

Two post-fix refutations support the optimization:

1. Balanced `div` projection now measured 0.0306, 0.0637, and 0.1520 seconds at depths 2,000, 4,000, and 8,000, closely matching the `span` control at 0.0310, 0.0616, and 0.1266 seconds.
2. Isolated repeated boundary checks measured 0.0038, 0.0077, 0.0144, and 0.0285 seconds at depths 2,000, 4,000, 8,000, and 16,000, removing the introduced quadratic path. Functional `p` rejection and balanced-`p` acceptance still passed after the counter change.

## Evidence and compatibility

The focused source-view test and Ruff passed on the final bytes. The retained mutation temporarily disabled only the rejection helper: the guard test failed because the expected exception was absent, then passed after exact restoration. The later counter change did not alter that helper or test, so repeating the mutation would add no distinct evidence.

All 24 regenerated files across the six H29 views are byte-identical to the retained dossier. The six sources have no implicit descendant pops, no unclosed non-void element except the permitted `html`/`body` wrappers in the index, no `p`-before-block risk, and no non-void self-closing callback. The original H29 pilot and its source evidence remain unchanged. Readiness, budget, schema, and denied proof guards are untouched.
