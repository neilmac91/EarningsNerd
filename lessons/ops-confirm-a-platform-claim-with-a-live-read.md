# Confirm a platform claim with a live read before an acceptance rests on it, and make each refusal print what it read

Date: 2026-11-12   Area: ops, verification

**Context**: The feedback-media verifier's resource acceptance (`ops/feedback_media/verify_runtime.py`'s sampler and
`verify_manage.py`'s acceptance) rested on one platform claim: that a Cloud Run service on the second generation reads
its cgroup v2 memory files (`memory.current`, `memory.peak` and `memory.max`) under `/sys/fs/cgroup`. No run had read
them there before the acceptance came to rest on them. Live verify-apply 43124458892 (12 November) passed its browser
stage and its cleanup, then failed at "measurement (resource-acceptance)" without naming why. #2038 made a refusal
name its conditions and figures, and the first read with it, the read-only `feedback-media-verify-inspect` Ops run
43138110953, printed "cgroup limit unread; kernel peak unexposed; sampled peak unread": none of the three files reads
there, so no verify-apply could pass whatever its workload. #2039 then sampled `/proc/meminfo` under a named evidence
basis, and verify-apply 43183491389 passed the same day. The refusal's own line found the gap, after a live sitting
had already been spent on it.

**Rule**:
- When an acceptance or a gate rests on a platform claim (a file a runtime exposes, a field an API returns, a limit
  it enforces), read it live once before the design counts on it, with a read-only probe where one exists, and cite
  that read in the pull request body beside the claim.
- Treat a platform's documentation of such behaviour as the claim to confirm, not as the read.
- Make every refusal of such a check print what it read and which condition failed, in its public output and
  without private values, so the first live failure names the claim that broke.

**Evidence**: #2038 (a refusal names its conditions and figures), #2039 (the `/proc/meminfo` basis), the resource
line of Ops run 43138110953, and verify-apply runs 43124458892 (refused) and 43183491389 (passed). Review-checked: no
gate tells a confirmed claim from an assumed one.
