"""Mutation proofs for the copilot-eval withhold-reason change. Offline; run from ``backend/``::

    env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL python \
        ../tasks/review-evidence/copilot-eval-withhold-reason-2026-10-02/mutate.py PYTHON

Each mutation edits one committed file (each target text must occur exactly once; a mutation
may make several such edits), runs ``tests/unit/test_copilot_gate.py``, records the failing
tests, and restores the file with ``git checkout --``; the tree must be clean afterwards. A
mutation is killed when at least one test fails.
"""
import json
import re
import subprocess
import sys

RUNNER = 'evals/copilot_runner.py'
WORKFLOW = '../.github/workflows/copilot-eval.yml'
MUTATIONS = [
    ('M1 capture records nothing', RUNNER,
     "            self.sink.append(str(reason)[:200])", "            pass"),
    ('M2 reason not copied to the row error', RUNNER,
     "                row['error']['withheld_reason'] = row['tool_trace']['withheld_reasons'][0]", "                pass"),
    ('M3 a named withhold counts as success', RUNNER,
     "            failures.append(_withheld_label(row) or 'operationally incomplete attempt')",
     "            if not _withheld_label(row):\n                failures.append('operationally incomplete attempt')"),
    ('M4 no attempt-context check', RUNNER,
     "if isinstance(reason, self.withheld) and _ATTEMPT_CAPTURE.get() is self:", "if isinstance(reason, self.withheld):"),
    ('M5 filter left on the service logger', RUNNER,
     "        self.service_log.removeFilter(self)\n", ""),
    ('M6 generic label kept', RUNNER,
     "    return 'publication withheld: ' + reason if isinstance(reason, str) and reason else None", "    return None"),
    ('M7 markdown verdict shows the raw error', RUNNER,
     "        verdict = (_withheld_label(row) or row.get('error')", "        verdict = (row.get('error')"),
    ('M8 summary step not always()', WORKFLOW,
     "      - name: Show the readable report on the run page\n        # Every row's verdict, including a named publication withhold, without downloading the artifact.\n        if: always()\n",
     "      - name: Show the readable report on the run page\n        # Every row's verdict, including a named publication withhold, without downloading the artifact.\n"),
    ('M9 summary step fails when the report is missing', WORKFLOW,
     '          if [ -f evals/reports/copilot/copilot-eval.md ]; then cat evals/reports/copilot/copilot-eval.md >> "$GITHUB_STEP_SUMMARY"; fi',
     '          cat evals/reports/copilot/copilot-eval.md >> "$GITHUB_STEP_SUMMARY"'),
    ('M10 workflow_dispatch trigger added', WORKFLOW,
     "on:\n  pull_request:\n", "on:\n  workflow_dispatch:\n  pull_request:\n"),
    ('M11 the filter drops the record', RUNNER,
     "            self.sink.append(str(reason)[:200])\n        return True\n",
     "            self.sink.append(str(reason)[:200])\n        return False\n"),
    # The capture as committed in 49677945: a handler, which switches off logging.lastResort.
    ('M12 the capture is a handler again', RUNNER, (
        "class _WithheldReasons(logging.Filter):",
        "        super().__init__()\n",
        "        self.service_log.addFilter(self)\n",
        "        self.service_log.removeFilter(self)\n",
        "    def filter(self, record: logging.LogRecord) -> bool:\n",
        "            self.sink.append(str(reason)[:200])\n        return True\n"), (
        "class _WithheldReasons(logging.Handler):",
        "        super().__init__(logging.WARNING)\n",
        "        self.service_log.addHandler(self)\n",
        "        self.service_log.removeHandler(self)\n",
        "    def emit(self, record: logging.LogRecord) -> None:\n",
        "            self.sink.append(str(reason)[:200])\n")),
]


def gate(python):
    return subprocess.run([python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests/unit/test_copilot_gate.py'],
                          capture_output=True, text=True)


def main():
    python = sys.argv[1]
    baseline = gate(python)
    print('baseline (unmutated):', baseline.stdout.strip().splitlines()[-1])
    assert baseline.returncode == 0, 'the unmutated tree must pass'
    results = []
    for name, path, old, new in MUTATIONS:
        text = open(path).read()
        for target, replacement in (zip(old, new) if isinstance(old, tuple) else [(old, new)]):
            assert text.count(target) == 1, (name, target, text.count(target))
            text = text.replace(target, replacement)
        open(path, 'w').write(text)
        try:
            run = gate(python)
        finally:
            subprocess.run(['git', 'checkout', '--', path], check=True)
        failed = sorted(set(re.findall(r'^FAILED (\S+)', run.stdout, re.M)))
        summary = (run.stdout.strip().splitlines() or [''])[-1]
        results.append({'mutation': name, 'file': path, 'killed': bool(failed), 'summary': summary, 'failed': failed})
        print(f"{name}: {'KILLED' if failed else 'SURVIVED'} -- {summary}")
        for test in failed:
            print('    ' + test)
    clean = subprocess.run(['git', 'status', '--porcelain', '--', RUNNER, WORKFLOW], capture_output=True, text=True).stdout
    print('tree restored clean:', clean == '')
    json.dump({'results': results, 'tree_restored_clean': clean == ''}, open('/dev/stderr', 'w'), indent=1)
    return 0 if clean == '' and all(r['killed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
