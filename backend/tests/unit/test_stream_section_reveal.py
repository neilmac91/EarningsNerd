"""A5 progressive section reveal: streaming helpers on openai_service.

No network — provider streams are mocked; the completion invariant uses the real renderer.
Covers: the partial-preview render
is best-effort (never raises), and _stream_collect accumulates the complete content while emitting
throttled preview frames via the callback.
"""
import json

import pytest

from app.services.openai_service import openai_service


@pytest.mark.parametrize(
    "partial",
    ["", "{", "not json at all", '{"sections":', '{"metadata":{},"sections":{"x":"y"}}', '{"sections":[]}'],
)
def test_partial_markdown_preview_never_raises(partial):
    # Best-effort: returns a string or None for any (often malformed) partial JSON, never raises.
    out = openai_service._partial_markdown_preview(partial, None)
    assert out is None or isinstance(out, str)


class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content):
        self.choices = [_Choice(content)]


@pytest.mark.asyncio
async def test_stream_collect_accumulates_and_emits(monkeypatch):
    pieces = ["a" * 800, "b" * 800, "c" * 200]  # total 1800 chars → crosses the ~1500 emit threshold

    async def fake_create(**kwargs):
        async def gen():
            for p in pieces:
                yield _Chunk(p)
        return gen()

    monkeypatch.setattr(openai_service.client.chat.completions, "create", fake_create)
    # Decouple from the real markdown builder — preview rendering is exercised separately above.
    monkeypatch.setattr(openai_service, "_partial_markdown_preview", lambda content, xbrl: "PREVIEW")

    emitted = []

    async def cb(md):
        emitted.append(md)

    content = await openai_service._stream_collect({}, cb, "10-K", None)

    assert content == "".join(pieces)          # complete content returned for assembly
    assert emitted and emitted[0] == "PREVIEW"  # at least one throttled preview frame fired


