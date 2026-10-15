"""A test's child Python script takes a signal with ``signal.sigwait``, never a Python-level handler
(lessons/test-child-scripts-wait-for-signals.md).

CPython's C-level handler only sets a flag. The Python handler installed with ``signal.signal`` runs
at the interpreter's next check: the end of a call, a backward jump, or a blocking call that returns
EINTR. A signal that lands after the last check but before the next blocking call enters its syscall
is consumed by the C handler, so ``time.sleep(60)`` starts with nothing pending and the Python handler
waits out the whole sleep. That made test_acceptance_process_groups.py's "slow" grandchild deaf to
SIGTERM about once in a thousand runs under load (CI run 38186685529). With gdb holding it at the
window, the runner escalated to SIGKILL after 5 s, and after 30 s with a 30 s grace. Blocking the
signal (``signal.pthread_sigmask``) and taking it with ``signal.sigwait`` keeps it pending until taken,
whenever it arrives. ``SIG_IGN`` and ``SIG_DFL`` are the kernel's own dispositions and cannot race.

This gate parses every string constant under ``backend/tests`` that is not a docstring as Python and
fails on a call to ``signal.signal`` there (also through ``import signal as s``, or a bare ``signal(...)``
call) whose handler is neither disposition. It parses the string constants inside a parsed script the
same way, so an inline ``-c`` grandchild a child script starts is read too. A string that does not
parse, such as one piece of a script built by concatenation, is read line by line: a line calling
``signal(`` with two arguments fails unless it names ``SIG_IGN`` or ``SIG_DFL``. An alias bound in one
string and used in another (``"\\n".join`` of separate lines) is out of reach. The test process's own
handlers are not child scripts and are not read.
"""
import ast
import re
import textwrap
import warnings
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
BACKEND = TESTS.parent
_KERNEL_DISPOSITIONS = {"SIG_IGN", "SIG_DFL"}
_CALL_TEXT = re.compile(r"\bsignal\([^()]*,")  # two arguments: prose naming signal(SIGTERM) passes
_DISPOSITION_TEXT = re.compile(r"\bSIG_(IGN|DFL)\b")


def _is_disposition(handler: ast.AST) -> bool:
    """signal.SIG_IGN, signal.Handlers.SIG_DFL, or a bare SIG_IGN after ``from signal import ...``."""
    if isinstance(handler, ast.Attribute):
        return handler.attr in _KERNEL_DISPOSITIONS
    return isinstance(handler, ast.Name) and handler.id in _KERNEL_DISPOSITIONS


def _python_handlers(text: str) -> list[int]:
    """The script lines that install a handler other than a kernel disposition."""
    try:
        with warnings.catch_warnings():  # an invalid escape in a string that is not Python
            warnings.simplefilter("ignore")
            tree = ast.parse(textwrap.dedent(text))
    # ValueError: a lone surrogate or a null byte; MemoryError, RecursionError: a long run of operators
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return [n for n, line in enumerate(text.splitlines(), 1)
                if _CALL_TEXT.search(line) and not _DISPOSITION_TEXT.search(line)]
    # The names the signal module and signal.signal are bound to. A bare signal(sig, handler) counts even
    # without its import, which may sit in another string; the module itself is not callable.
    modules, functions = {"signal"}, {"signal"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.asname or alias.name for alias in node.names if alias.name == "signal"}
        elif isinstance(node, ast.ImportFrom) and node.module == "signal":
            functions |= {alias.asname or alias.name for alias in node.names if alias.name == "signal"}
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        installs = (
            isinstance(func, ast.Attribute) and func.attr == "signal"
            and isinstance(func.value, ast.Name) and func.value.id in modules
        ) or (isinstance(func, ast.Name) and func.id in functions)
        if not installs:
            continue
        handler = node.args[1] if len(node.args) > 1 else next(
            (kw.value for kw in node.keywords if kw.arg == "handler"), None
        )
        if handler is None or not _is_disposition(handler):  # signal.signal(*args) is read as a handler
            lines.append(node.lineno)
    # A script inside the script: subprocess.Popen([sys.executable, "-c", "import signal ..."]).
    lines += [node.lineno for node in ast.walk(tree)
              if isinstance(node, ast.Constant) and isinstance(node.value, str) and _python_handlers(node.value)]
    return sorted(lines)


