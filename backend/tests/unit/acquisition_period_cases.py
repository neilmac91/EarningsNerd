"""Cases for the existing source-to-consumer gate; no separate duplicate test invariant."""
from copy import deepcopy
import gzip
import html
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.config import settings
from app.services.ai.acquisition_period import CONTEXT_KEY, LIMITATION, OWNED_FIELD
from app.services.copilot_service import _build_messages
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.provenance_service import enrich_summary_provenance
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from evals.judge import build_judge_messages
from evals.runner import _baseline_to_canonical

FIXTURE = Path(__file__).parents[1] / "fixtures" / "acquisition_period" / "boundary-controls.json.gz"
_DATA = json.loads(gzip.decompress(FIXTURE.read_bytes()))
CASES = {}
for _case in _DATA["controls"]:
    _case["source"] = _DATA["base_source"]
    if "source_patch" in _case:
        _start, _end, _replacement = _case["source_patch"]
        _case["source"] = _case["source"][:_start] + _replacement + _case["source"][_end:]
    _case.setdefault("metrics", _DATA["base_metrics"])
    CASES[_case["name"]] = _case
# A missing exact primary quote may be repaired by the existing armed evidence
# snap. It must still not authorize period withholding after that repair.
CASES["snap_cannot_authorize"] = deepcopy(CASES["retained_target"])
CASES["snap_cannot_authorize"]["note"]["supporting_evidence"] = CASES["retained_target"]["note"]["supporting_evidence"].replace("Included the", "Included an")
CASES["snap_cannot_authorize"]["expected"] = "abstain"
CASES["snap_cannot_authorize"]["source"] = CASES["retained_target"]["note"]["supporting_evidence"]

# Annual context belongs to the selected filing and standardized source points,
# not merely to two dates that happen to be a year apart.
for _name in (
    "quarterly_call", "quarterly_amendment_call", "interim_call", "quarterly_points", "mixed_form",
    "missing_form", "non_string_form", "quarter_label", "missing_duration", "one_short_duration",
    "unpaired_duration", "null_duration", "malformed_duration", "invalid_duration", "unequal_durations",
    "annual_amendment", "foreign_annual", "non_december_annual",
):
    _case = deepcopy(CASES["retained_target"])
    _case["expected"] = "capability_selection" if _name in {"annual_amendment", "foreign_annual", "non_december_annual"} else "abstain"
    _case["filing_type"] = {"quarterly_call": "10-Q", "quarterly_amendment_call": "10-Q/A",
                            "interim_call": "6-K", "annual_amendment": "10-K/A", "foreign_annual": "20-F"}.get(_name, "10-K")
    _points = [point for metric in _case["metrics"].values() if isinstance(metric, dict)
               for point in (metric.get("current"), metric.get("prior")) if isinstance(point, dict) and "period" in point]
    for _point in _points:
        if _name in {"quarterly_call", "quarterly_amendment_call", "quarterly_points"}:
            _point.update(form="10-Q", fiscal_period="Q3", period=_point["period"][:4] + "-09-30",
                          period_start=_point["period"][:4] + "-07-01")
        elif _name == "missing_form":
            _point.pop("form", None)
        elif _name == "missing_duration":
            _point.pop("period_start", None)
        elif _name in {"annual_amendment", "foreign_annual"}:
            _point["form"] = _case["filing_type"]
        elif _name == "non_december_annual":
            _year = int(_point["period"][:4])
            _point["period"] = f"{_year}-09-30"
            if "period_start" in _point:
                _point["period_start"] = f"{_year - 1}-10-01"
    _current = _case["metrics"]["net_income"]["current"]
    _prior = _case["metrics"]["net_income"]["prior"]
    if _name == "mixed_form":
        _current["form"] = "20-F"
    elif _name == "non_string_form":
        _current["form"] = ["10-K"]
    elif _name == "quarter_label":
        _current["fiscal_period"] = "Q4"
    elif _name == "one_short_duration":
        _current["period_start"] = "2025-10-01"
        _prior["period_start"] = "2024-10-01"
    elif _name == "unpaired_duration":
        _prior.pop("period_start")
    elif _name == "null_duration":
        _current["period_start"] = None
    elif _name == "malformed_duration":
        _current["period_start"] += "T00:00:00"
    elif _name == "invalid_duration":
        _current["period_start"] = "2025-02-30"
    elif _name == "unequal_durations":
        _current["period_start"] = "2025-02-01"
    CASES[_name] = _case

