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
- Gated four times. `_install_git_null_guard` in `backend/tests/conftest.py`, installed when conftest is
  imported, refuses on any runner a start through `subprocess`, `os.system`, `os.posix_spawn` or `os.spawn*`,
  from a test or a fixture of any scope, whose environment, shell line or git config file option (`--file`,
  `-f`, attached or not) gives git the device, however it was built (byte strings, an `env` by position, a
  shell line in a list), or leaves it to a shell expansion that may name it (`git config -f "$TARGET"`),
  and an `os.putenv` that would set it for later starts; a child run in
  `test_suite_isolation.py` proves each. `_install_null_device_path_guard` beside it fails a test before an
  `os.rename`, `os.replace`, `os.unlink` or `os.remove` (`shutil.move` and `pathlib` go through them) that
  would replace, move or remove the device in the test's own process: an atomic writer handed it as its
  target, a cleanup that removes it, or a test that breaks it and restores it within one phase.
  `backend/tests/unit/test_null_device_write_targets.py` fails on any tracked text file but Markdown,
  whatever its name or mode, that names `/dev/null` or `os.devnull`, or a shell variable it binds to
  either, in git's `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG` or `GIT_INDEX_FILE`, or as git
  config's file, on every runner (CI runs as a non-root user, where nothing can replace the device).
  The null-device checks in `backend/tests/conftest.py` fail the test during whose setup, body or teardown
  `/dev/null` stops being a character device (a fixture of any scope included), which can happen only in a
  root session, and fail the run for a loss outside every test or a device already broken when it starts; three
  child runs in `backend/tests/unit/test_suite_isolation.py` prove it on a stand-in. An atomic writer that
  another program runs and a linker's `-o` stay review-checked: curl's `-o /dev/null` writes in place and is
  safe, so no pattern tells them apart.
