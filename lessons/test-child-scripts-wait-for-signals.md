# A test's child script takes a signal with sigwait, never a Python handler around a blocking call

Date: 2026-10-15   Area: test

**Context**: `test_acceptance_process_groups.py`'s "slow" grandchild installed a Python SIGTERM
handler (sleep 0.5 s, then exit) and then called `time.sleep(60)`. About once in a thousand runs it
ignored the runner's SIGTERM for the whole sleep, so `_terminate_group` escalated to SIGKILL and the
test failed (CI run 38186685529, [judge]). The cause is CPython's signal model. The C-level handler
only sets a flag, and the Python handler runs at the interpreter's next check: the end of a call, a
backward jump, or a blocking call that returns EINTR. A SIGTERM that lands after the check at the
end of `print('ready')` but before `time.sleep` enters `clock_nanosleep` is consumed by the C
handler. The sleep then starts with nothing pending. The test's `ready` handshake timed the SIGTERM
to land right beside that window. The runner was correct: the member could still run when the
grace ended.

**Rule**: In a child process a test starts, never catch a signal with `signal.signal(sig, handler)`
when the script then blocks. Block the signal (`signal.pthread_sigmask(signal.SIG_BLOCK, {sig})`)
before announcing readiness, and take it with `signal.sigwait({sig})`, which returns at once
for a signal already pending. `SIG_IGN` and `SIG_DFL` are the kernel's own dispositions and are
safe. A longer grace or timeout does not fix this: the handler waits for the whole blocking call.

**Evidence**: the gdb reproduction held the grandchild at the libc entry of `clock_nanosleep` while
the SIGTERM landed. `_terminate_group` returned SIGKILL after 5.06 s (and after 30.03 s with a 30 s
grace), and the grandchild sat in `hrtimer_nanosleep` with nothing pending. The `sigwait` version
returned SIGTERM after 0.74 s under the same injection. A run with no injection left 3 of 1,100
grandchildren stuck. Gate: `backend/tests/unit/test_child_script_signals.py` fails on a
`signal.signal` call with a Python handler in any string constant under `backend/tests`.
