# The battlefield (2026-10-11)

Phase 2 of the brand studio brief. Eight competitor homepages were visited the same morning as the
audit and seven were captured, with Playwright 1.56.1 and the preinstalled Chromium at 1440×900, and probed for computed
styles (h1 face, size, weight, colour; page ground; the buttons in the first viewport). Captures are
downscaled JPEGs under [`battlefield/`](battlefield/), kept small and used only for comparison. The
feature tables in `tasks/research/competitors.md` (June 2026) and `docs/RESEARCH_SYNTHESIS.md`
cover what these products do; this page covers how they look and speak.

Two sites did not render on the first visit. Fiscal.ai answered it with HTTP 429 from a security
checkpoint; a second visit rendered the page, and the capture is from that visit. Simply Wall St
showed a bot challenge ("Just a moment…") on both visits; it is described from the repository's
research and from the brief, not from a capture, and is marked so. It should be captured by hand
in a normal browser before Phase 9's lineup.

## 1. The eight

### Fiscal.ai (formerly FinChat)

[capture](battlefield/fiscal-ai-1440-fold.jpg)

- **Colour.** Near-black ground, white type, one off-white pill button. Cinematic: a muted video
  loop behind the hero (a mute control sits in the corner).
- **Type.** A geometric grotesk, white, 72px-class headline, tight leading.
- **Tone.** Infrastructure: "Modern Financial Data Infrastructure" over "Clean auditable financial
  data updated in minutes after earnings. The data infrastructure powering the world's leading
  investors and platforms."
- **Imagery.** Video, then product screens.
- **Hero headline.** "Modern Financial Data Infrastructure".
- **Primary CTA.** "Request Demo" (secondary "View plans"); the nav leads with "Contact Sales".
- **Who it is for.** Institutions and platforms; the retail reader who made FinChat is no longer the
  subject of the page. The product still carries click-through citations and the "says I don't
  know" reputation (`tasks/research/competitors.md` §A). "AI" appears in the page title, not in
  the first viewport.

### Quartr

[capture](battlefield/quartr-1440-fold.jpg)

- **Colour.** Off-white ground (`oklch(0.993 …)`), near-black type, black buttons; a marble
  photograph under the product shot.
- **Type.** Inter Variable at 68px, weight 550; an editorial serif (PP Editorial New) is loaded for
  accents further down.
- **Tone.** Swiss, B2B, declarative: "Everything said and published by public companies,
  structured for AI and delivered in real-time." An announcement bar names an OpenAI partnership.
- **Imagery.** Marble, the desktop app's activity feed.
- **Hero headline.** "AI infrastructure for company research".
- **Primary CTA.** "Book demo".
- **Who it is for.** Financial institutions and AI companies ("Trusted by 700+").

### Koyfin

[capture](battlefield/koyfin-1440-fold.jpg)

- **Colour.** White ground, near-black type, a black primary button, one bright blue floating "Ask
  Koyfin AI" pill.
- **Type.** Aktiv Grotesk at 88px, weight 500, centred, three lines.
- **Tone.** Platform: "Research markets, analyze portfolios, and create client-ready reports in one
  place."
- **Imagery.** A dense dark terminal screenshot with news, FX and index tables in red and green.
- **Hero headline.** "A modern investment platform for advisors and investors."
- **Primary CTA.** "Sign Up For Free".
- **Who it is for.** Advisors first, then investors; the nav splits them.

### TIKR

[capture](battlefield/tikr-1440-fold.jpg)

- **Colour.** White ground, near-black type, orange primary buttons.
- **Type.** Inter at 48px, weight 800.
- **Tone.** Aspiration and social proof: "Find the best stocks, follow top investors, quickly
  analyze businesses, and monitor your portfolio", a row of six avatars, "Join over 500,000
  investors", "No credit card required".
- **Imagery.** A terminal screenshot (NVDA financials), a marquee of checkmarked features.
- **Hero headline.** "Invest like Wall Street with TIKR Terminal".
- **Primary CTA.** "Get Started for FREE".
- **Who it is for.** Retail and prosumer investors who want the professional's data at a consumer
  price.

### Simply Wall St (not captured)

Both visits ended at a bot challenge. From `docs/RESEARCH_SYNTHESIS.md` (the closest
freemium analogue: unlimited watchlists, metered reports) and the brief: warm cream ground, a gold
serif italic accent, a mascot illustration, the Snowflake radar as the signature device,
portfolio-first. It is the one competitor with a graphic device the market recognises without the
logo, and the one whose palette family (cream and a warm accent) sits nearest to EarningsNerd's.
It should be captured by hand in a normal browser before Phase 9's lineup.

### Stock Analysis

[capture](battlefield/stock-analysis-1440-fold.jpg)

- **Colour.** White ground, a blue primary button, green index sparklines in the first row, a
  grey sidebar.
- **Type.** The system sans at 42px, weight 700.
- **Tone.** Utility and scale: "All-in-one stock analysis platform with accurate information on
  130,000+ global stocks and funds."
- **Imagery.** None; a sidebar of fourteen sections, index tiles, app-store ratings (4.9, 4.8),
  a "Trending" line of tickers.
- **Hero headline.** "Search for a stock to start your analysis".
- **Primary CTA.** "Sign Up" (blue) beside a search field.
- **Who it is for.** Anyone; free, fast, dense.

### Public.com

[capture](battlefield/public-1440-fold.jpg)

- **Colour.** White ground, black pills, a dark product render with a green portfolio line.
- **Type.** Denton, a display serif, at 48px, weight 300, for the headline; Inter for the body.
- **Tone.** Category-making: "The investing platform for the agentic age", with "Multi-asset
  investing · AI Agents · 3.75% APY* on cash" as the subhead.
