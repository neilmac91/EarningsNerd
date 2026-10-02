"""Negative controls for revalidate.py: each tamper must be reported (offline, scratchpad only).

Usage (cwd = B backend, provider keys unset): python negctl.py <r_report.json> <workdir>
"""
import copy
import json
import os

import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import revalidate as rv  # noqa: E402

report_path, work = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(work, exist_ok=True)
B = os.getcwd()
PY = sys.executable
SCRIPT = os.path.join(HERE, "revalidate.py")
results = []


def record(name, ok, detail):
    results.append({"control": name, "caught": ok, "detail": detail})
    print(("CAUGHT " if ok else "MISSED ") + name + " :: " + str(detail)[:300])


def run_script(report, tag, backend=B):
    path = os.path.join(work, f"{tag}.json")
    json.dump(report, open(path, "w"))
    out = os.path.join(work, f"{tag}.out.json")
    p = subprocess.run([PY, SCRIPT, path, out, "--backend", backend], cwd=backend, capture_output=True, text=True)
    res = json.load(open(out)) if os.path.exists(out) else {}
    return p.returncode, res, p.stdout + p.stderr


report = json.load(open(report_path))
idx = {rv.result_key(x): i for i, x in enumerate(report["results"])}

# ---------------------------------------------------------------- end-to-end (exit code) controls
# 1. hosted field altered
r1 = copy.deepcopy(report)
x = r1["results"][idx["FIGS 10-Q run0"]]
x["raw_sections"]["value_drivers"]["returns_on_capital"] = x["raw_sections"]["value_drivers"]["returns_on_capital"].replace("6.4%", "6.5%", 1)
code, out, log = run_script(r1, "e2e-hosted-field")
record("hosted field differs from re-render", code == 1 and any(f["reason"] == "hosted line differs from re-render" for f in out.get("failures", [])), f"exit={code} failures={len(out.get('failures', []))}")

# 2. hosted Markdown altered (field intact)
r2 = copy.deepcopy(report)
x = r2["results"][idx["PLD 10-K run0"]]
line = x["raw_sections"]["value_drivers"]["returns_on_capital"]
x["payload"]["executive_summary"] = x["payload"]["executive_summary"].replace(line, line.replace("2024-12-31", "2024-12-30"))
code, out, log = run_script(r2, "e2e-hosted-markdown")
record("hosted Markdown line differs", code == 1 and any("Markdown" in f["reason"] for f in out.get("failures", [])), f"exit={code}")

# 3. wrong renderer (main archive as --backend) -> the hosted B-format line must not validate
main_backend = os.path.join(HERE, "main-f6e79a50", "backend")
code, out, log = run_script(report, "e2e-main-as-successor", backend=main_backend)
record("main renderer used as successor is refused (exit 2)", code == 2 and "lacks B's code under test" in log, f"exit={code} log={log.strip()[-160:]}")

# 4. mutated renderer: drop the date guard; an undated FIGS prior then renders with hosted == re-render
mut = os.path.join(work, "mut-backend")
if os.path.exists(mut):
    shutil.rmtree(mut)
shutil.copytree(B, mut, ignore=shutil.ignore_patterns("__pycache__", "tests", "evals"))
mr = os.path.join(mut, "app/services/ai/markdown_render.py")
src = open(mr).read()
guard = "if returns_ratio_in_band(prior_value) and prior_period is not None:"
assert guard in src
open(mr, "w").write(src.replace(guard, "if returns_ratio_in_band(prior_value):"))
r4 = copy.deepcopy(report)
x = r4["results"][idx["FIGS 10-Q run0"]]
x["xbrl_grounding"]["return_on_equity"]["prior"]["period"] = "N/A"
# Make the hosted copies equal to the mutated renderer's output so only the source check can catch it.
code, out, log = run_script(r4, "e2e-mut-undated-pre", backend=mut)
rer = next(c for c in out["changed_lines"] if c["key"] == "FIGS 10-Q run0")["successor"]
x["payload"]["executive_summary"] = x["payload"]["executive_summary"].replace(x["raw_sections"]["value_drivers"]["returns_on_capital"], rer)
x["raw_sections"]["value_drivers"]["returns_on_capital"] = rer
code, out, log = run_script(r4, "e2e-mut-undated", backend=mut)
reasons = [f["reason"] for f in out.get("failures", [])]
record("undated prior renders (date guard removed, hosted == re-render)",
       code == 1 and any("undated prior renders" in r for r in reasons) and not any("hosted" in r for r in reasons),
       f"exit={code} line={rer!r} reasons={reasons}")
shutil.rmtree(mut)

# ---------------------------------------------------------------- clause-level controls (direct)
rv.offline_environment()
r = rv.import_renderer(B)
from app.services.financial_basis import net_income_basis  # noqa: E402
from app.services.ai.xbrl_narrative import return_ratio_period, returns_ratio_in_band  # noqa: E402


