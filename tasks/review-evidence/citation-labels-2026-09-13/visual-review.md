# Citation labels and viewport review — September 13, 2026

Root inspected the actual CitationChip/CopilotMessage/FilingViewerProvider components through the CUA browser at a local isolated Vite harness. The harness uses actual CSS/tokens with local fallback fonts; only Next link integration and telemetry are substituted. It performs no API/model/source requests. This is actual-component local visual evidence, not a signed-in Vercel production assessment.

The pre-correction tall excerpt near y253 produced a 312px card with top=-67 and bottom=245 in an863px viewport. Screenshot confirmed the header was clipped offscreen. Two independent refutations failed: only the excerpt was height-capped, and fixed220px positioning never measured the full card. After measured placement the same card is top279/bottom591/height312, wholly visible. Root read the DOM geometry and screenshot independently. The card contains its scope and original link.

Light and dark theme screenshots were checked. The320px answer panel preserves the new source-match labels and scope text; the pre-existing long XBRL tag link can overflow the narrow panel, while its link/classes are unchanged in this PR. Fonts are local fallback rather than Next generated fonts, so no exact production-font fit is claimed. No token/theme changes were made.

Keyboard Enter on source9 records local viewer highlight request9 without a source fetch, and the original deep link remains in the rendered group. The viewport correction preserves portal content, provides full-card viewport bounds and allows scrolling inside the card/excerpt without the global captured scroll dismissing it; unit controls cover that scroll boundary and narrow/short viewport.

The proposed source-kind-specific reassurance was rejected after two independent checks: text section labels remain model-controlled, and the resolver reindexes real numeric and text citations to ordinary integers. Neutral `Source match found` with `A source match does not verify every claim in the answer.` applies to all verified rows. Existing visual grouping remains; it no longer determines the new semantic assurance. This does not repair the underlying supplemental-citation entailment defect.

Root reviewed the final application diff after restoration; no new scoped correctness or rule blocker remains. Backend code/wire shape unchanged. Final verified-Node22 full gate and the two corrected proof tails remain required for publication; early Node18 or environment-failed build runs do not fulfill that requirement.


September 13 final side-fit acceptance: actual 320×260 iframe, light and dark. Trigger y133–151, card y8–125, eight-pixel non-overlap gap. Browser pointer click reached citation9 and recorded viewer request9. Focusing the original-source action scrolled the card195px while the link remained visible y95.5–112, with the card still open. This supersedes the prior short-viewport hold. Actual components, local fallback fonts; no signed-in production generation is claimed.
