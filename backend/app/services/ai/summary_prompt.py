"""Primary summary request assembly, using the facade's live collaborator bindings."""
from __future__ import annotations

from types import ModuleType
from typing import Any, Dict, Optional


SCHEMA_TEMPLATE = """{
  "metadata": {
    "company_name": "<non-empty string>",
    "filing_type": "<non-empty string>",
    "reporting_period": "<non-empty string>",
    "filing_date": "<non-empty string>",
    "currency": "<non-empty string>",
    "has_prior_period": <bool>
  },
  "sections": {
    "the_print": {
      "headline": "<one sentence: the single most important takeaway, leading with the headline figure; apply the supported financial-driver condition below>",
      "key_takeaways": [
        "<2-4 high-signal takeaways; echo AT MOST the 2-3 headline figures (revenue, net income, EPS); apply the supported financial-driver condition below>",
        "... (use ['Not disclosed—explain why'] if no validated bullets)"
      ],
      "what_changed": "<financial_driver>",
      "tone": "<positive|neutral|cautious>",
      "source_section_ref": "<e.g., 'Cover page' or 'Item 2. MD&A'>"
    },
    "results_that_matter": {
      "table": [
        {
          "metric": "<reported_metric_label>",
          "current_period": "<non-empty string>",
          "prior_period": "<non-empty string>",
          "change": "<non-empty string; state margin changes in percentage points>",
          "commentary": "<financial_driver>",
          "supporting_evidence": "<a SHORT VERBATIM quote of NARRATIVE PROSE from the filing that backs this driver — a sentence or contiguous sentence fragment, copied CHARACTER-FOR-CHARACTER so it can be located in the text; NEVER a transcription of table rows or cells (the columns above already carry the figures), and NEVER a sentence you compose yourself to restate figures — the span must exist in the filing; use '' if the filing has no prose line to quote>"
        }
      ],
      "source_section_ref": "<e.g., 'Item 1. Financial Statements'>"
    },
    "earnings_quality": {
      "operating_vs_one_time": "<earnings_reconciliation>",
      "red_flags": ["<a specific quality flag, e.g. receivables growing faster than sales; leave empty if none>"],
      "source_section_ref": "<e.g., 'Item 8' or 'Statements of Cash Flows'>"
    },
    "value_drivers": {
      "capital_allocation": {"filing_statements": ["<copy a complete, contiguous VERBATIM passage explaining financing or capital allocation; no inferred funding/comparison claims. Monetary amounts must include their explicit thousand/million/billion scale in the passage; otherwise select qualitative prose. Leave empty if none>"]},
      "highlights": ["<copy a contiguous VERBATIM passage about a newly authorized repurchase program, dividend policy change or announced acquisition; preserve explicit amount scales; no paraphrase. Leave empty if none>"],
      "source_section_ref": "<e.g., 'Item 7' or 'Statements of Cash Flows'>"
    },
    "forward_signals": {
      "guidance": "<guidance exactly as the filing states it (raised/cut/maintained/not given); if none, say so and why it matters>",
      "known_trends": ["<an Item 303 known trend or uncertainty>"],
      "subsequent_events": ["<a material event after period end>"],
      "quotes": [
        {
          "speaker": "<non-empty string>",
          "quote": "<copied CHARACTER-FOR-CHARACTER from the filing so it can be located by exact search — never substitute, add, drop, or re-tense a word; to shorten, choose a shorter CONTIGUOUS span, never remove words inside it; forward-looking or unusual statements only; include a quote ONLY if you can copy it exactly — leave the quotes array empty otherwise>",
          "context": "<e.g., 'MD&A, Item 2'>"
        }
      ],
      "tone": "<positive|neutral|cautious>",
      "source_section_ref": "<e.g., 'Item 7. MD&A - Outlook'>"
    },
    "risks": [
      {
        "summary": "<non-empty string, tied to a specific line item or disclosed fact>",
        "supporting_evidence": "<non-empty excerpt or citation>",
        "materiality": "<low|medium|high>",
        "source_section_ref": "<e.g., 'Item 1A. Risk Factors'>"
      }
    ],
    "segments": [
      {
        "segment": "<copy a segment name EXACTLY as listed under REPORTABLE SEGMENTS in the data summary>",
        "commentary": "<supported one-line interpretation for that segment, or the supported movement alone when the filing states no cause — NEVER restate this segment's own revenue, operating income, or YoY change (the deterministic figure table carries them); finer-grained product/sub-segment facts are welcome as the filing discloses them>"
      }
    ],
    "balance_sheet_liquidity": {
      "leverage": "<total debt vs cash / equity; net position>",
      "liquidity": "<cash + available credit; runway>",
      "working_capital": "<current ratio / working-capital dynamics with YoY direction; skip for unclassified (bank) balance sheets. <financial_driver>>",
      "maturities_covenants": ["<a debt maturity or covenant detail>"],
      "source_section_ref": "<e.g., 'Liquidity and Capital Resources'>"
    },
    "notable_footnotes": [
      {
        "item": "<non-empty string>",
        "impact": "<non-empty string>",
        "supporting_evidence": "<a SHORT VERBATIM quote of NARRATIVE PROSE from the footnote text — a sentence or contiguous sentence fragment, copied CHARACTER-FOR-CHARACTER so it can be located in the filing; NEVER a transcription of a footnote table's rows or cells, and NEVER a sentence you compose yourself to restate figures — the span must exist in the footnote; use '' if the footnote has no prose line to quote>",
        "source_section_ref": "<relevant note reference where possible>"
      }
    ]
  }
}"""


