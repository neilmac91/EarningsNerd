"""The quarterly repair's proxy step (E211): proxy-statement values stored before #1622.

Before #1622 (``facts/currency.is_proxy_form``) a proxy or information statement's pay-versus-
performance figure could win a companyfacts period, and the backfill's cross-check could take it as
the authority over a filing's parse, replacing or confirming it. ``quarterly_fact_repair.
repair_company`` runs this step after its calendar relabels and before its same-identity loop. The
four passes, in order, follow ``ops/detection/proxy_form_winners.sql``'s sets:

1. Set 4. A filing row the old cross-check replaced with a proxy's figure is restored to its recorded
   ``original_value`` and passed through today's cross-check, as the backfill would store it now. A row
   that already holds the 10-K's figure is kept; one with no recorded original, or whose original the
   10-K contradicts, refuses the company.
2. Set 5. A filing row the old cross-check confirmed against a proxy's figure keeps its value, and its
   check is recorded again against today's authority; where the 10-K contradicts it, the company is
   refused, and where the figure it was confirmed against is the 10-K's, it is kept.
   The filing calculations over each row sets 4 and 5 changed are then re-annotated, once per scope.
3. Set 2. Each current proxy-form row is retired with the quarantine provenance, and the fresh 10-K
   winner at its key is inserted, or the stored row at the winner's identity promoted.
4. Set 3. A current calculation built on a proxy figure is left to the loop when the payload has a
   candidate at its identity; otherwise it is retired and the fresh fact at its key admitted.

Pure planning: no session, no network. It reads the payload the repair fetched and normalized, and
writes only into the repair's ``updates`` and its own inserts, so the repair's apply, journal
(``proxy-repair-v1``) and audited rollback carry every change. A case it cannot settle on positive
evidence refuses the whole company before any write, every reason in one error. The report names, by
fact id and with the step's verdict, each row the detection file's sets 4 and 5 will still list
(``detection_listed``), so the apply's done criterion is a comparison. Temporary: removed once the E211
cohort closes (``docs/quarterly-data-repair.md``, "Proxy-statement values (E211)").
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from app.services import facts_service
from app.services import quarterly_fact_repair as qfr  # repair_company imports this module at call time
from app.services.fact_provenance import METRIC_FORMULAS, METRIC_INPUTS, PROVENANCE_VERSION
from app.services.facts.concepts import CROSS_CHECK_TOLERANCE, HEADLINE_GAAP_TAGS, _INSTANT_HEADLINE, _parse_date
from app.services.facts.currency import is_proxy_form
from app.services.facts.lineage import _is_calculated, _scope, annotate_filing_calculations, local_reconciliation

PROXY_REPAIR_VERSION = "proxy-repair-v1"  # financial_fact_revision.calculation_version of the step's rows
RETIRED = "proxy_statement_value"  # a proxy-form row's quarantine reason
DEPENDENT = "proxy_statement_operand"  # a calculation built on one, with no fresh candidate
SAME = 1e-6  # proxy_form_winners.sql's equality between a value and a witness (relative)
FALLBACK_ACCESSION = "companyfacts"  # facts/quarterly.reported_fact names an item without one so
COUNTERS = (
    "retired", "inserted", "promoted", "corrected", "retired_without_winner",
    "dependents_recomputed", "dependents_retired", "filing_rows_restored",
    "filing_calculations_reannotated", "filing_rows_kept", "filing_rows_reconfirmed",
)
OTHER_KINDS = ("made_unavailable", "is_latest", "value", "label", "provenance_only")
_KEY = ("concept", "period_end", "fiscal_period", "unit")
_LABELS = ("fiscal_year", "fiscal_period", "period_start", "raw_tag", "form")
_FACT_FIELDS = (
    "company_id", "filing_id", "concept", "raw_tag", "unit", "period_start", "period_end", "fiscal_year",
    "fiscal_period", "form", "accession", "source", "reconciled", "provenance",
)

State = dict[str, Any]


class ProxyRepairRefused(ValueError):
    """A case the step cannot settle on positive evidence: the company is refused before any write."""


def _provenance(state: State) -> dict[str, Any]:
    stored = state.get("provenance")
    return stored if isinstance(stored, dict) else {}


def _authoritative_check(state: State) -> dict[str, Any]:
    """The cross-check's record (``checks.authoritative``, since #1191), or ``{}``."""
    checks = _provenance(state).get("checks")
    check = checks.get("authoritative") if isinstance(checks, dict) else None
    return check if isinstance(check, dict) else {}


