"""The depth harness's backstop probes (evals/trend_depth/probes.py, DEEPSEEK-ERRORS.md fix 12): each probe on the
recorded sentence it was written for, with its pack's real values, and on the true sentences it must leave alone
(the near misses in the recorded runs, and synthetic ones). Gate kinds fail ``factcheck.check(backstops=True)``;
the logic measures never do."""
from __future__ import annotations

import pytest

from evals.trend_depth import factcheck, probes


def _pack(*rows: tuple, passages: tuple = (), flags: tuple = ()) -> dict:
    """(id, label, period, value, unit, series) rows, as an evidence pack with its series keys."""
    return {"values": {r[0]: {"label": r[1], "period": r[2], "value": r[3], "unit": r[4]} for r in rows},
            "series_keys": {f"{r[5]}|{r[2]}": r[0] for r in rows},
            "passages": [{"id": pid, "fiscal_year": "FY2025", "text": text} for pid, text in passages],
            "red_flags": [{"id": fid, "evidence": [], "detail": "Flag."} for fid in flags]}


def _kinds(text: str, pack: dict) -> list[tuple[str, str]]:
    return [(hit["kind"], hit["claim"]) for hit in probes.probe([{"section": "s", "text": text, "type": "comparison"}], pack)]


OCF_NI = "Operating cash flow / net income"
FCF_NI_MEDIAN = "Free cash flow / net income window median"
CVX = _pack(("F60", "Operating cash flow", "FY2025", 33_939_000_000.0, "usd", "operating_cash_flow"),
            ("F20", "Net income", "FY2025", 12_300_000_000.0, "usd", "net_income"),
            ("D346", OCF_NI, "FY2025", 2.759268292682927, "x", "ocf_to_ni"),
            ("D622", FCF_NI_MEDIAN, "FY2017..FY2025", 1.0974974650927694, "x", "median:fcf_to_ni"),
            ("D611", "Net margin window low (FY2020)", "FY2016..FY2025", -5.8674090462, "pct", "low:net_margin"),
            ("D153", "Revenue growth", "FY2020", -32.45558216851964, "pct", "g:revenue"),
            ("D274", "Revenue growth", "FY2023", -16.462113466572205, "pct", "g:revenue"),
            ("D316", "Revenue growth", "FY2024", -1.7769268661794804, "pct", "g:revenue"),
            ("D358", "Revenue growth", "FY2025", -4.6439244315302926, "pct", "g:revenue"), flags=("R1",))
REGN = _pack(("F80", "Operating cash flow", "FY2025", 4_978_900_000.0, "usd", "operating_cash_flow"),
             ("F40", "Net income", "FY2025", 4_504_900_000.0, "usd", "net_income"),
             ("F100", "Free cash flow", "FY2025", 4_080_500_000.0, "usd", "free_cash_flow"),
             ("D428", OCF_NI, "FY2025", 1.1052187617927145, "x", "ocf_to_ni"),
             ("D429", "Free cash flow / net income", "FY2025", 0.9057914715088016, "x", "fcf_to_ni"),
             ("D763", FCF_NI_MEDIAN, "FY2016..FY2025", 0.8844768788499369, "x", "median:fcf_to_ni"),
             ("D783", "Free cash flow / net income: biopharma peer median (n=7)", "FY2025", 1.1111633372502938, "x", "peer_median:fcf_to_ni"))
NET_CASH = "Net cash (cash and investments less debt)"
DUK = _pack(("D14", NET_CASH, "FY2016", -49_990_000_000.0, "usd", "net_cash"),
            ("D352", NET_CASH, "FY2025", -89_591_000_000.0, "usd", "net_cash"),
            ("F100", "Free cash flow", "FY2025", -1_694_000_000.0, "usd", "free_cash_flow"), flags=("R3",))
CAT_DEBT = _pack(("D350", NET_CASH, "FY2023", -22_137_000_000.0, "usd", "net_cash"),
                 ("D456", NET_CASH, "FY2025", -26_230_000_000.0, "usd", "net_cash"))
ORCL = _pack(("D320", NET_CASH, "FY2024", -76_208_000_000.0, "usd", "net_cash"),
             ("D414", NET_CASH, "FY2026", -97_647_000_000.0, "usd", "net_cash"))
