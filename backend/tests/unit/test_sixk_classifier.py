"""W3-8b: deterministic 6-K pre-classifier over fixture excerpts.

Excerpts are short, attributed fragments in the shape of real exhibits observed on
September 15, 2026 (ASML Q2 2026 release, ASML AGM results, Sea AGM notice, JD board-meeting
notice, Alibaba HKEX monthly return, Alibaba placing completion, TSM cover-only 6-K). They are
fixtures, not the filings.
"""
from app.services.edgar.sixk_classifier import SIXK_CLASSES, classify_sixk_text

EARNINGS = (
    "Exhibit 99.1 ASML reports €9.3 billion total net sales and €2.9 billion net income in Q2 2026. "
    "Q2 total net sales of €9.3 billion, gross margin of 54.0%, net income of €2.9 billion. "
    "ASML expects Q3 2026 total net sales between €11.0 billion and €12.0 billion. "
    "Installed Base Management sales were €2.8 billion. Guidance: 2026 total net sales between "
    "€43 billion and €45 billion. Net income per ordinary share was €7.59. R&D costs of around "
    "€1.2 billion and SG&A costs of around €0.4 billion. Interim dividend of €1.88 per share. "
    "Operating income for the quarter ended June 28, 2026 rose; results reflect the outlook."
)
GOVERNANCE_AGM = (
    "Exhibit 99.1 ASML discloses 2026 AGM results. Veldhoven, the Netherlands, April 22, 2026 - "
    "ASML Holding N.V. today announces the results of its Annual General Meeting (AGM) held on "
    "April 22, 2026. Shareholders adopted the 2025 financial statements, approved the dividend of "
    "€6.40 per ordinary share, appointed a member of the Board of Directors, and authorized the "
    "Board of Directors to repurchase shares. The general meeting also approved the remuneration."
)
GOVERNANCE_NOTICE = (
    "Exhibit 99.1 Sea Limited to Hold Annual General Meeting on September 16, 2026. Singapore, "
    "August 25, 2026 - Sea Limited today announced that it will hold its annual general meeting of "
    "shareholders. The notice of meeting, proxy statement and the annual report are available. "
    "Shareholders of record are entitled to attend the shareholders meeting."
)
BOARD_MEETING = (
    "Exhibit 99.1 Hong Kong Exchanges and Clearing Limited take no responsibility for the contents "
    "of this announcement. DATE OF BOARD MEETING. The board of directors of JD.com, Inc. announces "
    "that a meeting of the board of directors will be held to consider and approve the interim "
    "results and to consider the payment of an interim dividend, if any."
)
MONTHLY_RETURN = (
    "Reporting month: September. Exhibit 99.1 FF301 Page 1 of 10 v 1.2.1 Monthly Return for Equity "
    "Issuer and Hong Kong Depositary Receipts listed under Chapter 19B of the Exchange Listing Rules "
    "on Movements in Securities. Board of directors resolution; dividend; share repurchase of "
    "HK$1,000,000 shares; buy-back HK$2.0 million; appointment none; resignation none; "
    "annual general meeting date; HK$12,000,000; HK$3,500; HK$44; HK$5,000; HK$800; HK$91; HK$7."
)
CAPITAL_ACTION = (
    "Exhibit 99.1 Alibaba Group Announced Completion of HK$80 Billion Placing of New Shares in Hong "
    "Kong. Hong Kong, China, August 26, 2026 - Alibaba Group Holding Limited today announced the "
    "completion of its placing of new ordinary shares at HK$135.00 per share for gross proceeds of "
    "approximately HK$80 billion (US$10.2 billion). The net proceeds of HK$79.5 billion will fund "
    "cloud and AI infrastructure."
)
COVER_ONLY = "Reporting month: September 2026"


def test_earnings_release_is_earnings():
    result = classify_sixk_text(EARNINGS)
    assert result.sixk_class == "earnings"
    assert result.earnings_cues >= 4 and result.money_tokens >= 8


def test_agm_results_and_meeting_notices_are_governance():
    assert classify_sixk_text(GOVERNANCE_AGM).sixk_class == "governance"
    assert classify_sixk_text(GOVERNANCE_NOTICE).sixk_class == "governance"
    assert classify_sixk_text(BOARD_MEETING).sixk_class == "governance"


def test_exchange_monthly_return_is_press_release_despite_governance_words():
    """HKEX periodic returns carry dividend/board/buy-back words and money tokens but are regulatory
    forms, never governance events; the governing contract has no fourth class."""
    result = classify_sixk_text(MONTHLY_RETURN)
    assert result.regulatory_return is True
    assert result.governance_cues >= 3
    assert result.sixk_class == "press_release"


def test_capital_action_and_cover_only_text_are_press_release():
    assert classify_sixk_text(CAPITAL_ACTION).sixk_class == "press_release"
    assert classify_sixk_text(COVER_ONLY).sixk_class == "press_release"
    assert classify_sixk_text("").sixk_class == "press_release"
    assert classify_sixk_text(None).sixk_class == "press_release"


def test_audit_record_is_json_safe_and_names_the_class():
    audit = classify_sixk_text(EARNINGS).as_audit()
    assert audit["class"] in SIXK_CLASSES
    assert set(audit) == {"class", "earnings_cues", "governance_cues", "money_tokens", "regulatory_return"}
    assert all(isinstance(v, (int, bool, str)) for v in audit.values())