def _build_context(financial_data: Dict, xbrl_section: str, filing_type_key: str) -> tuple[str, list[str]]:
    data_summary = f"""
EXTRACTED FINANCIAL SIGNALS:
- Revenue figures: {', '.join(financial_data['revenue'][:3]) if financial_data['revenue'] else 'Not observed'}
- Net income figures: {', '.join(financial_data['net_income'][:3]) if financial_data['net_income'] else 'Not observed'}
- Cash flow figures: {', '.join(financial_data['cash_flow'][:3]) if financial_data['cash_flow'] else 'Not observed'}
- Key segments: {', '.join([f"{seg[0]}: {seg[1]}" for seg in financial_data['segments'][:3]]) if financial_data['segments'] else 'Not observed'}
- Guidance references: {', '.join(financial_data['guidance'][:2]) if financial_data['guidance'] else 'Not observed'}
{xbrl_section if xbrl_section else ''}
""".strip()

    focus_guidance = {
        "10-Q": [
            "- Highlight sequential and year-on-year momentum for this quarter.",
            "- Connect quarterly execution to full-year guidance and structural themes.",
            "- Call out liquidity, leverage, and any covenant or contingency disclosures that are material to near-term risk."
        ],
        "10-K": [
            "- Evaluate year-long shifts in growth, profitability, cash generation, and capital allocation."
        ]
    }
    analysis_focus_lines = focus_guidance.get(filing_type_key, focus_guidance["10-K"])
    return data_summary, analysis_focus_lines