def _number(value: Any) -> float | None:
    """A recorded JSON number: an int or a float, never a bool, finite (the SQL's json_typeof 'number')."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _same(a: float, b: float) -> bool:
    return abs(a - b) <= SAME * max(abs(a), abs(b))


def _agrees(value: float, reference: float) -> bool:
    """Within ``cross_check_facts``' own tolerance of ``reference`` (facts/reconcile.py)."""
    return abs(value - reference) / (abs(reference) or 1.0) <= CROSS_CHECK_TOLERANCE


def _scale_up(value: float, original: float | None) -> bool:
    """``value`` is 1,000 or 1,000,000 times ``original`` (within 1%, same sign): the authority multiplying
    up a figure parsed in millions and read as units, the replacement set 4 also leaves out."""
    if not original or not value or (value > 0) != (original > 0):
        return False
    ratio = value / original
    return abs(ratio / 1_000 - 1) <= 0.01 or abs(ratio / 1_000_000 - 1) <= 0.01


def _scale_down(value: float, original: float | None) -> bool:
    """``value`` is 1/1,000 or 1/1,000,000 of ``original`` (within 1%, same sign): set 4's "scale" listing."""
    if not original or not value or (value > 0) != (original > 0):
        return False
    ratio = value / original
    return abs(ratio * 1_000 - 1) <= 0.01 or abs(ratio * 1_000_000 - 1) <= 0.01


def _key(state: State) -> tuple:
    return tuple(state[name] for name in _KEY)


def _quotes(state: State, accessions: set[str]) -> bool:
    """Set 3's test: the provenance text quotes a proxy row's accession, at any depth."""
    if not accessions:
        return False
    text = json.dumps(state.get("provenance") or {})
    return any(f'"{accession}"' in text for accession in accessions)


def _is_report_row(state: State) -> bool:
    """Set 4's report row: a form set and no proxy form, and not a filing row the cross-check replaced
    (one with a filing owner and source companyfacts holds the authority's figure, not its report's)."""
    form = state["form"]
    return (isinstance(form, str) and form.strip(" ") != "" and not is_proxy_form(form)
            and not (state["filing_id"] is not None and state["source"] == "companyfacts"))


def _reported(state: State) -> bool:
    """A figure a report states, not a calculation."""
    return state["source"] != "derived" and not _is_calculated(state)


def _disagreements(stored: State, target: State) -> list[str]:
    """The agreement test for a filing row at the winner's identity, by failing clause. The value is
    judged as the cross-check judges a parse against companyfacts' figure for the same filing. A
    missing start on the filing row agrees (founder, 2026-10-26): rows the per-filing writer stored
    before #831 keep a NULL start, and the identity already names the filing and period."""
    failed = []
    if not _agrees(float(stored["value"]), float(target["value"])):
        failed.append("value")
    if stored["period_start"] is not None and stored["period_start"] != target["period_start"]:
        failed.append("start")
    if stored["fiscal_year"] != target["fiscal_year"]:
        failed.append("fiscal year")
    return failed


def proxy_accessions(states: Iterable[State]) -> set[str]:
    """The accessions of the stored proxy-form rows, current or not. Never the fallback accession: every
    cross-checked filing row quotes it as its check's method (facts/lineage.py)."""
    return {state["accession"] for state in states if is_proxy_form(state["form"])
            and isinstance(state["accession"], str) and state["accession"] not in ("", FALLBACK_ACCESSION)}


def proxy_items(payload: Any) -> dict[tuple[str, str], list[float]]:
    """``(headline concept, period end) -> [value, ...]``, each proxy figure companyfacts lists, read by
    ``extract_authoritative_values``' own item rules (facts/reconcile.py): its tags, the USD list, a
    numeric non-bool ``val``, a parseable end and, for a duration, a span within 30 days of a year."""
    out: dict[tuple[str, str], list[float]] = {}
    root = payload.get("facts") if isinstance(payload, dict) else None
    usgaap = root.get("us-gaap") if isinstance(root, dict) else None
    if not isinstance(usgaap, dict):
        return out
    for concept, tags in HEADLINE_GAAP_TAGS.items():
        for tag in tags:
            node = usgaap.get(tag)
            units = node.get("units") if isinstance(node, dict) else None
            items = units.get("USD") if isinstance(units, dict) else None
            for item in items if isinstance(items, list) else ():
                if not isinstance(item, dict) or not is_proxy_form(item.get("form")):
                    continue
                value = item.get("val")
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                end = _parse_date(item.get("end"))
                if end is None:
                    continue
                if concept not in _INSTANT_HEADLINE:
                    start = _parse_date(item.get("start"))
                    if start is None or abs((end - start).days - 365) > 30:
                        continue
                out.setdefault((concept, end.isoformat()), []).append(float(value))
    return out


