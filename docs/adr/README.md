# Architecture Decision Records (ADRs)

This directory captures the significant, hard-to-reverse decisions behind EarningsNerd —
the *why* behind the architecture, so future contributors don't have to reverse-engineer
intent from the code or re-litigate settled trade-offs.

Each ADR is a short, immutable record. When a decision changes, we don't rewrite history —
we add a new ADR that **supersedes** the old one and update the status link.

## Format

We use a lightweight [MADR](https://adr.github.io/madr/)-style template:

- **Status** — Accepted | Superseded | Deprecated
- **Context** — the forces at play (technical, product, operational)
- **Decision** — what we chose
- **Consequences** — the trade-offs we accepted, good and bad

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](./0001-render-to-cloud-run.md) | Migrate hosting from Render to Google Cloud Run | Accepted |
| [0002](./0002-openai-gpt4-to-gemini.md) | Use Google AI Studio (Gemini) via an OpenAI-compatible client | Superseded by 0006 |
| [0003](./0003-edgartools-for-sec-data.md) | Consolidate SEC data access on `edgartools` | Accepted |
| [0004](./0004-redis-off-in-production.md) | Run Redis off in production (L1 in-memory cache only) | Accepted |
| [0005](./0005-stay-on-react-18.md) | Stay on React 18 under Next.js 16 | Accepted |
| [0006](./0006-deepseek-supersedes-gemini.md) | Standardize on DeepSeek V4 as the default AI provider | Accepted |

## Adding an ADR

1. Copy the structure of an existing record.
2. Use the next zero-padded sequence number; ADRs are append-only.
3. Add a row to the index above.
4. If it changes a prior decision, set the old ADR's status to **Superseded by ADR-NNNN**.
