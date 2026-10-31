# Withhold command values in capacity readbacks

Date: 2026-09-29   Area: ops

**Context**: A token allowlist printed standalone numeric command arguments outside
recognized capacity option positions. One-off privacy fixtures did not provide a
hosted regression gate.

**Rule**: The Ops capacity projection reports command-override presence only. Never
echo raw command/argument values in any formatting or resolve private environment references. Missing
runtime worker and egress identity remain unknown.

**Evidence**: `backend/tests/unit/test_capacity_projection_privacy.py` loads the
entire committed describe-service readback (`ops/describe/service.py`, by path) with private
service/job sentinels, numeric arguments, malformed configuration and valid capacity values. Stub
only the external gcloud reads (a dict-keyed fake that checks each call's exact argv, the API
service describe first), capture stdout and stderr at file-descriptor level (including inherited
child-process output), and pin the step's `run:` to the one-line module invocation.
Slicing at the capacity comment skipped earlier `show()`
emissions and falsely narrowed this rule. A deliberate pre-marker raw-command emission
fails the same gate; exact restoration passes. Assert every unique fixture command/argument
token absent from the combined output, including ordinary service and job commands. Array-format checks
missed joined command text. Use command numeric values distinct from permitted worker-environment
values, so privacy assertions cannot confuse a raw argument with allowed capacity evidence.
Python stream capture alone misses child emissions; a successful local child printing raw
command/argument tokens must fail the same gate.
