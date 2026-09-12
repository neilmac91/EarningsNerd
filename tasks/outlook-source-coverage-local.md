# Selected MD&A Outlook coverage — local implementation plan

2026-09-13. Based on main `fcffd060dc3cacb92a71f01ff15136807e872143`; unpublished local candidate; committed gates pending.

The selected Ford 10-Q's original retained HTML parses to an 87,806-character MD&A. Its complete Outlook block starts beyond the existing 45,000-character prefix and is 3,118 characters including page boilerplate. The fixture preserves original HTML bytes and is parsed using the installed EdgarTools 10-Q parser, rather than reconstructed review text.

The new generation-only source adapter recognizes exactly one standalone OUTLOOK heading followed by exactly one standalone Cautionary Note on Forward-Looking Statements heading. It appends the complete contiguous block only when the prefix omitted it and it is not already present elsewhere in the excerpt. Ambiguous, missing-end, stub and oversized blocks abstain. This narrow grammar makes no guidance-completeness claim.

Existing assembled excerpt bytes and the old global cap remain unchanged; the additional wrapper-inclusive allowance is 6,000 characters. Forward recovery first builds its existing 30,000-character context without the supplement competing for shares, then appends the complete supplement, for at most 36,000 characters. Other recovery contexts remain unchanged. Existing cached excerpts are not invalidated. No source retrieval, provider changes or historical generation is introduced.

The integrated ordinary test parses the retained original filing, passes its selected MD&A through real assembly and captures primary plus forward-recovery requests with the offline SDK transport. It checks the guidance table, final assumption, exact preserved prefix, and unchanged unrelated recovery contexts. Negative variants cover ambiguous headings, TOC stubs, missing end, oversized blocks, already-included blocks and no beyond-cap omission.

Single invariant/proof design: after committing, temporarily suppress the source supplement at its adapter return; the integrated original-Ford request-boundary test must fail. Restore exact committed bytes and rerun the same target. Root owns this mutation and the full committed PostgreSQL 15/backend gate; no tests, mutation or commit were run by the implementation agent.

Independent read-only correctness review found no surviving finding after checking source identity, contiguous boundaries, no displacement, wrapper-inclusive budgets and cache scope. The original fixture hash was independently verified. This clearance remains conditional on committed tests and current-main integration.

Root-owned integration before publication: review candidate, integrate current main, decide prompt-version treatment without rewriting financing's pending version, record source-budget/cost impact, run the serial full gate and one invariant proof, and allocate any paid assessment. Actual assessment must verify fresh source delivery and guidance behavior; no production quality clearance follows from offline delivery alone. Cached historical omissions and incorporated annual-report exhibits remain separate open items.
