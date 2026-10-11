"""Offline reproduction of the real META 12-quarter analysis dataset in three states.

Runs the repository's own engine (normalize_companyfacts -> upsert_facts_bulk -> build_dataset ->
observation catalogue -> citation resolution) on a freshly fetched SEC companyfacts payload inside a
private SQLite database. No production state, no AI call (the observation selection is a deterministic
"first three per section" stand-in for the model's choice), no network beyond the already-saved payload.

The output is pinned to the engine's shape before #1225, which the committed fixtures, the prototype, both
recorded runs and the baseline's fixture hash were built on: the two fields #1225 added are dropped on write
(PRE_1225_DROPS), so a re-run on later main still reproduces the committed files.

Usage: python build_states.py <companyfacts.json> <out_dir> [--probe]
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(BACKEND))

_DB_DIR = tempfile.mkdtemp(prefix="earningsnerd-design-review-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_DB_DIR, "earningsnerd.db")
# Placeholders only: Settings refuses to load without these keys; nothing here calls a provider.
os.environ["SECRET_KEY"] = "design-review-secret-key-must-be-long-enough-123"
os.environ["OPENAI_API_KEY"] = "sk-unused"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_unused"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_unused"
os.environ["SKIP_REDIS_INIT"] = "true"
os.environ["PWNED_PASSWORD_CHECK_ENABLED"] = "false"
for key in ("SENTRY_DSN", "POSTHOG_API_KEY", "RESEND_API_KEY", "ALPHA_VANTAGE_API_KEY", "TURNSTILE_SECRET_KEY"):
    os.environ[key] = ""

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Company, FinancialFact  # noqa: E402
from app.services import facts_service  # noqa: E402
from app.services import trend_analysis_service as svc  # noqa: E402
from app.services.trend_analysis.periods import available_periods  # noqa: E402
from app.services.trend_analysis.stream_events import analysis_completion  # noqa: E402

START, END = "2023Q3", "2026Q2"

# Production-like legacy records (modelled on the 2026-10 META screenshots: the visible warned cells are
# working capital + current ratio 2023Q4/2024Q1 and operating margin 2025Q2/2026Q2, net margin 2026Q2,
# current ratio 2026Q2; the remaining three of the ten are placed on plausible computed rows).
LEGACY_ROWS = [
    ("working_capital", "2023-12-31"), ("current_ratio", "2023-12-31"),
    ("working_capital", "2024-03-31"), ("current_ratio", "2024-03-31"),
    ("operating_margin", "2025-06-30"), ("operating_margin", "2026-06-30"),
    ("net_margin", "2026-06-30"), ("current_ratio", "2026-06-30"),
    ("net_margin", "2025-06-30"), ("working_capital", "2026-06-30"),
]
# Production shows capital expenditures and free cash flow as Unavailable for 2023Q3 and 2023Q4.
MISSING_ROWS = [
    ("capital_expenditures", "2023-09-30"), ("capital_expenditures", "2023-12-31"),
    ("free_cash_flow", "2023-09-30"), ("free_cash_flow", "2023-12-31"),
]
# Genuine discrepancy: available sources disagree on the latest reported revenue.
CONFLICT_ROW = ("revenue", "2026-06-30")


# The fields #1225 added, dropped on write. The dataset's data_notes: the prototype builds its own notes model.
# The completion's narrative_presentation: production renders that envelope and this builder does not, so
# analysis_completion copies a null, which the current frontend refuses (decodeNarrativePresentation throws and
# the page shows an error under the "AI trend analysis" heading), while a completion without the field renders
# from its narrative and citations.
PRE_1225_DROPS = (("dataset", "data_notes"), ("completion", "narrative_presentation"))


def deterministic_selection(catalogue):
    selection = {}
    for section, _ in svc.ANALYSIS_SECTIONS:
        ids = [item.id for item in catalogue if item.section == section and not item.required]
        selection[section] = ids[: svc._OPTIONAL_PER_SECTION]
    return selection


def narrative_for(dataset):
    catalogue = svc.build_observation_catalogue(dataset)
    selection = deterministic_selection(catalogue)
    code_narrative = svc.render_observation_selection(catalogue, selection)
    index = svc.marker_index(dataset)
    narrative, citations, grounded, unverified = svc.resolve_narrative_citations(code_narrative, index)
    mismatched = svc.scan_numeric_fidelity(narrative, citations, index)
    completion = analysis_completion(
        dataset, analysis_id=1, narrative=narrative, citations=citations, grounded=grounded,
        unverified=unverified, mismatched=len(mismatched), cached=False, invalidated=False, usage={},
    )
    completion["catalogue_size"] = len(catalogue)
    return completion


def quality_summary(dataset):
    points = [(s["label"], p) for s in dataset["series"] for p in s["points"]]
    flagged = [(l, p["period"], p["provenance"]["reasons"]) for l, p in points
               if p.get("provenance") and p["provenance"]["validation"] == "needs_review"]
    missing = [(l, p["period"]) for l, p in points if p["value"] is None]
    comparisons = []
    for s in dataset["series"]:
        for p in s["points"]:
            for key in ("qoq", "yoy"):
                prov = p.get(f"{key}_provenance")
                if prov and prov["validation"] == "needs_review":
                    comparisons.append((s["label"], p["period"], key))
    return {"flagged_points": flagged, "missing": missing, "flagged_comparisons": comparisons,
            "n_values": sum(1 for _, p in points if p["value"] is not None)}


def _differences(a, b, path="dataset"):
    """Paths where two JSON-like structures differ (first-level detail only, for a failure message)."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append(f"{path}/{key} present on one side only")
            else:
                out.extend(_differences(a[key], b[key], f"{path}/{key}"))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path} length {len(a)} vs {len(b)}")
        else:
            for index, (x, y) in enumerate(zip(a, b)):
                out.extend(_differences(x, y, f"{path}[{index}]"))
    elif a != b:
        out.append(f"{path}: {a!r:.60} vs {b!r:.60}")
    return out


