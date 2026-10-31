"""Prune the engine output to what the prototype renders, and emit browser-loadable JS modules.

Keeps every displayed figure, comparison, validation state, reason, formula and the first-level
operands of a calculated figure (with each operand's method, validation, reasons, formula, source
link and its own operands one level further down). A comparison keeps its validation, reasons and
formula plus its two operands' identity, value, period and validation. Nothing is recomputed or
relabelled; the full-depth engine output stays in the scratch directory.
"""
import json
import sys
from pathlib import Path

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

OPERAND_KEYS = ("concept", "value", "unit", "period_start", "period_end", "accession", "raw_tag", "filed_at", "source_url")
PROV_KEYS = ("method", "validation", "reasons", "formula", "calculation_version", "source_url", "period_calculation", "filed_at")


def prov_head(prov):
    if not isinstance(prov, dict):
        return None
    return {k: prov.get(k) for k in PROV_KEYS if prov.get(k) not in (None, [], False)}


def operand(op, depth):
    out = {k: op.get(k) for k in OPERAND_KEYS if op.get(k) is not None}
    head = prov_head(op.get("provenance")) or {}
    if depth < 2:
        head["inputs"] = [operand(o, depth + 1) for o in (op.get("provenance") or {}).get("inputs", [])]
    out["provenance"] = head
    return out


def point_provenance(prov):
    head = prov_head(prov)
    if head is None:
        return None
    head.setdefault("reasons", [])
    head["inputs"] = [operand(o, 1) for o in prov.get("inputs", [])]
    return head


def comparison_provenance(prov):
    head = prov_head(prov)
    if head is None:
        return None
    head.setdefault("reasons", [])
    head["inputs"] = [
        {"concept": o.get("concept"), "value": o.get("value"), "period_end": o.get("period_end"),
         "validation": (o.get("provenance") or {}).get("validation"),
         "reasons": (o.get("provenance") or {}).get("reasons") or []}
        for o in prov.get("inputs", [])
    ]
    return head


def point(p):
    out = {k: v for k, v in p.items() if k not in ("provenance", "yoy_provenance", "qoq_provenance")}
    if "provenance" in p:
        out["provenance"] = point_provenance(p["provenance"])
    for key in ("yoy_provenance", "qoq_provenance"):
        if p.get(key):
            out[key] = comparison_provenance(p[key])
    return out


def dataset(ds):
    out = dict(ds)
    out["series"] = []
    for s in ds["series"]:
        s2 = {k: v for k, v in s.items() if k not in ("points", "cagr_provenance", "window_pp_provenance")}
        s2["points"] = [point(p) for p in s["points"]]
        for key in ("cagr_provenance", "window_pp_provenance"):
            if s.get(key):
                s2[key] = comparison_provenance(s[key])
        out["series"].append(s2)
    return out


def completion(c):
    out = dict(c)
    out["citations"] = [{**cit, "provenance": point_provenance(cit.get("provenance"))} for cit in c["citations"]]
    return out


for name in ("clean", "legacy", "discrepancy"):
    raw = json.loads((SRC / f"{name}.json").read_text())
    state = {"dataset": dataset(raw["dataset"]), "completion": completion(raw["completion"])}
    text = json.dumps(state, separators=(",", ":"))
    (OUT / f"{name}.js").write_text(f"window.EN_STATES = window.EN_STATES || {{}};\nwindow.EN_STATES['{name}'] = {text};\n")
    print(name, len(text), "bytes")
coverage = json.loads((SRC / "coverage.json").read_text())
(OUT / "coverage.js").write_text("window.EN_COVERAGE = " + json.dumps(coverage, separators=(",", ":")) + ";\n")
