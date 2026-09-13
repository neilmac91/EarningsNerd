"""Selected original Ford source reaches actual offline primary/recovery requests intact."""
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

from edgar.documents import HTMLParser, ParserConfig
import pytest

from app.services.ai import provider_requests
from app.services.ai.outlook_source import OUTLOOK_LABEL, outlook_supplement
from app.services.ai.recovery_context import build_recovery_context, recovery_blocks
from app.services.openai_service import OpenAIService
from tests.unit.test_recovery_context import native_service, response


@pytest.fixture(scope="module")
def ford_mda():
    path = Path(__file__).parents[1] / "fixtures/outlook/ford-2026q1.html.gz"
    html = gzip.decompress(path.read_bytes())
    assert hashlib.sha256(html).hexdigest() == "8f7a1adee57f71fcb32c011cc47e8358ebb68f1b0248a3a719e32da26b27750e"
    # Same parser/config/part-qualified selection as TenQ and _extract_sections_sync.
    document = HTMLParser(ParserConfig(form="10-Q")).parse(html)
    return document.sections.get("part_i_item_2").text().strip()


def assembled(mda):
    service = object.__new__(OpenAIService)
    sections = {"financials": "RETAIN FINANCIALS " * 500,
                "mda": mda, "risk": "RETAIN RISKS " * 500}
    layout = service._SECTION_LAYOUT["10-Q"]
    # Independent reconstruction of the pre-change assembly: existing source bytes stay put.
    old = ("\n\n" + "=" * 50 + "\n\n").join(
        f"{label}:\n{sections[key].strip()[:cap]}" for key, label, cap in layout
    )[:320000]
    return service.assemble_excerpt_from_sections(sections, "10-Q"), old, layout


@pytest.mark.asyncio
async def test_original_ford_complete_outlook_reaches_primary_and_forward_recovery_without_displacement(
    ford_mda, monkeypatch,
):
    sample, old, layout = assembled(ford_mda)
    block = ford_mda[ford_mda.index("OUTLOOK"):ford_mda.index(
        "Cautionary Note on Forward-Looking Statements", ford_mda.index("OUTLOOK"))].strip()
    assert ford_mda.index("OUTLOOK") > 45000
    assert 3000 < len(block) < 6000
    assert "Adjusted EBIT (a)$8.5 - $10.5 billion" in block
    assert "Ford Energy" in block  # retain the final assumption, not merely the table
    supplement = f"\n\n{OUTLOOK_LABEL}:\n{block}"
    assert sample == old + supplement and len(supplement) <= 6000
    prior_blocks, blocks = recovery_blocks(old, layout), recovery_blocks(sample, layout)
    old_forward = build_recovery_context("forward_signals", prior_blocks, old)
    assert block not in old_forward
    expected = old_forward + supplement
    assert build_recovery_context("forward_signals", blocks, sample) == expected
    assert len(expected) <= 36000
    for section in ("the_print", "results_that_matter", "earnings_quality", "value_drivers",
                    "risks", "balance_sheet_liquidity", "notable_footnotes"):
        assert build_recovery_context(section, blocks, sample) == build_recovery_context(section, prior_blocks, old)

    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return response({"metadata": {}, "sections": {}, "forward_signals": {"guidance": "Selected source."}})

    monkeypatch.setattr(provider_requests, "record_ai_call", lambda **kwargs: kwargs)
    async with native_service(handler) as service:
        service._assemble_structured_summary = AsyncMock(return_value={"assembled": True})
        await service.generate_structured_summary("UNSELECTED RAW", "Ford", "10-Q", filing_excerpt=sample)
        prepared = service._assemble_structured_summary.call_args.args
        await service._recover_single_section("forward_signals", "10-Q", prepared[4], prepared[2], {})
    primary = requests[0]["messages"][1]["content"]
    recovery = requests[1]["messages"][1]["content"]
    assert "CRITICAL FILING EXCERPTS:\n" + sample in primary
    assert "UNSELECTED RAW" not in primary
    actual_context = recovery.split("FILING EXCERPT:\n", 1)[1].split("\n\nReturn JSON", 1)[0]
    assert actual_context == expected and block in actual_context


@pytest.mark.parametrize("variant", ["duplicate-start", "duplicate-end", "toc", "oversized", "clipped", "before-cap"])
def test_uncertain_or_unneeded_source_does_not_change_existing_excerpt(ford_mda, variant):
    start = ford_mda.index("OUTLOOK")
    end = ford_mda.index("Cautionary Note on Forward-Looking Statements", start)
    block = ford_mda[start:end]
    if variant == "duplicate-start":
        mda = ford_mda + "\nOUTLOOK\n"
    elif variant == "duplicate-end":
        mda = ford_mda + "\nCautionary Note on Forward-Looking Statements\n"
    elif variant == "toc":
        mda = "X" * 46000 + "\nOUTLOOK\n53\nCautionary Note on Forward-Looking Statements\n54"
    elif variant == "oversized":
        mda = ford_mda[:end] + "Additional source sentence.\n" * 300 + ford_mda[end:]
    elif variant == "clipped":
        mda = ford_mda[:end]
    else:
        mda = block + "Cautionary Note on Forward-Looking Statements\n" + "X" * 60000
    sample, old, _layout = assembled(mda)
    assert sample == old


def test_already_included_complete_source_is_not_duplicated(ford_mda):
    start = ford_mda.index("OUTLOOK")
    end = ford_mda.index("Cautionary Note on Forward-Looking Statements", start)
    block = ford_mda[start:end].strip()
    assert outlook_supplement(ford_mda, "An existing recovered window\n" + block, 45000) == ""
