"""The depth harness's backstop probes (evals/trend_depth/probes.py, DEEPSEEK-ERRORS.md fix 12): each probe on the
recorded sentence it was written for, with its pack's real values, and on the true sentences it must leave alone
(the near misses in the recorded runs, and synthetic ones). Gate kinds fail ``factcheck.check(backstops=True)``;
the logic measures never do. ``broken_debt`` and the series keys read the committed evidence packs: each break kind
(debt, liquidity, peer) on the real sentences and lines of the companies whose version-2 pack records it."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

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
# The candidate prompt's net-cash peer comparison (CAT, packs-v2), and the recorded true R2a hits whose reference takes
# the label of the level it is set against (Haiku-low NEE, DeepSeek ORCL).
CAT_NET = _pack(("D456", NET_CASH, "FY2025", -26_230_000_000.0, "usd", "net_cash"),
                ("D457", "Net cash % of revenue", "FY2025", -38.80809007382858, "pct", "net_cash_to_revenue"),
                ("D1152", "Net cash % of revenue: industrials peer median (n=7)", "FY2025", -35.61360562467165, "pct",
                 "peer_median:net_cash_to_revenue"))
NEE_NET = _pack(("D231", NET_CASH, "FY2025", -92_199_000_000.0, "usd", "net_cash"),
                ("D232", "Net cash % of revenue", "FY2025", -357.3605, "pct", "net_cash_to_revenue"),
                ("D314", "Net cash % of revenue: percentile vs utilities peers (n=4)", "FY2025", 0.0, "pctile", "peer_pctile:net_cash_to_revenue"),
                ("D315", "Net cash % of revenue: utilities peer median (n=4)", "FY2025", -228.3771, "pct", "peer_median:net_cash_to_revenue"))
ORCL_NET = _pack(("D414", NET_CASH, "FY2026", -97_647_000_000.0, "usd", "net_cash"),
                 ("D415", "Net cash % of revenue", "FY2026", -144.9693, "pct", "net_cash_to_revenue"),
                 ("D815", "Net cash % of revenue: percentile vs software peers (n=6)", "FY2026", 0.0, "pctile", "peer_pctile:net_cash_to_revenue"),
                 ("D816", "Net cash % of revenue: software peer median (n=6)", "FY2026", -0.5488, "pct", "peer_median:net_cash_to_revenue"))
# Net margin minus operating margin of one year: packs-v2's cited gap and the two margins (CAT below, SNAP above).
CAT_MARGINS = _pack(("D1168", "Net margin minus operating margin (pp, same year)", "FY2025", -3.3541, "pp", "margin_gap:net_minus_operating"),
                    ("F30", "Operating margin", "FY2025", 16.4982, "pct", "operating_margin"),
                    ("F50", "Net margin", "FY2025", 13.1442, "pct", "net_margin"),
                    ("D1200", "Net margin window low (FY2023)", "FY2016..FY2025", 9.7901, "pct", "low:net_margin"))
SNAP_MARGINS = _pack(("D591", "Net margin minus operating margin (pp, same year)", "FY2025", 1.2084, "pp", "margin_gap:net_minus_operating"),
                     ("F30", "Operating margin", "FY2025", -8.972, "pct", "operating_margin"),
                     ("F50", "Net margin", "FY2025", -7.7635, "pct", "net_margin"),
                     passages=(("P18", "Other income, net for the current year was primarily driven by $96.7 million in gains on "
                                       "extinguishment associated with the repurchases of certain outstanding convertible notes."),))
CAT_EPS = _pack(("F70", "EPS (diluted)", "FY2025", 18.81, "usd_per_share", "eps_diluted"),
                passages=(("P30", "Diluted earnings per share were $18.81 in 2025."),))
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
        # The 1.11x peer median is free cash flow's too, though operating cash flow's own 1.11x, cited first, matches it.
        (REGN, "Operating cash flow of $4,978.9 million was 1.11x net income in FY2025 [F80][F40][D428], above the 0.88x window "
               "median [D763] but below the 1.11x peer median [D783].", [("R1", "0.88x"), ("R1", "1.11x")]),
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
        # A reference takes the label of the level it is set against: the candidate prompt's own comparison (CAT, TGT)
        # is net cash's sign under net cash ...
        (CAT_NET, "Net debt of $26.2 billion [D456] is net cash of -38.8% of revenue [D457], against a -35.6% industrials "
                  "peer median [D1152].", []),
        (CAT_NET, "Net debt reached $26.2 billion in FY2025 [D456], and net cash of -38.8% of revenue sat below the -35.6% "
                  "peer median [D457][D1152].", []),
        (TGT, "Net debt of $4.3 billion [D410] leaves net cash at -4.1% of revenue [D411], below the -3.5% retail peer "
              "median [D613].", []),
        # ... and a median beside a "net debt" level is a net-debt figure, whatever label came first (recorded true hits).
        (CAT_NET, "Net cash turned negative: net debt is 38.8% of revenue, better than the -35.6% peer median [D457][D1152].",
         [("R2a", "-35.6%"), ("R2c", "-35.6%")]),
        (NEE_NET, "Net debt of $92.2 billion [D231] is -357.4% of revenue [D232], the lowest of four peers [D314] against a "
                  "median of -228.4% [D315].", [("R2a", "-357.4%"), ("R2a", "-228.4%")]),
        (ORCL_NET, "Net debt widened to $97.6 billion, 145.0% of revenue, the 0th percentile against six software peers whose "
                   "median is -0.5% [D414][D415][D815][D816].", [("R2a", "-0.5%")]),
        # Net cash nearer the figure governs it; a net cash flow is not a label.
        (CAT_NET, "Net debt rose as net cash fell to -$26.2 billion [D456].", []),
        (CAT_NET, "Net cash provided by operations rose, while net debt widened to -$26.2 billion [D456].",
         [("R2a", "-$26.2 billion")]),
        # "net-cash" is net cash, the candidate prompt's own spelling, and "net-debt" net debt (DeepSeek CAT, dev-v3).
        (CAT_NET, "On a net-cash basis, net debt of $26.2 billion is -38.8% of revenue in FY2025 [D456][D457], against a "
                  "-35.6% peer median [D1152].", []),
        (CAT, "That net-debt ratio is better than the industrials peer median of -35.6% of revenue but only the 43rd "
              "percentile of the seven-peer group [D1152][D1151].", [("R2a", "-35.6%")]),
        (CAT_NET, "Net cash fell as net-debt reached -$26.2 billion in FY2025 [D456].", [("R2a", "-$26.2 billion")]),
        (CAT_NET, "Net cash fell further, to -$26.2 billion of net-debt in FY2025 [D456].", [("R2a", "-$26.2 billion")]),
        # R2c: "better" that the signed net-cash values contradict (DeepSeek CAT, DeepSeek TGT), before or after both
        # numbers; "worse" there is true.
        (CAT, "Net debt is 38.8% of revenue, better than the -35.6% peer median but only the 43rd percentile of seven "
              "industrials peers [D457][D1152][D1151].", [("R2a", "-35.6%"), ("R2c", "-35.6%")]),
        (TGT, "Net debt was $4.3 billion, or 4.1% of revenue, better than the retail peer median of -3.5% net cash and at "
              "the 50th percentile of six peers [D410][D411][D613][D612].", [("R2c", "-3.5%")]),
        (CAT, "Net cash of -38.8% of revenue against the -35.6% peer median is the better position [D457][D1152].", [("R2c", "-35.6%")]),
        (CAT, "Net cash of -38.8% of revenue against the -35.6% peer median is the worse position [D457][D1152].", []),
        (TGT, "Net debt of 4.1% of revenue is worse than the -3.5% net cash retail peer median [D411][D613].", []),
        # A "better" past the end of the reference's clause is about something else.
        (CAT, "Net cash of -38.8% of revenue sat against the -35.6% peer median; free cash flow conversion was better "
              "[D457][D1152].", []),
        # R3: two margins of two years (DeepSeek DE); the same year's pair is fine.
        (DE, "Below the line, interest expense of $3.17 billion [X82] and a 20.1% tax rate [D400] left net margin 6.5pp under "
             "operating margin [F30][F50].", [("R3", "6.5pp")]),
        (DE, "In FY2024 net margin of 13.7% sat 3.7pp under the 17.5% operating margin [F49][F30].", []),
        # gap_direction: "above" or "below" against the sign of the same year's gap, cited (packs-v2) or computed from
        # the two margins, named either way round; "beat" and "trailed" likewise (SNAP, recorded).
        (CAT_MARGINS, "Net margin was 3.4pp above operating margin in FY2025 [D1168].", [("gap_direction", "3.4pp")]),
        (CAT_MARGINS, "Net margin was 3.4pp below operating margin in FY2025 [D1168].", []),
        (CAT_MARGINS, "Operating margin was 3.4pp above net margin in FY2025 [D1168].", []),
        (CAT_MARGINS, "Operating margin was 3.4pp below net margin in FY2025 [D1168].", [("gap_direction", "3.4pp")]),
        (CAT_MARGINS, "In FY2025 net margin of 13.1% sat 3.4pp below the 16.5% operating margin [F50][F30][D1168].", []),
        (CAT_MARGINS, "In FY2025 net margin of 13.1% sat 3.4pp above the 16.5% operating margin [F50][F30].",
         [("gap_direction", "3.4pp")]),
        (CAT_MARGINS, "Net margin of 13.1% trailed operating margin by 3.4pp in FY2025 [F50][F30].", []),
        (CAT_MARGINS, "Net margin of 13.1% beat operating margin by 3.4pp in FY2025 [F50][F30].", [("gap_direction", "3.4pp")]),
        (SNAP_MARGINS, "Net margin of -7.8% beat operating margin by 1.2pp, helped by $96.7 million of debt-extinguishment "
                       "gains in other income [F50][F30][P18].", []),
        (SNAP_MARGINS, "Net margin was 1.2pp below operating margin in FY2025 [D591].", [("gap_direction", "1.2pp")]),
        # ... and only when both margins are named on either side of the comparative, two different margins.
        (CAT_MARGINS, "Operating margin of 16.5% left net margin 3.4pp above it in FY2025 [F30][F50][D1168].", []),
        (CAT_MARGINS, "In FY2025 net margin stood 3.4pp above the net margin window low [F50][D1200][D1168].", []),
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
        (COP, "Revenue's three-year CAGR to FY2025 was a 5.3% drag [D844].", []),
        # A fall printed with a plus sign is wrong whatever surrounds it; a rise's plus sign is fine.
        (COP, "The three years to FY2025 show a +5.3% CAGR [D844].", [("U1", "5.3%")]),
        (COP, "Revenue growth was +20.5% in FY2023 [D274].", [("U1", "20.5%")]),
        (COP, "Revenue fell +20.5% in FY2023 [D274].", [("U1", "20.5%")]),  # beside its fall word, only the plus sign says it
        (SNAP, "Revenue growth was +10.6% in FY2025 [D406].", []),
        (COP, "Free cash flow stayed below 80% of net income in FY2024 and FY2025, at 0.45x and 0.40x [D387][D437].", []),
        # Unitless dollars: a table literal in millions read as dollars (DeepSeek COST); with its scale it is fine.
        (COST, "SG&A fell 10 basis points as a share of sales, though excluding gasoline inflation it rose one basis point, "
               "and currency moves added $126 of expense [P9].", [("unitless_dollars", "$126")]),
        (COST, "Currency moves added $126 million of SG&A expense [P9].", []),
        (CAT_EPS, "Diluted EPS was $18.81 in FY2025 [F70][P30].", []),  # a passage literal that a cited value also matches
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


@pytest.mark.parametrize("cites", ["[D1168]", "[F50][F30]"])
def test_a_same_year_margin_gap_has_one_sign_check_on_either_pack(cites: str) -> None:
    # packs-v2 cites the gap (D1168), packs/ the two margins: the gate reads no direction into either, so a move "to" the
    # gap passes both (review 7: it failed the packs-v2 arms alone), and gap_direction fails the wrong side on both.
    def gate(text: str) -> dict:
        return factcheck.check([{"section": "s", "text": text, "type": "comparison"}], CAT_MARGINS, backstops=True)

    assert gate(f"Net margin slipped to 3.4pp below operating margin in FY2025 {cites}.")["passed"]
    wrong = f"Net margin rose to 3.4pp above operating margin in FY2025 {cites}."
    assert factcheck.check([{"section": "s", "text": wrong, "type": "comparison"}], CAT_MARGINS)["passed"]
    assert [f["failure"][:23] for f in gate(wrong)["failures"]] == ["backstop gap_direction:"]


# broken_debt (DEEPSEEK-ERRORS.md fix 8, the gate's side) on the committed packs: packs-v2 records the breaks (its debt
# and liquidity checks, and the IDs it withholds with their reasons); packs/ (version 1) records none.
PACKS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"
TICKERS = sorted(path.name[:-len(".json.gz")] for path in (PACKS / "packs-v2").glob("*.json.gz"))


def _committed(ticker: str, version: str) -> dict:
    return json.loads(gzip.decompress((PACKS / version / f"{ticker}.json.gz").read_bytes()))


def _found(sentence: list, pack: dict, reference: dict | None = None) -> list:
    return [(hit["break"], hit["claim"]) for hit in probes.broken_debt(sentence, pack, reference)]


# The broken figure restated from the lines a version-2 pack still shows. Debt: cash less the one debt line left, or
# that line called total debt. Cash: a cash or investment line of a year a line is missing from (MSFT FY2017, NVDA
# FY2026, ORCL FY2017, COP FY2021: short-term investments), alone, summed or less debt, under net cash, net debt,
# liquidity or cash-and-investments words; TGT's cash and short-term investments summed, though cash already holds them.
RESTATED = [
    ("KO", "Net cash was $8.8 billion in FY2025 [D440][X186].", [("debt_break", "$8.8 billion")]),
    ("COP", "Net cash was $7.1 billion at FY2025 [D335][X203].", [("debt_break", "$7.1 billion")]),
    ("DE", "Net debt was $5.5 billion at FY2025 [D405][X185], down from $35.8 billion in FY2021 [D226].",
     [("debt_break", "$5.5 billion")]),
    ("KO", "Net cash was $8.8 billion at FY2025, cash of $10.3 billion less short-term borrowings of $1.5 billion "
           "[D440][X186].", [("debt_break", "$8.8 billion")]),
    ("COP", "Total debt was $1.0 billion in FY2025 [X203].", [("debt_break", "$1.0 billion")]),
    # DE's onset: before FY2020 total debt is long-term debt alone, its current portion untagged.
    ("DE", "Total debt was $23.7 billion in FY2016 [X186].", [("debt_break", "$23.7 billion")]),
    ("DE", "Net debt was $19.4 billion in FY2016 [D14][X186].", [("debt_break", "$19.4 billion")]),
    ("MSFT", "Cash and investments were $13.7 billion in FY2017 [F151][X167].", [("liquidity_break", "$13.7 billion")]),
    ("MSFT", "Cash and marketable securities were $13.7 billion in FY2017 [F151][X167].", [("liquidity_break", "$13.7 billion")]),
    ("MSFT", "Cash plus long-term investments came to $13.7 billion in FY2017 [F151][X167].",
     [("liquidity_break", "$13.7 billion")]),
    ("NVDA", "Cash, cash equivalents and short-term investments were $10.6 billion in FY2026 [F150].",
     [("liquidity_break", "$10.6 billion")]),
    ("MSFT", "Net debt was $78.5 billion in FY2017, cash of $7.7 billion against total debt of $86.2 billion [F151][D16].",
     [("liquidity_break", "$78.5 billion")]),
    ("NVDA", "Net cash was $2.1 billion in FY2026 [F150][D440].", [("liquidity_break", "$2.1 billion")]),
    ("NVDA", "Net cash only reached $2.1 billion in FY2026 [F150][D440].", [("liquidity_break", "$2.1 billion")]),  # no "cash alone"
    ("NVDA", "Cash and investments fell to $10.6 billion in FY2026 [F150].", [("liquidity_break", "$10.6 billion")]),
    ("ORCL", "Net debt was $36.1 billion in FY2017 [F135][D16].", [("liquidity_break", "$36.1 billion")]),
    ("ORCL", "Liquidity was $21.8 billion in FY2017 [F135].", [("liquidity_break", "$21.8 billion")]),
    ("COP", "Cash and investments were $5.3 billion in FY2021 [F109][X189].", [("liquidity_break", "$5.3 billion")]),
    ("COP", "Net cash was $3.8 billion in FY2021 [F109][X199].", [("debt_break", "$3.8 billion")]),  # both breaks: debt's line
    ("TGT", "Cash and short-term investments totalled $10.1 billion in FY2025 [F144][X170].",
     [("liquidity_break", "$10.1 billion")]),
    ("TGT", "Cash and investments were $3.6 billion in FY2016 [F135][X161].", [("liquidity_break", "$3.6 billion")]),
    # Review 7: the total named right after the figure, or after it at all ...
    ("COP", "ConocoPhillips held $7.1 billion of net cash in FY2025 [D335][X203].", [("debt_break", "$7.1 billion")]),
    ("COP", "Cash and investments were $8.1 billion against $1.0 billion of total debt [D335][X203].",
     [("debt_break", "$1.0 billion")]),  # DeepSeek dev-v3, which cited the withheld D336
    ("DE", "Deere carried $5.5 billion of net debt in FY2025 [D405][X185].", [("debt_break", "$5.5 billion")]),
    ("DE", "Deere ended FY2025 with a $5.5 billion net debt position [D405][X185].", [("debt_break", "$5.5 billion")]),
    ("KO", "Coca-Cola had $8.8 billion of net cash in FY2025 [D440][X186].", [("debt_break", "$8.8 billion")]),
    ("KO", "Coca-Cola held $8.8 billion more cash than debt in FY2025 [D440][X186].", [("debt_break", "$8.8 billion")]),
    # ... plain "debt" or "borrowings", the whole, in K0's wording of a withheld total (arm-fairness [1], [3]) ...
    ("KO", "Debt was $1.5 billion in FY2025 [X186].", [("debt_break", "$1.5 billion")]),
    ("KO", "Liquidity of $10.3 billion exceeded debt by $8.8 billion in FY2025 [D440][X186].", [("debt_break", "$8.8 billion")]),
    ("KO", "Debt rose 31.3% in FY2025 to $1.5 billion [X185][X186].", [("debt_break", "31.3%"), ("debt_break", "$1.5 billion")]),
    ("DE", "Deere's debt fell to $13.8 billion in FY2025 [X185].", [("debt_break", "$13.8 billion")]),
    ("DE", "Borrowings were $13.8 billion in FY2025 [X185].", [("debt_break", "$13.8 billion")]),
    ("KO", "Net-cash was $8.8 billion in FY2025 [D440][X186].", [("debt_break", "$8.8 billion")]),
    # ... a line of a break year beside a total of another year, whatever it is called (DE's "deleveraging" of eval-v1,
    # NVDA's cash and investments growth called cash) ...
    ("DE", "Debt fell 68.5% from FY2021 to FY2025 [D225][X185].", [("debt_break", "68.5%")]),
    ("DE", "Current debt fell 68.5% from FY2021 to FY2025 [D225][X185].", [("debt_break", "68.5%")]),
    ("NVDA", "Cash fell 75.5% in FY2026 [D384][F150].", [("liquidity_break", "75.5%")]),
    # ... TGT's two cash lines summed, under any name ...
    ("TGT", "Target held cash of $10.1 billion in FY2025 [F144][X170].", [("liquidity_break", "$10.1 billion")]),
    # ... and disclosure words about something else (measures [3], tests-and-gates [0]).
    ("CVX", "Net cash was $4.9 billion in FY2025 [D349][X177], though revenue is a later recast and not comparable with the "
            "first-reported years.", [("debt_break", "$4.9 billion")]),
    ("COP", "Net cash was $7.1 billion at FY2025 [D335][X203], while revenue figures are not comparable after the recast.",
     [("debt_break", "$7.1 billion")]),
    ("KO", "Net cash was $8.8 billion in FY2025 [D440][X186], though one-off tax payments understate free cash flow.",
     [("debt_break", "$8.8 billion")]),
    ("KO", "Net cash was $8.8 billion in FY2025 [D440][X186], a cushion that a missing dividend increase would not explain.",
     [("debt_break", "$8.8 billion")]),
    ("KO", "Net cash was $8.8 billion in FY2025 [D440][X186]; the caveat is that margins may fall.", [("debt_break", "$8.8 billion")]),
    ("KO", "Net cash was $8.8 billion in FY2025 [D440][X186], and segment data is missing for FY2025.",
     [("debt_break", "$8.8 billion")]),
]
# The same figures through the IDs version 2 withholds, as the frozen arms state them, one per reason (eval-v1
# DeepSeek KO, DE, NVDA, TGT, CAT, PG): only an arm reading version 1 sees them.
WITHHELD = [
    ("KO", "Net cash was $8.8 billion at FY2025, or 18.3% of revenue, against $10.3 billion of cash and investments "
           "[D442][D443][D440].", [("debt_break", "$8.8 billion"), ("debt_break", "18.3%")]),
    ("DE", "Net debt was $5.52 billion at FY2025 [D407], down from $35.8 billion in FY2021 [D226], or 12.1% of revenue "
           "[D408].", [("debt_break", "$5.52 billion"), ("debt_break", "12.1%")]),
    ("KO", "That ranks at the 100th percentile of six staples peers, whose median net cash is -14.5% of revenue "
           "[D793][D794].", [("debt_break", "100th percentile"), ("debt_break", "-14.5%")]),
    ("DE", "Total debt jumped 36.7% in FY2020 [D205].", [("debt_break", "36.7%")]),  # across DE's onset (review 6)
    ("NVDA", "Net cash fell to $2.1 billion, just 1.0% of revenue, from $34.7 billion a year earlier, as cash and "
             "investments dropped 75.5% to $10.6 billion [D441][D442][D386][D471][D439].",
     [("liquidity_break", "$2.1 billion"), ("liquidity_break", "1.0%"), ("liquidity_break", "75.5%"),
      ("liquidity_break", "$10.6 billion")]),
    ("TGT", "Net debt was $4.3 billion, or 4.1% of revenue, better than the retail peer median of -3.5% net cash and at "
            "the 50th percentile of six peers [D410][D411][D613][D612].",
     [("liquidity_break", "$4.3 billion"), ("liquidity_break", "4.1%"), ("liquidity_break", "-3.5%"),
      ("liquidity_break", "50th percentile")]),
    ("CAT", "Net debt is 38.8% of revenue, better than the -35.6% peer median but only the 43rd percentile of seven "
            "industrials peers [D457][D1152][D1151].", [("peer_break", "-35.6%"), ("peer_break", "43rd percentile")]),
    ("PG", "Net debt was $24.2 billion, or 27.8% of revenue, against a staples peer median of -1.0% net cash, placing it "
           "in the 33rd percentile of six peers [D450][D451][D677][D676].", [("peer_break", "-1.0%"), ("peer_break", "33rd percentile")]),
    # A revenue basis break (COP's data check of a recast) discloses nothing of the debt.
    ("COP", "Despite the revenue basis break, net cash was $7.1 billion at FY2025 [D337].", [("debt_break", "$7.1 billion")]),
]
# True sentences: a disclosure (synthetic ones in each form a break's disclosure takes, and the recorded ones of Sonnet
# COP in eval-v1 and dev-v3, Haiku KO, and Sonnet NVDA in dev-v3 and dev-v4), a debt line under its own name, plain
# cash under its own name, a year before the break, TGT's cash alone (its right basis: the short-term investments are
# inside it), and version 2's checked peer rank.
SPARED = [
    ("KO", "Net cash was $8.8 billion in FY2025 [D440][X186], but long-term debt is not reported after FY2023, so it "
           "omits that debt."),
    ("KO", "Net cash of $8.8 billion in FY2025 leaves out long-term debt, which the pack does not report after FY2023 "
           "[D440][X186]."),
    ("COP", "In FY2025 total debt shows only a $1.0 billion current portion, while interest expense rose to $1.2 billion, "
            "which the filing ties to debt assumed from Marathon Oil [D336][X203][X81][P10]."),
    ("COP", "That net cash rests on total debt of $1.0 billion [D336], which matches the current portion alone [X203]; "
            "long-term debt is untagged after FY2020, when it was $19.1 billion [F157]."),
    ("KO", "Net cash was $8.78 billion in FY2025 [D442], but FY2024 and FY2025 debt equals short-term borrowings only "
           "[D391][D441][X185][X186], so it is not comparable with FY2023's net debt of $32.4 billion [D341]."),
    ("KO", "Short-term borrowings were $1.5 billion in FY2025 [X186]."),
    ("KO", "Cash and investments were $10.3 billion in FY2025 [D440]."),
    ("DE", "Net debt was $35.8 billion in FY2021 [D226]."),
    ("DE", "Long-term debt was $23.7 billion in FY2016 [X186]."),
    ("MSFT", "Cash was $7.7 billion in FY2017 [F151]."),
    ("MSFT", "Net debt in FY2017 sat beside long-term investments of $6.0 billion [X167]."),  # the nearest words: a line
    ("NVDA", "Cash rose to $10.6 billion in FY2026 [F150]."),
    ("NVDA", "Net cash fell in FY2026 as cash rose to $10.6 billion [F150]."),
    ("NVDA", "Net cash provided by operating activities far exceeded the $10.6 billion held at FY2026 [F150]."),  # a flow
    ("NVDA", "Cash and cash equivalents were $10.6 billion in FY2026 [F150]."),
    ("ORCL", "Cash was $21.8 billion in FY2017 [F135]."),
    ("COP", "Cash was $5.0 billion in FY2021 [F109]."),
    ("TGT", "Net debt was $8.9 billion in FY2025 [F144][D409]."),
    ("TGT", "Cash and short-term investments were $5.5 billion in FY2025 [F144]."),
    ("TGT", "Short-term investments were $4.6 billion in FY2025 [X170]."),
    ("AMD", "Net cash ranks at the 100th percentile of five semis peers, against a -17.3% median [D844][D845]."),
    ("MSFT", "Cash and investments were $13.7 billion in FY2017 [F151][X167], which excludes short-term investments."),
    ("MSFT", "Cash and investments were $13.7 billion in FY2017 [F151][X167], as the short-term investment line is missing."),
    ("NVDA", "Cash and investments fell to $10.6 billion in FY2026 [F150], a figure that lacks short-term investments."),
    ("TGT", "Cash and short-term investments totalled $10.1 billion in FY2025 [F144][X170], but that double counts them."),
    ("TGT", "Cash and short-term investments totalled $10.1 billion in FY2025 [F144][X170], which counts them twice."),
    ("TGT", "Cash and short-term investments totalled $10.1 billion in FY2025 [F144][X170], though they are already inside cash."),
    ("TGT", "Cash and short-term investments totalled $10.1 billion in FY2025 [F144][X170], but cash already includes its "
            "short-term investments."),
    ("NVDA", "Net cash fell to $2.14 billion in FY2026 from $34.7 billion, but FY2026 cash and investments of $10.6 billion "
             "equal cash alone [D441][D386][D439][F150]."),
    ("NVDA", "Net cash was 83rd percentile of six semiconductor peers [D844] against a peer median of -13.9% of revenue "
             "[D845], subject to the same data caveat."),
    ("KO", "Against six staples peers, net cash ranks at the 100th percentile [D793], with a peer median of -14.5% of revenue "
           "[D794], but that ranking uses the same debt input."),  # Haiku eval-v1, after its disclosing sentence
    ("TGT", "Cash and short-term investments totalled $10.1 billion in FY2025 [F144][X170], but that counts the short-term "
            "investments twice."),
    # Review 7: a line under its own name, named after the figure, where a total is named before it ...
    ("KO", "For net cash, the pack shows only $1.5 billion of short-term borrowings in FY2025 [X186]."),
    ("COP", "Net cash would rest on a $1.0 billion current portion of debt [X203]."),
    ("DE", "Total debt in FY2025 includes $13.8 billion of current borrowings [X185]."),
    ("DE", "The current portion of debt was $13.8 billion in FY2025 [X185]."),
    ("KO", "Cash and investments of $10.3 billion exceeded short-term borrowings by $8.8 billion in FY2025 [D440][X186]."),
    ("KO", "Short-term borrowings rose 31.3% in FY2025 [X185][X186]."),
    ("NVDA", "Cash rose 23.5% in FY2026 [F149][F150]."),
    ("TGT", "Short-term investments made up 84% of cash in FY2025 [F144][X170]."),  # both lines, not their sum
    # ... and a line outside its break year, under a total's name (tests-and-gates [2]: KO's debt break is FY2024 to
    # FY2025, NVDA's liquidity break FY2026, COP's FY2021).
    ("KO", "Of FY2022's total debt, $36.4 billion was long-term [X193]."),
    ("NVDA", "Liquidity was $43.2 billion in FY2025 [F149][X188]."),
    ("NVDA", "Cash and short-term investments were $43.2 billion in FY2025 [F149][X188]."),
    ("COP", "Cash and short-term investments were $6.6 billion in FY2020 [F108][X183]."),
]


@pytest.mark.parametrize("ticker, text, found", RESTATED)
def test_broken_debt_restated_from_visible_lines_fails_the_v2_gate(ticker: str, text: str, found: list) -> None:
    sentence = [{"section": "balance_sheet", "type": "fact", "text": text}]
    v2, v1 = _committed(ticker, "packs-v2"), _committed(ticker, "packs")
    assert _found(sentence, v2) == found
    gate = factcheck.check(sentence, v2, backstops=True)
    assert factcheck.check(sentence, v2)["passed"] and not gate["passed"]
    assert all(f["failure"].startswith("backstop broken_debt:") for f in gate["failures"])
    # A version-1 pack records no break: the gate stays silent, and the measure, given version 2's pack, still counts.
    assert factcheck.check(sentence, v1, backstops=True)["passed"] and _found(sentence, v1) == []
    assert _found(sentence, v1, v2) == found


@pytest.mark.parametrize("ticker, text, found", WITHHELD)
def test_broken_debt_counts_withheld_ids_on_either_pack_version(ticker: str, text: str, found: list) -> None:
    sentence = [{"section": "balance_sheet", "type": "fact", "text": text}]
    v2 = _committed(ticker, "packs-v2")
    for pack in (v2, _committed(ticker, "packs")):
        assert _found(sentence, pack, v2) == found
    assert _found(sentence, v2) == found and not factcheck.check(sentence, v2, backstops=True)["passed"]


@pytest.mark.parametrize("ticker, text", SPARED)
def test_broken_debt_spares_disclosures_and_other_lines(ticker: str, text: str) -> None:
    sentence = [{"section": "balance_sheet", "type": "fact", "text": text}]
    v2 = _committed(ticker, "packs-v2")
    assert _found(sentence, v2) == []
    assert _found(sentence, _committed(ticker, "packs"), v2) == []


@pytest.mark.parametrize("text, says", [
    # A disclosure in a clause about debt or cash, as recorded (Sonnet COP eval-v1 and KO, Haiku DE, Sonnet NVDA) ...
    ("Reported total debt of $1.0 billion equals only the current portion, so net cash of $7.1 billion and its 100th "
     "percentile among six peers are unreliable.", True),
    ("Reported net cash of $8,775 million and its 100th percentile peer rank among six peers are therefore unreliable and "
     "support no conclusion.", True),
    ("The total-debt series falls from $43.8 billion in FY2021 to $12.6 billion in FY2022, so I do not compare debt across "
     "that break.", True),
    ("FY2026 short-term investments are absent from the filed lines, so FY2026 net cash, the 75.5% fall in cash and "
     "investments and the peer ranking are not comparable with earlier years.", True),
    ("Net cash was 83rd percentile of six semiconductor peers against a peer median of -13.9% of revenue, subject to the "
     "same data caveat.", True),
    ("Cash and short-term investments totalled $10.1 billion in FY2025, but that double counts them.", True),
    # ... not one about something else, in a sentence that names net cash (review 7), nor Sonnet MSFT's investment marks
    # (dev-v3), which the report's rule of a disclosure word beside any cash word counted.
    ("Net cash was $4.9 billion in FY2025, though revenue is a later recast and not comparable with the first-reported "
     "years.", False),
    ("Net cash was $8.8 billion in FY2025, though one-off tax payments understate free cash flow.", False),
    ("Net cash was $8.8 billion in FY2025, a cushion that a missing dividend increase would not explain.", False),
    ("Those gains are investment marks rather than operations, so net income overstates the earnings run-rate.", False),
])
def test_a_disclosure_counts_only_about_debt_or_cash(text: str, says: bool) -> None:
    assert probes.discloses(text) is says


def test_broken_ids_follow_the_withheld_rule_on_both_pack_versions() -> None:
    # The breaks are the reference pack's own record, on every company and for every reason: its withheld IDs with
    # their reasons, each withheld level in a year its reason's checks name. A version-1 pack records none, and holds
    # every withheld ID with its version-2 value, so version 2's record reads a version-1 output.
    assert len(TICKERS) == 20
    reasons: set = set()
    for ticker in TICKERS:
        v2, v1 = _committed(ticker, "packs-v2"), _committed(ticker, "packs")
        breaks = probes.debt_breaks(v2)
        assert breaks.ids == v2["withheld"]
        reasons |= set(breaks.ids.values())
        keys = probes.series_by_id(v2)
        flags = {f["id"]: f for f in v1["red_flags"]}
        for vid, why in breaks.ids.items():
            if keys.get(vid) in ("total_debt", "liquidity", "net_cash"):
                assert v2["values"][vid]["period"] in (breaks.debt_years if why == "debt_break" else breaks.cash_years), (ticker, vid)
            assert v1["values"].get(vid, flags.get(vid)) == v2["values"].get(vid, flags.get(vid)) is not None, (ticker, vid)
        assert probes.debt_breaks(v1) == probes.Breaks(frozenset(), frozenset(), {})
    assert reasons == set(probes.BREAK_KINDS)


# Series keys: "<series>|<period>", a segment's series holding bars of its own, and version 2's "<series>|<period>|checked".
@pytest.mark.parametrize("key, parts", [
    ("net_cash|FY2025", ("net_cash", "FY2025", "")),
    ("median:fcf_to_ni|FY2017..FY2025", ("median:fcf_to_ni", "FY2017..FY2025", "")),
    ("peer_pctile:net_cash_to_revenue|FY2025|checked", ("peer_pctile:net_cash_to_revenue", "FY2025", "checked")),
    ("seg:dei_LegalEntityAxis+us-gaap_StatementBusinessSegmentsAxis:revenue:duk:DukeEnergyFloridaMember|"
     "duk:ElectricUtilitiesandInfrastructureMember|FY2025",
     ("seg:dei_LegalEntityAxis+us-gaap_StatementBusinessSegmentsAxis:revenue:duk:DukeEnergyFloridaMember|"
      "duk:ElectricUtilitiesandInfrastructureMember", "FY2025", "")),
])
def test_a_series_key_splits_at_its_period(key: str, parts: tuple) -> None:
    assert probes.split_key(key) == parts


def test_a_segment_series_keeps_its_bars_and_a_checked_rank_its_series() -> None:
    # Cut at the first bar, Duke Energy Florida's electric revenue was one series with its gas revenue, and had no
    # year before: "fell to $6.99 billion" (from $6.49 billion) went unread.
    duk, amd = _committed("DUK", "packs"), _committed("AMD", "packs-v2")
    assert probes.series_by_id(duk)["S123"].endswith("DukeEnergyFloridaMember|duk:ElectricUtilitiesandInfrastructureMember")
    assert _kinds("Duke Energy Florida electric revenue fell to $6.99 billion in FY2025 [S123].", duk) == [
        ("logic_direction", "$6.99 billion")]
    assert _kinds("Duke Energy Florida electric revenue rose to $6.99 billion in FY2025 [S123].", duk) == []
    keys = probes.series_by_id(amd)
    assert keys["D844"] == keys["D826"] == "peer_pctile:net_cash_to_revenue"
    assert keys["D845"] == keys["D827"] == "peer_median:net_cash_to_revenue"


def test_a_tagged_value_has_no_year_before() -> None:
    # A checked rank's series runs under its version-1 twin: the twin's year before is no move of the checked rank.
    pack = _pack(("D1", "Net cash % of revenue: percentile vs peers (n=6)", "FY2024", 70.0, "pctile", "peer_pctile:net_cash_to_revenue"),
                 ("D2", "Net cash % of revenue: percentile vs peers (n=6)", "FY2025", 80.0, "pctile", "peer_pctile:net_cash_to_revenue"),
                 ("D3", "Net cash % of revenue: percentile vs peers (n=5)", "FY2025", 60.0, "pctile", "peer_pctile:net_cash_to_revenue"))
    pack["series_keys"]["peer_pctile:net_cash_to_revenue|FY2025|checked"] = "D3"
    pack["series_keys"]["peer_pctile:net_cash_to_revenue|FY2025"] = "D2"
    assert _kinds("Against five peers, net cash rose to 60th percentile in FY2025 [D3].", pack) == []
    assert _kinds("Against six peers, net cash rose to 80th percentile in FY2025 [D2].", pack) == []
    assert _kinds("Against six peers, net cash fell to 80th percentile in FY2025 [D2].", pack) == [("logic_direction", "80th percentile")]
