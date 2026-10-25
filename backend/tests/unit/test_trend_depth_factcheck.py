"""The depth harness's fact-check gate (evals/trend_depth/factcheck.py): one planted case per failure
class and per accepted claim form, on a small synthetic evidence pack."""
from __future__ import annotations

import pytest

from evals.trend_depth import factcheck

PACK = {
    "values": {
        "F1": {"label": "Revenue", "period": "FY2016", "value": 4_860_400_000.0, "unit": "usd", "source": "filed"},
        "F10": {"label": "Revenue", "period": "FY2025", "value": 14_342_900_000.0, "unit": "usd", "source": "filed"},
        "F9": {"label": "Revenue", "period": "FY2024", "value": 14_202_000_000.0, "unit": "usd", "source": "filed"},
        "F29": {"label": "Operating margin", "period": "FY2024", "value": 28.0996, "unit": "pct", "source": "calculated"},
        "F30": {"label": "Operating margin", "period": "FY2025", "value": 24.9454, "unit": "pct", "source": "calculated"},
        "F40": {"label": "Net income", "period": "FY2025", "value": 4_504_900_000.0, "unit": "usd", "source": "filed"},
        "F100": {"label": "Free cash flow", "period": "FY2025", "value": 4_080_500_000.0, "unit": "usd", "source": "calculated"},
        "D440": {"label": "Revenue growth", "period": "FY2025", "value": 0.9921, "unit": "pct", "source": "derived"},
        "D445": {"label": "Revenue growth minus operating-cost growth", "period": "FY2025", "value": -0.3522, "unit": "pp", "source": "derived"},
        "D420": {"label": "Incremental operating margin (change in operating income / change in revenue)",
                 "period": "FY2025", "value": 69.68, "unit": "pct", "source": "derived"},
        "S7": {"label": "Lower 48 (segment)", "period": "FY2025", "value": 30_000_000_000.0, "unit": "usd", "source": "filed"},
    },
    "passages": [
        {"id": "P11", "fiscal_year": "FY2025", "text": "Net product sales of EYLEA decreased in 2025 compared to 2024, "
         "due to lower sales volumes and a lower net selling price. Sales fell by $2,019.3 million. "
         "Net sales increased $27,335 or 10% during 2026."},
        {"id": "P12", "fiscal_year": "FY2025", "text": "We expect capital expenditures of $18 billion to $19 billion in 2026."},
    ],
    "red_flags": [{"id": "R1", "evidence": ["F29", "F30"], "detail": "Operating margin fell."},
                  {"id": "R2", "evidence": [], "detail": "Segment members sum to 227% of consolidated revenue in FY2025."}],
}


def _check(text: str, kind: str = "fact") -> factcheck.SentenceResult:
    return factcheck.check_sentence({"text": text, "type": kind}, PACK)


