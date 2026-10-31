# A gate that compares against a token or an exemption set must pin those too

Date: 2026-10-07   Area: arch / frontend

**Context**: The EN-02 ladder gate (`bottomChromeLadder.spec.ts`) checked every fixed site against
`Number(zIndex.consent)` and exempted the `z-toast` ladder name wholesale. Two review probes passed
it 11/11: `consent: '45'` in `tailwind.config.js` (every comparison still held, with the bar back
over the launcher corner) and `fixed bottom-4 right-4 z-toast` in an unpinned file (the retired
cookie toast's exact shape, exempt because its token name was on the transient list). The gate had
encoded the rule only relative to values it did not guard.

**Rule**:

(a) When a gate reads a reference value from configuration (a design token, a limit, a list), add a
case that pins that value to its rung or range — in terms of the other rungs, not a magic number
alone (`sticky < consent < scrim < the pinned workspace level < header`).

(b) An exemption is a shape, not a name: say where the exempt thing may be anchored or what it must
contain (`z-toast` only top-anchored and never bottom-anchored; a z-scrim site only `inset-0
bg-overlay`), and add the negative fixtures that would otherwise slip through.

(c) The repository records exactly one mutation demonstration on committed state per gate; every
other clause is probed on a scratch copy (restore from a backup copy when the tree is dirty, never
`git checkout --`) and cited in the PR as evidence, not as a second repository mutation.

**Evidence**: `frontend/tests/unit/bottomChromeLadder.spec.ts` ("the ladder tokens sit on their
rungs"; `toastIsTransient`; the z-scrim shape clause; the header's mutation paragraph). Scratch
probes on 2026-10-07: `consent: '45'` → "the sheet scrims must dim the bar: expected 35 to be greater
than 45"; `PROBE_TOAST = 'fixed bottom-4 right-4 z-toast rounded-lg'` in `lib/featureFlags.ts` →
"fixed chrome at z-80 (must be below z-consent = 32)"; the scrim back at `z-30` → the pin drift.
