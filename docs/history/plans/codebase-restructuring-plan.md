# EarningsNerd Restructuring Plan

## Executive Summary

This document outlines the strategic plan to restructure the EarningsNerd codebase. The current architecture suffers from "God Files" (e.g., `openai_service.py`, `summaries.py`), tight coupling, and a lack of clear domain boundaries. This creates high cognitive load for developers and increases the risk of regressions during updates.

**Proposed Solution**: Transition to a **Domain-Driven Design (DDD)** structure for the frontend (`features/`) and a **Clean Architecture** approach for the backend (Ports & Adapters).

**Key Benefits**:
-   **Scalability**: New features can be added in isolated modules without touching core logic.
-   **Testability**: Decoupled services allow for easier mocking and unit testing.
-   **Maintainability**: Smaller, single-purpose files reduce cognitive load.

**Primary Risk**: Regression in core summary generation logic due to low existing test coverage.
**Mitigation**: Implementation of a "Safety Net" test suite before any refactoring begins.

---

## Detailed Changes

### Change 1: Resolve Code Duplication (`StatCard.tsx`)
-   **Current**: Two components named `StatCard.tsx` exist in `frontend/components/` (124 lines) and `frontend/components/charts/` (24 lines).
-   **Proposed**: Analyze usage. If distinct, rename clearly (e.g., `SummaryStatCard` vs `ChartStatCard`). If similar, merge into a unified, flexible component.
-   **Rationale**: Eliminates import ambiguity and reduces bundle size.
-   **Complexity**: S
-   **Dependencies**: None.
-   **Risks**: Visual regression in dashboards.

### Change 2: Split Frontend `api.ts`
-   **Current**: `frontend/lib/api.ts` (651 lines) contains ALL API definitions, mixing auth, filing, and company logic.
-   **Proposed**: Split into domain-specific files under `frontend/features/`:
    -   `frontend/features/auth/api/auth-api.ts`
    -   `frontend/features/filings/api/filings-api.ts`
    -   `frontend/features/companies/api/companies-api.ts`
    -   `frontend/lib/api/client.ts` (Core Axios instance only)
-   **Rationale**: Improves code discoverability and enables lazy loading of features.
-   **Complexity**: M
-   **Dependencies**: Change 1 (Directory setup).
-   **Risks**: Breaking imports across the entire frontend.

### Change 3: Refactor `backend/app/routers/summaries.py`
-   **Current**: 1,117 lines. Contains the core `_generate_summary_background` logic, mixing HTTP routing with heavy business logic (orchestration, DB access, external API calls).
-   **Proposed**: Extract business logic into a dedicated service layer:
    -   Create `backend/app/services/summary_orchestrator.py` (or similar) to hold the generation logic.
    -   Keep `summaries.py` as a thin router that calls this service.
-   **Rationale**: Separation of concerns. Router should only handle HTTP request/response, not business rules.
-   **Complexity**: XL
-   **Dependencies**: Phase 0 (Tests).
-   **Risks**: Breaking the core product loop (summary generation).

### Change 4: Decompose `SummarySections.tsx`
-   **Current**: 409 lines. Handles UI rendering, Markdown processing, and data normalization.
-   **Proposed**:
    -   Extract `normalizeRisk`, `renderMarkdownValue` to `frontend/lib/formatters.ts`.
    -   Create sub-components: `frontend/features/filings/components/SummaryFinancials.tsx`, `SummaryRisks.tsx`, etc.
-   **Rationale**: Improves readability and allows for independent testing of section rendering.
-   **Complexity**: M
-   **Dependencies**: Change 1.
-   **Risks**: Visual regressions in summary view.

### Change 5: Modularize `openai_service.py` (Cautious Approach)
-   **Current**: 2,471 lines. Handles Prompts, Validation, API Calls, Parsing.
-   **Proposed**: **Do NOT split blindly.**
    -   Identify clear seams (e.g., `PromptManager` class, `ResponseParser` class).
    -   Extract *only* if it simplifies the main service without adding excessive indirection.
    -   **Decision**: Defer strict splitting until better backend test coverage is established, unless a clear, low-risk extraction is found (e.g., moving static prompt text to config/files).
-   **Complexity**: L (Deferred/Limited)
-   **Risks**: Performance regression (import overhead), logic errors.

---

## Migration Sequence

### Phase 0: The Safety Net (Mandatory)
1.  **Backend**: Create `backend/tests/integration/test_summaries_flow.py` to cover the `_generate_summary_background` logic end-to-end.
2.  **Frontend**: Ensure `filing-page-renders.spec.ts` covers all tabs in `SummarySections`.
3.  **Baseline**: Run `./scripts/performance-comparison.sh` (to be created) to establish baseline metrics.

### Phase 1: Low Hanging Fruit & Structure
1.  **Structure**: Create the `frontend/features/` directory skeleton.
2.  **Cleanup**: Resolve `StatCard.tsx` duplication.
3.  **Config**: Fix `requirements.txt` confusion (root vs backend).

### Phase 2: Frontend Refactoring
1.  **API Split**: Refactor `api.ts` into feature-based modules.
    -   *Validation*: Check all imports, run E2E tests.
2.  **UI Decomposition**: Split `SummarySections.tsx`.
    -   *Validation*: Visual check, Unit tests.

### Phase 3: Backend Core Refactoring
1.  **Service Extraction**: Move `_generate_summary_background` to `SummaryGenerationService`.
    -   *Validation*: Run new integration tests.
2.  **Dependency Injection**: Refactor Router to use the new Service.

---

## Risk Assessment

| Change | Risk Level | Impact | Mitigation |
| :--- | :--- | :--- | :--- |
| **Backend Summary Refactor** | 🔴 High | Summaries stop generating or fail silently. | **Critical**: Write integration tests FIRST. Feature flag new service if possible. |
| **Frontend API Split** | 🟡 Medium | "Module not found" errors, broken auth flow. | TypeScript compiler (strict), full E2E run. |
| **StatCard Merge** | 🟢 Low | Minor UI glitch. | Visual regression check. |

---

## Success Criteria

-   [ ] **Test Coverage**: Backend coverage increases from <5% to >20% (focused on critical paths).
-   [ ] **File Size**: `api.ts` < 200 lines (currently 651). `summaries.py` < 400 lines (currently 1117).
-   [ ] **Performance**: API response times do not degrade by >5%.
-   [ ] **Build**: `npm run build` passes. `mypy` passes.

## Rollback Plan

1.  **Git Tags**: Tag `pre-refactor` before starting.
2.  **Atomic Commits**: Each move (e.g., "Extract auth-api") is a separate commit.
3.  **Revert Trigger**: If `npm run test` or `pytest` fails after a step, **revert immediately** and investigate. Do not "fix forward" on a broken refactor.
