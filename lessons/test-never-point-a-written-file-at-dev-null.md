# Never point a file a tool writes at /dev/null; as root, a rename or unlink over it destroys the null device

Date: 2026-10-20   Area: test / ops

**Context**: On 2026-10-20 a full backend run in a cloud session failed 22 tests and errored 36 because
`/dev/null` was by turns missing and an ordinary 48-byte file. Cloud sessions run as root, and root may write
in `/dev`. The first diagnosis blamed `ctypes.util.find_library`. When the backend imports
WeasyPrint, cffi looks up 21 library names in this container that miss, and each miss ends in `_findLib_ld`,
which runs `ld -t -o /dev/null -l<name>`. GNU ld deletes its output when the link fails. That was only the
second step. GNU ld removes its output through `unlink_if_ordinary`, so a character device survives it, and
`ld` destroys `/dev/null` only after something else has made it an ordinary file. From then on each of those
misses unlinked the file, so git and `subprocess.DEVNULL` failed until the next `>/dev/null` created it again.

The first replacement came just after 04:00, during mutation testing of the E126 branch's push-guard tests,
which ran git with `GIT_CONFIG_GLOBAL=/dev/null`. A git config write takes its lock as `<file>.lock` and
renames the lock over the file, so as root it swaps the device for a regular file. That branch's round-2
commit (65ba41ef) gives every case its own empty config for exactly this reason. Main had the same pattern in
`backend/tests/unit/test_ci_cost_controls.py`, which never wrote config, so the hazard stayed latent there.

**Rule**: Never give a tool `/dev/null` (or `os.devnull`) as a file it may write. This covers git's
`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_INDEX_FILE` and `config --file`, the target of an atomic
writer, and a linker's `-o`. Give it an empty file in the test's own temp directory instead. When `/dev/null`
is found broken, ask what first turned the device into a file before blaming the last tool seen unlinking it:
many tools remove an ordinary file, few remove a device. Restore it as root before trusting any run
(`rm -f /dev/null && mknod -m 666 /dev/null c 1 3`; the session's classifier may hold that for the founder),
and say so in the hand-off.

**Evidence**:
- `ld -t -o <node> -lzzz_not_a_lib` (binutils 2.42) on a `mknod c 1 3` node in a scratch directory: exit 1,
  node intact, no unlink in strace. On a non-empty ordinary file it unlinks twice: once before opening it and
  once on failure. The strace that first blamed `ld` showed exactly those two unlinks of `/dev/null`.
- Under a private `/dev` (`unshare --mount`), main's full suite ran 21 `ld -t -o /dev/null` lookups, none of
  which unlinked or renamed `/dev/null`, and 10,790 tests passed. Seven green full runs as root earlier that
  day had left the device in place too. In the same private `/dev`, `GIT_CONFIG_GLOBAL=/dev/null git config --global probe.key value`
  ran `rename("/dev/null.lock", "/dev/null")` and left a 21-byte ordinary file.
- Production runs the same lookups on its first PDF export: `backend/Dockerfile` has no `USER`, its `gcc`
  pulls in binutils' `ld`, and `export_service.py` imports WeasyPrint at request time. Its `/dev/null` is a
  device, so `ld` leaves it alone.
- Partly gated: `_null_device_survives` in `backend/tests/conftest.py` fails the test during which `/dev/null`
  stops being a character device. It can fire only where something can replace the device, which means a root
  session. `test_a_test_that_replaces_the_null_device_fails` in `backend/tests/unit/test_suite_isolation.py`
  proves it on a symlinked stand-in. Pointing a written file at `/dev/null` on a non-root runner is
  review-checked.
