# Comprehension test transcripts (report §3, verification §9c)

Each round gave one image and one fixed prompt to a fresh model instance (Sonnet, a separate
subagent with no conversation context). The instance was told to open nothing but that image.
Every round asked the same questions. The answers are reproduced verbatim.

**The prompt (identical in every round, except the image path):**

> You are a paying subscriber to an investment-research website. You have opened a company's
> multi-year financial analysis page. Look at this one screenshot of part of the page (use the Read
> tool on this path, and open NOTHING else — no other files, no web search, no code; answer only
> from what the image shows): `<image>`
> Answer these in plain words, as the subscriber, quoting the on-screen text you relied on for each
> answer: 1. What does the letter "a" mean here? What does "b" mean? What does "†" mean? 2. How much
> would you trust the Free cash flow figure of $4.1B, on a 1–5 scale (1 = not at all, 5 = fully)?
> Why? 3. Which figures, if any, would you check before relying on them? Name them and the years.
> 4. What would you actually do about "a" and "b"? 5. Is anything on the screen confusing or
> misleading? Say what. Keep the whole answer under 300 words. If you are unsure of a meaning, say
> so and give your best guess rather than inventing certainty.

**Images:** the current design is [comprehension-current.png](comprehension-current.png). Round 1
is [comprehension-round1.png](comprehension-round1.png), round 2
[comprehension-round2.png](comprehension-round2.png) and round 3
[comprehension-round3.png](comprehension-round3.png).

**Caveat for the current design and round 1.** Those two composites stack the KPI strip, then the
Data notes strip closed, then the same strip open. Both instances read the two strips as "the
block appears twice". That is an artefact of the composite, not a page defect. Rounds 2 and 3 show
the open strip only.

## Current design (production as of 2026-10-24)

> **1. Meanings (as I read them)**
> - "a": "This saved calculation predates the current source checks. Its inputs need review." The
>   header says "11 figures need review (a)". My guess is that the numbers were computed before the
>   site's latest data checks and haven't been re-verified. It doesn't say they're wrong.
> - "b": "Not available in this dataset." The header says "3 unavailable (b)". The only item is
>   "Long-term debt (FY2016, FY2017, FY2018)".
> - "†": "† marks a calculated figure, not an error." The header says "50 calculated †".
>
> **2. Trust in FCF $4.1B: 2/5.** It carries both † and ᵃ. The note lists "Free cash flow (FY2023,
> FY2024, FY2025)" as needing review. The page also says checks "are not an audit of the company's
> accounts." It's probably fine, but the page itself says unverified.
>
> **3. Check before relying on them**
> - Free cash flow FY2023, FY2024 and FY2025, which includes the $4.1B and the "CAGR +17.3%"
>   (FY2016–FY2025).
> - Net margin FY2023–FY2025, including 31.4% and "Chg +13.0pp" (FY2016–FY2025).
> - Operating margin FY2023–FY2025.
> - Working capital FY2024 and Current ratio FY2024.
>
> Revenue and Net income show no flag.
>
> **4. What I'd do**
> - For "a", I'd open the figure ("Select a figure to inspect its source, reporting period and
>   calculation"). Then I'd compare it with the filing's cash-flow statement before using it.
> - For "b", I'd not assume a value for long-term debt FY2016–18. I'd look it up in the old filings
>   myself if it mattered.
>
> **5. Confusing or misleading**
> - "Predates the current source checks" doesn't say what changed or whether the number moves. It
>   also doesn't say how to resolve it.
> - Net margin is flagged, yet Revenue and Net income (its inputs) aren't, which is puzzling.
> - Some figures have both † ("not an error") and ᵃ ("needs review"). The two superscripts are tiny
>   and easy to confuse.
> - The Data notes block appears twice, collapsed and expanded.
> - The lines about "13 YoY… table shows 13. Exports carry all 13" and "headline cards show 1" are
>   jargon-heavy.
> - A long line is clipped at the right edge ("Net / margin window…").
> - The card says "FY2025 Chg +13.0pp", but the note says the window is FY2016–FY2025.

## Round 1 (ringed review letter, fixed-size †, plain-words summary)

