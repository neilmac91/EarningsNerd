"""copilot-eval's source check: the preparation step's last act (E80, the founder's decision of 31 October 2026).

Run in "Prepare actual SEC sources in a new scratch database", after the bootstrap:
python -m evals.copilot_source_check --preparation evals/reports/copilot/preparation.json

It holds the prepared sources to the golden cases' declarations with the runner's own preflight,
``copilot_runner.validate_preparation``, which makes no provider call and reads no credential. A refused source then
fails the preparation step. That is before "Run every verified question three times", the step the draw gate counts,
so the refusal spends no draw. A re-run draws once the declared source prepares again, as after an SEC outage. A
refusal the pull request itself causes, a parser change for one, refuses on every re-run, at no provider cost, until a
push.

The bootstrap stays blind to the golden set (it never reads questions or expected answers); this check reads the
golden cases only once the preparation is written. The runner still calls the same preflight before any provider
call. So a check skipped or removed here refuses there instead, at the cost of the head's draw: the check fails closed
(``tests/unit/test_copilot_source_check.py`` pins both placements).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from evals.copilot_runner import GOLDEN_PATH, _load_cases, validate_preparation

TITLE = "Source refused"


def _command_value(text: str) -> str:
    """The text as a workflow-command value: GitHub reads %, CR and LF in one as escapes."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def refusal(preparation: Path, golden: Path = GOLDEN_PATH) -> str | None:
    """None when every prepared source is the one its golden case declares, else why it is refused.

    The reason is the one the runner's preflight would report: a ValueError's own message (the preflight's refusals,
    which name fields, sections and lengths, never a hash or text), and any other failure's type alone, so no text a
    reader did not write reaches the public log. Every failure refuses: the check fails closed."""
    try:
        validate_preparation(preparation, _load_cases(golden))
    except Exception as exc:  # noqa: BLE001 — any failure refuses, as the runner's preflight reports it
        return str(exc)[:200] if type(exc) is ValueError else type(exc).__name__
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", required=True, type=Path)
    args = parser.parse_args(argv)
    reason = refusal(args.preparation)
    if reason is None:
        print("source check: every prepared source is the one its golden case declares")
        return 0
    print(f"::error title={TITLE}::{_command_value(reason)}. No draw was spent: a re-run draws once the declared "
          "source prepares again, and a refusal this pull request causes needs a push "
          '(backend/evals/RUNBOOK.md, "Source preflight (E80)").')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