def check(key, line, xg):
    checks, line_fails, _ = rv.check_line(key, line, xg, net_income_basis, returns_ratio_in_band, return_ratio_period)
    return line_fails + [f for ch in checks for f in ch["failures"]], checks


def base(key):
    res = report["results"][idx[key]]
    return res["raw_sections"]["value_drivers"]["returns_on_capital"], copy.deepcopy(res["xbrl_grounding"])


line, xg = base("FIGS 10-Q run0")
fails, _ = check("FIGS", line, xg)
record("control baseline passes (FIGS run0 untampered)", fails == [], fails)

fails, _ = check("FIGS", line.replace("6.4%", "6.3%", 1), xg)
record("wrong current value", any("current value renders" in f for f in fails), fails)

fails, _ = check("FIGS", line.replace("attributable to the parent", "including noncontrolling interests", 1), xg)
record("wrong numerator scope", any("scope renders" in f for f in fails), fails)

fails, _ = check("FIGS", line.replace("prior at 2026-03-31", "prior at 2025-06-30"), xg)
record("mis-dated prior (YoY date on a sequential point)", any("mis-dated prior" in f for f in fails), fails)

fails, _ = check("FIGS", line.replace(" (prior at 2026-03-31: 1.5%)", ""), xg)
record("in-band dated prior silently dropped", any("not rendered" in f for f in fails), fails)

fails, _ = check("FIGS", line.replace("prior at 2026-03-31: 1.5%", "prior year: 1.5%"), xg)
record("sequential prior worded as YoY", any("does not parse" in f for f in fails), fails)

x2 = copy.deepcopy(xg)
x2["return_on_equity"]["prior"]["period"] = "FY26Q1"
fails, _ = check("FIGS", line.replace("prior at 2026-03-31", "prior at FY26Q1"), x2)
record("non-ISO prior period renders", any("undated prior renders" in f for f in fails), fails)

x3 = copy.deepcopy(xg)
x3["return_on_equity"]["prior"]["numerator"]["period_start"] = "2025-04-01"
fails, _ = check("FIGS", line, x3)
record("prior numerator duration class differs", any("duration class" in f for f in fails), fails)

x4 = copy.deepcopy(xg)
x4["return_on_equity"]["prior"]["numerator"]["raw_tag"] = "us-gaap:ProfitLoss"
fails, _ = check("FIGS", line, x4)
record("missing prior basis note", any("prior basis note" in f for f in fails), fails)
noted = line.replace("(prior at 2026-03-31: 1.5%)",
                     "(prior at 2026-03-31: 1.5%; period net income including noncontrolling interests / period-end equity, not annualized)")
fails, _ = check("FIGS", noted, x4)
record("correct prior basis note accepted", fails == [], fails)

x5 = copy.deepcopy(xg)
for k in ("return_on_equity", "return_on_assets"):
    x5[k]["current"]["numerator"]["raw_tag"] = "abc:AdjustedNetIncome"
un = line.replace("attributable to the parent", "(numerator scope unestablished)")
fails, checks = check("FIGS", un, x5)
basis_fail = [f for f in fails if "prior basis note" in f]
record("unestablished clause listed, not failed on scope",
       all(ch["numerator_unestablished"] for ch in checks) and not any("scope renders" in f for f in fails),
       {"unestablished": [ch["numerator_unestablished"] for ch in checks], "other_failures": fails})
record("unestablished current vs established prior requires a basis note", bool(basis_fail), basis_fail)

x6 = copy.deepcopy(xg)
x6["return_on_equity"]["current"].pop("numerator")
fails, _ = check("FIGS", line, x6)
record("operand copies missing", any("operand copies missing" in f for f in fails), fails)

x7 = copy.deepcopy(xg)
x7["return_on_equity"]["current"]["denominator"]["period"] = "2026-03-31"
fails, _ = check("FIGS", line, x7)
record("operand period differs from ratio period", any("operand periods differ" in f for f in fails), fails)

gline, gxg = base("GPRO 10-K run0")
fails, _ = check("GPRO", gline.replace("not annualized: -122.1%", "not annualized: -122.1% (prior at 2024-12-31: -285.0%)", 1), gxg)
record("out-of-band prior renders", any("out-of-band prior renders" in f for f in fails), fails)

bline, bxg = base("BYND 10-Q run0")
fails, _ = check("BYND", bline, bxg)
record("control baseline passes (BYND single ROA clause)", fails == [], fails)

fails, _ = check("FIGS", None, xg)
record("missing line while in-band ratios exist", bool(fails), fails)

json.dump(results, open(os.path.join(work, "negctl-results.json"), "w"), indent=1)
missed = [c for c in results if not c["caught"]]
print(f"controls={len(results)} missed={len(missed)}")
sys.exit(1 if missed else 0)