NEE = _pack(("D231", NET_CASH, "FY2025", -92_199_000_000.0, "usd", "net_cash"),
            ("D9", NET_CASH, "FY2018", -34_325_000_000.0, "usd", "net_cash"), flags=("R2",))
CAT = _pack(("D457", "Net cash % of revenue", "FY2025", -38.80809007382858, "pct", "net_cash_to_revenue"),
            ("D1152", "Net cash % of revenue: industrials peer median (n=7)", "FY2025", -35.61360562467165, "pct", "peer_median:net_cash_to_revenue"),
            ("D1151", "Net cash % of revenue: percentile vs industrials peers (n=7)", "FY2025", 42.857142857142854, "pctile", "peer_pctile:net_cash_to_revenue"))
TGT = _pack(("D410", NET_CASH, "FY2025", -4_299_000_000.0, "usd", "net_cash"),
            ("D411", "Net cash % of revenue", "FY2025", -4.1028822294330975, "pct", "net_cash_to_revenue"),
            ("D613", "Net cash % of revenue: retail peer median (n=6)", "FY2025", -3.488050753330144, "pct", "peer_median:net_cash_to_revenue"),
            ("D612", "Net cash % of revenue: percentile vs retail peers (n=6)", "FY2025", 50.0, "pctile", "peer_pctile:net_cash_to_revenue"))
DE = _pack(("X82", "Interest expense", "FY2025", 3_170_000_000.0, "usd", "interest_expense"),
           ("D400", "Effective tax rate", "FY2025", 20.12146396036439, "pct", "tax_rate"),
           ("F30", "Operating margin", "FY2024", 17.4781498956, "pct", "operating_margin"),
           ("F49", "Net margin", "FY2024", 13.7288266687, "pct", "net_margin"),
           ("F50", "Net margin", "FY2025", 11.0038525523, "pct", "net_margin"))
COP = _pack(("F8", "Revenue", "FY2023", 48_522_000_000.0, "usd", "revenue"),
            ("D274", "Revenue growth", "FY2023", -20.519582630346115, "pct", "g:revenue"),
            ("D844", "Revenue 3-year CAGR", "FY2022..FY2025", -5.314358606609759, "pct", "cagr3:revenue"),
            ("D275", "Net income growth", "FY2023", -41.34368308351178, "pct", "g:net_income"),
            ("D309", "Net income growth", "FY2024", -15.62471479419549, "pct", "g:net_income"),
            ("D343", "Net income growth", "FY2025", -13.596538669551109, "pct", "g:net_income"),
            ("D845", "Net income 3-year CAGR", "FY2022..FY2025", -24.660905733907523, "pct", "cagr3:net_income"),
            ("D387", "Free cash flow / net income", "FY2024", 0.4459599285109585, "x", "fcf_to_ni"),
            ("D437", "Free cash flow / net income", "FY2025", 0.40405889982452126, "x", "fcf_to_ni"))
COST = _pack(("D422", "Free cash flow / net income", "FY2026", 1.01690873618036, "x", "fcf_to_ni"),
             ("D701", "Free cash flow / net income window median", "FY2017..FY2026", 0.9922795316906244, "x", "median:fcf_to_ni"),
             ("D423", "Capex / D&A", "FY2026", 2.406507105459985, "x", "capex_to_dna"),
             passages=(("P9", "SG&A expenses as a percentage of net sales decreased 10 basis points compared to 2025. Changes in "
                              "foreign currencies relative to the U.S. dollar increased SG&A expenses by $126, attributable to our "
                              "Other International and Canadian operations."),))
SNAP = _pack(("D398", "Total debt", "FY2025", 3_536_829_000.0, "usd", "total_debt"),
             ("D350", "Total debt", "FY2024", 3_643_929_000.0, "usd", "total_debt"),
             ("D218", "Revenue growth", "FY2021", 64.24660080921527, "pct", "g:revenue"),
             ("D311", "Revenue growth", "FY2023", 0.09274536941362892, "pct", "g:revenue"),
             ("D406", "Revenue growth", "FY2025", 10.632469367131483, "pct", "g:revenue"),
             ("F120", "Investing cash flow", "FY2026", -52_228_000_000.0, "usd", "investing_cash_flow"),
             ("F119", "Investing cash flow", "FY2025", -20_421_000_000.0, "usd", "investing_cash_flow"),
             passages=(("P1", "In February 2025, we repurchased $ 45.3 million of the 2026 Notes."),
                       ("P2", "In February 2025, we sold $ 1.50 billion principal amount of senior notes due in 2033.")))


