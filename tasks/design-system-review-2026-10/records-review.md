# Independent records review

Reviewed 15 October 2026 in `/workspace/earningsnerd-design-review`. Tier: records, following AGENTS.md sections 4 and 5, Codex by-hand read-only pass. This was a separate reviewer context. No branch file was edited. Findings below are unrefuted reviewer observations; this tier does not require refuters.

## Scope

Reviewed REPORT.md in full, its scorecards, fourteen findings, six Distill items, nine Polish items, one Clarify item, founder decisions, coordination notes and evidence limits. Spot-checked census.md, drift.md, routes.md, the critique archive, JSON inventories and source claims against frozen baseline `1f12fc835fcbf525042473ab0e988b4827734f38`. The author is separately running the complete mechanical link, anchor, JSON and budget validator. This pass does not claim an independent exhaustive browser walk or test-suite run.

## Blockers

None found.

## Should-fix

None found.

## Nits

1. REPORT.md, Founder decisions, F2: replace "The home snapshot still ends at FY2024" with "The homepage Multi-Period Analysis demo snapshot still ends at FY2024". T5 correctly distinguishes the FY2025 hero filing from the FY2024 Multi-Period demonstration. The shorter F2 wording can look like a contradiction when the decisions table is read alone. This is a clarity improvement, not evidence that either source assertion is false.

## Checks and observations

- The visible worktree change set contains only the authorized task directory and one critique archive. No application implementation or settled-design change is included. The plans explicitly preserve founder holds, E9 timing and existing PR ownership.
- Verified baseline-to-delivery-main changes are confined to review-gate.yml, its backend test, OPERATIONS.md and todo.md. The report's frontend-byte-identity qualification is supported.
- Score rows add to sameness 36/12/12, craft 20/36 and health 28/40. The plan size counts match the enumerated items: Distill three S plus three M; Polish two S plus seven M; Clarify one M. The different health direction and different historical target scope are stated.
- Source spot checks support the HeroExample fixed tracks/nowrap issue, ContactForm and HeroExample Card recipe equivalence, missing semantic main/terminal heading leads, the scoped auth glass behavior, and the nineteen list ceilings plus two z-value bounds. The 373 raw-candidate count is explicitly not a defect count.
- Opened the retained hero enlarged-text and pricing-header exhibits. The hero exhibit visibly supports colliding amounts; the pricing exhibit is consistent with the documented blank secondary-header remnant. Corresponding machine measurements are retained.
- The critique's target SHA-256 matches current `frontend/components/ui/index.ts`: `1a68bbbec0ebad07084b263758a6fa2e94439cfd644f68fd6c29b97fa9221dba`. Its metadata score and five initial priority entries match its body. The wider report's additional findings are identified as synthesis additions.
- Public production appearance, unknown deployed revision and local fixture evidence are clearly separated. Performance claims are bounded laboratory observations. No production account, genuine generated answer, payment or export fidelity is claimed.
- Auth glow removal is explicitly dropped in REPORT.md, drift.md and the archive's final corrections. Current globals.css and DESIGN.md support retaining the existing scoped treatment. The unused glow token removal is a different, qualified inventory item.
- The archive retains original assessment wording but links the complete report and appends synthesis corrections, including inputClasses preference and the launcher scope reduction. No new implementation authority is inferred from the archived intermediate recommendation.
- verification.md still contains the author's pending gate-record placeholder. Complete it with actual results before delivery; this is expected in-progress author work, not a review finding.

Author disposition: the F2 clarity nit is fixed in REPORT.md as “Multi-Period Analysis demo snapshot”. No other review findings required a change.

Follow-up read-only review: inspected the pinned-tree source lookup and committed-plus-pending scope helpers after GitHub feedback. No material false-pass bug was found in those helpers. A subsequent GitHub review identified a CLI mismatch that this pass missed: an arbitrary selected head changed scope while contents still came from the worktree. The author removed that option. The verification record now explicitly describes current-checkout validation and the scratch application-change/rename probes.
