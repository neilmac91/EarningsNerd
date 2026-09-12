"""Complete source paragraphs, never unowned or assembled prose, supply the fallback."""
from app.services.ai.capital_passages import fallback_capital_passages
from app.services.ai.financing_comparison import _self_contained_numbers

MELI = (
    "Furthermore, the evolution of Mercado Pago’s activities themselves has resulted in the Company "
    "managing a significant volume of cash, cash equivalents and investments. This is due to an "
    "increase in users’ account balances in their Mercado Pago digital account managed by the "
    "Company, and an increase in the level of the Company’s indebtedness to finance those "
    "operations. As a result, these Mercado Pago’s funds, together with the financing activities, "
    "have generated a significant volume of interest income and other financial gains and interest "
    "expenses and other financial losses, respectively."
)
LABEL = "FINANCIAL STATEMENTS CONTEXT (recovered from filing):\n"
PREFIX = "Selected source context before the passage.\n"
SUFFIX = "\nFollowing source context remains available.\n"


def select(source):
    return fallback_capital_passages(source, lambda q: (
        25 <= len(q) <= 2000 and source.count(q) == 1 and _self_contained_numbers(q)
    ))


def test_actual_financing_explanation_requires_owned_complete_unique_paragraph():
    assert select(LABEL + PREFIX + MELI + SUFFIX) == [MELI]
    assert select(MELI + "\n") == []  # unknown source family
    assert select("ITEM 1A - RISK FACTORS:\n" + MELI + "\n") == []
    assert select(LABEL + MELI) == []  # cannot prove the final paragraph is complete
    assert select(LABEL + MELI + "\n" + MELI + "\n") == []
    assert select(LABEL + MELI.replace(". This is", ".\nThis is") + "\n") != [MELI]
    assert select(LABEL + MELI[:-1] + "\n") == []


def test_ranking_never_admits_table_join_unscaled_amount_or_risk_paragraph():
    risk = "ITEM 1A - RISK FACTORS:\n" + MELI + "\n"
    table = "Proceeds from financing activities\nCash generated\n12,000\n"
    unscaled = "Financing activities provided cash of $6,500 to fund the company's operating activities."
    source = LABEL + table + unscaled + "\n" + risk
    assert select(source) == []
    assert fallback_capital_passages(LABEL + MELI + "\n", lambda q: False) == []


def test_source_order_breaks_equal_topic_rank_and_returns_only_one():
    second = MELI.replace("Furthermore,", "Separately,")
    source = LABEL + PREFIX + MELI + "\n" + second + SUFFIX
    assert select(source) == [MELI]


def test_direct_financing_context_wins_over_actual_earlier_fcf_definition():
    definition = (
        'Adjusted free cash flow represents cash from operating activities less the increase (decrease) '
        'in cash and cash equivalents and investments related to customer funds due to regulatory requir'
        'ements and other restrictions and equity securities held at cost, investments in property and e'
        'quipment and intangible assets, changes in loans receivable, net and net proceeds from/payments'
        ' on loans payable and other financial liabilities related to our Fintech solutions, since we co'
        'nsider those liabilities as the working capital of the Fintech activities. From the second quar'
        'ter of 2025 onwards, we have also included increase (decrease) in cash and cash equivalents and'
        ' investments restricted due to management restriction policies and digital assets as an adjustm'
        'ent in the calculation of our adjusted free cash flow. We consider adjusted free cash flow to b'
        'e a measure of liquidity generation that provides useful information to management and investor'
        's since it shows how much cash the Company generates with its core activities that can be used '
        'for discretionary purposes and to repay its corporate and/or commerce debt. A limitation of the'
        ' utility of adjusted free cash flow as a measure of liquidity generation is that it is a partia'
        'l representation of the total increase or decrease in our available cash, investments and digit'
        'al assets balance for the year. Therefore, we believe it is important to view the adjusted free'
        ' cash flow measure only as a complement to our entire consolidated statements of cash flows.'
    )
    source = LABEL + PREFIX + definition + "\nAdjusted free cash flow reconciliation\n1,481\n" + MELI + SUFFIX
    assert select(source) == [MELI]


def test_generated_separators_do_not_certify_clipped_block_edges():
    # Producers can append a separator after a cap lands at an internal sentence period.
    assert select(LABEL + MELI + "\n\n") == []
    assert select(LABEL + PREFIX + MELI + "\n\n") == []
    assert select(LABEL + MELI + SUFFIX) == []
    assert select(LABEL + PREFIX + MELI + SUFFIX) == [MELI]
