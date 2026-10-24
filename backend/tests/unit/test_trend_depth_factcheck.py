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