> 1. Meanings. The page spells them out:
> - "a" (a ringed letter): "A ringed letter marks a figure that needs a source check." The note
>   says: "Working not recorded. We calculated these figures before 10 October 2026, when we began
>   recording each calculation's inputs. They are shown as stored, without links to their inputs."
> - "b" (a plain letter): "a plain letter marks a gap." It says "Not in our data for these periods.
>   Shown as —, never as zero."
> - "†": "marks a figure we calculated, not an error."
>
> 2. Trust in Free cash flow $4.1B: 3 out of 5. It carries both † and the ringed "a". The page also
> lists "Free cash flow (FY2023, FY2024, FY2025)" under "Check before relying on". So it is probably
> computed correctly, but the page says it can't show the inputs. The "CAGR +17.3%" beside it also
> has the "a" note.
>
> 3. Check before relying on (quoting "Check before relying on"):
> - Operating margin: FY2023, FY2024, FY2025.
> - Net margin: FY2023, FY2024, FY2025.
> - Free cash flow: FY2023, FY2024, FY2025.
> - Working capital: FY2024.
> - Current ratio: FY2024.
> - The "16 growth figures built on them carry the same note." That includes the Free cash flow
>   CAGR and the Net margin "Chg +13.0pp".
>
> 4. What I'd do:
> - For "a": open each flagged figure, find the inputs in the filing, and compare. The page says
>   "Before relying on one, open it and compare it with the filing."
> - For "b": do nothing with Long-term debt FY2016–FY2018, because those years are "—" and not
>   zero. I'd only avoid assuming zero debt.
>
> 5. Confusing or misleading:
> - The whole "Data notes" block appears twice, one copy straight after the other. It looks like a
>   bug.
> - "11 need a source check" is the headline, but "11 figures · 13 YoY comparisons · 1 CAGR
>   comparison · 2 window percentage-point comparisons" are listed separately. This makes the count
>   feel inconsistent. The page does say "Counts describe distinct figures and comparisons."
> - The tiny superscript marks next to the headline numbers are hard to read.
> - "Not an audit" is said, but "186 of 200 figures passed source checks" can read as more
>   assurance than it gives.
> - I'm unsure whether "a" means a likely error or only "no audit trail". My best guess is the
>   second.

## Round 2 (round 1 plus: "not that the figure is wrong", a KPI word line, "automated checks")

> **1. Meanings.**
> - **Ringed "a":** "Working not recorded. We calculated these figures before 10 October 2026, when
>   we began recording each calculation's inputs. This note says the record is incomplete, not that
>   the figure is wrong... Before relying on one, open it and compare it with the filing." So "a"
>   means we can't see how the figure was worked out, and I should verify it myself.
> - **Plain "b":** "Not in our data for these periods. Shown as —, never as zero." It's a gap. The
>   example is Long-term debt (FY2016, FY2017, FY2018).
> - **"†":** "marks a figure we calculated, not an error."
>
> **2. Trust in FCF $4.1B: 3 out of 5.** The card says "needs a source check" and carries both †
> and ⓐ. The site says the figure isn't necessarily wrong, but it can't show me its inputs. I'd
> treat it as plausible but unconfirmed.
>
> **3. Check before relying on them.** The page says: "Check before relying on: Operating margin,
> Net margin and Free cash flow (FY2023–FY2025); Working capital and Current ratio (FY2024). 16
> growth figures built on them carry the same note." On the cards, that means these:
> - Free cash flow $4.1B and its "CAGR +17.3%".
> - Net margin 31.4% and its "Chg +13.0pp". A 13-point jump is large, so I'd look at it first.
>
> Revenue and Net income show no flag.
>
> **4. What I'd do.**
> - **"a":** I'd open the Free cash flow and Net margin figures and compare them with the filing's
>   cash-flow statement and income statement. That's the page's own instruction.
> - **"b":** I'd ignore it unless I need FY2016–18 debt. I would not read the dash as zero.
>
> **5. Confusing or misleading.**
> - "needs a source check" in orange sounds alarming, but the note says it's "not that the figure
>   is wrong". I had to read the long note to find that out.
> - "Working not recorded" is jargon. I only understood it after reading the full paragraph.
> - The distinction between a ringed letter (a) and a plain letter (b) is explained only in small
>   print at the bottom.
> - No figure on this screen carries a "b", so that marker feels disconnected.
> - "186 of 200 passed automated checks" could read as 14 failures. In fact 11 are flagged and 3
>   are gaps.
> - Counts like "50 calculated" and "11 figures · 13 YoY" mix figures and comparisons.
> - "Details" and "Growth figures that carry this note" are collapsed, so I can't see which growth
>   numbers are affected.