def main():
    payload_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    probe = "--probe" in sys.argv
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(payload_path.read_text())
    Base.metadata.create_all(engine)
    db = SessionLocal()
    company = Company(ticker="META", cik="1326801", name="Meta Platforms, Inc.", exchange="NASDAQ", sic="7370")
    db.add(company)
    db.commit()
    facts, meta = facts_service.normalize_companyfacts(company.id, payload, financial_sic=False)
    result = facts_service.upsert_facts_bulk(db, facts, commit=False)
    company.facts_synced_at = datetime.now(timezone.utc)
    db.commit()
    print("ingest:", result, meta, "facts:", len(facts))

    coverage = available_periods(db, company.id)
    (out_dir / "coverage.json").write_text(json.dumps({
        "ticker": "META", "company_name": company.name, "supported": True, "reason": None,
        "syncing": False, "synced_at": company.facts_synced_at.isoformat(),
        "annual": coverage["annual"], "quarterly": coverage["quarterly"],
        "limits": {"annual": 10, "quarterly": 12},
    }, indent=1))
    (out_dir / "company.json").write_text(json.dumps({
        "id": company.id, "cik": company.cik, "ticker": "META", "name": company.name, "exchange": "NASDAQ",
    }))

    def build():
        db.expire_all()
        return svc.build_dataset(db, company, "quarterly", START, END)

    def row(concept, period_end):
        return (db.query(FinancialFact)
                .filter(FinancialFact.company_id == company.id, FinancialFact.concept == concept,
                        FinancialFact.period_end == datetime.fromisoformat(period_end).date(),
                        FinancialFact.is_latest.is_(True))
                .first())

    clean = build()
    if probe:
        for s in clean["series"]:
            print(f"\n{s['label']} ({s['unit']}, percent={s['percent']})")
            for p in s["points"]:
                prov = p.get("provenance") or {}
                print(f"  {p['period']}: {p['value']!s:>18} method={prov.get('method')} validation={prov.get('validation')} reasons={prov.get('reasons')} derived={p.get('derived')} src={p.get('source_url')!s:.60} inputs={len(prov.get('inputs') or [])} raw={p.get('raw_tag')} acc={p.get('accession')}")
        print("\ninflections:", json.dumps(clean["inflections"], indent=1)[:3000])
        return

    states = {}
    # 1. clean: fresh engine output (post-repair shape)
    states["clean"] = {"dataset": clean, "completion": narrative_for(clean)}

    # 2. legacy (current production-like): ten saved calculations without lineage + four missing values
    snapshots = {}
    for concept, period_end in LEGACY_ROWS:
        r = row(concept, period_end)
        if r is None:
            print("legacy row missing", concept, period_end)
            continue
        snapshots[(concept, period_end)] = (r.provenance, r.reconciled, r.source)
        r.provenance = None
        r.reconciled = False
        r.source = "derived"
    hidden = []
    for concept, period_end in MISSING_ROWS:
        r = row(concept, period_end)
        if r is None:
            print("missing row absent already", concept, period_end)
            continue
        hidden.append(r)
        r.is_latest = False
    db.commit()
    legacy = build()
    states["legacy"] = {"dataset": legacy, "completion": narrative_for(legacy)}
    for (concept, period_end), (prov, rec, src) in snapshots.items():
        r = row(concept, period_end)
        r.provenance, r.reconciled, r.source = prov, rec, src
    for r in hidden:
        r.is_latest = True
    db.commit()
    # The restoration must leave the engine's output exactly as the clean build saw it, or the discrepancy
    # state below would be built on contaminated rows. Nothing volatile differs within one run (the
    # source timestamp is the ingest time), so the comparison is exact.
    restored = build()
    differences = _differences(restored, clean)
    if differences:
        raise SystemExit("legacy restoration left the dataset changed: " + "; ".join(differences[:10]))

    # 3. discrepancy: sources disagree on the latest reported revenue; the margins computed from it inherit
    r = row(*CONFLICT_ROW)
    saved = (copy.deepcopy(r.provenance), r.reconciled)
    prov = copy.deepcopy(r.provenance) or {}
    prov.update(validation="needs_review", reasons=["source_conflict"])
    r.provenance, r.reconciled = prov, False
    patched = []
    for concept in ("net_margin", "operating_margin"):
        m = row(concept, CONFLICT_ROW[1])
        if m is None or not m.provenance:
            continue
        mp = copy.deepcopy(m.provenance)
        patched.append((m, copy.deepcopy(m.provenance), m.reconciled))
        mp.update(validation="needs_review", reasons=["source_conflict"])
        for operand in mp.get("inputs", []):
            if operand.get("concept") == "revenue" and isinstance(operand.get("provenance"), dict):
                operand["provenance"].update(validation="needs_review", reasons=["source_conflict"])
        m.provenance, m.reconciled = mp, False
    db.commit()
    discrepancy = build()
    states["discrepancy"] = {"dataset": discrepancy, "completion": narrative_for(discrepancy)}
    r.provenance, r.reconciled = saved
    for m, p, rec in patched:
        m.provenance, m.reconciled = p, rec
    db.commit()

    for name, state in states.items():
        for part, key in PRE_1225_DROPS:
            state[part].pop(key, None)
        (out_dir / f"{name}.json").write_text(json.dumps(state, indent=1, default=str))
        summary = quality_summary(state["dataset"])
        print(f"\n== {name}: values={summary['n_values']} flagged_points={len(summary['flagged_points'])} "
              f"flagged_comparisons={len(summary['flagged_comparisons'])} missing={len(summary['missing'])} "
              f"citations={state['completion']['grounded']} unverified={state['completion']['unverified']} "
              f"mismatched={state['completion']['mismatched']} snapshot={state['dataset']['snapshot_id'][:12]}")
        for item in summary["flagged_points"]:
            print("   point:", item)
        qoq = [c for c in summary["flagged_comparisons"] if c[2] == "qoq"]
        yoy = [c for c in summary["flagged_comparisons"] if c[2] == "yoy"]
        print(f"   comparisons: qoq={len(qoq)} yoy={len(yoy)}")
        print("   missing:", summary["missing"])
    db.close()


if __name__ == "__main__":
    main()