@pytest.mark.parametrize(
    "text, kind",
    [
        ("Revenue rose from $4.9 billion in FY2016 to $14.3 billion in FY2025 [F1][F10].", "fact"),
        ("Revenue grew 1.0% in FY2025 [D440].", "comparison"),
        ("Revenue grew 195% between FY2016 and FY2025 [F1][F10].", "comparison"),
        ("Revenue compounded at 12.8% a year from FY2016 to FY2025 [F1][F10].", "comparison"),
        ("Operating margin fell 3.2 percentage points to 24.9% in FY2025 [F29][F30].", "comparison"),
        ("Free cash flow was about $4.1 billion in FY2025, 0.91x net income [F100][F40].", "fact"),
        ("Revenue nearly tripled over the decade [F1][F10].", "judgement"),
        ("EYLEA sales fell by $2,019.3 million in FY2025 on lower volumes and price [P11].", "cause"),
        ("Net sales rose $27.3 billion, or 10%, in 2026 [P11].", "cause"),
        ("Leverage is narrowing: incremental operating margin was 69.7% in FY2025 [D420].", "comparison"),
        ("The Lower 48 segment earned $30.0 billion in FY2025 [S7].", "fact"),
        ("Segment members sum to 227% of revenue, so they overlap [R2].", "fact"),
        ("The margin decline is the main risk to watch [R1].", "judgement"),
        ("Revenue held near $14.3 billion in FY2025 [F10] while the margin fell for a fourth straight year [F30].", "fact"),
        ("Operating margin fell 320 basis points in FY2025 [F29][F30].", "comparison"),
        ("Operating income fell to 24.9% of revenue in FY2025 [F30], against 28.1% in FY2024 [F29].", "comparison"),
        ("Net income was $4.5 billion in FY2025 [F40] on 1.0% revenue growth [D440].", "fact"),
        ("EYLEA sales fell by $2,019.3 million [P11], or $2.02 billion, in FY2025.", "cause"),
        # A year after "than" is the comparison's base, not the period of the figure before it.
        ("Revenue in FY2025 was 1.0% higher than FY2024 [D440].", "comparison"),
        # "<figure> of <metric> in <year>" binds the year to that figure, not to the next one.
        ("Revenue moved from $4.9 billion of total revenue in FY2016 to $14.3 billion in FY2025 [F1][F10].", "fact"),
        # A list chain links figures of one unit only: the dollar figure is not part of "28.1% in FY2024".
        ("Revenue grew 1.0% in FY2025 to $14.3 billion [D440][F10] and 28.1% in FY2024 [F29].", "comparison"),
        # "Fell back to 1.0%", "dropping below 1.0%": the rate's level, not a negative change.
        ("Revenue growth fell back to 1.0% in FY2025 [D440].", "comparison"),
        ("Cost growth dropping below the 1.0% revenue growth of FY2025 [D440] would restore leverage.", "comparison"),
        # A hyphenated range takes the scale of its second end: both ends are dollars in billions.
        ("Capital spending guidance for 2026 is $18-19 billion [P12].", "fact"),
        # The noun "growth" is not a direction word: the gap below is negative and the sentence says so.
        ("Revenue growth ran 0.4pp below operating-cost growth [D445] in FY2025.", "comparison"),
        # A word claim ("nearly tripled") parsed after the figures must not displace them in period binding.
        ("Revenue nearly tripled from $4.9 billion in FY2016 [F1] to $14.3 billion in FY2025 [F10].", "comparison"),
    ],
)
def test_reconciling_claims_pass(text: str, kind: str) -> None:
    result = _check(text, kind)
    assert result.failures == [], result.failures


@pytest.mark.parametrize(
    "text, kind, fragment",
    [
        ("Revenue was $15.1 billion in FY2025 [F10].", "fact", "matches nothing"),
        ("Revenue fell 1.0% in FY2025 [D440].", "comparison", "other way"),
        ("Operating margin rose 3.2 percentage points in FY2025 [F29][F30].", "comparison", "other way"),
        ("Operating margin fell 400 basis points in FY2025 [F29][F30].", "comparison", "matches nothing"),
        ("Operating margin was 24.9% in FY2024 [F30].", "fact", "not in the period"),
        ("Cash generation looks resilient at about $4 billion of free cash flow.", "judgement", "no citation"),
        ("EYLEA sales fell on competition [F10].", "cause", "no filing passage"),
        ("Revenue was $14.3 billion in FY2025 [F999].", "fact", "unknown citation"),
        ("Capital spending guidance for 2026 is $18-21 billion [P12].", "fact", "matches nothing"),
    ],
)
def test_each_failure_class_fails(text: str, kind: str, fragment: str) -> None:
    result = _check(text, kind)
    assert any(fragment in failure for failure in result.failures), result.failures


def test_identifiers_and_years_are_not_figures() -> None:
    claims = factcheck.parse_claims("In FY2025 the 10-K (Item 7, Note 3) discussed 2024 and COVID-19 [F10].")
    assert claims == []


