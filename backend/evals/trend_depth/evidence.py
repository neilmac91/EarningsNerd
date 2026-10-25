"""Assemble one company's evidence pack: every citable value and passage, with IDs, plus its rendering.

    cd backend && python -m evals.trend_depth.evidence REGN SNAP JPM COST NVDA
    cd backend && python -m evals.trend_depth.evidence --out ../tasks/analysis-depth-2026-10/packs-v2 --fulltext-end 2026-10-24 KO

Writes ``<out>/<TICKER>.json.gz`` (default ``tasks/analysis-depth-2026-10/packs/``). The pack is the ONLY input
the proposed generator sees, and the reference the fact-check gate reconciles every printed number against.

This builds pack version 2 (``PACK_VERSION``): version 1 plus the additions of DEEPSEEK-ERRORS.md §2 fixes 3, 4,
8, 9 and 11, every one under a new ID, so each version-1 ID keeps its value. ``packs/`` holds version 1, the
input of the frozen runs (eval-v1, dev-v4), and the builder refuses to overwrite a pack of another version there.
The EDGAR full-text queries are cached under their end date; ``--fulltext-end`` replays a build made on another
day from the cache (the version-1 packs were built on 2026-10-24).

Contents: the production dataset over the UI's "Last 10" annual window (``F#``); extended companyfacts
lines (``X#``); disaggregated revenue and segment profit from each 10-K's own XBRL (``S#``); derived
driver metrics, window reference levels and peer percentiles (``D#``); red-flag candidates with severity
and persistence (``R#``); data checks the analysis must disclose; MD&A and note passages with EDGAR
locations (``P#``); and an EDGAR full-text index of where the top drivers are discussed.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

from evals.trend_depth import bootstrap
from evals.trend_depth import derived, dimensions, passages, sec_inputs, xfacts
from evals.trend_depth.companies import PEERS, by_ticker

PACK_VERSION = "trend-depth-pack-v2"
PACKS = bootstrap.RECORDS / "packs"


def _dataset(company_id: int, start: str, end: str) -> dict[str, Any]:
    from app.models import Company
    from app.services.trend_analysis.dataset import build_dataset

    db = bootstrap.SessionLocal()
    try:
        company = db.get(Company, company_id)
        return build_dataset(db, company, "annual", start, end)
    finally:
        db.close()


def _period_maps(dataset: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, str]]:
    keys = [p["key"] for p in dataset["periods"]]
    end_to_key = {p["period_end"]: p["key"] for p in dataset["periods"]}
    key_to_end = {p["key"]: p["period_end"] for p in dataset["periods"]}
    return keys, end_to_key, key_to_end


def _fuzzy_end_map(ends: list[str], end_to_key: dict[str, str]) -> dict[str, str]:
    """Map arbitrary period ends (52/53-week years) onto the dataset's period keys within a week."""
    out = {}
    for end in ends:
        target = date.fromisoformat(end[:10])
        best = None
        for known, key in end_to_key.items():
            gap = abs((date.fromisoformat(known) - target).days)
            if gap <= 7 and (best is None or gap < best[0]):
                best = (gap, key)
        if best:
            out[end] = best[1]
    return out


def _proxy_sourced(company_id: int) -> dict[str, str]:
    """Fiscal years whose stored annual net income came from a proxy statement (DEF 14A) -> accession.

    The production ingest keeps the latest-filed value per period, and a proxy statement's
    pay-versus-performance table tags net income (rounded) after the 10-K is filed."""
    from app.models import FinancialFact

    db = bootstrap.SessionLocal()
    try:
        rows = (db.query(FinancialFact)
                .filter(FinancialFact.company_id == company_id, FinancialFact.is_latest.is_(True),
                        FinancialFact.fiscal_period == "FY", FinancialFact.form.like("DEF 14A%"))
                .all())
        return {f"FY{row.fiscal_year}": row.accession for row in rows if row.fiscal_year}
    finally:
        db.close()