def _docstrings(tree: ast.Module) -> set[int]:
    owners = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return {
        id(owner.body[0].value) for owner in owners
        if owner.body and isinstance(owner.body[0], ast.Expr) and isinstance(owner.body[0].value, ast.Constant)
    }


def test_no_child_script_catches_a_signal_in_python():
    found = {}
    for module in sorted(TESTS.rglob("*.py")):
        if module == Path(__file__).resolve():
            continue  # its own self-test samples
        tree = ast.parse(module.read_text(encoding="utf-8"))
        skip = _docstrings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
                if _python_handlers(node.value):
                    found.setdefault(module.relative_to(BACKEND).as_posix(), []).append(node.lineno)
    assert not found, (
        f"A child script installs a Python-level signal handler: {found}. A signal delivered between the "
        "interpreter's last check and a blocking call waits out that call. Block the signal with "
        "signal.pthread_sigmask and take it with signal.sigwait, or use signal.SIG_IGN / signal.SIG_DFL."
    )


def test_the_detector_reads_handlers_and_spares_kernel_dispositions():
    racing = {
        "a named handler": "import signal\ndef stop(*_):\n    raise SystemExit\nsignal.signal(signal.SIGTERM, stop)\n",
        "a lambda": "signal.signal(signal.SIGINT, lambda *_: None)\n",
        "a handler that calls": "import signal, sys\nsignal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n",
        "a partial": "import functools, signal\nsignal.signal(signal.SIGTERM, functools.partial(stop, 1))\n",
        "an aliased module": "import signal as s\ns.signal(s.SIGTERM, stop)\n",
        "an imported function": "from signal import SIGTERM, signal as on\non(SIGTERM, stop)\n",
        "a keyword handler": "import signal\nsignal.signal(signal.SIGTERM, handler=stop)\n",
        "an indented script": "\n    import signal\n    signal.signal(signal.SIGTERM, stop)\n",
        "a fragment": "signal.signal(signal.SIGTERM, lambda *_: (\n",
        "not source text": "\ud800 signal.signal(signal.SIGTERM, stop)\x00",
        "a grandchild inside a child script": (
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c', 'import signal, time\\nsignal.signal(signal.SIGTERM, stop)\\n'])\n"
        ),
        "a bare call in a line of its own": "signal(SIGTERM, stop)",
    }
    safe = {
        "ignored": "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n",
        "default": "signal.signal(signal.SIGPIPE, signal.SIG_DFL)\n",
        "a trailing comma": "signal.signal(\n    signal.SIGTERM,\n    signal.SIG_IGN,\n)\n",
        "the Handlers enum": "import signal\nsignal.signal(signal.SIGTERM, signal.Handlers.SIG_DFL)\n",
        "bare names": "from signal import SIGTERM, SIG_IGN, signal\nsignal(SIGTERM, SIG_IGN)\n",
        "sigwait": "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})\nsignal.sigwait({signal.SIGTERM})\n",
        "a fragment ignoring": "signal.signal(signal.SIGTERM, signal.SIG_IGN\n",
        "prose": "the child got signal 15 and exited",
        "prose naming the call": "the child must call signal(SIGTERM) before it reads stdin",
        "a long run of operators": "-" * 6000,
        "a deeper run of operators": "-" * 3000 + "1",
        "an ignoring grandchild inside a child script": (
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c', 'import signal\\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\\n'])\n"
        ),
        "not source text": "\ud800 signal.signal(signal.SIGTERM, signal.SIG_DFL)\x00",
    }
    assert {name: src for name, src in racing.items() if not _python_handlers(src)} == {}
    assert {name: src for name, src in safe.items() if _python_handlers(src)} == {}


def test_the_detector_skips_docstrings_and_reads_the_old_slow_grandchild():
    module = ast.parse('"""Calls signal.signal(signal.SIGTERM, stop) in prose."""\nX = 1\n')
    assert _docstrings(module) == {id(module.body[0].value)}
    old_slow = (  # test_acceptance_process_groups.py's grandchild before it took SIGTERM with sigwait
        "import signal, sys, time\n"
        "def stop(*_):\n"
        "    time.sleep(0.5)\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)\n"
    )
    assert _python_handlers(old_slow) == [5]
