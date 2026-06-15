# What Investors Most Want to Learn From SEC Filings

**Research input for an EarningsNerd.io product review**
Target user: prosumer / serious individual investors, with a retail free tier.
Framing: "Jobs To Be Done" (JTBD). Each need is the underlying job a reader is "hiring" a 10-K/10-Q (or a tool that summarizes one) to do.
Date: 2026-06-13

---

## How to read this report

- **Need** = a distinct information job a reader wants done.
- **Segments** = (R) retail/DIY, (P) prosumer/serious individual, (A) professional analyst. A bolded segment is where the need matters *most*.
- Ranking weighs both how universally a need is cited as high-signal AND how poorly it is served by reading the raw filing unaided (i.e., where an AI summarizer adds the most value).

The most consistent finding across investor-education, analyst-workflow, and community sources: the *highest-signal* content is not any single section read in isolation, but **what changed** — period-over-period diffs of language and numbers — combined with a **cash-flow reality check** on reported earnings. Both jobs are exactly the ones that are tedious and error-prone to do by hand, which is where a summarizer earns its keep.

---

## 1. RANKED user information needs (most-wanted first)

### 1. "What CHANGED since the last filing" — the period-over-period diff
**JTBD:** *"When a new filing drops, help me see what's materially different from last time — added/removed risk factors, shifts in MD&A wording, new accounting policies — so I don't have to diff two 150-page documents by hand."*
This is repeatedly cited as the single highest-signal output. Risk-factor additions and deletions "reflect management insights into changes in the exposure to the risks a firm faces," and textual-analysis research links year-over-year risk-language changes to future stock returns, volatility, and key ratios (ROA, Tobin's Q). The SEC frames the MD&A itself as the place where "material changes in the company's results compared to a prior period" live, and the 10-Q's whole structure is period-over-period (this quarter vs. last quarter, and vs. the year-ago quarter). Experienced readers say the strongest tell is when "MD&A language tightens up year over year with more numbers and fewer adjectives," and the weakest is when it "gets vaguer."
**Segments:** **P**, **A** (R less so — most retail readers never compare two filings).
**Sources:** [ResearchGate – Year-over-year changes in Risk Factor disclosure](https://www.researchgate.net/publication/326049095_Analysis_of_year-over-year_changes_in_Risk_Factors_Disclosure_in_10-K_filings); [Boardroom Alpha – Identifying new & changing risk factors](https://www.boardroomalpha.com/identifying-new-changing-risk-factors-in-the-latest-10-k-filings/); [SEC Investor.gov – How to Read a 10-K/10-Q](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/how-read); [PennyInsight – How to Read 10Ks Like a Hedge Fund](https://pennyinsight.substack.com/p/how-to-read-10ks-like-a-hedge-fund).

### 2. Cash-flow quality — does the cash back up the earnings?
**JTBD:** *"Tell me whether reported net income is real cash or accounting — show free cash flow vs. net income, capex, and where the gap comes from."*
Near-universal advice: the cash-flow statement is the "truth serum." "When net income and free cash flow tell the same story, the company likely has high earnings quality; when they diverge, trust the cash flow." A persistently low FCF/net-income conversion ratio "can indicate aggressive accounting." Community and analyst guides both say the biggest reading mistake is starting with the income statement — instead "verify whether the cash flow supports the reported earnings." This is genuinely tedious to compute from a raw filing, so it's high-value to surface automatically.
**Segments:** **P**, **A**, and R (universally useful; this is the one "advanced" metric retail readers are told to learn first).
**Sources:** [Investing.com – Cash Flow Quality guide](https://www.investing.com/academy/analysis/cash-flow-quality-guide/); [TIKR – FCF vs Net Income](https://www.tikr.com/blog/how-to-analyze-a-companys-free-cash-flow-vs-net-income); [PennyInsight – How to Read 10Ks Like a Hedge Fund](https://pennyinsight.substack.com/p/how-to-read-10ks-like-a-hedge-fund).

### 3. Red-flag / anomaly detection
**JTBD:** *"Scan the filing and flag the scary stuff — going-concern doubt, material weakness in controls, qualified audit opinion, restatements, auditor changes, big new litigation, unusual one-off items — so I don't miss a buried disclosure."*
These are the most direct, consequential signals in a filing. "Disclosures of 'material weaknesses' are particularly serious red flags." "Anything other than 'unqualified' in the auditor's opinion is a red flag." "Repeated auditor changes or frequent restatements often signal weak internal controls or disagreements over accounting treatment." The recommended manual method is literally keyword-searching for "material weakness," "going concern," "restatement," and "discontinued" — a mechanical task ideal for automation.
**Segments:** **R**, **P**, **A** (matters to everyone; retail benefits most because they're least likely to know to look).
**Sources:** [SECFilingData – Red Flags in SEC Filings](https://www.secfilingdata.com/red-flags-in-sec-filings-how-to-spot-hidden-risks-before-they-surface/); [Deloitte DART – Restatements & corrections of accounting errors](https://dart.deloitte.com/USDART/home/publications/deloitte/additional-deloitte-guidance/roadmap-initial-public-offerings/chapter-3-financial-statement-preparation-disclosure/3-7-restatements-corrections-accounting-errors).

### 4. Segment & KPI breakdowns + GAAP vs non-GAAP reconciliation
**JTBD:** *"Break the business into segments, surface the operating KPIs management actually steers by, and show me where the 'adjusted' numbers diverge from GAAP — and whether the add-backs are legit."*
Experienced readers cite "direct discussion of unit economics, customer concentration, and segment-level performance" as a strong signal. On non-GAAP, the SEC requires a reconciliation to the most comparable GAAP measure precisely to avoid misleading investors; the analyst's job is to judge "the appropriateness of adjustments such as elimination of normal, recurring cash operating expenses and labeling items as non-recurring... when they are not." This is core analyst work and only partly relevant to passive retail readers.
**Segments:** **A**, **P** (R rarely).
**Sources:** [SEC – Non-GAAP Financial Measures C&DIs](https://www.sec.gov/corpfin/non-gaap-financial-measures.htm); [GAAP Dynamics – Non-GAAP measures and segment reporting](https://www.gaapdynamics.com/non-gaap-measures-and-segment-reporting/); [PennyInsight – How to Read 10Ks Like a Hedge Fund](https://pennyinsight.substack.com/p/how-to-read-10ks-like-a-hedge-fund).

### 5. Context vs. consensus / peers
**JTBD:** *"Don't just tell me the numbers — tell me whether they beat or missed expectations, how guidance changed, and how the company stacks up against peers, because price reacts to surprise, not to absolute results."*
"The movement is generally related to how the report compares to the analysts' expectations rather than whether a company made or lost money." And "forward guidance often matters more than the reported number" — a beat with cut guidance still drops. Analysts further stress identifying *where* a beat/miss came from (top line vs. margins vs. one-offs) to judge durability. Note: consensus/peer data is largely *outside* the filing, so this is a need a filing-only tool can only partly satisfy — useful to flag as a product gap.
**Segments:** **A**, **P** (R cares about the headline beat/miss but rarely the attribution).
**Sources:** [HeyGoTrade – Understanding Earnings Surprise (beat vs miss)](https://www.heygotrade.com/en/blog/understanding-earnings-surprise/); [HeyGoTrade – Whisper numbers vs consensus](https://www.heygotrade.com/en/blog/whisper-numbers-vs-consensus-why-stocks-drop-on-beats/).

### 6. Cash-flow *use*: capital allocation (buybacks, dividends, capex discipline)
**JTBD:** *"Show me how management deploys cash — buybacks, dividends, reinvestment, debt paydown — and whether it looks disciplined or like financial engineering."*
"A consistent buyback strategy demonstrates a company's long-term commitment... and signals confidence," whereas "a large, discretionary buyback program may indicate that management sees few compelling internal growth projects, or that they are more focused on manipulating per-share metrics." Reading multiple years of capital-allocation choices is how readers judge management quality. (Closely related to #2; separated because it's a distinct judgment job, not a quality check.)
**Segments:** **P**, **A** (R: dividend-focused readers care about the dividend record specifically).
**Sources:** [Motley Fool – Capital Allocation: Buybacks, Dividends, and More](https://www.fool.com/investing/2017/10/11/capital-allocation-buybacks-dividends-and-more.aspx); [AInvest – Assessing the value of share buybacks](https://www.ainvest.com/news/assessing-share-buybacks-capital-allocation-check-2601/).

### 7. Genuine tone / sentiment shifts in management language
**JTBD:** *"Flag real changes in management's tone — hedging, new caveats, disappearing confidence — but only the meaningful ones, not boilerplate."*
Academic evidence is strong: tone *change* in 10-K/10-Q filings significantly affects market reaction "even after controlling for accruals and earnings surprises," and predicts the next quarter's earnings surprise; manager sentiment is a notable predictor of returns. The hard part — and the value-add — is distinguishing a genuine shift from routine legalese, which is why the practical advice is to read tone "year over year" rather than in a single filing.
**Segments:** **A**, **P** (R: too subtle to action without help — a place where AI can democratize an analyst skill, but also where hallucination risk is highest).
**Sources:** [ScienceDirect – Earnings calls & stock returns: incremental informativeness of textual tone](https://www.sciencedirect.com/science/article/abs/pii/S0378426611002901); [Wiley – Tone Distance: managerial tone divergence and market reaction](https://onlinelibrary.wiley.com/doi/10.1111/fire.70002).

### 8. Source verifiability — trust output you can click through to the filing
**JTBD:** *"Whatever the summary tells me, let me click straight to the exact passage in the filing so I can verify it — I won't act on a number I can't trace."*
This is a trust/credibility need rather than a content need, but it gates adoption of any AI tool. "Hallucinations and inaccurate AI outputs... undermine credibility, diminish trust." The recommended mitigation is exactly a product feature: "grounding answers in retrieved text, requiring references" and "returning targeted source passages and citation URLs that agents can cite and users can verify." For a filing-summary product, click-through-to-source is effectively table stakes.
**Segments:** **R**, **P**, **A** (universal; non-negotiable for any reader who will act on the output).
**Sources:** [Harvard Law CorpGov – AI risk disclosures in the S&P 500](https://corpgov.law.harvard.edu/2025/10/15/ai-risk-disclosures-in-the-sp-500-reputation-cybersecurity-and-regulation/); [AlphaCreek – SEC retrieval / citation grounding](https://www.alphacreek.ai/).

### 9. A plain-language orientation to the business and its risks (the "starter" job)
**JTBD:** *"I'm new to this company — explain what it actually does, how it makes money, and the top real risks, in plain English."*
The SEC and every beginner guide say to start with the Business section ("a good place to start to understand the company") and then Risk Factors ("significant risks... generally listed in order of importance"), reading risks *after* MD&A so you can tell "whether the risks listed are boilerplate or real." This is the foundational job for newcomers; experienced readers already have this context, so its marginal value falls as sophistication rises.
**Segments:** **R**, **P** (A: already knows the business).
**Sources:** [SEC Investor.gov – How to Read a 10-K](https://www.investor.gov/introduction-investing/getting-started/researching-investments/how-read-10-k); [Investopedia/Investor.gov guidance via CFI – Form 10-K overview](https://corporatefinanceinstitute.com/resources/financial-modeling/form-10-k/).

### 10. Footnote / disclosure deep-dive (debt terms, leases, off-balance-sheet, contingencies)
**JTBD:** *"Surface what's buried in the notes — debt maturities and covenants, operating leases, off-balance-sheet items, legal contingencies, accounting-policy choices — because that's where the real risk hides."*
"Footnotes are where companies disclose detailed information... terms, structure, and components of debt, off-balance sheet liabilities, and more," and CFI flags them for "accounting policies, debt obligations, income taxes, and stock option plans." High-value but ranked lower mainly because the audience that *uses* footnote detail is narrower (serious individuals and analysts), even though it's high-signal for them.
**Segments:** **A**, **P** (R rarely).
**Sources:** [CFI – Form 10-K overview](https://corporatefinanceinstitute.com/resources/financial-modeling/form-10-k/); [Motley Fool – The most important parts of a company's 10-K](https://www.fool.com/investing/2019/06/07/the-most-important-parts-of-a-companys-10k.aspx).

---

## 2. How needs differ: retail vs. prosumer vs. analyst

**Retail / DIY (R).** Most don't read filings at all — the dominant DIY culture (e.g., Bogleheads) is passive indexing, where stock-level filing analysis is explicitly *not* part of the process ([Bogleheads – Index Fund](https://www.bogleheads.org/wiki/Index_fund)). Those who do read want **orientation** (what the company does), **headline red flags**, the **beat/miss verdict**, and a **plain-English cash-flow sanity check**. They are least equipped to do period-over-period diffs or judge non-GAAP add-backs, so they benefit *most* from automation of needs #1–#3 — but they're also the segment most exposed to AI error, making **source verifiability (#8)** essential to deploy this safely. Their JTBD is "tell me if anything is obviously wrong and what this company is," not "give me an investment thesis."

**Prosumer / serious individual (P) — EarningsNerd's core user.** This reader knows the sections and *wants the tedium removed*. Their highest-value jobs are the **"what changed" diff (#1)**, **cash-flow quality (#2)**, **capital-allocation judgment (#6)**, and **segment/KPI + non-GAAP scrutiny (#4)** — i.e., the work an analyst does, but without an analyst's time budget. They will cross-check against **consensus/peers (#5)** when they can. They are sophisticated enough to *notice* a wrong number, so they will only trust a tool that lets them **click through to the source (#8)**. This is the segment for which a filing-diff + cash-flow + red-flag summarizer is most differentiated.

**Professional analyst (A).** Treats the filing as raw input to a model, not an end product. Cares about everything above at maximum depth — footnote-level debt/lease detail (#10), exact non-GAAP reconciliation mechanics (#4), tone-change attribution (#7), and rigorous beat/miss source attribution (#5). 10-K initiation is flagged as one of the most "time-consuming, repetitive workflows," and analysts will adopt an AI tool only if it "saves 50%+ time without sacrificing quality" ([AlphaSense / Marvin Labs workflow](https://www.alpha-sense.com/resources/equity-research-guide/)). For them the tool is an accelerant; the bar on accuracy and verifiability is highest, and they are the least likely to be on a free tier.

**The throughline:** value rises with sophistication for *analytical* needs (#1, #4, #6, #7, #10) and is flat-to-universal for *safety/orientation* needs (#2, #3, #8, #9). A product that nails the **"what changed" diff** and a **trustworthy, click-to-source cash-flow + red-flag readout** serves all three segments — deepest for the prosumer it's built for.

---

## 3. Sources

**Investor education / official guidance**
- SEC Investor.gov — How to Read a 10-K: https://www.investor.gov/introduction-investing/getting-started/researching-investments/how-read-10-k
- SEC Investor.gov — How to Read a 10-K/10-Q (combined bulletin): https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/how-read
- SEC — Investor Bulletin: How to Read a 10-K (PDF): https://www.sec.gov/files/reada10k.pdf
- SEC — Non-GAAP Financial Measures (C&DIs): https://www.sec.gov/corpfin/non-gaap-financial-measures.htm
- Corporate Finance Institute — Form 10-K overview: https://corporatefinanceinstitute.com/resources/financial-modeling/form-10-k/
- Motley Fool — The most important parts of a company's 10-K: https://www.fool.com/investing/2019/06/07/the-most-important-parts-of-a-companys-10k.aspx
- Motley Fool — Capital Allocation: Buybacks, Dividends, and More: https://www.fool.com/investing/2017/10/11/capital-allocation-buybacks-dividends-and-more.aspx

**Cash-flow quality & earnings quality**
- Investing.com — Cash Flow Quality guide: https://www.investing.com/academy/analysis/cash-flow-quality-guide/
- TIKR — How to analyze FCF vs Net Income: https://www.tikr.com/blog/how-to-analyze-a-companys-free-cash-flow-vs-net-income

**Red flags / anomaly detection**
- SECFilingData — Red Flags in SEC Filings: https://www.secfilingdata.com/red-flags-in-sec-filings-how-to-spot-hidden-risks-before-they-surface/
- Deloitte DART — Restatements and corrections of accounting errors: https://dart.deloitte.com/USDART/home/publications/deloitte/additional-deloitte-guidance/roadmap-initial-public-offerings/chapter-3-financial-statement-preparation-disclosure/3-7-restatements-corrections-accounting-errors

**"What changed" / risk-factor & tone diffs**
- ResearchGate — Analysis of year-over-year changes in Risk Factors Disclosure in 10-K filings: https://www.researchgate.net/publication/326049095_Analysis_of_year-over-year_changes_in_Risk_Factors_Disclosure_in_10-K_filings
- Boardroom Alpha — Identifying new & changing risk factors in the latest 10-K filings: https://www.boardroomalpha.com/identifying-new-changing-risk-factors-in-the-latest-10-k-filings/
- ScienceDirect — Earnings conference calls and stock returns: incremental informativeness of textual tone: https://www.sciencedirect.com/science/article/abs/pii/S0378426611002901
- Wiley/Financial Review — Tone Distance: managerial tone divergence and market reaction: https://onlinelibrary.wiley.com/doi/10.1111/fire.70002

**Segment / non-GAAP**
- GAAP Dynamics — Non-GAAP measures and segment reporting: https://www.gaapdynamics.com/non-gaap-measures-and-segment-reporting/

**Context vs. consensus / peers**
- HeyGoTrade — Understanding Earnings Surprise (beat vs miss): https://www.heygotrade.com/en/blog/understanding-earnings-surprise/
- HeyGoTrade — Whisper numbers vs consensus: https://www.heygotrade.com/en/blog/whisper-numbers-vs-consensus-why-stocks-drop-on-beats/

**Capital allocation**
- AInvest — Assessing the value of share buybacks: https://www.ainvest.com/news/assessing-share-buybacks-capital-allocation-check-2601/

**AI trust / source verifiability**
- Harvard Law Forum on Corporate Governance — AI risk disclosures in the S&P 500: https://corpgov.law.harvard.edu/2025/10/15/ai-risk-disclosures-in-the-sp-500-reputation-cybersecurity-and-regulation/
- AlphaCreek — SEC retrieval, citation grounding to reduce hallucination: https://www.alphacreek.ai/

**Community & analyst-workflow perspective**
- PennyInsight (Substack) — How to Read 10Ks Like a Hedge Fund: https://pennyinsight.substack.com/p/how-to-read-10ks-like-a-hedge-fund
- ValueFund (Substack) — How to Read a 10-K Like a Professional Investor: https://valuefund.substack.com/p/how-to-read-a-10-k-like-a-professional
- AlphaSense — Equity research guide (analyst workflow & AI adoption bar): https://www.alpha-sense.com/resources/equity-research-guide/
- Bogleheads — Index Fund (DIY/retail passive context): https://www.bogleheads.org/wiki/Index_fund