- **Imagery.** A brokerage dashboard: account value, a rising chart, alerts ("BTC up 5%",
  "Q3 earnings: beat by 3.1%").
- **Hero headline.** "The investing platform for the agentic age".
- **Primary CTA.** "Get started".
- **Who it is for.** Retail investors and traders; it is a brokerage, and its AI over filings (Alpha)
  is a free feature of the account.

### BamSEC (AlphaSense)

[capture](battlefield/bamsec-1440-fold.jpg)

- **Colour.** A red-to-orange gradient ground, white type, a green "Get Started" button, a white
  "Free Trial" button; AlphaSense's cookie bar in a corner.
- **Type.** Roboto at 40px, weight 700, white.
- **Tone.** Productivity: "Transform how you work with SEC filings and earnings transcripts. Focus on
  what matters, save time, and do better work — no matter what other tools you have." Beneath: "Say
  goodbye to Ctrl-F".
- **Imagery.** None in the hero; a four-up grid of red-linked features.
- **Hero headline.** "Financial research made easier".
- **Primary CTA.** "Get Started" (green) and "Free Trial" (nav).
- **Who it is for.** Professionals who already live in filings and want power tools: full-text
  search, redlines, Excel pulls.

## 2. The lineup, read across

| | Ground | Headline face | Headline register | Primary CTA | The claim | Device |
|---|---|---|---|---|---|---|
| Fiscal.ai | black, video | grotesk, white | infrastructure | Request Demo | auditable data, minutes after earnings | none (video) |
| Quartr | off-white, marble | Inter 550 | infrastructure | Book demo | everything companies say, structured for AI, real time | marble |
| Koyfin | white | Aktiv Grotesk 500 | platform | Sign Up For Free | one place for research, portfolios, reports | none |
| TIKR | white | Inter 800 | aspiration | Get Started for FREE | invest like Wall Street; 500,000 investors | avatars |
| Simply Wall St | cream (not captured) | serif italic accent | portfolio | (not captured) | understand a company in one picture | the Snowflake |
| Stock Analysis | white | system sans 700 | utility | Sign Up | 130,000+ stocks, free, fast | sparklines |
| Public.com | white, dark render | Denton serif 300 | category | Get started | the agentic age; yield | the rising line |
| BamSEC | red gradient | Roboto 700 | productivity | Get Started | research made easier; goodbye Ctrl-F | gradient |
| **EarningsNerd today** | cream | Inter 600 | scope statement | See a live example | read faster, keep the source in view | none |

What the eight share:

- **Breadth, speed and AI.** Of the seven captured first viewports, three say "AI" (Quartr, Koyfin,
  Public) and Fiscal.ai says it in its page title; two count something large (TIKR's 500,000
  investors, Stock Analysis's 130,000+ stocks) and Quartr's "700+" sits in its meta description;
  four claim speed ("updated in minutes", "real-time", "quickly analyze", "save time").
- **One register: the platform.** "Infrastructure", "platform", "terminal", "all-in-one", "one
  place". The reader is a user of a system. Nobody speaks as a colleague who has read the document.
- **One composition.** Headline, one-sentence subhead, a button, a product screenshot. Six of the
  seven captured (Stock Analysis leads with a search field instead). EarningsNerd matches it too.
- **Red and green do the talking.** Koyfin's, Stock Analysis's and Public's first viewports all show
  price direction in red and green. TIKR's hero screenshot too. The casino floor is the default
  wallpaper of the category.
- **The same cookie sentence.** "We value your privacy" opens Koyfin's and BamSEC's bars and
  EarningsNerd's.

What none of the eight does:

- **Nobody shows verification as a visible act.** No first viewport shows a source span, a count of
  matches, a citation marker, or the word "withheld". Fiscal.ai's "auditable" and Quartr's
  "structured" are adjectives in a subhead. The product features exist (Fiscal.ai's click-through,
  BamSEC's redlines, Quartr's traceability; `tasks/research/competitors.md`), and nobody has made the
  act of checking the identity.
- **Nobody speaks to an individual who reads filings.** Fiscal.ai and Quartr moved to institutions;
  Koyfin addresses advisors; TIKR and Public address people who want the market, not the document;
  Stock Analysis addresses everyone; BamSEC addresses the professional's workflow. The person who
  opens a 10-K on a Saturday and wants it read with them is addressed by no one.
- **Nobody is dry.** The category is either loud (TIKR, BamSEC) or corporate (Fiscal.ai, Quartr,
  Koyfin). Nobody understates.

## 3. The empty space, and the claim

The hypothesis under test: nobody in the category owns verification as a visible act, and nobody
speaks to an individual who reads filings in the register of a careful, dry, numerate colleague.

**The hypothesis holds, with one refinement.** Citation is not empty space: three of the eight
have citations as a feature and will keep them, and every competitor will have an AI copilot within
a year. What is empty is the *identity* built on the act of checking: showing the span, counting the
matches, saying "withheld", and saying it in the voice of someone who checked. No competitor's
brand is the receipt. Fiscal.ai had the nearest claim and walked away from the reader toward the
enterprise; that is the opening.

So the brand owns the receipt: not "we have citations" (a feature every copilot will grow) but
"you can check this, and we already counted what you can't". The visual system must make the act
of checking recognisable without the logo; the voice must sound like the person who did the checking.
Phases 3 and 4 build on that sentence.

Two guards the lineup suggests:

- Keep away from the terminal look (dense dark tables, red and green) and from the category's
  gradient-and-glow decoration. Those are the two visual defaults, and the audit's cream-and-sage
  already avoids them; the system should hold that line and add the device.
- Keep the cream, since nothing in the lineup but Simply Wall St uses it, but do not let cream alone
  carry the identity: Simply Wall St proves a warm palette reads as "friendly retail" unless a device
  gives it an edge.
