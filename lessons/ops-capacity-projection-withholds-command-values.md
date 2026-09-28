# Withhold command values in capacity readbacks

Date: 2026-09-29   Area: ops

**Context**: A token allowlist printed standalone numeric command arguments outside
recognized capacity option positions. One-off privacy fixtures did not provide a
hosted regression gate.

**Rule**: The Ops capacity projection reports command-override presence only. Never
echo raw command/argument arrays or resolve private environment references. Missing
runtime worker and egress identity remain unknown.

**Evidence**: `backend/tests/unit/test_capacity_projection_privacy.py` executes the
exact committed projection with private sentinels, numeric arguments, malformed
configuration and valid capacity values. A deliberate raw-command emission fails
that gate; exact restoration passes.
