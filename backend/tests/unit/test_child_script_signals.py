"""A test's child Python script takes a signal with ``signal.sigwait``, never a Python-level handler
(lessons/test-child-scripts-wait-for-signals.md).

CPython's C-level handler only sets a flag. The Python handler installed with ``signal.signal`` runs
at the interpreter's next check: the end of a call, a backward jump, or a blocking call that returns
EINTR. A signal that lands after the last check but before the next blocking call enters its syscall
is consumed by the C handler, so ``time.sleep(60)`` starts with nothing pending and the Python handler
waits out the whole sleep. That made test_acceptance_process_groups.py's "slow" grandchild deaf to
SIGTERM about once in a thousand runs (CI run 38186685529). With gdb holding it at the window, the
runner escalated to SIGKILL after 5 s, and after 30 s with a 30 s grace. Blocking the signal
(``signal.pthread_sigmask``) and taking it with ``signal.sigwait`` keeps it pending until taken,
whenever it arrives. ``SIG_IGN`` and ``SIG_DFL`` are the kernel's own dispositions and cannot race.

This gate reads every string constant under ``backend/tests`` and fails on a ``signal.signal`` call
there whose handler is neither. The test process's own handlers are not child scripts and are not
read.
"""
import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
BACKEND = TESTS.parent
_CALL = re.compile(r"signal\.signal\(\s*[^,()]+,\s*([^()]+?)\s*\)")
_KERNEL_DISPOSITIONS = {"signal.SIG_IGN", "signal.SIG_DFL"}


def _python_handlers(text: str) -> list[str]:
    return [m.group(0) for m in _CALL.finditer(text) if m.group(1) not in _KERNEL_DISPOSITIONS]


def test_no_child_script_catches_a_signal_in_python():
    found = {}
    for module in sorted(TESTS.rglob("*.py")):
        if module == Path(__file__).resolve():
            continue  # its own self-test samples
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _python_handlers(node.value):
                found.setdefault(module.relative_to(BACKEND).as_posix(), []).append(node.lineno)
    assert not found, (
        f"A child script installs a Python-level signal handler: {found}. A signal delivered between the "
        "interpreter's last check and a blocking call waits out that call. Block the signal with "
        "signal.pthread_sigmask and take it with signal.sigwait, or use signal.SIG_IGN / signal.SIG_DFL."
    )


def test_the_detector_reads_handlers_and_spares_kernel_dispositions():
    racing = "import signal\ndef stop(*_):\n    raise SystemExit\nsignal.signal(signal.SIGTERM, stop)\n"
    assert _python_handlers(racing) == ["signal.signal(signal.SIGTERM, stop)"]
    assert _python_handlers("signal.signal(signal.SIGINT, lambda *_: None)\n")
    for safe in ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n",
                 "signal.signal(signal.SIGPIPE, signal.SIG_DFL)\n",
                 "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})\nsignal.sigwait({signal.SIGTERM})\n"):
        assert _python_handlers(safe) == [], safe
