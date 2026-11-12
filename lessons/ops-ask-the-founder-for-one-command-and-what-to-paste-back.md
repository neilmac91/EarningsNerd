# Ask the founder for evidence as one copyable command and the exact output to paste back

Date: 2026-11-11 | Area: ops, founder asks

**Context**: The first live feedback-media `verify-apply` (run 43102273017) and its retry (run 43103925587)
were refused by Cloud Run with an HTTP 400 whose text the public log withholds. The reason was only in the
project's audit log, which no session tool can read. The first ask was a console walk: open a link, find an
entry, expand two levels and copy a field. The founder answered: "sorry it's not clear what you need me to
do. please explain, or, ideally, do it yourself". The next ask, one Cloud Shell command that printed only the
refusal's status, came back within minutes and named the cause: Cloud Run requires a Cloud SQL volume to be
named `cloudsql`.

**Rule**:
1. Before asking, check whether a session tool or an approved read-only operation can get the evidence. If
   none can, say in one sentence why the session cannot.
2. Ask for one copyable command in its own `bash` block, whose output is only what you need. Say where to run
   it and what to paste back. Never ask for a multi-step console walk.
3. Then make that evidence self-serve. Change the closed public output so the next failure of its kind names
   its cause without the founder.

**Evidence**: `ops/feedback_media/manage.py` (`field_path`: a refused request's field, named in a closed
shape); `ops/feedback_media/verify_manage.py` (`validate_writes`: Cloud Run validates the job and service
writes before the run seeds its lease); `backend/tests/unit/test_feedback_media_infrastructure.py` and
`test_feedback_media_verification_ops.py` pin both.
