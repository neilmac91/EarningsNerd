# Withhold command values in capacity readbacks

Date: 2026-09-29   Area: ops

**Context**: A token allowlist printed standalone numeric command arguments outside
recognized capacity option positions. One-off privacy fixtures did not provide a
hosted regression gate.

**Rule**: The Ops capacity projection reports command-override presence only. Never
echo raw command/argument arrays or resolve private environment references. Missing
runtime worker and egress identity remain unknown.

**Evidence**: `backend/tests/unit/test_capacity_projection_privacy.py` executes the
entire committed describe-service Python heredoc with private service/job sentinels,
numeric arguments, malformed configuration and valid capacity values. Stub only the
external JSON reads, capture all Python stdout, and constrain the surrounding shell
to its redirected read. Slicing at the capacity comment skipped earlier `show()`
emissions and falsely narrowed this rule. A deliberate pre-marker raw-command emission
fails the same gate; exact restoration passes. Check nonempty raw command/argument
arrays as well as private sentinels, so conditional leakage of numeric or ordinary
worker commands cannot escape the same cases.