def _data_checks(reg: derived.Registry, keys: list[str], coverage: list[dict[str, Any]],
                 recasts: list[dict[str, Any]], dataset: dict[str, Any], proxy_years: dict[str, str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    proxied = []
    for key in keys:
        shown, filed = reg.get("net_income", key), reg.get("net_income_10k", key)
        if key in proxy_years and shown and filed and filed.value and shown.value != filed.value:
            proxied.append((key, shown, filed))
    if proxied:
        worst = max(abs(s.value - f.value) / abs(f.value) for _, s, f in proxied)
        checks.append({
            "kind": "proxy_sourced_net_income", "severity": "medium", "period": ",".join(k for k, _, _ in proxied),
            "detail": (f"Net income for {', '.join(k for k, _, _ in proxied)} in the metrics table comes from the proxy statement's "
                       f"pay-versus-performance table (rounded), not the 10-K; the 10-K figures differ by up to {worst * 100:.2f}%. "
                       "Cite the 10-K figure where precision matters."),
            "evidence": [x for _, s, f in proxied for x in (s.id, f.id)],
        })
    # Basis breaks: the metrics table keeps each year's LATEST-filed value, so recast years and
    # never-recast years can sit side by side. Growth across that boundary compares two presentations.
    recast_years = []
    for key in keys:
        shown, reported = reg.get("revenue", key), reg.get("revenue_reported_total", key)
        if shown and reported and reported.value and abs(shown.value - reported.value) / reported.value > 0.02:
            recast_years.append((key, shown, reported))
    if recast_years:
        listing = "; ".join(
            f"{key} {shown.value / 1e6:,.1f}M in the table vs {reported.value / 1e6:,.1f}M in that year's 10-K"
            for key, shown, reported in recast_years
        )
        checks.append({
            "kind": "revenue_basis_break", "severity": "high", "period": ",".join(k for k, _, _ in recast_years),
            "detail": (f"Revenue for some years in the metrics table is a later recast, not the figure first reported: "
                       f"{listing}. Growth and margins that compare a recast year with a year never recast mix two presentations."),
            "evidence": [x for _, shown, reported in recast_years for x in (shown.id, reported.id)],
        })
        recast_keys = {k for k, _, _ in recast_years}
        for i, key in enumerate(keys[1:], start=1):
            prior = keys[i - 1]
            # Only a recast year that follows a never-recast year compares two presentations; a later
            # year's own 10-K restates its prior year onto its basis, so that boundary is consistent.
            if key not in recast_keys or prior in recast_keys:
                continue
            cur_first, prior_first = reg.get("revenue_reported_total", key), reg.get("revenue_reported_total", prior)
            if cur_first and prior_first and prior_first.value:
                reg.add("D", "g:revenue_as_first_reported", "Revenue growth, both years as first reported", key,
                        (cur_first.value / prior_first.value - 1) * 100.0, "pct",
                        formula="first-reported revenue / prior first-reported revenue - 1",
                        inputs=[cur_first.id, prior_first.id])
    material = {"cost_of_revenue", "research_and_development", "selling_general_admin", "operating_expenses",
                "stock_based_compensation", "income_tax", "pretax_income", "share_repurchases", "receivables", "inventory"}
    kept = 0
    for recast in sorted(recasts, key=lambda r: r["period"], reverse=True):
        if recast["concept"] not in material or abs(recast["latest"] - recast["first"]) < 5e6 or kept >= 4:
            continue
        kept += 1
        checks.append({
            "kind": "recast", "severity": "low", "period": recast["period"],
            "detail": (f"{recast['concept'].replace('_', ' ')} for {recast['period']} was later reported as "
                       f"{recast['latest'] / 1e6:,.1f}M against {recast['first'] / 1e6:,.1f}M first reported; the pack uses "
                       f"the first-reported value, which that year's MD&A discusses."),
            "evidence": [recast["id"]],
        })
    latest_rows = [row for row in coverage if row["period"] == keys[-1] and row["kind"] in ("product", "segment")]
    for row in latest_rows:
        if row["ratio"] > 1.05:
            checks.append({
                "kind": "disaggregation_overlap", "severity": "low", "period": row["period"],
                "detail": (f"{row['kind'].title()} revenue members tagged on one axis sum to {row['ratio'] * 100:.0f}% of "
                           f"consolidated revenue in {row['period']}: some members are totals of others, so do not add them up."),
                "evidence": [],
            })
    for note in dataset.get("data_notes") or []:
        if isinstance(note, dict) and note.get("kind") in ("needs_review", "unavailable"):
            checks.append({"kind": f"dataset_{note['kind']}", "severity": "low", "period": note.get("period", ""),
                           "detail": str(note.get("summary") or note.get("detail") or note)[:300], "evidence": []})
    # Keep the list readable: one recast line per concept, the latest first.
    seen: set[tuple[str, str]] = set()
    unique = []
    for check in sorted(checks, key=lambda c: (c["kind"], c.get("period", "")), reverse=True):
        mark = (check["kind"], check["detail"].split(" for ")[0] if check["kind"] == "recast" else check["detail"])
        if mark in seen:
            continue
        seen.add(mark)
        unique.append(check)
    return unique


def _material(series: dict[str, Any], fuzzy: dict[str, str], reg: derived.Registry, floor: float = 0.02) -> bool:
    """Keep a disaggregated member that reached ``floor`` of consolidated revenue in some year."""
    for end, point in series["points"].items():
        key = fuzzy.get(end)
        total = (reg.val("revenue", key) or reg.val("bank_revenue", key) or reg.val("net_interest_income", key)) if key else None
        if total and abs(point["value"]) >= floor * abs(total):
            return True
    return False


def _inflection_years(reg: derived.Registry, keys: list[str]) -> set[str]:
    years = set()
    for i in range(1, len(keys)):
        cur, prior = keys[i], keys[i - 1]
        rev, rev_p = reg.val("revenue", cur) or reg.val("bank_revenue", cur), reg.val("revenue", prior) or reg.val("bank_revenue", prior)
        if rev and rev_p and abs(rev / rev_p - 1) >= 0.15:
            years.add(cur)
        om, om_p = reg.val("operating_margin", cur), reg.val("operating_margin", prior)
        if om is not None and om_p is not None and abs(om - om_p) >= 5:
            years.add(cur)
        ni, ni_p = reg.val("net_income", cur), reg.val("net_income", prior)
        if ni is not None and ni_p is not None and ni_p != 0 and ((ni > 0) != (ni_p > 0) or abs(ni / ni_p - 1) >= 0.2):
            years.add(cur)
    return years


async def _peer_metrics(ticker: str, target_end: str) -> Optional[dict[str, float]]:
    """Latest comparable-year metrics for one peer, through the same ingest and derivation."""
    try:
        identity = await bootstrap.resolve_identity(ticker)
        company_id = await bootstrap.ingest(ticker)
        start, end = bootstrap.latest_annual_window(company_id, years=5)
        dataset = _dataset(company_id, start, end)
        payload = await bootstrap.companyfacts(identity["cik"])
    except Exception:  # noqa: BLE001 - a peer that cannot be built is reported as missing
        return None
    keys, end_to_key, _ = _period_maps(dataset)
    ends = [p["period_end"] for p in dataset["periods"]]
    target = date.fromisoformat(target_end)
    chosen = min(ends, key=lambda e: abs((date.fromisoformat(e) - target).days))
    if abs((date.fromisoformat(chosen) - target).days) > 270:
        return None
    reg = derived.Registry()
    derived.register_dataset(reg, dataset)
    derived.register_extended(reg, xfacts.extended_series(payload, ends), end_to_key, derived.X_LABELS)
    from app.services.facts.concepts import _is_financial_sic
    profile = "bank" if _is_financial_sic(identity.get("sic")) and reg.ref("net_interest_income", end_to_key[chosen]) else "operating"
    derived.build_derived(reg, keys, profile, [])
    period = end_to_key[chosen]
    out = {"period": period}
    for key in PEER_METRICS:
        value = reg.val(key, period)
        if value is not None:
            out[key] = value
    return out


PEER_METRICS: dict[str, tuple[str, str]] = {
    "operating_margin": ("Operating margin", "pct"),
    "net_margin": ("Net margin", "pct"),
    "cs:free_cash_flow": ("Free cash flow margin", "pct"),
    "cs:research_and_development": ("R&D % of revenue", "pct"),
    "net_cash_to_revenue": ("Net cash % of revenue", "pct"),
    "fcf_to_ni": ("Free cash flow / net income", "x"),
    "efficiency_ratio": ("Efficiency ratio", "pct"),
    "roe": ("Return on average equity", "pct"),
    "provision_to_revenue": ("Credit-loss provision % of revenue", "pct"),
}


async def _register_peers(reg: derived.Registry, ticker: str, peer_group: str, latest_key: str, latest_end: str) -> dict[str, Any]:
    tickers = [t for t in PEERS.get(peer_group, ()) if t != ticker]
    results = {}
    for peer in tickers:
        metrics = await _peer_metrics(peer, latest_end)
        if metrics:
            results[peer] = metrics
    summary = {"group": peer_group, "peers": sorted(results), "missing": sorted(set(tickers) - set(results)), "metrics": {}}
    for key, (label, unit) in PEER_METRICS.items():
        own = reg.get(key, latest_key)
        values = [m[key] for m in results.values() if key in m]
        if own is None or len(values) < 3:
            continue
        rank = derived.percentile_rank(own.value, values)
        ordered = sorted(values)
        mid = ordered[len(ordered) // 2] if len(ordered) % 2 else (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
        peer_note = "; ".join(f"{t} {results[t][key]:.1f}" for t in sorted(results) if key in results[t])
        rank_id = reg.add("D", f"peer_pctile:{key}", f"{label}: percentile vs {peer_group} peers (n={len(values)})", latest_key,
                          rank, "pctile", formula="share of peers below (ties half)", inputs=[own.id], source="peer", note=peer_note)
        median_id = reg.add("D", f"peer_median:{key}", f"{label}: {peer_group} peer median (n={len(values)})", latest_key,
                            mid, unit, formula="median of peer values", source="peer", note=peer_note)
        summary["metrics"][key] = {"percentile_id": rank_id, "median_id": median_id, "n": len(values)}
    return summary


async def build_pack(ticker: str, *, with_peers: bool = True, fulltext_end: Optional[str] = None) -> dict[str, Any]:
    company = by_ticker(ticker)
    fulltext_end = fulltext_end or date.today().isoformat()
    identity = await bootstrap.resolve_identity(ticker)
    company_id = await bootstrap.ingest(ticker)
    start, end = bootstrap.latest_annual_window(company_id)
    dataset = _dataset(company_id, start, end)
    keys, end_to_key, key_to_end = _period_maps(dataset)
    payload = await bootstrap.companyfacts(identity["cik"])

    reg = derived.Registry()
    derived.register_dataset(reg, dataset)
    xseries = xfacts.extended_series(payload, [p["period_end"] for p in dataset["periods"]])
    recasts = derived.register_extended(reg, xseries, end_to_key, derived.X_LABELS)

    # 10-K filings in the window and their XBRL disaggregation.
    reports = await sec_inputs.annual_reports(identity["cik"], payload)
    in_window = [(key, sec_inputs.find_filing(reports, key_to_end[key])) for key in keys]
    in_window = [(key, filing) for key, filing in in_window if filing]
    dim_filings = in_window[::-1][::3]  # latest, then every third back
    dims = []
    for _key, filing in dim_filings:
        rows = await sec_inputs.dimensional_facts(identity["cik"], filing["accession"])
        dims.append((filing, rows))
    seg_series = dimensions.disaggregation(dims)
    all_ends = sorted({end for s in seg_series for end in s["points"]})
    fuzzy = _fuzzy_end_map(all_ends, end_to_key)
    for item in seg_series:
        item["points"] = {e: p for e, p in item["points"].items() if e in fuzzy}
    seg_series = [s for s in seg_series if s["points"] and _material(s, fuzzy, reg)]
    segments = derived.register_segments(reg, seg_series, fuzzy)
    revenue_totals = {e: reg.val("revenue", fuzzy[e]) for e in all_ends if e in fuzzy and reg.val("revenue", fuzzy[e])}
    coverage = [{**row, "period": fuzzy.get(row["period_end"], row["period_end"])}
                for row in dimensions.coverage(seg_series, revenue_totals)]

    derived.build_derived(reg, keys, company.profile, segments)
    data_checks = _data_checks(reg, keys, coverage, recasts, dataset, _proxy_sourced(company_id))
    flags = derived.red_flags(reg, keys, company.profile, segments, data_checks)
    inflections = sorted(_inflection_years(reg, keys))

    # Passages: every 10-K in the window, ranked toward drivers and inflection years.
    driver_names = list(dict.fromkeys(s["label"].split(" — ")[0] for s in sorted(
        (s for s in segments if s["measure"] == "revenue" and not s.get("subtotal") and not s.get("generic")),
        key=lambda s: -max((reg.val(s["key"], k) or 0) for k in keys))))[:10]
    pool: list[dict[str, Any]] = []
    for key, filing in in_window:
        parsed = await sec_inputs.document_text(filing, identity["cik"])
        pool.extend(passages.candidates(filing, parsed, key, driver_names))
    chosen = passages.select(pool, keys[-1], set(inflections))

    fulltext = []
    for name in driver_names[:5]:
        hits = await sec_inputs.fulltext_hits(name, identity["cik"], f"{keys[0][2:]}-01-01", fulltext_end)
        fulltext.append({"term": name, "filings": [{"accession": h["accession"], "form": h["form"], "filed": h["filed"]} for h in hits]})

    peers = await _register_peers(reg, ticker, company.peer_group, keys[-1], key_to_end[keys[-1]]) if with_peers else {}

    # Version 2: new values, the debt-break and implied-rate checks with their red flags, and the IDs the render
    # withholds. All of it after the last version-1 ID (peers included), so no version-1 ID moves.
    derived.version_two_values(reg, keys, company.profile)
    broken = derived.debt_breaks(reg, keys)
    added_checks = derived.debt_checks(reg, keys, company.profile, broken)
    data_checks = data_checks + added_checks
    derived.append_flags(flags, added_checks)
    withheld = derived.withheld(reg, broken, flags)

    pack = {
        "version": PACK_VERSION,
        "ticker": ticker,
        "company_name": dataset["company_name"],
        "cik": identity["cik"],
        "sic": identity.get("sic"),
        "industry": identity.get("industry"),
        "sector": company.sector,
        "profile": company.profile,
        "split": company.split,
        "window": dataset["period_key"],
        "periods": dataset["periods"],
        "snapshot_id": dataset["snapshot_id"],
        "data_as_of": dataset.get("data_as_of"),
        "values": {vid: value.as_dict() for vid, value in reg.values.items()},
        "series_keys": {f"{k}|{p}": vid for (k, p), vid in reg.by_key.items()},
        "segments": [{"key": s["key"], "kind": s["kind"], "measure": s["measure"], "label": s["label"],
                      "axis": s["axis"], "member": s["member"], "subtotal": s["subtotal"], "generic": s["generic"],
                      "ids": s["ids"]} for s in segments],
        "coverage": coverage,
        "data_checks": data_checks,
        "red_flags": flags,
        "withheld": withheld,
        "inflection_years": inflections,
        "filings": [{"period": key, **filing} for key, filing in in_window],
        "passages": [{k: v for k, v in p.items() if k != "score"} | {"score": round(p["score"], 2)} for p in chosen],
        "fulltext_index": fulltext,
        "fulltext_end": fulltext_end,
        "peers": peers,
    }
    return pack


def _version_at(path: Path) -> Optional[str]:
    if path.exists():
        return json.loads(gzip.decompress(path.read_bytes())).get("version")
    plain = path.with_suffix("")  # an uncompressed pack.json beside it
    return json.loads(plain.read_text()).get("version") if plain.exists() else None


async def _main(tickers: list[str], out: Path = PACKS, fulltext_end: Optional[str] = None, replace: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        path = out / f"{ticker}.json.gz"  # committed compressed; mtime 0 keeps the bytes reproducible
        found = _version_at(path)
        if found not in (None, PACK_VERSION) and not replace:
            # packs/ holds version 1, the input the frozen runs read; a rebuild there would change their evidence.
            raise SystemExit(f"{path} is {found}, not {PACK_VERSION}: write elsewhere with --out (packs-v2/ holds "
                             "version 2), or pass --replace to overwrite it")
        pack = await build_pack(ticker, fulltext_end=fulltext_end)
        path.write_bytes(gzip.compress(json.dumps(pack, separators=(",", ":"), sort_keys=True).encode(), mtime=0))
        (out / f"{ticker}.json").unlink(missing_ok=True)
        n = pack["values"]
        print(f"{ticker}: {len(n)} values, {len(pack['segments'])} segment series, {len(pack['passages'])} passages, "
              f"{len(pack['red_flags'])} flags, {len(pack['data_checks'])} checks, {len(pack['withheld'])} withheld "
              f"-> {path} ({path.stat().st_size // 1024} KB)")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Build evidence packs (version 2).")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--out", type=Path, default=PACKS, help=f"output directory (default {PACKS})")
    parser.add_argument("--fulltext-end", default=None,
                        help="end date of the EDGAR full-text queries, YYYY-MM-DD (default today); the cache is keyed by it")
    parser.add_argument("--replace", action="store_true", help="overwrite a pack of another version")
    args = parser.parse_args(argv)
    asyncio.run(_main(args.tickers, args.out, args.fulltext_end, args.replace))


if __name__ == "__main__":
    main()