def test_markdown_gold_format_reads_types() -> None:
    sentences = factcheck.sentences_from_markdown(
        "## The arc\nRevenue reached $14.3 billion in FY2025 [F10]. {fact} It fell [P11]. {cause}\n"
    )
    assert [(s["section"], s["type"]) for s in sentences] == [("The arc", "fact"), ("The arc", "cause")]


def test_run_passes_only_without_failures() -> None:
    passing = factcheck.check([{"text": "Revenue was $14.3 billion in FY2025 [F10].", "type": "fact"}], PACK)
    failing = factcheck.check([{"text": "Revenue was $15.0 billion in FY2025 [F10].", "type": "fact"}], PACK)
    assert passing["passed"] and not failing["passed"]


# Narrow fixes to gate artefacts (DEEPSEEK-ERRORS.md fix 7). Each case is a sentence from the recorded runs on its
# pack's real values: the sentence is true and passes, and a wrong mutation of it still fails.

def _pack(*rows: tuple, passages: tuple = ()) -> dict:
    """(id, label, period, value, unit) rows, as an evidence pack's values."""
    return {"values": {r[0]: {"label": r[1], "period": r[2], "value": r[3], "unit": r[4]} for r in rows},
            "passages": [{"id": pid, "fiscal_year": "FY2025", "text": text} for pid, text in passages], "red_flags": []}


JPM_OCF = _pack(("F60", "Operating cash flow", "FY2025", -147_782_000_000.0, "usd"))
USB_EFFICIENCY = _pack(("D195", "Efficiency ratio (noninterest expense / revenue)", "FY2024", 62.879092738247664, "pct"),
                       ("D220", "Efficiency ratio (noninterest expense / revenue)", "FY2025", 58.99439383321654, "pct"),
                       ("F29", "Operating margin", "FY2024", 28.0996, "pct"), ("F30", "Operating margin", "FY2025", 24.9454, "pct"),
                       passages=(("P10", "Noninterest expense in 2025 was $16.8 billion, compared with $17.2 billion in 2024."),))
ORCL_GAP = _pack(("D443", "Revenue growth minus operating-cost growth", "FY2026", -0.3497123669848605, "pp"),
                 ("D442", "Incremental operating margin (change in operating income / change in revenue)", "FY2026", 29.403494677646115, "pct"),
                 ("D395", "Incremental operating margin (change in operating income / change in revenue)", "FY2025", 52.38846327174402, "pct"))
CVX_NET_MARGIN = _pack(("D613", "Net margin window median", "FY2016..FY2025", 7.910239377, "pct"),
                       ("F28", "Net margin", "FY2023", 10.8677, "pct"),
                       ("F29", "Net margin", "FY2024", 9.1513540902, "pct"), ("F30", "Net margin", "FY2025", 6.6691246638, "pct"))
# Revenue growth minus operating-cost growth when both fell: costs fell less than revenue (CVX: its two growths, which
# DeepSeek's eval-v1 sentence cites beside it), and DE held out.
CVX_GAP = _pack(("D379", "Revenue growth minus operating-cost growth", "FY2025", -1.2221, "pp"),
                ("D373", "Operating expenses growth", "FY2025", -3.4218, "pct"), ("D358", "Revenue growth", "FY2025", -4.6439, "pct"))
