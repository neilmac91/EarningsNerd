# Validate design-sidecar specimens in their consumer, and check what its engine reads

Date: 2026-10-04   Area: frontend documentation

**Context**: The first `.impeccable/design.json` passed a preview in a block-level host with a
`.dark` class. Impeccable's design panel mounts each specimen in a bare host inside a centered
~350px flex stage and sets no theme class, so the navigation overflowed the panel, the table never
scrolled, viewport media queries chose desktop layouts and dark mode never applied. Synthetic
`tonalRamp` steps labelled preview-only were read by the detector as allowed palette colors.

**Rule**: Render sidecar specimens through the consumer's own code
(`frontend/scripts/impeccable-panel-harness.mjs`) with a narrow panel on a wide viewport and on a
phone viewport, in both app themes and both OS color schemes. Constrain the host, use container
queries rather than viewport queries, and key dark styling to the app's own theme signal, never to
the OS preference. Match a theme signal against the CSS the app actually serves, not its source
text: Turbopack's lightningcss lowercases hex, so a style query on the source spelling never
matched (the second review caught it). Before adding sidecar metadata that a document calls
"preview-only", read the engine code that consumes it.
`frontend/tests/unit/designSnapshotParity.spec.ts` gates the structural parts.

**Evidence**: [PR #1083](https://github.com/neilmac91/EarningsNerd/pull/1083); Impeccable 4.3.1
`renderComponentTiles` / `designPanelCss` in `scripts/live-browser.js`; engine 0.1.5
`crates/detect/src/design_system.rs` `add_sidecar_colors`.
