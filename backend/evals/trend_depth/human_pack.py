"""Blind preference pack for human raters: current vs proposed analyses for five companies.

    cd backend && python -m evals.trend_depth.human_pack --label eval-v1 --proposed claude-sonnet-5-5 \
        --key-out /path/outside/the/repository/unblinding-key.json

Writes ``tasks/analysis-depth-2026-10/human-pack/``: ``index.html`` (one self-contained page per rater:
each company's two analyses as "Analysis A" and "Analysis B", the metrics table they sat above, and the
questions), ``scoring-sheet.csv`` (one row per rater x company) and ``README.md`` (instructions and the
SHA-256 of the unblinding key). The A/B order is drawn per company from a random seed that is written only
into the key (``--seed`` fixes it, for tests); the key that maps A/B to current/proposed is written only to
``--key-out``. The repository is public, so the key, and the seed, must stay outside it until the ratings
are in.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import secrets
from pathlib import Path
from typing import Any

from evals.trend_depth import bootstrap, readable
from evals.trend_depth.companies import HUMAN_PACK
from evals.trend_depth.generate import RUNS, load_pack
from evals.trend_depth.render import fmt

OUT = bootstrap.RECORDS / "human-pack"

QUESTIONS = (
    ("preference", "Which analysis would you rather read above this company's metrics table?", "A / B / no preference"),
    ("useful_A", "Analysis A: how much does it tell you that the table does not? (1 = nothing, 5 = a lot)", "1-5"),
    ("useful_B", "Analysis B: how much does it tell you that the table does not? (1-5)", "1-5"),
    ("trust_A", "Analysis A: how far do you trust its statements, having spot-checked two sources? (1-5)", "1-5"),
    ("trust_B", "Analysis B: how far do you trust its statements, having spot-checked two sources? (1-5)", "1-5"),
    ("clarity_A", "Analysis A: how clear is it for a non-professional investor? (1-5)", "1-5"),
    ("clarity_B", "Analysis B: how clear is it for a non-professional investor? (1-5)", "1-5"),
    ("errors", "Any statement you believe is wrong or unsupported (quote it, say which analysis)", "free text"),
    ("comment", "Anything else", "free text"),
)


def _md_to_html(markdown: str) -> str:
    out: list[str] = []
    in_list = False
    for line in markdown.splitlines():
        text = html.escape(line, quote=False)
        text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
        text = re.sub(r"(https://www\.sec\.gov/[^\s<)]+)", r"<a href='\1' target='_blank' rel='noopener'>open in EDGAR</a>", text)
        if line.startswith("### "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h4>{text[4:]}</h4>")
        elif line.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{text[3:]}</h3>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{text[2:]}</li>")
        elif line.startswith("[") and re.match(r"\[\d+\]", line):
            out.append(f"<p class='src'>{text}</p>")
        elif line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{text}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _table(pack: dict[str, Any]) -> str:
    periods = [p["key"] for p in pack["periods"]]
    rows: dict[str, dict[str, str]] = {}
    for vid, value in pack["values"].items():
        if vid.startswith("F") and value["period"] in periods:
            rows.setdefault(value["label"], {})[value["period"]] = fmt(value["value"], value["unit"])
    head = "".join(f"<th>{p}</th>" for p in periods)
    body = "".join(
        f"<tr><th>{html.escape(label)}</th>" + "".join(f"<td>{cells.get(p, '—')}</td>" for p in periods) + "</tr>"
        for label, cells in rows.items()
    )
    return f"<div class='table'><table><thead><tr><th>Metric</th>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def build(label: str, proposed: str, key_out: Path, seed: int, raters: int) -> None:
    rng = random.Random(seed)
    OUT.mkdir(parents=True, exist_ok=True)
    key: dict[str, Any] = {"label": label, "proposed_arm": proposed, "seed": seed, "companies": {}}
    sections = []
    for ticker in HUMAN_PACK:
        pack = load_pack(ticker)
        current = json.loads((RUNS / label / "current" / f"{ticker}.json").read_text())
        candidate = json.loads((RUNS / label / proposed / f"{ticker}.json").read_text())
        texts = {"current": readable.current_markdown(current),
                 "proposed": readable.proposed_markdown(candidate["output"], pack, passage_chars=320, links=True)}
        order = ["current", "proposed"]
        rng.shuffle(order)
        key["companies"][ticker] = {"A": order[0], "B": order[1]}
        sections.append(
            f"<section id='{ticker}'><h2>{html.escape(pack['company_name'])} ({ticker}) · {pack['window']}</h2>"
            f"<details><summary>The metrics table these analyses sit above</summary>{_table(pack)}</details>"
            f"<div class='pair'><article><h3 class='label'>Analysis A</h3>{_md_to_html(texts[order[0]])}</article>"
            f"<article><h3 class='label'>Analysis B</h3>{_md_to_html(texts[order[1]])}</article></div></section>"
        )
    key_bytes = json.dumps(key, indent=1, sort_keys=True).encode()
    key_out.parent.mkdir(parents=True, exist_ok=True)
    key_out.write_bytes(key_bytes)
    digest = hashlib.sha256(key_bytes).hexdigest()
    questions = "".join(f"<li><b>{html.escape(q)}</b> <span>({html.escape(a)})</span></li>" for _, q, a in QUESTIONS)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analysis preference study</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5d5b55;--panel:#fff;--line:#dedad2}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16150f;--fg:#ecebe6;--muted:#b2afa6;--panel:#201f19;--line:#3a3830}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:16px}}
main{{max-width:1280px;margin:auto}} section{{margin:40px 0;border-top:2px solid var(--line);padding-top:16px}}
.pair{{display:grid;grid-template-columns:1fr;gap:16px}} @media(min-width:900px){{.pair{{grid-template-columns:1fr 1fr}}}}
article{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;min-width:0}}
.label{{margin-top:0}} .src{{font-size:13px;color:var(--muted);margin:2px 0;overflow-wrap:anywhere}}
.table{{overflow-x:auto}} table{{border-collapse:collapse;font-size:13px}} td,th{{border-bottom:1px solid var(--line);padding:3px 8px;text-align:right;white-space:nowrap}}
th:first-child{{text-align:left}} h4{{font-size:14px;color:var(--muted)}}
</style></head><body><main>
<h1>Which analysis would you rather read?</h1>
<p>Each company below has two analyses of the same ten years of filings, labelled A and B in random order. Both sit above
the same metrics table (expand it to see the figures). Read both, spot-check two sources in each, then answer for that
company in your scoring sheet:</p><ol>{questions}</ol>
<p>Please do not look anything up beyond the filings and sources linked. Take the companies in the order shown.</p>
{''.join(sections)}
</main></body></html>"""
    (OUT / "index.html").write_text(page)
    header = ["rater", "company", *[q for q, _, _ in QUESTIONS]]
    rows = [",".join(header)] + [",".join([f"rater{r}", ticker] + [""] * len(QUESTIONS)) for r in range(1, raters + 1) for ticker in HUMAN_PACK]
    (OUT / "scoring-sheet.csv").write_text("\n".join(rows) + "\n")
    (OUT / "README.md").write_text(
        "# Blind preference pack\n\n"
        f"Five companies ({', '.join(HUMAN_PACK)}): the current production analysis against the proposed one "
        f"(`{proposed}`, run `{label}`), A/B order drawn per company from a random seed kept in the key. Send each rater `index.html` "
        "and a copy of `scoring-sheet.csv` (rows for that rater only). Ratings are 1-5; preference is A, B or none.\n\n"
        f"The unblinding key was written outside the repository. Its SHA-256 is `{digest}`. Check the key against it "
        "before scoring, so the order cannot have been changed after the ratings arrived.\n\n"
        "The two analyses differ visibly in length and style, so a rater who knows the current page may recognise it. "
        "Ask raters to judge what each analysis tells them and how far they trust it, not which one looks newer.\n\n"
        "Scoring: count preferences for proposed vs current per company and overall; compare mean usefulness, trust and "
        "clarity; read every 'errors' entry against the sources and record whether it is a real error.\n"
    )
    print(f"wrote {OUT}; key {key_out} sha256 {digest}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--proposed", required=True)
    parser.add_argument("--key-out", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=None, help="fixed seed for tests; by default a random one, kept in the key")
    parser.add_argument("--raters", type=int, default=3)
    args = parser.parse_args()
    if bootstrap.REPO in args.key_out.resolve().parents:
        raise SystemExit("--key-out must be outside the repository (it is public)")
    build(args.label, args.proposed, args.key_out, args.seed if args.seed is not None else secrets.randbits(63), args.raters)


if __name__ == "__main__":
    main()