DE_GAP = _pack(("D431", "Revenue growth minus operating-cost growth", "FY2025", -4.4113, "pp"))
# The same label where the recorded outputs state it with standing verbs: costs outgrew sales (PG, MSFT), revenue's
# growth trailed by 4.4pp (REGN).
PG_GAP = _pack(("D482", "Revenue growth minus operating-cost growth", "FY2026", -2.1459, "pp"))
REGN_GAP = _pack(("D464", "Revenue growth minus operating-cost growth", "FY2025", -4.4303, "pp"))
MSFT_GAP = _pack(("D499", "Revenue growth minus operating-cost growth", "FY2026", 10.3489, "pp"))
# packs-v2's same-year net margin minus operating margin (CAT: net margin is 3.4pp below operating margin; TGT 1.3pp).
CAT_MARGIN_GAP = _pack(("D1168", "Net margin minus operating margin (pp, same year)", "FY2025", -3.3541, "pp"))
TGT_MARGIN_GAP = _pack(("D629", "Net margin minus operating margin (pp, same year)", "FY2025", -1.3476, "pp"))
# Margin bridges of two years: cost of revenue's effect in FY2023 and FY2024 (CAT), R&D's and other lines' in FY2025
# and FY2026 (MSFT); the FY2023 and FY2024 operating-margin changes.
CAT_BRIDGE = _pack(("D384", "Operating-margin effect of cost of revenue (pp)", "FY2023", 5.8069, "pp"),
                   ("D437", "Operating-margin effect of cost of revenue (pp)", "FY2024", 1.7474, "pp"),
                   ("D370", "Operating margin change", "FY2023", 6.0346, "pp"),
                   ("D423", "Operating margin change", "FY2024", 0.8351, "pp"))
MSFT_BRIDGE = _pack(("D447", "Operating-margin effect of R&D (pp)", "FY2025", 0.507, "pp"),
                    ("D448", "Operating-margin effect of other lines (residual, pp)", "FY2025", 1.4113, "pp"),
                    ("D501", "Operating-margin effect of R&D (pp)", "FY2026", 0.8152, "pp"),
                    ("D502", "Operating-margin effect of other lines (residual, pp)", "FY2026", 1.2233, "pp"))
# Haiku-low VRTX: FY2025's operating margin recovered to 34.8% from -2.1% in FY2024.
VRTX_MARGIN = _pack(("D663", "Operating margin window median", "FY2016..FY2025", 31.7702, "pct"),
                    ("F33", "Operating margin", "FY2023", 38.8279, "pct"), ("F34", "Operating margin", "FY2024", -2.1134, "pct"),
                    ("F35", "Operating margin", "FY2025", 34.7737, "pct"))
JPM_SHARES = _pack(("X102", "Share repurchases (cash)", "FY2025", 31_591_000_000.0, "usd"),
                   ("X101", "Share repurchases (cash)", "FY2024", 18_830_000_000.0, "usd"),
                   ("D224", "Diluted share count change", "FY2025", -3.386592566863494, "pct"),
                   ("D80", "Diluted share count change", "FY2019", -5.377855887521968, "pct"))
NVDA_GROWTH = _pack(("D448", "Revenue growth", "FY2026", 65.4735357900948, "pct"),
                    ("D622", "Data Center (product) contribution to revenue growth (pp)", "FY2026", 60.19372092845047, "pp"),
                    ("F30", "Gross margin", "FY2026", 71.0680843575, "pct"))
AMD_FCF = _pack(("D467", "Free cash flow margin", "FY2025", 19.443401945783652, "pct"),
                ("D803", "Free cash flow margin window high (FY2021)", "FY2016..FY2025", 19.593525617622003, "pct"),
                ("F10", "Revenue", "FY2025", 34_639_000_000.0, "usd"))
# runs/plant-sem: the two year swaps planted into Sonnet's REGN analysis, which the gate must keep catching.
REGN_PLANT = _pack(("F30", "Operating margin", "FY2025", 24.9454433901, "pct"),
                   ("D749", "Operating margin window low (FY2025)", "FY2016..FY2025", 24.9454433901, "pct"),
                   ("D751", "Operating margin window median", "FY2016..FY2025", 34.55631469145, "pct"),
                   ("D750", "Operating margin window high (FY2021)", "FY2016..FY2025", 55.6680376065, "pct"),
                   ("D453", "Operating margin change", "FY2025", -3.1541200517000014, "pp"),
                   ("D465", "Operating-margin effect of R&D (pp)", "FY2025", -4.65236960769375, "pp"),
                   ("D466", "Operating-margin effect of SG&A (pp)", "FY2025", 1.9780588982488965, "pp"))