@pytest.mark.parametrize(
    "pack, text, expected",
    [
        # R1: operating cash flow's ratio set against free cash flow's median (DeepSeek CVX, DeepSeek REGN dev-v3) ...
        (CVX, "Operating cash flow of $33.9 billion was 2.76x net income, well above the 1.10x window median [F60][F20][D346][D622].",
         [("R1", "1.10x")]),
        (REGN, "Operating cash flow of $4,978.9 million was 1.11x net income in FY2025 [F80][F40][D428], above the 0.88x window "
               "median [D763] but below the 1.11x peer median [D783].", [("R1", "0.88x")]),
        # ... not a median set against its own ratio (Sonnet REGN), one stated before the ratio (Sonnet CAT dev-v3),
        # nor a margin's reference named in words (Haiku CVX).
        (REGN, "FY2025 operating cash flow of $4.98 billion was 1.11x net income, while free cash flow of $4.08 billion was "
               "0.91x, against a 0.88x window median [F80][D428][F100][D429][D763].", []),
        (REGN, "Free cash flow to net income staying above the 0.88x median while operating cash flow runs at 1.11x net "
               "income would show conversion holding [D763][D428].", []),
        (CVX, "FY2020 was the weakest year, with revenue down 32.5% [D153] and a net margin of -5.9% [D611]; the filings "
              "cited do not explain that year.", []),
        # R2a: net cash's minus sign under "net debt" (DeepSeek DUK, DeepSeek CAT watch item) ...
        (DUK, "Net debt has deepened for nine straight years, from -$50.0 billion to -$89.6 billion [D14][D352][R3].",
         [("R2a", "-$50.0 billion"), ("R2a", "-$89.6 billion")]),
        (CAT_DEBT, "Net debt: a further widening beyond the FY2025 -$26.2 billion would extend the two-year trend; a narrowing "
                   "back toward the FY2023 -$22.1 billion would reverse it [D456][D350].",
         [("R2a", "-$26.2 billion"), ("R2a", "-$22.1 billion")]),
        # ... never net cash's sign under its own name, as subject (DeepSeek ORCL) or attached (DeepSeek NEE, TGT
        # below), nor a minus sign on another metric.
        (ORCL, "Net cash has fallen into deeper net debt for two straight years, from -$76.2 billion to -$97.6 billion [D320][D414].", []),
        (NEE, "Net debt reached $92.2 billion in FY2025, down from net cash of -$34.3 billion in FY2018, a seventh "
                   "straight year of deterioration [D231][D9][R2].", []),
        (DUK, "Net cash was -$89.6 billion in FY2025, a net debt position [D352].", []),
        (DUK, "Net debt rose while free cash flow fell to -$1.7 billion [F100].", []),
        # R2c: "better" that the signed net-cash values contradict (DeepSeek CAT, DeepSeek TGT), before or after both
        # numbers; "worse" there is true.
        (CAT, "Net debt is 38.8% of revenue, better than the -35.6% peer median but only the 43rd percentile of seven "
              "industrials peers [D457][D1152][D1151].", [("R2a", "-35.6%"), ("R2c", "-35.6%")]),
        (TGT, "Net debt was $4.3 billion, or 4.1% of revenue, better than the retail peer median of -3.5% net cash and at "
              "the 50th percentile of six peers [D410][D411][D613][D612].", [("R2c", "-3.5%")]),
        (CAT, "Net cash of -38.8% of revenue against the -35.6% peer median is the better position [D457][D1152].", [("R2c", "-35.6%")]),
        (CAT, "Net cash of -38.8% of revenue against the -35.6% peer median is the worse position [D457][D1152].", []),
        (TGT, "Net debt of 4.1% of revenue is worse than the -3.5% net cash retail peer median [D411][D613].", []),
        # R3: two margins of two years (DeepSeek DE); the same year's pair is fine.
        (DE, "Below the line, interest expense of $3.17 billion [X82] and a 20.1% tax rate [D400] left net margin 6.5pp under "
             "operating margin [F30][F50].", [("R3", "6.5pp")]),
        (DE, "In FY2024 net margin of 13.7% sat 3.7pp under the 17.5% operating margin [F49][F30].", []),
        # U1: a fall stated as a CAGR with no sign (DeepSeek COP) ...
        (COP, "Revenue then fell 20.5% in FY2023 on lower realized prices, and the three years to FY2025 show a 5.3% CAGR "
              "[F8][D274][D844].", [("U1", "5.3%")]),
        # ... but not the six claims the first unsigned-fall rule failed (REPORT.md 7.5: Sonnet CVX, Haiku-low COP),
        # a signed or worded fall, or a bound (DeepSeek KO's "below 80%").
        (CVX, "Revenue declined three years running: 16.5% in FY2023, 1.8% in FY2024 and 4.6% in FY2025 [R1][D274][D316][D358].", []),
        (COP, "Net income fell three years running: 41.3% in FY2023 [D275], 15.6% in FY2024 [D309] and 13.6% in FY2025 [D343]; "
              "the three-year CAGR is -24.7% [D845].", []),
        (COP, "The three years to FY2025 show a -5.3% CAGR [D844].", []),
        (COP, "The three years to FY2025 show a 5.3% CAGR decline [D844].", []),
        (COP, "Free cash flow stayed below 80% of net income in FY2024 and FY2025, at 0.45x and 0.40x [D387][D437].", []),
        # Unitless dollars: a table literal in millions read as dollars (DeepSeek COST); with its scale it is fine.
        (COST, "SG&A fell 10 basis points as a share of sales, though excluding gasoline inflation it rose one basis point, "
               "and currency moves added $126 of expense [P9].", [("unitless_dollars", "$126")]),
        (COST, "Currency moves added $126 million of SG&A expense [P9].", []),
        # Logic measures: "rose to" a level below the year before (DeepSeek SNAP) ...
        (SNAP, "Debt rose to $3,536.8 million as $1.4 billion of notes were repurchased and $1.50 billion of 2033 Notes "
               "issued in February 2025 [D398][P1][P2].", [("logic_direction", "$3,536.8 million")]),
        # ... not an outflow growing in size (Sonnet NVDA), nor a move measured from the figure the sentence names.
        (SNAP, "Investing outflow rose to $52.2 billion, driven by equity investment purchases [F120].", []),
        (SNAP, "Debt fell to $3,536.8 million from $3,643.9 million [D398][D350].", []),
        (SNAP, "Debt fell to $3,643.9 million from $3,536.8 million [D350][D398].", [("logic_direction", "$3,643.9 million")]),
        # "From A to B" from the later year, or against its direction word.
        (SNAP, "Total debt went from $3,536.8 million to $3,643.9 million [D398][D350].", [("logic_from_order", "$3,536.8 million")]),
        (SNAP, "Total debt rose from $3,643.9 million to $3,536.8 million [D350][D398].", [("logic_from_order", "$3,643.9 million")]),
        (SNAP, "Total debt fell from $3,643.9 million to $3,536.8 million [D350][D398].", []),
        # "Recover toward" a lower level (DeepSeek COST watch item); recovering upwards is fine (Sonnet SNAP).
        (COST, "Whether free cash flow per dollar of net income recovers toward the 0.99x median from 1.02x, or capex keeps "
               "the capex-to-D&A ratio above 2.41x [D422][D701][D423].", [("logic_recover", "0.99x")]),
        (SNAP, "Growth slowed from 64.2% in FY2021 to 0.1% in FY2023, before recovering to 10.6% in FY2025 [D218][D311][D406].", []),
    ],
)
def test_each_probe_fires_on_its_error_and_spares_true_sentences(pack: dict, text: str, expected: list) -> None:
    assert sorted(_kinds(text, pack)) == sorted(expected)


def test_backstops_fail_gate_kinds_but_never_logic_measures() -> None:
    def gate(text: str, pack: dict) -> dict:
        return factcheck.check([{"section": "s", "text": text, "type": "fact"}], pack, backstops=True)

    logic_only = gate("Debt rose to $3,536.8 million in FY2025 [D398].", SNAP)
    unsigned = gate("Revenue then fell 20.5% in FY2023 on lower realized prices, and the three years to FY2025 show a 5.3% "
                    "CAGR [F8][D274][D844].", COP)
    assert logic_only["passed"] and logic_only["backstop_failures"] == 0
    assert not unsigned["passed"] and [f["failure"][:12] for f in unsigned["failures"]] == ["backstop U1:"]
    assert set(probes.GATE_KINDS).isdisjoint(probes.MEASURE_KINDS)