## Round 3 (copy only: "Inputs not linked", "Of 200 figures, 186 passed", a ringed-letter key line)

> **1. What the marks mean.**
> - "a" (a ringed letter): "Inputs not linked. We calculated these figures before 10 October
>   2026... This note says the record is incomplete, not that the figure is wrong... Before relying
>   on one, open it and compare it with the filing." So it means the site can't show how the figure
>   was built, and I should check it myself.
> - "b" (a plain letter): "Not in our data for these periods. Shown as —, never as zero." Here
>   that's Long-term debt for FY2016-FY2018. It marks a gap, not a problem with a number.
> - "†": "marks a figure we calculated, not an error." The "50 calculated" count matches this.
>
> **2. Trust in the $4.1B Free cash flow: 3 out of 5.** The card says "needs a source check" and
> carries both † and ringed a. The notes say the record is incomplete "not that the figure is
> wrong", so I wouldn't dismiss it. I also can't treat it as verified, because it is "shown as
> stored, without links to its inputs."
>
> **3. What I'd check first.** The note names these: "Operating margin, Net margin and Free cash
> flow (FY2023–FY2025); Working capital and Current ratio (FY2024)." On screen, that means Free cash
> flow $4.1B (FY2025), Net margin 31.4% (FY2025) and the growth figures built on them: "CAGR +17.3%"
> and "Chg +13.0pp". Revenue and Net income have no flag.
>
> **4. What I'd do about a and b.** For a, I'd open the filing and compare. I'd take operating cash
> flow minus capex for Free cash flow, and net income divided by revenue for Net margin. For b, I'd
> do nothing. I just wouldn't use the FY2016-FY2018 debt figures, and I'd read "—" as missing, not
> zero.
>
> **5. What's confusing or misleading.**
> - "Ringed a" and plain "b" look like the same kind of footnote, but one means "check this" and
>   the other means "gap". Only the fine print at the bottom explains the difference.
> - "11 need a source check" sits beside "16 growth figures built on them", which makes the count
>   hard to follow. The small "13 YoY comparisons · 1 CAGR · 2 window pp" line doesn't clearly add
>   up to 16.
> - "Automated checks" could sound like a guarantee. The page says it is "not an audit".
> - It never says what the 14 other flagged-or-calculated figures are, or whether a is a likely
>   error. "Not wrong, but verify" is ambiguous.
> - The growth figures show in green despite the "needs a source check" note.

## Scoring the rounds

| Round | "a" read as | Certainty about "a" | "b" read as | "†" read as | Trust in FCF $4.1B | Right action for "a" |
|---|---|---|---|---|---|---|
| Current | not re-verified since newer checks | a guess ("my guess") | not available | calculated | 2/5 | open it and compare, but resolution unclear |
| 1 | inputs not recorded | a guess ("my best guess is the second") | a gap, not zero | calculated | 3/5 | open it and compare with the filing |
| 2 | incomplete record, not a wrong figure | stated from the page | a gap, not zero | calculated | 3/5 ("plausible but unconfirmed") | open it and compare with the filing |
| 3 | incomplete record, not a wrong figure | stated from the page | a gap, not zero | calculated | 3/5 | names the formulas to check (OCF − capex; NI ÷ revenue) |

Every reader read "†" correctly in every round; the current page already explains it. "a" needed
the most change. On the current page the reader had to guess what "a" meant. Rounds 2 and 3 state
it from the page and give a trust level that matches what the data supports: plausible, not yet
verified. The residuals from round 3 stay open in the report (§3.5).