def test_a_minus_sign_after_the_dollar_sign_is_parsed() -> None:
    claim, = factcheck.parse_claims("Operating cash flow was $-147.8 billion in FY2025 [F60].")
    assert (claim.text, claim.value, claim.unit, claim.scale) == ("$-147.8 billion", -147.8, "usd", 1e9)


@pytest.mark.parametrize(
    "pack, text, fragment",
    [
        # "$-X" (Sonnet JPM).
        (JPM_OCF, "Operating cash flow is not a meaningful earnings-quality measure for a bank, and was $-147.8 billion in FY2025 [F60].", None),
        (JPM_OCF, "Operating cash flow was $-150.0 billion in FY2025 [F60].", "matches nothing"),
        # "Improved" for a metric where lower is better (Sonnet USB): the efficiency ratio fell 3.9pp.
        (USB_EFFICIENCY, "The ratio improved 3.9pp from 62.9% in FY2024 [D195] to 59.0% [D220], as prior-year merger "
                         "charges and the FDIC special assessment dropped out [P10].", None),
        (USB_EFFICIENCY, "The ratio worsened 3.9pp from 62.9% in FY2024 [D195] to 59.0% [D220].", "other way"),
        (USB_EFFICIENCY, "Operating margin improved 3.2pp in FY2025 [F29][F30].", "other way"),
        # ... and only those words: a plain rise or fall of the ratio reads as it is.
        (USB_EFFICIENCY, "The efficiency ratio fell 3.9pp in FY2025 [D195][D220].", None),
        (USB_EFFICIENCY, "The efficiency ratio rose 3.9pp in FY2025 [D195][D220].", "other way"),
        # A difference labelled "A minus B", said as B against A (Sonnet ORCL): costs did grow 0.35pp faster.
        (ORCL_GAP, "Operating costs grew 0.3pp faster than revenue in FY2026, and incremental operating margin was "
                   "29.4% against 52.4% in FY2025 [D443][D442][D395].", None),
        (ORCL_GAP, "Revenue grew 0.3pp faster than operating costs in FY2026 [D443].", "other way"),
        # The comparative decides with the naming order: "slower" or "less" says the side named first trails.
        (ORCL_GAP, "Operating costs grew 0.3pp slower than revenue in FY2026 [D443].", "other way"),
        (ORCL_GAP, "Operating costs rose 0.3pp less than revenue in FY2026 [D443].", "other way"),
        (ORCL_GAP, "Revenue grew 0.3pp slower than operating costs in FY2026 [D443].", None),
        (ORCL_GAP, "Operating costs grew faster than revenue by 0.3pp in FY2026 [D443].", None),
        (CVX_GAP, "Operating costs grew 1.2pp slower than revenue in FY2025 [D379].", "other way"),
        (CVX_GAP, "Operating costs fell 1.2pp less than revenue in FY2025 [D379].", None),
        (CVX_GAP, "Operating costs fell 1.2pp more than revenue in FY2025 [D379].", "other way"),
        (CVX_GAP, "Revenue fell 1.2pp more than operating costs in FY2025 [D379].", None),
        (DE_GAP, "Operating costs fell 4.4pp less than revenue in FY2025 [D431].", None),
        # The sides go by their key nouns, as a sentence names them: costs, expenses or spending, and sales (review 7:
        # with "costs" unread, "slower" reversed the wrong side, and the false sentences passed) ...
        (ORCL_GAP, "Costs grew 0.3pp faster than revenue in FY2026 [D443].", None),
        (ORCL_GAP, "Costs grew 0.3pp slower than revenue in FY2026 [D443].", "other way"),
        (PG_GAP, "In FY2026 expenses rose 2.1pp faster than sales [D482].", None),
        (PG_GAP, "In FY2026 costs grew 2.1pp slower than sales [D482].", "other way"),
        (PG_GAP, "In FY2026 expenses rose 2.1pp more slowly than sales [D482].", "other way"),
        (CVX_GAP, "Costs fell 1.2pp less than revenue in FY2025 [D379].", None),
        (CVX_GAP, "Costs fell 1.2pp more than revenue in FY2025 [D379].", "other way"),
        (ORCL_GAP, "Operating costs grew 0.3pp more slowly than revenue in FY2026 [D443].", "other way"),
        (ORCL_GAP, "Operating expenses grew 0.3pp faster than revenue in FY2026 [D443].", None),
        (ORCL_GAP, "Sales grew 0.3pp slower than operating costs in FY2026 [D443].", None),
        # ... the side named first is the last one before the comparative, and one is enough; a first side the label
        # does not have keeps the cited sign, as the gate read it before; "more than 0.3pp" is a bound.
        (ORCL_GAP, "Operating costs grew 0.3pp faster in FY2026 [D443].", None),
        (ORCL_GAP, "Operating income grew 0.3pp slower than revenue in FY2026 [D443].", "other way"),
        (ORCL_GAP, "Operating costs grew more than 0.3pp in FY2026 [D443].", "other way"),
        (ORCL_GAP, "Operating-cost growth rose more than 0.3pp above revenue growth in FY2026 [D443].", None),
        # A standing gives the sign whatever the direction word: an outpacing before the figure or a position after it
        # (the recorded forms: "outgrew", "trailed", "ran ahead of"; "top-line" is no verb) ...
        (REGN_GAP, "Revenue growth beat operating-cost growth by 4.4pp in FY2025 [D464].", "other way"),
        (REGN_GAP, "Revenue outgrew operating costs by 4.4pp in FY2025 [D464].", "other way"),
        (REGN_GAP, "Revenue growth ran 4.4pp ahead of operating-cost growth in FY2025 [D464].", "other way"),
        (REGN_GAP, "Revenue growth trailed operating-cost growth by 4.4pp in FY2025 [D464].", None),
        (REGN_GAP, "Operating-cost growth outran revenue growth by 4.4pp in FY2025 [D464].", None),
        (REGN_GAP, "Top-line growth trailed operating costs by 4.4pp in FY2025 [D464].", None),
        (REGN_GAP, "Operating costs trailed top-line growth by 4.4pp in FY2025 [D464].", "other way"),
        (REGN_GAP, "Revenue, which exceeded guidance, trailed operating-cost growth by 4.4pp in FY2025 [D464].", None),
        # With no direction word, "more" or "less" says where the side named first stands.
        (REGN_GAP, "Revenue growth was 4.4pp more than operating-cost growth in FY2025 [D464].", "other way"),
        (REGN_GAP, "Revenue growth was 4.4pp less than operating-cost growth in FY2025 [D464].", None),
        (MSFT_GAP, "Operating costs outgrew revenue by 10.3pp in FY2026 [D499].", "other way"),
        (MSFT_GAP, "Operating cost growth trailed revenue growth by 10.3pp in FY2026 [D499].", None),
        (PG_GAP, "In FY2026 costs outgrew sales by 2.1pp [D482].", None),
        # ... said the other way of a side named as its fall (DeepSeek CVX's "cost reduction"); a move's fall noun is
        # its direction word.
        (CVX_GAP, "The revenue decline outran cost reduction by 1.2pp in FY2025 [D379].", None),
        (CVX_GAP, "Cost reduction outran the revenue decline by 1.2pp in FY2025 [D379].", "other way"),
        (CVX_GAP, "The revenue decline was 1.2pp more than the cost reduction in FY2025 [D379].", None),
        # A side is its whole phrase: "operating income" or "operating expenses" before "net margin" is not
        # operating margin named first.
        (CAT_MARGIN_GAP, "Below operating income, net margin fell 3.4pp under operating margin in FY2025 [D1168].", None),
        (CAT_MARGIN_GAP, "As operating expenses held, net margin dropped 3.4pp below operating margin in FY2025 [D1168].", None),
        # A gap between two levels of one year carries no direction, like the difference of the two margins an arm on
        # packs/ cites: "narrowed to" and "slipped to" read by magnitude (review 7: they failed on packs-v2 alone), and
        # the backstop gap_direction reads which margin is above (test_trend_depth_probes).
        (CAT_MARGIN_GAP, "The gap between net and operating margin narrowed to 3.4pp in FY2025 [D1168].", None),
        (TGT_MARGIN_GAP, "Net margin slipped to 1.3pp below operating margin in FY2025 [D629].", None),
        (CAT_MARGIN_GAP, "Below operating income, net margin rose 3.4pp above operating margin in FY2025 [D1168].", None),
        # "<year> <noun> from": the figure is the year before's level, where the move started (DeepSeek CVX), or the
        # year's own, the level a move would continue from (its repair) ...
        (CVX_NET_MARGIN, "Watch net margin against the 7.9% window median; a print below it would extend the FY2025 "
                         "slide from 9.2% [D613][F29][F30].", None),
        (CVX_NET_MARGIN, "Watch net margin against the 7.9% window median; a print below it would extend the FY2025 "
                         "slide from 6.7% [D613][F30].", None),
        (VRTX_MARGIN, "Operating margin should hold at or above its 31.8% window median [D663]; a fall below it would "
                      "reverse the FY2025 recovery from 34.8% [F35], checked in the FY2026 10-K.", None),
        (CVX_NET_MARGIN, "A print below it would extend the FY2025 slide from 10.9% [D613][F28].", "not in the period"),
        # ... after "<year> <metric> fell from" only the year before's ...
        (CVX_NET_MARGIN, "FY2025 net margin fell from 9.2% [F29].", None),
        (CVX_NET_MARGIN, "FY2025 net margin fell from 6.7% [F30].", "not in the period"),
        # ... and after any other verb the year's own: "came from" or "benefited from" names a source (MSFT).
        (MSFT_BRIDGE, "The FY2026 gain came from 1.2pp of other lines and 0.8pp of R&D [D502][D501].", None),
        (MSFT_BRIDGE, "The FY2026 gain came from 1.4pp of other lines [D448].", "not in the period"),
        (MSFT_BRIDGE, "In FY2026 margin benefited from 0.5pp of R&D leverage [D447].", "not in the period"),
        # "Xpp of the <year> gain of Ypp": the year is the whole's, and binds both parts (CAT, MSFT).
        (CAT_BRIDGE, "Cost of revenue supplied 5.8pp of the FY2023 gain of 6.0pp [D384][D370].", None),
        (CAT_BRIDGE, "Cost of revenue supplied 1.7pp of the FY2023 gain of 6.0pp [D437][D370].", "not in the period"),
        (CAT_BRIDGE, "Cost of revenue supplied 5.8pp of the FY2023 gain of 0.8pp [D384][D423].", "not in the period"),
        (MSFT_BRIDGE, "R&D added 0.5pp in the FY2026 gain of 1.2pp [D447][D502].", "not in the period"),
        # "Since FY2019's 5.4%" keeps binding forward under the rules above (Sonnet JPM).
        (JPM_SHARES, "Buybacks rose to $31.6 billion from $18.8 billion [X102][X101] and diluted shares fell 3.4% [D224], "
                     "the largest fall since FY2019's 5.4% [D80].", None),
        (JPM_SHARES, "Diluted shares fell 3.4% [D224], the largest fall since FY2018's 5.4% [D80].", "not in the period"),
        # "Xpp of the Ypp total": the total is the cited revenue growth (DeepSeek NVDA), and only that.
        (NVDA_GROWTH, "FY2026 growth slowed to 65.5% as Data Center still contributed 60.2pp of the 65.5pp total [D448][D622].", None),
        (NVDA_GROWTH, "Data Center contributed 60.2pp of the 64.0pp total [D448][D622].", "matches nothing"),
        (NVDA_GROWTH, "Data Center contributed 60.2pp of the 71.1pp total [D448][D622][F30].", "matches nothing"),
        # "matched the FY2021 high of 19.6%": the year names the figure after it (DeepSeek AMD) ...
        (AMD_FCF, "Free cash flow margin of 19.4% matched the FY2021 high of 19.6% [D467][D803].", None),
        (AMD_FCF, "Free cash flow margin of 19.4% matched the FY2022 high of 19.6% [D467][D803].", "not in the period"),
        (AMD_FCF, "Free cash flow margin of 19.4% in FY2021 matched the high of 19.6% [D467][D803].", "not in the period"),
        # ... but with no figure after it, "the <year> <noun>" still binds back.
        (AMD_FCF, "Revenue of $34.6 billion was the FY2024 high [F10].", "not in the period"),
        # The planted year swaps stay caught.
        (REGN_PLANT, "FY2023 operating margin of 24.9% is the window low, below the 34.6% median and the 55.7% high of "
                     "FY2021 [F30][D749][D751][D750].", "not in the period"),
        (REGN_PLANT, "Of the 3.2pp FY2023 decline, R&D cost 4.7pp while SG&A recovered 2.0pp [D453][D465][D466].", "not in the period"),
        (REGN_PLANT, "Of the 3.2pp FY2025 decline, R&D cost 4.7pp while SG&A recovered 2.0pp [D453][D465][D466].", None),
    ],
)
def test_gate_artefact_fixes_keep_their_mutations_failing(pack: dict, text: str, fragment: str) -> None:
    failures = factcheck.check_sentence({"text": text, "type": "comparison"}, pack).failures
    if fragment is None:
        assert failures == [], failures
    else:
        assert any(fragment in failure for failure in failures), failures


