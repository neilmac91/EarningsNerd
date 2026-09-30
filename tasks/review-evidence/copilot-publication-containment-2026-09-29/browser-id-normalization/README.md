# Citation ID handoff evidence

The [manifest](./manifest.json) binds the two changed files and retained receipts. [Independent review](./independent-review.json) and [root review](./root-review.json) clear the stored-ID normalization and actual shared-renderer handoff.

The existing stream owner naturally failed two spaced-ID cases on committed f189, with 44 other tests passing. Corrected focused coverage passes 46 tests. The [full frontend gate](./full-gate.json) passes lint, TypeScript, all 718 tests and the unchanged default production build. Backend tree `57eb8340` equals the earlier 4,151-test gate.

[Actual manual review](./f189-manual-review.json) blocked f189 despite the previously noted compatibility nuance. Both fresh refutations uphold it within the complete PR. Accepted string IDs now lose whitespace before storage; numeric IDs and letter case are preserved. Tests pass real admitted payloads into the shared renderer and verify both repeated chip callbacks. Earlier failed measurements and gates remain retained. Fresh hosted checks and serial release evidence are still required.
