# Connect new design references to the existing agent workflow

Date: 2026-10-04   Area: frontend documentation

**Context**: The first draft of the portable design reference described the current UI, but
AGENTS.md, CLAUDE.md and specialist briefs still routed UI work only to the older implementation
guide. The founder requested that the new document be integrated into the existing workflow.

**Rule**: When adding or replacing a design reference, inspect the active agent entrypoints and
UI handoff references in the same change. Link the new reference where relevant, distinguish its
role from existing guidance, preserve code-first authority and existing verification gates, and
state which artifacts need to stay synchronized. Validate the changed links and anchors; follow
the repository's docs-only verification policy.

**Evidence**: [PR #1083](https://github.com/neilmac91/EarningsNerd/pull/1083),
[AGENTS.md context routing](../AGENTS.md#1-load-context-for-the-task), and
[CLAUDE.md design documentation](../CLAUDE.md#design-documentation).
