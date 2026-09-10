repo: neilmac91/EarningsNerd
branch: main
path: frontend

## Last sync
date: 2026-09-10T17:59:53Z

### Updated in this project
- Wired company marks to the production `CompanyLogo.tsx` pattern (monogram → Logo.dev ticker PNG fade-in) behind a `logoToken` tweak
- Read `next.config.js` and `.env.local.example` to confirm the publishable-token hotlink approach

## Sync history
- 2026-09-10T13:32:35Z: recreated current landing from `app/page.tsx`; built redesign on July 2026 single-Sage tokens; copied EN logo SVGs from `public/assets/`

## Screen map
| Screen | Repo files |
|---|---|
| Landing (current).dc.html | frontend/app/page.tsx, frontend/components/Header.tsx, frontend/components/Footer.tsx, frontend/components/ThemeToggle.tsx, frontend/components/EarningsNerdLogoIcon.tsx, frontend/components/CompanyLogo.tsx, frontend/features/marketing/components/{HeroExample,ExampleSummaryCard,QuickAccessBar,SocialProofStrip,HowItWorks,FeatureShowcase,AccuracySection,CtaBanner}.tsx, frontend/features/calendar/components/ReportingThisWeek.tsx, frontend/features/companies/components/CompanySearch.tsx, frontend/app/globals.css, frontend/tailwind.config.js |
| Landing (redesign).dc.html | all of the above plus frontend/components/ui/{Button,Badge,Card,Input}.tsx, frontend/features/summaries/components/{FinancialMetricsTable,SummaryDisplay}.tsx, frontend/features/filings/components/{SourceTrace,MetricSourceLink,WhatChanged}.tsx, frontend/features/filings/components/copilot/CitationChip.tsx, frontend/features/analysis/components/{KpiStrip,AnalysisTeaser}.tsx, frontend/app/pricing/prices.ts, frontend/lib/planLimits.ts, frontend/DESIGN_SYSTEM.md, frontend/components/CompanyLogo.tsx, frontend/next.config.js |
| Landing (redesign) — Breakpoints.dc.html | (composition board over the two screens above) |
