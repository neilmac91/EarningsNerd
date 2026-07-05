"""Deterministic scorers for the eval harness.

These are pure functions with no network/AI dependency, so they are fast, reproducible, and
unit-tested offline. They are the defensible core of the bake-off: schema validity, numeric
grounding against XBRL ground truth, and substantive section coverage. (An optional LLM-judge
dimension can be layered on later for usefulness/precision — see README.)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from evals.schema import REQUIRED_SECTIONS, GroundTruthFact, RubricScore

# Placeholder/failure phrases that must NOT count as substantive content. Kept in sync with
# summary_generation_service.calculate_section_coverage so the harness and product agree on
# what "covered" means.
PLACEHOLDER_PATTERNS = (
    "not disclosed", "not available", "unavailable", "n/a", "not found",
    "not provided", "no data", "could not", "unable to", "failed to",
    "missing", "pending", "being processed", "retry", "error",
    "not captured", "not extracted",
)

_MIN_SUBSTANTIVE_CHARS = 20

# A financial_highlights object is well-formed in EITHER of two shapes:
#   - the flat canonical shape a bake-off candidate is prompted to emit, or
#   - the production pipeline's richer shape (a metric table + profitability / cash_flow /
#     balance_sheet bullet lists).
# Requiring only the flat shape made real production output structurally schema-invalid, which
# silently capped the aggregate (the schema weight was unearnable). Accepting either is the honest
# check: it still rejects a malformed/empty object.
_FLAT_FH_KEYS = ("revenue", "net_income", "eps", "key_metrics")
_PRODUCT_FH_KEYS = ("table", "profitability", "cash_flow", "balance_sheet")


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------
def validate_schema(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Lightweight structural validation against EVAL_SUMMARY_JSON_SCHEMA.

    We don't pull a full JSON-schema lib for this — the canonical shape is small and fixed.
    Returns (is_valid, list_of_problems)."""
    problems: List[str] = []
    if not isinstance(payload, dict):
        return False, ["top-level value is not an object"]

    for key in REQUIRED_SECTIONS:
        if key not in payload:
            problems.append(f"missing key: {key}")

    fh = payload.get("financial_highlights")
    if not isinstance(fh, dict):
        problems.append("financial_highlights is not an object")
    elif any(k in fh for k in _PRODUCT_FH_KEYS):
        # Production pipeline shape (table + bullet lists) — structurally well-formed. Check key
        # PRESENCE, not truthiness: an empty-but-structured object is still valid here; emptiness
        # is coverage's concern, not schema validity's.
        pass
    else:
        # Otherwise require the full flat canonical shape (a candidate that emits it).
        for k in _FLAT_FH_KEYS:
            if k not in fh:
                problems.append(f"financial_highlights missing: {k}")
        if "key_metrics" in fh and not isinstance(fh["key_metrics"], list):
            problems.append("financial_highlights.key_metrics is not an array")

    if "risk_factors" in payload and not isinstance(payload["risk_factors"], list):
        problems.append("risk_factors is not an array")

    for str_key in ("executive_summary", "management_discussion", "outlook"):
        if str_key in payload and not isinstance(payload[str_key], str):
            problems.append(f"{str_key} is not a string")

    return (len(problems) == 0), problems