def residual(states: list[State], accessions: set[str], keys: dict[tuple, int], *,
             twins_at: Iterable[tuple]) -> dict[str, Any]:
    """What detection sets 2 and 3 would still read, and each settled key whose current rows differ from
    the plan's: ``[*key, held, twin, expected]``. ``twin`` counts, at the quarter keys of ``twins_at``, a
    current row with no fiscal period at the key's period, which no upsert will demote there (the D1
    rule, facts/upsert.py): one is too many beside the key's own row."""
    twin_keys = set(twins_at)
    current: Counter = Counter()
    unlabelled: Counter = Counter()
    for state in states:
        if state["is_latest"]:
            current[_key(state)] += 1
            if state["fiscal_period"] is None:
                unlabelled[(state["concept"], state["period_end"], state["unit"])] += 1
    unsettled = []
    for key, expected in keys.items():
        held = current[key]
        twin = unlabelled[(key[0], key[1], key[3])] if key in twin_keys and key[2] in qfr.QUARTERS else 0
        if held != expected or held + twin > 1:
            unsettled.append([*key, held, twin, expected])
    return {
        "current_proxy_rows": sum(1 for s in states if s["is_latest"] and is_proxy_form(s["form"])),
        "current_rows_built_on_proxy": sum(1 for s in states if s["is_latest"] and not is_proxy_form(s["form"])
                                           and _quotes(s, accessions)),
        "keys_not_settled": unsettled,
    }


def detection_listed(rows: list[tuple[int | None, State]], verdicts: dict[int, str]) -> list[dict[str, Any]]:
    """Each filing row detection sets 4 and 5 (``ops/detection/proxy_form_winners.sql``) list over ``rows``,
    ``(fact id or None, state)``, by the file's own rules: only a stored proxy-form row witnesses, and set 4
    also lists a value 1/1,000 or 1/1,000,000 of its original that no proxy row holds. Each carries the
    plan's verdict on the row. After an apply, the file reads exactly these fact ids for the company."""
    near: dict[tuple, list[tuple[int | None, State]]] = {}
    for row_id, state in rows:
        near.setdefault((state["concept"], state["period_end"]), []).append((row_id, state))
    listed = []
    for row_id, state in rows:
        if row_id is None or state["filing_id"] is None:
            continue
        period = near[(state["concept"], state["period_end"])]
        witnesses = [float(other["value"]) for _other_id, other in period if is_proxy_form(other["form"])]
        check = _authoritative_check(state)
        if state["source"] == "companyfacts":  # set 4: why = proxy row, or why = scale
            number, original = float(state["value"]), _number(check.get("original_value"))
            witnessed = any(_same(number, witness) for witness in witnesses)
            shown = not _scale_up(number, original) if witnessed else _scale_down(number, original)
            in_set = 4 if shown else None
        else:  # set 5: a confirmed check whose authoritative_value a proxy row holds
            number = _number(check.get("authoritative_value"))
            confirmed = check.get("outcome") == "confirmed" and number is not None
            in_set = 5 if confirmed and any(_same(number, witness) for witness in witnesses) else None
        if in_set is None or any(other_id != row_id and _is_report_row(other) and _same(float(other["value"]), number)
                                 for other_id, other in period):
            continue
        listed.append({"fact_id": row_id, "set": in_set, "verdict": verdicts.get(row_id, "unclassified")})
    return listed


def other_kinds(before: dict[int, State], updates: dict[int, State], tagged: set[int]) -> dict[str, int]:
    """Each update the step did not plan, by the first kind it is: made unavailable (the figure leaves
    the public pages), the current-row flag, the value, a label, else provenance only."""
    out = dict.fromkeys(OTHER_KINDS, 0)
    for row_id, after in updates.items():
        if row_id in tagged:
            continue
        old = before[row_id]
        if (_provenance(after).get("validation") == "unavailable"
                and _provenance(old).get("validation") != "unavailable"):
            out["made_unavailable"] += 1
        elif after["is_latest"] != old["is_latest"]:
            out["is_latest"] += 1
        elif after["value"] != old["value"]:
            out["value"] += 1
        elif any(after[name] != old[name] for name in _LABELS):
            out["label"] += 1
        else:
            out["provenance_only"] += 1
    return out