def build_primary_request(
    service: Any, facade: ModuleType, filing_type_key: str, sixk_class: Optional[str],
    xbrl_metrics: Optional[Dict], financial_data: Dict, company_name: str,
    filing_type: str, filing_sample: str,
) -> Dict[str, Any]:
    """Assemble in the original order; callbacks/settings resolve on the facade at call time."""
    config = service._get_type_config(filing_type_key)
    # W3-8b: a 6-K carries the deterministic pre-classifier's class so the class variant prompt
    # is used; other forms ignore it.
    prompt_template = facade.get_prompt(filing_type_key, sixk_class=sixk_class)

    # Roadmap 2.6 Phase B: the grounding block is built by the module-level
    # `build_xbrl_narrative_section` (testable, behavior-preserving). It now also surfaces the
    # full cash-flow statement (investing/financing) + working-capital lines when present.
    xbrl_section = facade.build_xbrl_narrative_section(xbrl_metrics)

    data_summary, analysis_focus_lines = _build_context(financial_data, xbrl_section, filing_type_key)

    schema_template = SCHEMA_TEMPLATE

    schema_template = (schema_template.replace("<reported_metric_label>", facade.REPORTED_METRIC_LABEL)
                       .replace("<financial_driver>", facade.FINANCIAL_DRIVER)
                       .replace("<earnings_reconciliation>", facade.EARNINGS_RECONCILIATION))

    output_reference = ""
    if prompt_template.user:
        output_reference = (
            "\n\nOUTPUT REFERENCE (use for content coverage; respond in JSON schema below):\n"
            f"{prompt_template.user}\n"
        )

    # Roadmap S1 (flagged): in structured-output mode use the schema-first prompt (which
    # omits the narrative "produce a cohesive markdown summary / 600-1000 words" block that
    # contradicts the JSON demand). Off → current behavior, unchanged.
    structured_mode = facade.settings.USE_STRUCTURED_OUTPUT
    analyst_preamble = (
        facade.get_structured_prompt(filing_type_key) if structured_mode else prompt_template.system
    )

    prompt = f"""{analyst_preamble}

You are a forensic financial analyst preparing structured briefing materials for newsroom editors.

Company: {company_name}
Filing type: {filing_type}

Use the extracted context below to populate quantitative and qualitative data. Focus on concrete, verifiable metrics and management disclosures. Avoid prose paragraphs; capture facts in concise data fields.

Guidance for emphasis:
- {" ".join(analysis_focus_lines)}
- {facade.FINANCIAL_EXPLANATION_SUPPORT}
- If prior-period data is unavailable, set related fields to "Not disclosed" and mark "has_prior_period": false.

{data_summary}

CRITICAL FILING EXCERPTS:
{filing_sample}

{output_reference}

Return ONLY valid JSON (no markdown fences) that matches this schema (replace placeholders with actual values or meaningful nulls). Every string must contain substantive content—never emit blank strings or placeholder tokens, except `results_that_matter.table[].supporting_evidence` and `notable_footnotes[].supporting_evidence`, which must be "" when no exactly-copyable prose span exists. Arrays must never be empty (exceptions: `results_that_matter.table` is empty when no reported metric is substantiated; `segments` is OMITTED entirely when no segments are listed, and `red_flags` / `highlights` / `quotes` are left EMPTY when nothing qualifies — a quote you cannot copy exactly does NOT qualify; no filler); otherwise, if no verifiable bullet exists, supply a single-element array with "Not disclosed—<concise reason>":
{schema_template}

Rules:
- OBJECTIVITY: Use neutral, factual language. Do NOT use promotional or subjective adjectives (e.g. strong, robust, solid, healthy, surged, soared, plunged, record, exceptional, impressive, fortress); state magnitude and direction with figures instead (e.g. "increased 14% YoY"). Such words are permitted ONLY inside a direct, attributed management quote.
- Populate ONLY the nine sections defined in the schema above (the_print, results_that_matter, earnings_quality, value_drivers, forward_signals, risks, segments, balance_sheet_liquidity, notable_footnotes). Do not invent additional section keys. `segments` is COMMENTARY-ONLY: its figure table (revenue, operating income) is filled deterministically from XBRL — emit one row per segment listed under REPORTABLE SEGMENTS in the data summary (name copied EXACTLY; a row whose name is not on that list is discarded), and omit the section entirely when no segments are listed.
- ONE HOME PER NUMBER — do not restate the same figure across sections. Each specific $-amount or %-change belongs in ONE home: reported P&L figures in results_that_matter ({facade.REPORTED_METRIC_LABEL}); earnings-quality figures (supported reported/adjusted earnings description) in earnings_quality — the cash-conversion read (NI-vs-CFO, free cash flow) is filled deterministically from XBRL, so do NOT restate the cash-flow $ legs here; the cash-flow statement bridge (operating/investing/financing cash flow) and balance-sheet/liquidity figures (working capital, current ratio) in balance_sheet_liquidity; capital-allocation figures belong to value_drivers, where the shareholder-returns line (dividends, buybacks, capex) and the returns read (ROE/ROA) are filled deterministically from XBRL — do NOT restate those $ amounts or ratios; give the value read qualitatively; the per-segment table (segment revenue / operating income) is filled deterministically from XBRL — segment commentary must never restate the segment's own $ figures or YoY %-change (the table carries them); finer-grained product/sub-segment facts as the filing states them are permitted. the_print may echo AT MOST the 2-3 headline figures (revenue, net income, EPS). Every OTHER section may add a driver, significance or inflection only when the filing supports it on the same basis; otherwise retain the supported movement without an invented explanation. Reference a number qualitatively (e.g. "margins widened on the services mix") rather than re-quoting a $-amount or %-change already stated in its home section. Never drop a figure to comply; relocate it to its home. Figures inside a direct, attributed management quote are exempt — never alter or truncate a quote to comply.
- Keep monetary values human-readable (e.g., "$17.7B", "$425M", "$912M").
- Express percentage changes with one decimal place where available (e.g., "up 8.3% YoY").
- For arrays, include 1-4 high-signal, evidence-backed bullets ordered by materiality. If nothing qualifies, return ["Not disclosed—<concise reason>"] instead of leaving the array empty — EXCEPT `results_that_matter.table` when no reported metric is substantiated, and `red_flags`, `highlights`, and `quotes`, which are left empty when nothing qualifies (a "Not disclosed" bullet under populated figures reads self-contradictory, and a quote you cannot copy character-for-character never qualifies).
- Empty sections are unacceptable (except `segments`, omitted entirely when none are listed, and `results_that_matter.table` when no reported metric is substantiated). Do not fabricate data; explain the absence using the Not disclosed pattern when required.
- VERBATIM COPYING — applies to every `quotes[].quote` and to `supporting_evidence` in `results_that_matter` and `notable_footnotes` (risks `supporting_evidence` keeps its own contract: a verbatim excerpt OR a citation/XBRL reference — never empty): copy the span CHARACTER-FOR-CHARACTER from the filing text so it can be located by exact search. Never substitute, add, drop, or re-tense a word; shorten ONLY by choosing a shorter contiguous span. Example (illustrative only — NOT from the filing you are summarizing): a filing says "We anticipate the Meridian platform will enter volume production in fiscal 2028." RIGHT: "We anticipate the Meridian platform will enter volume production" (a shorter contiguous span). WRONG: "We expect the Meridian platform to enter volume production" (words substituted). WRONG: "We anticipate the Meridian platform will enter production" (a word removed inside the span). If no exactly-copyable line exists, leave `quotes` empty and set that `supporting_evidence` to "".
- EVIDENCE IS PROSE — `supporting_evidence` in `results_that_matter` and `notable_footnotes` must be NARRATIVE PROSE: a sentence or a contiguous sentence fragment, never a transcription of table rows or cells (a bare metric label followed only by its figures). A table has no single linear text form, so a row transcription can never be located by exact search and is discarded downstream; the table columns already carry those figures. A prose sentence that contains figures is fine — that is exactly the desired evidence. COPY, don't COMPOSE: the `supporting_evidence` span must EXIST in the filing text — never write a sentence of your own that restates figures, however accurate; a composed sentence cannot be located by exact search, making it fabricated evidence — worse than the honest "". Example (illustrative only — NOT from the filing you are summarizing): a filing says "Demand for the Meridian platform exceeded our production capacity during the period." RIGHT: "Demand for the Meridian platform exceeded our production capacity" (an existing span, shortened only to a contiguous span). WRONG: "Meridian demand exceeded capacity" (a sentence you composed — it does not exist in the filing and cannot be located by exact search).
- Provide supporting evidence excerpts for each risk factor (direct quote or XBRL tag reference), and when possible populate `source_section_ref` with the most relevant 10-Q section (for example: "Item 1A. Risk Factors", "Item 2. MD&A")."""

    return _request_kwargs(service, filing_type_key, prompt, structured_mode, config)


def _request_kwargs(
    service: Any, filing_type_key: str, prompt: str, structured_mode: bool, config: Dict,
) -> Dict[str, Any]:
    return dict(
        model=service.get_model_for_filing(filing_type_key),
        messages=[
            {"role": "system", "content": (
                "You are a structured data extraction engine for financial journalism. "
                "You never write narrative prose. You output STRICT RFC8259 COMPLIANT JSON. "
                "ALL keys and strings must use DOUBLE QUOTES. No trailing commas. "
                "Adhere strictly to the requested schema. "
                "Fill in 'Not disclosed' when data is missing, except "
                "results_that_matter.table[].supporting_evidence and "
                "notable_footnotes[].supporting_evidence: use an empty string "
                "when no exactly-copyable prose span exists. "
                "Never invent prior-period figures."
            )},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1 if structured_mode else 0.2,
        max_tokens=config.get("max_tokens", 1500),
        response_format={"type": "json_object"},
    )