@pytest.mark.asyncio
async def test_stream_collect_consumer_error_does_not_abort(monkeypatch):
    async def fake_create(**kwargs):
        async def gen():
            yield _Chunk("z" * 2000)
        return gen()

    monkeypatch.setattr(openai_service.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(openai_service, "_partial_markdown_preview", lambda content, xbrl: "PREVIEW")

    async def bad_cb(_md):
        raise RuntimeError("consumer blew up")

    # A consumer error must never abort generation — content still returns intact.
    content = await openai_service._stream_collect({}, bad_cb, "10-K", None)
    assert content == "z" * 2000


@pytest.mark.asyncio
async def test_previews_render_only_originally_complete_current_sections(monkeypatch):
    """A preview is the shared projection of complete containers, never repaired claims."""
    from app.services.summary_sections import render_sections, sections_to_markdown
    from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION

    sections = {
        "the_print": {"headline": 'Revenue rose; management said "growth {continues}".',
                      "key_takeaways": ["Disclosed demand. " * 100]},
        "results_that_matter": {"table": [
            {"metric": "Revenue", "current_period": "$1,000M", "prior_period": "$800M",
             "change": "+25%", "commentary": "Volume", "source_value": 1.25e3},
        ]},
        "risks": [{"summary": "Concentration risk", "supporting_evidence": "A \\ B",
                   "materiality": "high"}],
        "forward_signals": {"guidance": "Sales guidance is $1,100M to $1,200M."},
    }
    prefix = '{"metadata":{"company_name":"Example"},"sections":{'
    content = prefix
    boundaries = []
    for key, value in sections.items():
        content += ("," if boundaries else "") + json.dumps(key) + ":" + json.dumps(value)
        boundaries.append(len(content))
    content += "}}"

    def expected(count):
        selected = dict(list(sections.items())[:count])
        return sections_to_markdown(render_sections({
            "schema_version": SUMMARY_SCHEMA_VERSION, "sections": selected,
        })) or None

    # Every byte boundary includes unfinished strings, escapes, numbers and nested arrays.
    # Closing only the first section must make progress before the root closes.
    for end in range(len(content) + 1):
        complete = sum(boundary <= end for boundary in boundaries)
        assert openai_service._partial_markdown_preview(content[:end], None) == expected(complete), end
    assert expected(1) and "Revenue rose" in expected(1)
    assert "$1,000M" in expected(2) and "Concentration risk" in expected(3)
    assert "Sales guidance" in expected(4)
    assert openai_service._partial_markdown_preview("```json\n" + content + "\n```", None) == expected(4)

    for malformed in (
        content + "garbage", content.replace('"sections":{', '"sections":['),
        content[:boundaries[0]] + 'x', content[:boundaries[0]] + ',}}',
        '{"sections":{"the_print":{"headline":"one","headline":"two"}}}',
        '{"sections":{"the_print":{"headline":"one"},"the_print":{}}}',
        '{"sections":{"the_print":{"headline":"one","bad":NaN}}}',
        '{"sections":{"results_that_matter":{"table":[{"metric":"Revenue","current_period":1e999}]}}}',
        '{"sections":{"the_print":"scalar"}}',
        '{"nested":{"sections":{"the_print":{"headline":"not root"}}}}',
        '{"sections":{"executive_snapshot":{"headline":"legacy"}}}',
        " " * 256_001 + content,
    ):
        assert openai_service._partial_markdown_preview(malformed, None) is None

    # Exercise the actual callback owner too: first frame precedes the completed root,
    # and optional preview rendering cannot change the assembled provider content.
    split = boundaries[0]
    pieces = [content[:split], content[split:]]
    seen = []

    async def fake_create(**kwargs):
        async def gen():
            yield _Chunk(pieces[0])
            assert seen == [expected(1)]
            yield _Chunk(pieces[1])
        return gen()

    async def cb(markdown):
        seen.append(markdown)

    monkeypatch.setattr(openai_service.client.chat.completions, "create", fake_create)
    assert await openai_service._stream_collect({}, cb, "10-K", None) == content
    assert seen[0] == expected(1)


def test_previews_respect_final_numeric_ownership_and_guarded_quotes(monkeypatch):
    """Complete model containers cannot bypass the final numeric/quote owners."""
    import copy

    from app.config import settings

    def metric(value):
        return {"current": {"value": value, "period": "2025-12-31"}}

    facts = {
        "net_income": metric(100_000_000), "operating_cash_flow": metric(200_000_000),
        "free_cash_flow": metric(150_000_000), "current_assets": metric(600_000_000),
        "current_liabilities": metric(300_000_000), "dividends_paid": metric(20_000_000),
        "return_on_equity": metric(12),
        "segments": [{"name": "Products", "revenue": 500_000_000,
                      "revenue_prior": 400_000_000, "operating_income": 100_000_000}],
    }
    sections = {
        "earnings_quality": {"operating_vs_one_time": "A retained earnings explanation.",
                             "cash_conversion": "MODEL CASH CLAIM"},
        "value_drivers": {"capital_allocation": "A retained capital decision.",
                          "shareholder_returns": "MODEL DISTRIBUTIONS", "returns_on_capital": "MODEL RETURNS"},
        "balance_sheet_liquidity": {"liquidity": "A retained liquidity discussion.",
                                    "working_capital": "MODEL WORKING CAPITAL", "cash_flow": "MODEL CASH FLOWS"},
        "segments": [{"segment": "Products", "revenue": "$999B", "commentary": "Product demand."},
                     {"segment": "End market", "revenue": "$888B", "commentary": "Unmatched model row."}],
        "forward_signals": {"guidance": "A retained outlook.",
                            "quotes": [{"speaker": "CEO", "quote": "A quotation awaiting verification."}]},
    }
    text = json.dumps({"sections": sections})[:-1]  # root still open; sections originally complete
    original_facts = copy.deepcopy(facts)
    monkeypatch.setattr(settings, "AI_FORWARD_QUOTE_GATE", False)
    preview = openai_service._partial_markdown_preview(text, facts)
    assert preview and "MODEL" not in preview and "$999B" not in preview and "$888B" not in preview
    assert "End market" not in preview and "Product demand." in preview
    assert "$500.0M" in preview and "20% operating margin" in preview
    assert "2.0x net income" in preview and "free cash flow of $150.0M" in preview
    assert "dividends paid $20.0M" in preview and "12.0%" in preview
    assert "current ratio 2.00x" in preview and "operating $200.0M" in preview
    assert "A retained outlook." in preview and "A quotation awaiting verification." in preview
    # The filler knows NI, but must not create an unreceived P&L/lead section in a preview.
    assert "## The Print" not in preview and "## Results That Matter" not in preview
    assert facts == original_facts

    thin = openai_service._partial_markdown_preview(text, None)
    assert thin and "MODEL CASH CLAIM" not in thin and "MODEL DISTRIBUTIONS" not in thin
    assert "MODEL RETURNS" not in thin and "## Segments" not in thin
    # These conditional fields survive final processing when XBRL is absent; preserve that policy.
    assert "MODEL WORKING CAPITAL" in thin and "MODEL CASH FLOWS" in thin
    assert "A retained earnings explanation." in thin and "A retained capital decision." in thin

    bank = {"net_interest_income": metric(100_000_000), "noninterest_income": metric(50_000_000)}
    bank_text = json.dumps({"sections": {
        "results_that_matter": {"table": [{"metric": "Revenue", "current_period": "$999B"}]},
        "earnings_quality": sections["earnings_quality"], "segments": sections["segments"],
    }})
    bank_preview = openai_service._partial_markdown_preview(bank_text, bank)
    assert bank_preview and "$999B" not in bank_preview and "MODEL CASH CLAIM" not in bank_preview
    assert "Net Interest Income" in bank_preview and "Non-Interest Income" in bank_preview
    assert "## Segments" not in bank_preview
    bank["revenue"] = metric(150_000_000)
    # With a reported total, final policy preserves the model row; this is not value verification.
    assert "$999B" in openai_service._partial_markdown_preview(bank_text, bank)

    monkeypatch.setattr(settings, "AI_FORWARD_QUOTE_GATE", True)
    guarded = openai_service._partial_markdown_preview(text, facts)
    assert guarded and "A quotation awaiting verification." not in guarded
    assert "A retained outlook." in guarded and "Product demand." in guarded
    assert "quotes" in sections["forward_signals"]  # parsed-copy mutation only