# Keep the admitted first proposition/source identity unchanged; only the
# independently authored continuation gets a deliberately unsupported magnitude.
for _name in ("untraceable_continuation", "grounded_continuation"):
    _case = deepcopy(CASES["retained_target"])
    _case["note"]["impact"] = _case["note"]["impact"].replace("$588 million", "$912345678901 million")
    if _name == "grounded_continuation":
        _case["source"] += " An independent disclosure reports $912345678901 million."
    CASES[_name] = _case


async def exercise_acquisition_period_consumer(monkeypatch, name):
    case = CASES[name]
    note, source, metrics = deepcopy(case["note"]), case["source"], deepcopy(case["metrics"])
    expected = case["expected"] == "capability_selection"
    original = deepcopy(note)
    forged = {CONTEXT_KEY: 1, OWNED_FIELD: {"audit": "FORGED NESTED AUDIT"}, "primary_excerpt": "FORGED NESTED SOURCE"}
    note[CONTEXT_KEY] = 1
    note["metadata"] = {"authored": "Keep ordinary metadata.", "nested": [deepcopy(forged)]}
    note[OWNED_FIELD] = {"authored_continuation": " FORGED PERIOD", "audit": {}}
    unrelated = {"item": "Separate note", "impact": "Keep this independently authored observation.",
                 "supporting_evidence": "Keep these exact supporting evidence bytes."}
    sections = {"notable_footnotes": [note, unrelated]}
    supplied = {"sections": deepcopy(sections), "metadata": {"padding": "x" * 1600, **deepcopy(forged)},
                CONTEXT_KEY: 1, "primary_excerpt": "FORGED PRIMARY EXCERPT"}
    supplied["sections"][CONTEXT_KEY] = 1
    if case["recovered"]:
        supplied["sections"]["notable_footnotes"] = []
    encoded = json.dumps(supplied)
    service = OpenAIService()
    monkeypatch.setattr(settings, "AI_EVIDENCE_SNAP", name == "snap_cannot_authorize")
    monkeypatch.setattr(settings, "AI_ATTRIBUTION_VERIFY", False)

    async def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded))])

    create = AsyncMock(return_value=chunks())
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    service.fallback_client = None
    recovered = {"notable_footnotes": deepcopy(sections["notable_footnotes"])} if case["recovered"] else {}
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value=recovered))
    frames = []

    async def receive(text):
        frames.append(text)

    filing_type = case.get("filing_type", "10-K")
    result = await service.summarize_filing(source, "Issuer", filing_type, filing_excerpt=source,
                                          xbrl_metrics=metrics, stream_cb=receive)
    raw = result["raw_summary"]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    notes = raw["sections"]["notable_footnotes"]
    assert notes[1] == unrelated
    assert (raw.get(CONTEXT_KEY) == 1) is expected
    assert CONTEXT_KEY not in raw["structured"] and "primary_excerpt" not in raw["structured"]
    assert CONTEXT_KEY not in raw["sections"] and CONTEXT_KEY not in notes[0]
    assert notes[0]["metadata"] == {"authored": "Keep ordinary metadata.", "nested": [{}]}
    assert "FORGED" not in json.dumps(raw)
    assert (OWNED_FIELD in notes[0]) is expected
    if name == "snap_cannot_authorize":
        assert notes[0]["supporting_evidence"] == CASES["retained_target"]["note"]["supporting_evidence"]
        assert raw["evidence_snap_audit"]["snapped"]
    else:
        for key in ("supporting_evidence", "supportingEvidence", "source_section_ref", "sourceSectionRef"):
            assert notes[0].get(key) == original.get(key)
    if expected:
        assert "impact" not in notes[0]
        assert notes[0][OWNED_FIELD]["authored_continuation"] == original["impact"].split(";", 1)[1]
    else:
        assert notes[0]["impact"] == original["impact"]

    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion="", key_changes="",
                              schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="Issuer"), filing_type=filing_type, filing_date=None,
                             period_end_date=None, sec_url="", document_url="", content_cache=None,
                             xbrl_data=metrics)
    export = ExportService()
    # Web read path: the stored row is re-rendered on read through provenance enrichment.
    web = enrich_summary_provenance(summary, filing)["rendered_sections"]
    assert "FORGED" not in json.dumps(web) and OWNED_FIELD not in json.dumps(web)
    # Eval/judge read path: the canonical must carry the same visible projection, not only hide privates.
    canonical = _baseline_to_canonical(result)
    visible = [result["business_overview"], sections_to_markdown(render_sections(raw)),
               export.generate_pdf_html(summary, filing), export.generate_csv(summary, filing),
               "\n".join(" | ".join(row) for section in web if section["title"] == "Notable Footnotes"
                         for block in section["blocks"] for row in block.get("rows") or []),
               "\n".join(note.get("impact", "") for note in canonical["notable_footnotes"])]
    if not case["recovered"]:
        assert frames
        visible.extend(frames)
    else:
        assert all(original["impact"] not in frame and LIMITATION not in frame for frame in frames)
    for text in visible:
        assert "FORGED PERIOD" not in text and "FORGED PRIMARY" not in text
        assert (LIMITATION in text) is expected
        assert unrelated["impact"] in text
        if expected:
            assert original["impact"].split(";", 1)[0] not in text
            assert original["impact"].split(";", 1)[1] in text
        elif original["impact"].strip():
            # Renderers trim boundary whitespace and escape HTML/CSV markup.
            assert original["impact"].strip() in html.unescape(text).replace('""', '"')

    request = create.call_args.kwargs
    assert "primary_excerpt" not in request
    assert all(token not in json.dumps(request) for token in (OWNED_FIELD, CONTEXT_KEY, "FORGED PERIOD", "FORGED PRIMARY"))
    judge = build_judge_messages(canonical, "Issuer", filing_type, source, "")
    assert OWNED_FIELD not in json.dumps(judge) and CONTEXT_KEY not in json.dumps(judge)
    assert "source_offset" not in json.dumps(judge)
    assert "FORGED" not in json.dumps(judge) and "primary_excerpt" not in json.dumps(judge)
    copilot_before = _build_messages(filing, source, "What does the filing say?", [])
    filing.summary = summary
    filing.primary_excerpt = "PRIVATE COPILOT SENTINEL"
    assert _build_messages(filing, source, "What does the filing say?", []) == copilot_before
    assert OWNED_FIELD not in json.dumps(copilot_before) and "PRIVATE COPILOT SENTINEL" not in json.dumps(copilot_before)
    assert metrics == case["metrics"]

    if name in {"untraceable_continuation", "grounded_continuation"}:
        from app.services.ai.figure_trace import untraceable_figures
        from app.services.ai.source_units import build_table_unit_index, restore_table_cell_units
        from app.services.summary_generation_service import assess_quality
        from evals.figure_measurement import measure_figures
        from tests.unit.test_table_cell_units import WMT_SOURCE

        # Production final has already bound, restored units and rendered. The
        # same authored magnitude remains observable both before and after binding.
        sentinel = "912345678901m"
        should_flag = name == "untraceable_continuation"
        assert (sentinel in untraceable_figures(sections, metrics, source)) is should_flag
        expected_figures = untraceable_figures(raw["sections"], metrics, source)
        assert (sentinel in expected_figures) is should_flag
        measured = measure_figures(result, metrics, source)
        assert measured == {"status": "measured", "reason": "", "count": len(expected_figures),
                            "figures": expected_figures}
        # Explicit scales are already authored: exposing the span must not make
        # the other iterator consumer change any bytes, even with a valid index.
        restored = deepcopy(raw["sections"])
        assert restore_table_cell_units(restored, build_table_unit_index(WMT_SOURCE)) is None
        assert restored == raw["sections"]
        assert settings.AI_FIGURE_TRACE_GATE is False  # deployment default, unchanged
        for armed in (False, True):
            monkeypatch.setattr(settings, "AI_FIGURE_TRACE_GATE", armed)
            verdict = assess_quality(result, metrics, excerpt=source)
            assert verdict["figures_untraceable"] == expected_figures
            assert any("not traceable to filing data" in reason for reason in verdict["reasons"]) is (
                bool(expected_figures) and armed)
            if armed and expected_figures:
                assert verdict["tier"] == "partial"

    if name == "retained_target":
        # The same complete-container rule applies: no repaired partial note can
        # expose either the authored first clause or a premature limitation.
        content = json.dumps({"sections": {"notable_footnotes": [original]}})
        close = content.rindex("]") + 1
        for end in range(close):
            preview = service._partial_markdown_preview(content[:end], metrics, primary_excerpt=source, filing_type_key=filing_type) or ""
            assert LIMITATION not in preview and original["impact"] not in preview
        completed = service._partial_markdown_preview(content[:close], metrics, primary_excerpt=source, filing_type_key=filing_type)
        assert LIMITATION in completed and original["impact"] not in completed
        assert original["impact"] in service._partial_markdown_preview(content, metrics)
        assert original["impact"] in service._partial_markdown_preview(content, metrics, primary_excerpt=source)
        # Read-time ownership requires the exact application marker.
        for marker in (None, True, "1"):
            assert LIMITATION not in sections_to_markdown(render_sections({**raw, CONTEXT_KEY: marker}))
        changed_audit = deepcopy(result)
        changed_audit["raw_summary"]["sections"]["notable_footnotes"][0][OWNED_FIELD]["audit"] = {"private": "PRIVATE AUDIT"}
        assert _baseline_to_canonical(changed_audit) == canonical