def parse_model_json(raw: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Parse a model's text output as JSON. Returns (payload, repaired).

    `repaired` is True when strict json.loads failed and we fell back to extracting a JSON
    object — a soft failure that, in aggregate, signals the model isn't honoring enforced
    structured output (the whole motivation for S1)."""
    try:
        return json.loads(raw), False
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: strip markdown fences and grab the outermost {...}.
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1]), True
        except json.JSONDecodeError:
            return None, True
    return None, True


# ---------------------------------------------------------------------------
# Numeric grounding
# ---------------------------------------------------------------------------
def _number_renderings(value: float, unit: str) -> List[str]:
    """Plausible string renderings of a ground-truth value a model might emit.

    Covers billions/millions/raw with 0-3 decimals and comma grouping, so "383.3",
    "$383.285 billion", "383,285" (millions) and "383,285,000,000" all match revenue."""
    out: set[str] = set()
    av = abs(value)

    def with_decimals(x: float) -> List[str]:
        reps = []
        for d in range(0, 4):
            s = f"{x:.{d}f}"
            reps.append(s)
            # comma-grouped integer part
            try:
                intpart, _, frac = s.partition(".")
                grouped = f"{int(intpart):,}"
                reps.append(grouped if not frac else f"{grouped}.{frac}")
            except ValueError:
                pass
        return reps

    if unit.endswith("_per_share"):
        # Per-share figures (USD_per_share, CNY_per_share, …) are small — render at full precision,
        # never scaled to billions/millions. The currency prefix doesn't change the numeric
        # rendering, so a foreign EPS like "RMB 6.00" still matches on "6.00".
        out.update(with_decimals(av))
    else:
        if av >= 1e9:
            out.update(with_decimals(av / 1e9))  # billions
        if av >= 1e6:
            out.update(with_decimals(av / 1e6))  # millions
        # raw dollars, grouped and ungrouped
        out.add(f"{int(round(av))}")
        out.add(f"{int(round(av)):,}")
    # drop trivially-short tokens that would false-match everywhere
    return [r for r in out if len(r.replace(",", "").replace(".", "")) >= 2]


def _fact_renderings(fact: GroundTruthFact) -> List[str]:
    """All acceptable string renderings of a fact: its `value` plus any `alt_values`.

    Alts let one fact accept more than one correct figure — e.g. EPS matches whether the summary
    quotes basic or diluted (both are right; the model headlines diluted)."""
    out = list(_number_renderings(fact.value, fact.unit))
    for alt in (fact.alt_values or []):  # tolerate alt_values being None (e.g. JSON null)
        out.extend(_number_renderings(alt, fact.unit))
    return out


def score_numeric_accuracy(
    haystack: str, ground_truth: List[GroundTruthFact]
) -> Tuple[float, List[str], List[str]]:
    """Fraction of ground-truth facts whose value appears (in any common rendering) in the
    candidate's financial text. Returns (recall, matched_metrics, missing_metrics)."""
    if not ground_truth:
        return 1.0, [], []  # nothing to verify → not penalized
    hay = haystack.lower()
    matched, missing = [], []
    for fact in ground_truth:
        renderings = _fact_renderings(fact)
        if any(r.lower() in hay for r in renderings):
            matched.append(fact.metric)
        else:
            missing.append(fact.metric)
    recall = len(matched) / len(ground_truth)
    return round(recall, 4), matched, missing


# ---------------------------------------------------------------------------
# Section coverage (substantive content, not placeholders)
# ---------------------------------------------------------------------------
def _is_substantive(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        if len(text) < _MIN_SUBSTANTIVE_CHARS:
            return False
        if len(text) < 200 and any(p in text for p in PLACEHOLDER_PATTERNS):
            return False
        return True
    if isinstance(value, list):
        return any(_is_substantive(v) for v in value)
    if isinstance(value, dict):
        # financial_highlights: substantive if any sub-value is substantive
        return any(_is_substantive(v) for v in value.values())
    if isinstance(value, (int, float)):
        return True
    return False


def score_coverage(payload: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Fraction of required sections containing substantive content. Returns (ratio, missing)."""
    missing = [s for s in REQUIRED_SECTIONS if not _is_substantive(payload.get(s))]
    covered = len(REQUIRED_SECTIONS) - len(missing)
    return round(covered / len(REQUIRED_SECTIONS), 4), missing


# ---------------------------------------------------------------------------
# Financial depth (report-quality P1.0)
# ---------------------------------------------------------------------------
# Coverage asks "are the sections non-empty?". DEPTH asks the question Phase-1 is about: does the
# financial content actually surface cash flow, the balance sheet, and margins — not just the three
# headline income-statement numbers? A category counts only when its term sits next to a real number
# and not inside a placeholder phrase, so "cash flow not disclosed" does NOT score.
_DEPTH_CATEGORIES: Dict[str, Tuple[str, ...]] = {
    "cash_flow": ("operating cash flow", "free cash flow", "cash flow from operations",
                  "cash provided by operating", "capital expenditure", "capex"),
    "balance_sheet": ("total assets", "total debt", "long-term debt", "long term debt",
                      "shareholders' equity", "shareholders equity", "stockholders' equity"),
    "margins": ("gross margin", "operating margin", "gross profit", "operating income"),
}


def _term_near_number(text: str, terms: Tuple[str, ...]) -> bool:
    """True when any term appears within ~40 chars of a digit and not inside a placeholder phrase."""
    for term in terms:
        start = text.find(term)
        while start != -1:
            window = text[max(0, start - 40): start + len(term) + 40]
            if re.search(r"\d", window) and not any(p in window for p in PLACEHOLDER_PATTERNS):
                return True
            start = text.find(term, start + 1)
    return False


def score_financial_depth(payload: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Fraction of {cash_flow, balance_sheet, margins} surfaced with real figures. (ratio, missing)."""
    blob = _financial_haystack(payload).lower()
    missing = [name for name, terms in _DEPTH_CATEGORIES.items() if not _term_near_number(blob, terms)]
    present = len(_DEPTH_CATEGORIES) - len(missing)
    return round(present / len(_DEPTH_CATEGORIES), 4), missing


# ---------------------------------------------------------------------------
# Numeric precision / contradiction (Artifact-1 hard gate G1)
# ---------------------------------------------------------------------------
# `score_numeric_accuracy` above measures RECALL — are the right numbers present? It cannot
# catch a confidently-wrong figure: a summary whose revenue field reads "$4.2B" still scores
# perfect recall if the correct "$3.8B" appears elsewhere. Precision closes that: it checks the
# LABELED financial fields directly, so a number that contradicts ground truth is caught.
_LABELED_METRICS = ("revenue", "net_income", "eps")
_NUMBER_TOKEN_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")
# Negative-value indicators: a leading minus or accounting parentheses on a figure, or an
# explicit loss word. `_number_renderings` matches on abs(value), so without this a profit
# reported where the truth is a loss (sign-flipped) would silently satisfy the G1 gate.
_NEGATIVE_INDICATOR_RE = re.compile(r"-\s*\$?\d|\(\s*\$?\d")
_LOSS_WORDS = ("loss", "deficit", "negative")


def _indicates_negative(field_val: str) -> bool:
    low = field_val.lower()
    return bool(_NEGATIVE_INDICATOR_RE.search(field_val)) or any(w in low for w in _LOSS_WORDS)


def score_numeric_precision(
    payload: Dict[str, Any], ground_truth: List[GroundTruthFact]
) -> Tuple[float, List[str]]:
    """Precision of the labeled financial fields. Returns (precision, contradictions).

    For each ground-truth metric with a matching `financial_highlights` field that contains a
    number, the field must (a) match the metric's sign and (b) render its value. A wrong number
    OR a flipped sign (a loss reported as a profit) is a contradiction. Absent values
    ("Not disclosed") are coverage's concern. precision = 1.0 when nothing numeric is checkable."""
    fh = payload.get("financial_highlights")
    if not isinstance(fh, dict) or not ground_truth:
        return 1.0, []
    gt_by_metric = {f.metric: f for f in ground_truth}
    checked = 0
    contradictions: List[str] = []
    for metric in _LABELED_METRICS:
        fact = gt_by_metric.get(metric)
        if fact is None:
            continue
        field_val = fh.get(metric)
        if not isinstance(field_val, str) or not _NUMBER_TOKEN_RE.search(field_val):
            continue  # absent or non-numeric → not a contradiction
        checked += 1
        if (fact.value < 0) != _indicates_negative(field_val):
            contradictions.append(
                f"{metric}: field '{field_val.strip()[:50]}' sign mismatch with ground truth "
                f"{fact.value:g} {fact.unit}"
            )
            continue
        renderings = _fact_renderings(fact)  # accept value OR an alt (e.g. basic/diluted EPS)
        if not any(r.lower() in field_val.lower() for r in renderings):
            contradictions.append(
                f"{metric}: field '{field_val.strip()[:50]}' contradicts ground truth "
                f"{fact.value:g} {fact.unit}"
            )
    precision = round((checked - len(contradictions)) / checked, 4) if checked else 1.0
    return precision, contradictions


# ---------------------------------------------------------------------------
# Output hygiene (Artifact-1 hard gate G4)
# ---------------------------------------------------------------------------
# Leaked AI/internal notices and placeholder filler must never reach a user. Deterministic and
# cheap to catch in the prose fields. (G2 fabricated comparatives / G3 hallucinated events need
# the source document and are assessed by the optional LLM judge, not here.)
HYGIENE_PATTERNS = (
    "as an ai", "as a language model", "i cannot", "i'm sorry", "i am sorry",
    "internal note", "internal only", "system prompt", "do not show", "do not display",
    "todo", "tbd", "lorem ipsum", "[insert", "[placeholder", "placeholder text", "xxxx",
    # Regression guard: known product boilerplate/templated filler that must never reach a user
    # again (report-quality Phase 0 removed these from _apply_structured_fallbacks).
    "based on available xbrl data", "proxy for balance sheet size",
    "align with standard operational and market conditions",
    "focused on operational execution and market conditions",
    "ongoing business momentum", "not disclosed in the targeted excerpts",
    "standard risk disclosures apply", "adopted a neutral tone",
)
_HYGIENE_PROSE_FIELDS = ("executive_summary", "management_discussion", "outlook")


def detect_hygiene_violations(payload: Dict[str, Any]) -> List[str]:
    """Return human-readable hygiene violations found in the prose fields and risk list."""
    violations: List[str] = []

    def scan(label: str, text: Any) -> None:
        if not isinstance(text, str):
            return
        low = text.lower()
        for p in HYGIENE_PATTERNS:
            if p in low:
                violations.append(f"{label}: contains '{p}'")

    for key in _HYGIENE_PROSE_FIELDS:
        scan(key, payload.get(key))
    rf = payload.get("risk_factors")
    if isinstance(rf, list):
        for i, item in enumerate(rf):
            scan(f"risk_factors[{i}]", item)
    return violations


def score_bank_revenue_integrity(
    haystack: str, ground_truth: List[GroundTruthFact]
) -> Tuple[float, List[str]]:
    """Bank revenue integrity (deterministic, Artifact-1 gate G5).

    ACTIVE only when the ground truth carries bank COMPONENT facts
    (``net_interest_income`` / ``noninterest_income``) — i.e. a bank that reports no single revenue
    line. In that case both components must appear separately in the candidate's financial text, so a
    summary that dropped them or replaced them with one conflated "revenue" fails. Returns
    ``(score, failures)``; ``(1.0, [])`` for every non-bank filing, so a golden set that carries no
    component facts is unaffected (this gate stays dormant until the golden set adds a no-total bank,
    e.g. MCB). The generation-time sanitizer guarantees the *negative* (no fabricated total) in
    production; this gate protects the *positive* (components surfaced) in the bake-off."""
    components = [
        f for f in ground_truth
        if f.metric in ("net_interest_income", "noninterest_income")
    ]
    if not components:
        return 1.0, []
    hay = haystack.lower()
    failures: List[str] = []
    matched = 0
    for fact in components:
        if any(r.lower() in hay for r in _fact_renderings(fact)):
            matched += 1
        else:
            failures.append(f"bank component not surfaced separately: {fact.metric}")
    return round(matched / len(components), 4), failures


def compute_gate_failures(
    payload: Dict[str, Any], contradictions: List[str],
    ground_truth: Optional[List[GroundTruthFact]] = None,
) -> List[str]:
    """Combine Artifact-1 deterministic hard gates into a single veto list."""
    failures = [f"G1 numeric fidelity — {c}" for c in contradictions]
    failures += [f"G4 output hygiene — {h}" for h in detect_hygiene_violations(payload)]
    # G5 (bank revenue integrity) is inert unless the ground truth carries bank component facts.
    _bank_score, bank_failures = score_bank_revenue_integrity(
        _financial_haystack(payload), ground_truth or []
    )
    failures += [f"G5 bank revenue — {m}" for m in bank_failures]
    return failures


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def _financial_haystack(payload: Dict[str, Any]) -> str:
    """Text we search for ground-truth numbers: financial section + executive summary."""
    parts: List[str] = []
    fh = payload.get("financial_highlights")
    if isinstance(fh, dict):
        parts.append(json.dumps(fh))
    elif fh is not None:
        parts.append(str(fh))
    for k in ("executive_summary", "management_discussion", "outlook"):
        v = payload.get(k)
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Narrative specificity (Wave 2 anti-boilerplate signal)
# ---------------------------------------------------------------------------
# Coverage/depth ask "is the content present, with figures?". SPECIFICITY asks the Wave-2 question:
# is the PROSE concrete, or padded with vague filler? It penalises generic boilerplate (distinct
# from the hygiene gate's leaked-notice patterns — these phrases are merely vague, not forbidden)
# and gives partial credit for explicit period-over-period framing (the "what changed" Wave 2
# targets). Reported alongside the aggregate (NOT folded in, like financial_depth), so a prompt
# change that de-boilerplates the narrative is measurable in CI without the LLM judge.
BOILERPLATE_PHRASES = (
    "well-positioned", "well positioned", "strong position", "market conditions",
    "operational execution", "business momentum", "ongoing momentum", "robust demand",
    "remains committed", "poised for", "poised to", "navigate the", "headwinds and tailwinds",
    "operational and market conditions", "continued growth", "solid performance",
    "challenging environment", "challenging macro", "dynamic market", "competitive landscape",
    "in line with expectations", "consistent with prior", "no material change",
    "focused on execution", "execution and market conditions", "long-term value", "going forward",
)
_COMPARATIVE_TERMS = (
    "yoy", "y/y", "year-over-year", "year over year", "vs prior", "vs. prior", "versus prior",
    "compared to", "compared with", "increased from", "decreased from", "rose from", "fell from",
    "up from", "down from", "prior year", "prior-year", "year-ago", "quarter-over-quarter",
    "q/q", "qoq", "sequentially", "from the prior",
)
_SPECIFICITY_MIN_WORDS = 25       # below this, prose is too short to judge — don't penalise
_BOILERPLATE_DENSITY_FLOOR = 6.0  # boilerplate hits per 100 words that zeroes the component


def _prose_blob(payload: Dict[str, Any]) -> str:
    """Concatenate the narrative prose fields (same set the hygiene gate inspects)."""
    return " ".join(str(payload.get(k) or "") for k in _HYGIENE_PROSE_FIELDS)


def score_specificity(payload: Dict[str, Any]) -> Tuple[float, List[str]]:
    """[0,1] narrative specificity over the prose fields. Returns (score, flagged_phrases).

    score = 0.8 * boilerplate_component + 0.2 * change_component
      - boilerplate_component: 1.0 with no vague filler, falling to 0 at _BOILERPLATE_DENSITY_FLOOR
        boilerplate hits per 100 words.
      - change_component: 1.0 when the prose uses explicit period-over-period language, else 0.6
        (Wave 2 wants the "what changed" stated, not just a static description).
    Short/empty prose returns 1.0 (not assessable → not penalised)."""
    blob = _prose_blob(payload)
    low = blob.lower()
    words = len(blob.split())
    if words < _SPECIFICITY_MIN_WORDS:
        return 1.0, []
    # De-dup overlapping substrings (e.g. "market conditions" inside "execution and market
    # conditions"): match longest-first and blank each hit so a contained phrase isn't recounted.
    flagged: List[str] = []
    hits = 0
    remaining = low
    for phrase in sorted(BOILERPLATE_PHRASES, key=len, reverse=True):
        count = remaining.count(phrase)
        if count:
            hits += count
            flagged.append(phrase)
            remaining = remaining.replace(phrase, " ")
    flagged = [p for p in BOILERPLATE_PHRASES if p in flagged]
    density = hits / (words / 100.0)
    boilerplate_component = max(0.0, 1.0 - density / _BOILERPLATE_DENSITY_FLOOR)
    change_component = 1.0 if any(t in low for t in _COMPARATIVE_TERMS) else 0.6
    return round(0.8 * boilerplate_component + 0.2 * change_component, 4), flagged


def _expected_reporting_currency(ground_truth: List[GroundTruthFact]) -> Optional[str]:
    """The filing's reporting currency, inferred from ground-truth units (e.g. 'CNY',
    'DKK_per_share' -> 'DKK'). Returns None for USD/domestic filers (no currency check needed)."""
    codes: Dict[str, int] = {}
    for f in ground_truth:
        code = (f.unit or "USD").split("_")[0].upper()
        if code and code != "USD":
            codes[code] = codes.get(code, 0) + 1
    if not codes:
        return None
    return max(codes, key=codes.get)


# How each reporting currency is actually rendered in prose (ISO code differs from the symbol/name
# the model writes — CNY->"RMB", DKK->"kroner", TWD->"NT$"). Used to count native mentions.
_CURRENCY_ALIASES: Dict[str, Tuple[str, ...]] = {
    "CNY": ("cny", "rmb", "renminbi", "yuan", "¥"),
    "EUR": ("eur", "€"),
    "DKK": ("dkk", "kroner", "krone"),
    "TWD": ("twd", "nt$", "ntd"),
    "JPY": ("jpy", "yen", "¥"),
    "GBP": ("gbp", "£"),
    "HKD": ("hkd", "hk$"),
    "SGD": ("sgd", "s$"),
}

# A BARE '$' figure: a '$' NOT preceded by a letter or another '$', followed by a number. The
# negative lookbehind means localized dollar symbols (US$, NT$, HK$, S$, A$, C$) are treated as
# labeled/native, not as a mislabel — only a truly bare "$309B" is flagged.
_BARE_DOLLAR_RE = re.compile(
    r"(?<![A-Za-z$])\$\s?\d[\d,.]*\s?(?:B|M|K|bn|billion|million|thousand)?", re.IGNORECASE
)


def score_currency_consistency(
    payload: Dict[str, Any], ground_truth: List[GroundTruthFact]
) -> Tuple[float, List[str]]:
    """[0,1] currency-labeling fidelity for foreign (non-USD) filers. Returns (score, violations).

    A foreign issuer's figures must be in its reporting currency (RMB/EUR/DKK/TWD...), never a bare
    '$' — rendering e.g. DKK as '$' is a ~7x distortion the currency-AGNOSTIC numeric scorers cannot
    catch (numeric_precision matched only the value, not the unit). This flags bare-'$' monetary
    tokens (US$/NT$/HK$ etc. are excluded — those are labeled). score = native-currency mentions /
    (native + bare-'$'), so a wholesale mislabel (all figures '$') -> ~0 while an incidental labeled
    US$ convenience figure amid native prose -> ~1.0. USD/domestic filers return 1.0.

    NOTE: a foreign filer with genuinely USD-denominated items (e.g. USD convertible notes) can draw
    a mild (<1.0) score; that's why this is a WARN signal + eyeball prompt for the FPI adoption gate,
    not (yet) a hard gate."""
    cur = _expected_reporting_currency(ground_truth)
    if cur is None:
        return 1.0, []
    blob = _financial_haystack(payload)
    bare = [m.group(0).strip() for m in _BARE_DOLLAR_RE.finditer(blob)]
    if not bare:
        return 1.0, []
    low = blob.lower()
    native = sum(low.count(a) for a in _CURRENCY_ALIASES.get(cur, (cur.lower(),)))
    denom = native + len(bare)
    score = round(native / denom, 4) if denom else 0.0
    return score, [f"non-USD filer ({cur}) rendered bare-'$' figures: {', '.join(bare[:6])}"]


def score_summary(
    raw_or_payload: Any, ground_truth: List[GroundTruthFact]
) -> RubricScore:
    """Score one candidate summary. Accepts a raw string (from a model) or an already-parsed
    dict (from the baseline pipeline mapped into canonical shape)."""
    if isinstance(raw_or_payload, str):
        payload, repaired = parse_model_json(raw_or_payload)
    else:
        payload, repaired = raw_or_payload, False

    if payload is None:
        return RubricScore(
            schema_valid=False, repaired=True, numeric_accuracy=0.0, coverage=0.0,
            numeric_precision=0.0, financial_depth=0.0,
            gate_failures=["G1 numeric fidelity — unparseable output (no JSON object found)"],
            missing_sections=list(REQUIRED_SECTIONS),
            missing_facts=[f.metric for f in ground_truth],
        )

    schema_valid, _ = validate_schema(payload)
    numeric, matched, missing_facts = score_numeric_accuracy(
        _financial_haystack(payload), ground_truth
    )
    coverage, missing_sections = score_coverage(payload)
    precision, contradictions = score_numeric_precision(payload, ground_truth)
    depth, _ = score_financial_depth(payload)
    specificity, _ = score_specificity(payload)
    currency_consistency, _ = score_currency_consistency(payload, ground_truth)
    return RubricScore(
        schema_valid=schema_valid,
        repaired=repaired,
        numeric_accuracy=numeric,
        coverage=coverage,
        numeric_precision=precision,
        financial_depth=depth,
        specificity=specificity,
        currency_consistency=currency_consistency,
        gate_failures=compute_gate_failures(payload, contradictions, ground_truth),
        missing_sections=missing_sections,
        matched_facts=matched,
        missing_facts=missing_facts,
    )