@pytest.mark.parametrize(
    "pack, text, claim, matched",
    [
        # A compared "A minus B" value is read as the side named first minus the other, which the semantic auditor is
        # shown (semantics._computed): eval-v1's DeepSeek PG and Sonnet MSFT, which name costs first ...
        (PG_GAP, "In FY2026 costs outgrew sales by 2.1pp [D482].", "2.1pp", "reversed D482"),
        (MSFT_GAP, "Operating cost growth trailed revenue growth by 10.3pp in FY2026 [D499].", "10.3pp", "reversed D499"),
        # ... a side found once its label's parenthesis is dropped ...
        (CAT_MARGIN_GAP, "Operating margin was 3.4pp above net margin in FY2025 [D1168].", "3.4pp", "reversed D1168"),
        # ... and DeepSeek CVX's sentence as eval-v1 read it: revenue's fall, named first, outran the costs' fall.
        (CVX_GAP, "Operating costs fell 3.4% while revenue fell 4.6%, so the revenue decline outran cost reduction by 1.2pp "
                  "[D373][D358][D379].", "1.2pp", "cited"),
    ],
)
def test_a_compared_gap_reads_as_the_side_named_first_minus_the_other(pack: dict, text: str, claim: str, matched: str) -> None:
    result = factcheck.check_sentence({"text": text, "type": "comparison"}, pack)
    found = next(c for c in result.claims if c["claim"] == claim)
    assert (result.failures, found["status"], found["matched"]) == ([], "verified", matched)


def test_backstops_are_off_by_default_and_fail_only_when_asked() -> None:
    pack = {**_pack(("D14", "Net cash (cash and investments less debt)", "FY2016", -49_990_000_000.0, "usd"),
                    ("D352", "Net cash (cash and investments less debt)", "FY2025", -89_591_000_000.0, "usd")),
            "series_keys": {"net_cash|FY2016": "D14", "net_cash|FY2025": "D352"}}
    sentences = [{"section": "balance_sheet", "type": "fact",
                  "text": "Net debt has deepened for nine straight years, from -$50.0 billion to -$89.6 billion [D14][D352]."}]
    default, backstopped = factcheck.check(sentences, pack), factcheck.check(sentences, pack, backstops=True)
    assert default["passed"] and "backstop_failures" not in default
    assert not backstopped["passed"] and backstopped["backstop_failures"] == 2
    assert all(f["failure"].startswith("backstop R2a:") for f in backstopped["failures"])