def totals(blocks: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """A batch's ``proxy_totals``: each counter and each other-correction entry, summed over the
    companies' ``proxy`` blocks."""
    out: dict[str, Any] = {**dict.fromkeys(COUNTERS, 0), "other_planned_updates": 0,
                           "other_planned_inserts": 0, "other_updates_by_kind": dict.fromkeys(OTHER_KINDS, 0),
                           "other_inserts_by_concept": {}}
    for block in blocks:
        for name in (*COUNTERS, "other_planned_updates", "other_planned_inserts"):
            out[name] += block[name]
        for name in ("other_updates_by_kind", "other_inserts_by_concept"):
            for entry, count in block[name].items():
                out[name][entry] = out[name].get(entry, 0) + count
    out["other_inserts_by_concept"] = dict(sorted(out["other_inserts_by_concept"].items()))
    return out


@dataclass
class _Admission:
    action: str  # inserted, promoted, corrected, retired_without_winner or refused
    evidence: dict[str, Any] | None = None
    winner: State | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProxyPlan:
    """What ``repair_company`` consumes: the step's inserts, its report, and its postcondition."""

    inserts: list[dict[str, Any]]
    tagged: set[int]  # rows the step wrote or left to the loop, and rows that are or quote a proxy
    accessions: set[str]
    keys: dict[tuple, int]  # each key the step settled -> the current rows it expects there (1, or 0)
    counts: dict[str, int]
    rows: list[dict[str, Any]]
    stored_keys: set[tuple] = field(default_factory=set)  # settled in place: no upsert decides them
    verdicts: dict[int, str] = field(default_factory=dict)  # the step's verdict on each set 4 and 5 candidate
    own: set[tuple] = field(init=False)  # the identities of the step's inserts

    def __post_init__(self) -> None:
        self.own = {qfr._identity(qfr._candidate_state(fact)) for fact in self.inserts}

    def summary(self, before: dict[int, State], updates: dict[int, State], inserts: list[dict]) -> dict[str, Any]:
        """The company's ``proxy`` block; ``other_*`` describe the corrections one approval also applies."""
        others = [fact for fact in inserts if qfr._identity(qfr._candidate_state(fact)) not in self.own]
        return {
            "version": PROXY_REPAIR_VERSION, **self.counts,
            "other_planned_updates": sum(1 for row_id in updates if row_id not in self.tagged),
            "other_planned_inserts": len(others),
            "other_updates_by_kind": other_kinds(before, updates, self.tagged),
            "other_inserts_by_concept": dict(sorted(Counter(
                f"{fact['concept']} {fact['fiscal_period']}" for fact in others).items())),
            "rows": self.rows,
        }

    def residual(self, states: list[State], *, twins_at: Iterable[tuple]) -> dict[str, Any]:
        return residual(states, self.accessions, self.keys, twins_at=twins_at)

    def detection_listed(self, rows: list[tuple[int | None, State]]) -> list[dict[str, Any]]:
        return detection_listed(rows, self.verdicts)

    def journal_version(self, row_id: int, after: State, *, inserted: bool) -> str:
        """``proxy-repair-v1`` for the step's rows, so one query lists the proxy repair alone."""
        if row_id in self.tagged or (inserted and qfr._identity(after) in self.own):
            return PROXY_REPAIR_VERSION
        return qfr.REPAIR_VERSION


class _Planner:
    """One company's plan over the repair's snapshots; ``state`` is the projected state."""

    def __init__(self, before: dict[int, State], updates: dict[int, State], facts: list[dict],
                 normalized: dict[tuple, dict], payload: dict[str, Any]) -> None:
        self.before, self.updates, self.normalized = before, updates, normalized
        self.identities = {qfr._identity(state): row_id for row_id, state in before.items()}
        self.by_key: dict[tuple, list[int]] = {}
        self.by_period: dict[tuple, list[int]] = {}
        self.by_scope: dict[tuple, list[int]] = {}
        for row_id in before:  # the step never writes these fields, so the indexes hold
            state = self.state(row_id)
            self.by_key.setdefault(_key(state), []).append(row_id)
            self.by_period.setdefault((state["concept"], state["period_end"]), []).append(row_id)
            self.by_scope.setdefault(_scope(state), []).append(row_id)
        self.fresh: dict[tuple, list[dict]] = {}
        for fact in facts:
            self.fresh.setdefault(_key(qfr._candidate_state(fact)), []).append(fact)
        self.authority = facts_service.extract_authoritative_values(payload)
        self.witnesses = proxy_items(payload)
        for state in before.values():
            if is_proxy_form(state["form"]):
                self.witnesses.setdefault((state["concept"], state["period_end"]), []).append(float(state["value"]))
        self.accessions = proxy_accessions(before.values())
        self.inserts: dict[tuple, dict] = {}
        self.keys: dict[tuple, int] = {}
        self.stored_keys: set[tuple] = set()
        self.verdicts: dict[int, str] = {}
        self.rechecked: dict[tuple, set[str]] = {}  # scope -> the concepts sets 4 and 5 rewrote there
        self.touched: set[int] = set()
        self.counts = dict.fromkeys(COUNTERS, 0)
        self.rows: list[dict[str, Any]] = []
        self.refusals: list[str] = []

    def state(self, row_id: int) -> State:
        return self.updates.get(row_id, self.before[row_id])

    def write(self, row_id: int, state: State) -> None:
        if state != self.state(row_id):
            self.updates[row_id] = state
            self.touched.add(row_id)

    def refuse(self, row_id: int, why: str) -> None:
        state = self.state(row_id)
        self.refusals.append(f"{state['concept']} {state['fiscal_period']} {state['period_end']} (fact {row_id}): {why}")

    def _witnessed(self, state: State, value: float) -> bool:
        """A proxy figure at the concept and period end holds ``value``: a payload proxy item, or a stored
        proxy-form row, current or not."""
        return any(_same(value, witness) for witness in self.witnesses.get((state["concept"], state["period_end"]), ()))

    def _report_backed(self, row_id: int, state: State, value: float) -> bool:
        """Set 4's exclusion: another stored report row at the concept and period end, any unit, holds it."""
        return any(other_id != row_id and _is_report_row(self.before[other_id])
                   and _same(float(self.before[other_id]["value"]), value)
                   for other_id in self.by_period[(state["concept"], state["period_end"])])

    def _authority(self, state: State) -> float | None:
        """Today's authority (``extract_authoritative_values``, which skips a proxy's item)."""
        return self.authority.get((state["concept"], date.fromisoformat(state["period_end"])))

    def _row(self, row_id: int, action: str, before: State, after: State | None, **extra: Any) -> dict[str, Any]:
        old = float(before["value"])
        new = None if after is None else float(after["value"])
        gap = None if new is None else (0.0 if old == new else abs(old - new) / max(abs(old), abs(new)))
        return {
            "fact_id": row_id, "action": action,
            **{name: before[name] for name in ("concept", "fiscal_year", "fiscal_period", "period_end",
                                               "accession", "form", "value")},
            "winner_accession": None if after is None else after["accession"],
            "winner_value": None if after is None else after["value"],
            "gap": None if gap is None else round(gap, 6), **extra,
        }

    def _left(self, row_id: int, state: State, value: float) -> bool:
        """Sets 4 and 5's first two cases, with the verdict: no proxy figure holds ``value``, or a report does."""
        verdict = ("no_proxy_figure" if not self._witnessed(state, value)
                   else "report_backed" if self._report_backed(row_id, state, value) else None)
        if verdict is not None:
            self.verdicts[row_id] = verdict
        return verdict is not None

    def _rewrote(self, row_id: int, state: State, verdict: str) -> None:
        self.write(row_id, state)
        self.verdicts[row_id] = verdict
        self.rechecked.setdefault(_scope(state), set()).add(state["concept"])

    def restore_filing_rows(self) -> None:
        """Set 4: a filing row the old cross-check replaced with a proxy's figure. Only that check writes
        source companyfacts on a filing's row. The first case that applies decides."""
        for row_id, state in self.before.items():
            if state["filing_id"] is None or state["source"] != "companyfacts":
                continue
            value = float(state["value"])
            if self._left(row_id, state, value):
                continue
            check = _authoritative_check(state)
            original = _number(check.get("original_value"))
            if _scale_up(value, original):
                self.verdicts[row_id] = "scale_up"  # the authority scaled up a parse in units: the check's job
                continue
            authority = self._authority(state)
            if authority is not None and _same(value, authority):
                self.verdicts[row_id] = "kept_agrees_with_authority"
                self.counts["filing_rows_kept"] += 1
                self.rows.append(self._row(row_id, "kept_agrees_with_authority", state, None,
                                           authority=authority, original=original))
            elif original is None:
                self.refuse(row_id, "a filing row holds a proxy's figure, not the 10-K's, and records no original value")
            elif authority is not None and not _agrees(original, authority):
                self.refuse(row_id, "the 10-K's figure disagrees with the recorded original value by more "
                                    "than 1%, and the filing row holds neither")
            else:
                restored = self._rechecked(state, original, qfr._json_value(Decimal(str(original))),
                                           authority, check, "edgar_xbrl")
                self._rewrote(row_id, restored, "restored")
                self.counts["filing_rows_restored"] += 1
                self.rows.append(self._row(row_id, "restored", state, restored, authority=authority, original=original))

    def reconfirm_filing_rows(self) -> None:
        """Set 5: a filing row the old cross-check confirmed against a proxy's figure keeps its value."""
        for row_id, state in self.before.items():
            if state["filing_id"] is None or state["source"] == "companyfacts":
                continue
            check = _authoritative_check(state)
            witness = _number(check.get("authoritative_value"))
            if check.get("outcome") != "confirmed" or witness is None or self._left(row_id, state, witness):
                continue
            authority = self._authority(state)
            if authority is not None and _same(witness, authority):  # a proxy quoting the 10-K exactly
                self.verdicts[row_id] = "kept_confirmed_by_10k"
                self.counts["filing_rows_kept"] += 1
                self.rows.append(self._row(row_id, "kept_confirmed_by_10k", state, None, authority=authority,
                                           confirmed_against=witness))
                continue
            if authority is not None and not _agrees(float(state["value"]), authority):
                self.refuse(row_id, "the old cross-check confirmed this filing row against a proxy's figure, "
                                    "and the 10-K's figure disagrees with it by more than 1%")
                continue
            confirmed = self._rechecked(state, float(state["value"]), state["value"], authority, check,
                                        state["source"])
            self._rewrote(row_id, confirmed, "reconfirmed")
            self.counts["filing_rows_reconfirmed"] += 1
            self.rows.append(self._row(row_id, "reconfirmed", state, confirmed, authority=authority,
                                       confirmed_against=witness))

    def _rechecked(self, state: State, parsed: float, stored: str, authority: float | None,
                   check: dict[str, Any], source: str) -> State:
        """``state`` as today's backfill stores its filing's figure ``parsed``: the local gate's verdict
        that the old check kept (``resolved_reasons``), then today's cross-check against ``authority``.
        Only ``value`` (as ``stored``), ``source``, ``reconciled`` and ``provenance`` change."""
        provenance = _provenance(state)
        checks = provenance.get("checks") if isinstance(provenance.get("checks"), dict) else {}
        fact = {
            **{name: state[name] for name in _FACT_FIELDS if name not in ("provenance", "reconciled")},
            "period_end": date.fromisoformat(state["period_end"]), "value": parsed, "source": source,
            "provenance": {"filed_at": provenance.get("filed_at"),
                           "checks": {name: item for name, item in checks.items() if name != "authoritative"}},
        }
        fact = local_reconciliation(fact, list(check.get("resolved_reasons") or []))
        if authority is not None:
            fact = facts_service.cross_check_facts([fact], {(fact["concept"], fact["period_end"]): authority})[0]
        return {**state, "value": stored, "source": fact["source"], "reconciled": fact["reconciled"],
                "provenance": fact["provenance"]}

    def reannotate(self) -> None:
        """The filing calculations over the rows sets 4 and 5 rewrote, recomputed once per scope after both
        passes, so each operand's record in them is its own record now, as the lineage backfill recomputes
        them (filing_lineage_repair.py): provenance and ``reconciled`` only, on a filing-owned version-1
        calculation of a rewritten concept whose operands the calculator finds."""
        for scope, concepts in self.rechecked.items():
            self._reannotate(self.by_scope[scope], concepts)

    def _reannotate(self, scope: list[int], concepts: set[str]) -> None:
        members = [(row_id, self.state(row_id)) for row_id in scope]
        facts = [{**{name: state[name] for name in _FACT_FIELDS}, "value": float(state["value"])}
                 for _row_id, state in members]
        for (row_id, state), result in zip(members, annotate_filing_calculations(facts)):
            if (state["filing_id"] is None or state["concept"] not in METRIC_FORMULAS
                    or not concepts.intersection(METRIC_INPUTS[state["concept"]])
                    or _provenance(state).get("version") != PROVENANCE_VERSION
                    or not result["provenance"]["inputs"]):
                continue
            annotated = {**state, "provenance": result["provenance"], "reconciled": result["reconciled"]}
            if annotated != state:
                self.write(row_id, annotated)
                self.counts["filing_calculations_reannotated"] += 1
                self.rows.append(self._row(row_id, "reannotated", state, annotated))

    def retire_proxy_rows(self) -> None:
        """Set 2: each current proxy-form row is retired; the fresh winner at its key is admitted."""
        targets: dict[tuple, list[int]] = {}
        for row_id in self.before:
            state = self.state(row_id)
            if not (state["is_latest"] and is_proxy_form(state["form"])):
                continue
            if state["filing_id"] is not None:
                self.refuse(row_id, "a row with a filing owner carries a proxy form, which no writer stores")
                continue
            targets.setdefault(_key(state), []).append(row_id)
        for key, row_ids in targets.items():
            outcome = self.admit(key, row_ids[0], set(row_ids))
            if outcome.action in ("inserted", "promoted", "corrected", "retired_without_winner"):
                self.counts[outcome.action] += 1  # once per key, whose proxy rows all retire
            for row_id in row_ids:
                state = self.state(row_id)
                self.write(row_id, self._retired(state, RETIRED, outcome))
                self.counts["retired"] += 1
                self.rows.append(self._row(row_id, outcome.action, state, outcome.winner, **outcome.extra))

    @staticmethod
    def _retired(state: State, reason: str, outcome: _Admission) -> State:
        """The quarantine provenance, non-current, with the evidence of what replaced it at its key."""
        retired = {**qfr._quarantine(state, reason), "is_latest": False}
        retired["provenance"]["replacement"] = outcome.evidence
        return retired

    def admit(self, key: tuple, anchor_id: int, excluded: set[int]) -> _Admission:
        """The fresh winner at ``key`` once the rows ``excluded`` leave it. The first case that applies decides."""
        current = [row_id for row_id in self.by_key.get(key, ())
                   if row_id not in excluded and self.state(row_id)["is_latest"]]
        if current:
            self.refuse(anchor_id, f"another row is current at this key (fact {current[0]})")
            return _Admission("refused")
        fresh = self.fresh.get(key, [])
        if len(fresh) > 1:
            self.refuse(anchor_id, "the payload holds more than one winner at this key")
            return _Admission("refused")
        if not fresh:
            return self._no_winner(key, anchor_id, excluded)
        target = qfr._candidate_state(fresh[0])
        evidence = {name: target[name] for name in ("accession", "form", "value", "source")}
        extra = {"winner_form": target["form"], "winner_filed": _provenance(target).get("filed_at")}
        twin = self._twin(key)
        if twin is not None:
            extra["twin_fact_id"] = twin  # an insert's: the upsert's D1 rule decides it (facts/upsert.py)
        stored_id = self.identities.get(qfr._identity(target))
        if stored_id is None:
            self.inserts[qfr._identity(target)] = fresh[0]
            self.keys[key] = 1
            return _Admission("inserted", evidence, target, extra)
        return self._stored_winner(key, anchor_id, stored_id, target, {**evidence, "fact_id": stored_id}, extra)

    def _no_winner(self, key: tuple, anchor_id: int, excluded: set[int]) -> _Admission:
        other_units = sorted(other[3] for other in self.fresh if other[:3] == key[:3])
        if other_units:
            self.refuse(anchor_id, f"the payload's winner for this period is in {other_units[0]}; "
                                   "sync the company first")
            return _Admission("refused")
        stored = [row_id for row_id in self.by_key.get(key, ()) if row_id not in excluded
                  and _is_report_row(self.state(row_id)) and _reported(self.state(row_id))
                  and _provenance(self.state(row_id)).get("validation") != "unavailable"]
        if stored:
            self.refuse(anchor_id, f"a stored report row (fact {stored[0]}) has no fresh winner to agree with")
            return _Admission("refused")
        self.keys[key] = 0  # the fixed ingest's own result: a period only a proxy tags gets no row
        return _Admission("retired_without_winner")

    def _stored_winner(self, key: tuple, anchor_id: int, stored_id: int, target: State,
                       evidence: dict[str, Any], extra: dict[str, Any]) -> _Admission:
        """The winner's identity is stored: correct and promote a companyfacts-owned row; promote a
        filing-owned one only where it agrees with the winner, never touching its value or labels."""
        stored = self.state(stored_id)
        if "repair_rolled_back" in (_provenance(stored).get("reasons") or []):
            self.refuse(anchor_id, f"the winner's row (fact {stored_id}) was rolled back; "
                                   "a reviewed reapplication is required")
            return _Admission("refused")
        if stored["filing_id"] is None and stored["source"] in {"companyfacts", "derived"}:
            winner = {**stored, **{name: target[name] for name in qfr._MUTABLE_FIELDS}, "is_latest": True}
            changed = any(stored[name] != target[name] for name in qfr._MUTABLE_FIELDS)
            action = "corrected" if changed else "promoted"
        else:
            failed = _disagreements(stored, target)
            if failed:
                self.refuse(anchor_id, f"the filing row holding the 10-K's identity (fact {stored_id}) "
                                       f"disagrees with the 10-K on: {', '.join(failed)}")
                return _Admission("refused")
            winner, action = {**stored, "is_latest": True}, "promoted"
        self.write(stored_id, winner)
        self.keys[key] = 1
        self.stored_keys.add(key)
        return _Admission(action, evidence, winner, extra)

    def _twin(self, key: tuple) -> int | None:
        """A current row with no fiscal period at a quarter key's period, which the upsert's D1 rule
        demotes on an insert there unless its filing is later (the plan cannot see filing dates)."""
        concept, period_end, fiscal_period, unit = key
        if fiscal_period not in qfr.QUARTERS:
            return None
        return next((row_id for row_id in self.by_key.get((concept, period_end, None, unit), ())
                     if self.state(row_id)["is_latest"]), None)

    def settle_dependents(self) -> None:
        """Set 3: each current row of another form built on a proxy figure."""
        if not self.accessions:
            return
        for row_id, stored in self.before.items():
            state = self.state(row_id)
            if not state["is_latest"] or is_proxy_form(state["form"]) or not _quotes(state, self.accessions):
                continue
            if not qfr._loop_scope(stored):  # the loop's own test, on the row it reads
                self.refuse(row_id, "a row outside the repair's scope is built on a proxy figure")
                continue
            self.touched.add(row_id)
            if qfr._identity(stored) in self.normalized:
                self.counts["dependents_recomputed"] += 1  # the loop recomputes it from the fresh operands
                self.keys.setdefault(_key(state), 1)
                self.stored_keys.add(_key(state))
                continue
            outcome = self.admit(_key(state), row_id, {row_id})
            self.write(row_id, self._retired(state, DEPENDENT, outcome))
            self.counts["dependents_retired"] += 1
            self.rows.append(self._row(row_id, f"dependent_{outcome.action}", state, outcome.winner, **outcome.extra))


def plan(before: dict[int, State], updates: dict[int, State], facts: list[dict],
         normalized: dict[tuple, dict], payload: dict[str, Any]) -> ProxyPlan:
    """Plan the step over the repair's snapshots, writing into ``updates``; raise ``ProxyRepairRefused``
    with every reason before any write when a case cannot be settled on positive evidence."""
    planner = _Planner(before, updates, facts, normalized, payload)
    planner.restore_filing_rows()
    planner.reconfirm_filing_rows()
    planner.reannotate()
    planner.retire_proxy_rows()
    planner.settle_dependents()
    if planner.refusals:
        raise ProxyRepairRefused(f"Proxy repair refused for this company ({len(planner.refusals)}): "
                                 + "; ".join(planner.refusals))
    tagged = planner.touched | {row_id for row_id, state in before.items()
                                if is_proxy_form(state["form"]) or _quotes(state, planner.accessions)}
    return ProxyPlan(inserts=list(planner.inserts.values()), tagged=tagged, accessions=planner.accessions,
                     keys=planner.keys, counts=planner.counts, rows=planner.rows,
                     stored_keys=planner.stored_keys, verdicts=planner.verdicts)
