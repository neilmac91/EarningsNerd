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
                       ("F29", "Net margin", "FY2024", 9.1513540902, "pct"), ("F30", "Net margin", "FY2025", 6.6691246638, "pct"))
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
        # A difference labelled "A minus B", said as B against A (Sonnet ORCL): costs did grow 0.35pp faster.
        (ORCL_GAP, "Operating costs grew 0.3pp faster than revenue in FY2026, and incremental operating margin was "
                   "29.4% against 52.4% in FY2025 [D443][D442][D395].", None),
        (ORCL_GAP, "Revenue grew 0.3pp faster than operating costs in FY2026 [D443].", "other way"),
        # "<year> <noun> from": the figure is the year before's level (DeepSeek CVX); its repair's "from 6.7%",
        # FY2025's own level, is wrong.
        (CVX_NET_MARGIN, "Watch net margin against the 7.9% window median; a print below it would extend the FY2025 "
                         "slide from 9.2% [D613][F29][F30].", None),
        (CVX_NET_MARGIN, "Watch net margin against the 7.9% window median; a print below it would extend the FY2025 "
                         "slide from 6.7% [D613][F30].", "not in the period"),
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
