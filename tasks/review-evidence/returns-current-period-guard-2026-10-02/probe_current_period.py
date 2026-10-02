#!/usr/bin/env python3
"""Offline probe: a return ratio whose current point is not net income's current period.

Extends the close-out R4 probe (scratch `neg_equity_probe.py`) with a 10-Q FIGS-like shape and a
zero-equity variant. Each case runs raw XBRL series through the real standardizer
(`extract_standardized_metrics`), then records the model-facing grounding block
(`build_xbrl_narrative_section`) and the code-rendered `value_drivers.returns_on_capital` line plus
its Markdown, under two backends: main (a `git archive`) and the branch. Each backend renders in its
own subprocess so the two `app` packages never mix.

Usage (any cwd; real provider keys unset):

    python probe_current_period.py --main-backend DIR --branch-backend DIR out.json

No network: provider keys are replaced by the tests/conftest.py placeholder and every socket
connect raises. Bytecode writing is disabled so neither backend tree changes.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402

PROVIDER_KEYS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY",
                 "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_FALLBACK_API_KEY", "OPENAI_FALLBACK_BASE_URL")


def ni(period, start, value, form):
    return {"period": period, "period_start": start, "value": value, "form": form, "currency": "USD",
            "raw_tag": "us-gaap:NetIncomeLoss"}


def inst(period, value, form):
    return {"period": period, "value": value, "form": form, "currency": "USD"}


def annual(equity):
    return {
        "net_income": [ni("2025-12-31", "2025-01-01", 100.0, "10-K"), ni("2024-12-31", "2024-01-01", 80.0, "10-K"),
                       ni("2023-12-31", "2023-01-01", 60.0, "10-K")],
        "shareholders_equity": [inst(p, v, "10-K") for p, v in equity],
        "total_assets": [inst("2025-12-31", 2000.0, "10-K"), inst("2024-12-31", 1900.0, "10-K")],
    }


def quarterly(q2_equity):
    # FIGS-like 10-Q (Q2): three-month net income for Q2, Q1 and the prior-year Q2; the instance path
    # keeps only 75-105 day durations, so no year-to-date figure is in play.
    equity = [inst("2026-03-31", 500.0, "10-Q"), inst("2025-12-31", 450.0, "10-Q")]
    if q2_equity is not None:
        equity.insert(0, inst("2026-06-30", q2_equity, "10-Q"))
    return {
        "net_income": [ni("2026-06-30", "2026-04-01", 12.0, "10-Q"), ni("2026-03-31", "2026-01-01", 7.5, "10-Q"),
                       ni("2025-06-30", "2025-04-01", 9.0, "10-Q")],
        "shareholders_equity": equity,
        "total_assets": [inst("2026-06-30", 2000.0, "10-Q"), inst("2026-03-31", 1900.0, "10-Q"),
                         inst("2025-12-31", 1800.0, "10-Q")],
    }


CASES = {
    # R4 cases A-C, with period_start added.
    "A_10k_negative_equity_at_report_date": annual([("2025-12-31", -50.0), ("2024-12-31", 400.0),
                                                    ("2023-12-31", 300.0)]),
    "B_10k_equity_missing_at_report_date": annual([("2024-12-31", 400.0), ("2023-12-31", 300.0)]),
    "C_10k_normal": annual([("2025-12-31", 500.0), ("2024-12-31", 400.0)]),
    "D_10k_zero_equity_at_report_date": annual([("2025-12-31", 0.0), ("2024-12-31", 400.0),
                                                ("2023-12-31", 300.0)]),
    "E_10q_figs_like_negative_equity_at_report_date": quarterly(-20.0),
    "F_10q_figs_like_normal_sequential_prior": quarterly(520.0),
}


def offline_environment() -> None:
    for key in PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ.update({
        "OPENAI_API_KEY": "sk-test-key-for-mocking", "OPENAI_BASE_URL": "http://127.0.0.1:9/offline-blocked",
        "SECRET_KEY": "offline-probe-secret-key-0123456789abcdef", "SKIP_REDIS_INIT": "true",
        "PWNED_PASSWORD_CHECK_ENABLED": "false", "DATABASE_URL": "sqlite://", "ENVIRONMENT": "development",
        "PYTHONDONTWRITEBYTECODE": "1",
    })

    def _blocked(*_a, **_k):
        raise RuntimeError("probe is offline: network access is blocked")

    socket.socket.connect = _blocked  # type: ignore[assignment]
    socket.socket.connect_ex = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]


def worker(backend: str) -> None:
    offline_environment()
    sys.path.insert(0, backend)
    os.chdir(backend)
    from app.services.ai.xbrl_narrative import build_xbrl_narrative_section
    from app.services.edgar.xbrl_service import edgar_xbrl_service
    from app.services.openai_service import openai_service
    from app.services.summary_sections import render_sections, sections_to_markdown
    app_file = os.path.abspath(sys.modules["app"].__file__)
    assert app_file.startswith(os.path.abspath(backend) + os.sep), app_file

    out = {"app_file": app_file, "cases": {}}
    for name, raw in CASES.items():
        metrics = edgar_xbrl_service.extract_standardized_metrics(raw)

        def period(key, which):
            return ((metrics.get(key) or {}).get(which) or {}).get("period")

        sections: dict = {}
        openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, metrics)
        out["cases"][name] = {
            "net_income_current": period("net_income", "current"),
            "roe_current": period("return_on_equity", "current"), "roe_prior": period("return_on_equity", "prior"),
            "roa_current": period("return_on_assets", "current"), "roa_prior": period("return_on_assets", "prior"),
            "grounding": build_xbrl_narrative_section(metrics),
            "line": (sections.get("value_drivers") or {}).get("returns_on_capital"),
            "markdown": sections_to_markdown(render_sections({"schema_version": 2, "sections": sections})),
        }
    json.dump(out, sys.stdout)


def render(backend: str) -> dict:
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", backend], cwd=backend,
                          capture_output=True, text=True, timeout=600,
                          env={k: v for k, v in os.environ.items() if k not in PROVIDER_KEYS + ("PYTHONPATH",)})
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(2)
    return json.loads(proc.stdout)


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-backend", required=True)
    ap.add_argument("--branch-backend", required=True)
    ap.add_argument("out")
    args = ap.parse_args()
    main_run, branch_run = render(os.path.abspath(args.main_backend)), render(os.path.abspath(args.branch_backend))
    cases = {}
    for name in CASES:
        m, b = main_run["cases"][name], branch_run["cases"][name]
        cases[name] = {
            **{k: m[k] for k in ("net_income_current", "roe_current", "roe_prior", "roa_current", "roa_prior")},
            "ratio_current_differs_from_net_income": sorted(
                r for r in ("roe", "roa") if m[f"{r}_current"] not in (None, m["net_income_current"])),
            "grounding_identical": m["grounding"] == b["grounding"],
            "line_identical": m["line"] == b["line"],
            "markdown_identical_outside_returns_line": (
                [x for x in m["markdown"].splitlines() if x not in (m["line"], b["line"])]
                == [x for x in b["markdown"].splitlines() if x not in (m["line"], b["line"])]),
            "main_line": m["line"], "branch_line": b["line"],
            "grounding_ratio_lines": [x for x in m["grounding"].splitlines() if "Return on" in x],
        }
    result = {"main_app_file": main_run["app_file"], "branch_app_file": branch_run["app_file"], "cases": cases}
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=1)
        fh.write("\n")
    for name, c in cases.items():
        print(f"{name}: differs={c['ratio_current_differs_from_net_income']} grounding_identical="
              f"{c['grounding_identical']} line_identical={c['line_identical']}")
        print(f"  main:   {c['main_line']}")
        print(f"  branch: {c['branch_line']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
