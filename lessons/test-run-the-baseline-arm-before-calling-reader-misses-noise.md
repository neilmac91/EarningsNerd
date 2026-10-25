# Run the same readout on the baseline build before calling a reader's miss noise

Date: 2026-10-25   Area: testing

**Context**: The metrics-table readout has fresh model readers transcribe 21 cells from a screenshot. On
the shipping build one reader dropped a note letter and, in a second round, two readers gave a period with
no change line the next column's change. One of those cells was pixel-identical to the first round, where
every reader got it right, so the misses were written off as reader variance. A blind arm on main's build,
the same 21 cells and three readers an image, said otherwise: main read 252 of 252, the branch 247 of 252,
and all five misses sat on one image, dark at 1x, repeated across readers. Two controlled rounds on that
image found both causes (a dotted underline under every value; dagger and letter raised level), and the
fixed build read every cell.

**Rule**: When a readout shows misses, run the identical protocol on the baseline build before deciding
what they mean: same cells, same prompt, opaque paths, at least three readers per image, every theme and
pixel density. Break the result down by image. A miss more than one reader makes on the same image is a
finding, whatever one earlier round said. To find the cause, vary one property at a time on that image
(CSS overrides on the captured page are enough) with fresh readers per variant, then fix in code and
re-read every image.

**Evidence**: the metrics-table number system's pull request, #1606 (its Verification section: the A/B,
the two variant rounds and the final read). Review-checked; a readout spends model calls and runs outside CI.
