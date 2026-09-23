# Independent corrective review — E7 source capacity preflight

**Reviewed commits:** base `b73492dddf4224bafa96e174e66ff72f59e5f1e9`, corrective commit `abf4ca640d48b35be5099b2b6883c3298cf2d3b3`  
**Scope:** the corrective delta in `backend/evals/acceptance_source_capacity.py` and `backend/tests/unit/test_acceptance_source_capacity.py`  
**Disposition:** no actionable finding in the corrective delta.

The earlier b734 review missed a real acceptance mismatch. `HTMLParser` can consume malformed input without invoking a callback. For `</><!--x-->`, b734 left its derived cursor at byte 0 and allowed the comment callback to absorb the skipped three-byte prefix, while `project_html` located the callback at byte 3 and rejected the uncovered prefix. The historical review is retained and marked superseded in `independent-review.md`.

The correction closes that class without restoring the large per-character byte-offset array:

- `_record_span` now compares the parser callback's `getpos()` with the expected source line and column before accepting any raw span. A callback following silently consumed input therefore fails before a delimiter scan can legitimize the skipped bytes.
- After an accepted span, the implementation decodes only that already-verified UTF-8 slice and advances the expected position exactly as `HTMLParser.updatepos` does: count line-feed characters; after any line feed, set the column to the Unicode-character count after the last one; otherwise add the decoded character count. This handles multibyte characters, LF, CRLF, and CR consistently with the parser and with the source-view locator.
- Every callback still passes through the central guard. Exact raw checks remain for start tags, data, and references; the source-view-equivalent boundary scans remain for end tags, comments, declarations, and processing instructions. Final byte coverage still rejects silently consumed trailing input when no later callback exists.
- The invariant now includes multibyte text before later callbacks on the same line and callbacks across several line feeds. It also proves the exact skipped-prefix counterexample fails in both the preflight and `project_html`. This directly covers the corrected failure mode without expanding into a malformed-markup corpus.

I reviewed the committed objects read-only and did not run tests or edit the capacity worktree. The author reported the focused invariant and Ruff passing. Root's full gate and real-source pilots remain separate evidence.

