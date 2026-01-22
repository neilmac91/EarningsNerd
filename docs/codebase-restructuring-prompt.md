# EarningsNerd Codebase Restructuring & Optimization

You are a world-class software architect and senior developer with expertise in Next.js, FastAPI, TypeScript, Python, and enterprise-scale application architecture. Your task is to analyze and restructure the EarningsNerd codebase to optimize it for long-term maintainability, scalability, and developer experience.

## Context

EarningsNerd is an AI-powered SEC filing analysis platform with:
- **Frontend**: Next.js 14 (App Router), TypeScript, React Query, Tailwind CSS
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, OpenAI-compatible API
- **Features**: User authentication, Stripe payments, AI summarization, watchlists, analytics
- **Architecture**: Layered architecture with clear frontend/backend separation

## Critical Requirements

**⚠️ PLANNING PHASE IS MANDATORY ⚠️**

Before making ANY code changes, you MUST:

1. **Create a comprehensive restructuring plan** that includes:
   - Detailed analysis of current issues and their impact
   - Proposed new directory structure with rationale
   - File-by-file migration strategy
   - Risk assessment and mitigation strategies
   - Testing strategy to ensure no regression
   - Rollback plan if issues arise

2. **Present the plan for review** with:
   - Clear before/after comparisons
   - Estimated complexity for each change
   - Dependencies between changes
   - Recommended order of operations
   - Breaking changes and migration notes

3. **Wait for explicit approval** before executing any changes

## Known Issues to Address

### 🔴 Critical Priority

1. **Code Duplication**
   - Location: `/frontend/components/StatCard.tsx` (124 lines) vs `/frontend/components/charts/StatCard.tsx` (25 lines)
   - Impact: Two different components with same name causing import confusion
   - Action Required: Resolve naming conflict and consolidate if appropriate

2. **Extremely Large Files**
   - `/backend/app/services/openai_service.py` (2,471 lines)
     - Handles: prompt loading, AI summarization, validation, normalization
     - Action Required: Split into focused, single-responsibility modules

   - `/backend/app/routers/summaries.py` (1,116 lines)
     - Action Required: Extract streaming logic, progress tracking to separate modules

   - `/frontend/app/filing/[id]/page-client.tsx` (1,100 lines)
     - Action Required: Extract sub-components for header, generator, metadata

   - `/frontend/lib/api.ts` (651 lines, 44 functions)
     - Action Required: Split by domain (companies, filings, auth, etc.)

3. **Missing/Incorrect Dependencies**
   - `/requirements.txt` lists Flask (unused) instead of FastAPI
   - Action Required: Generate complete, accurate dependency list

### 🟡 High Priority

4. **Tight Coupling**
   - Direct imports of private functions (e.g., `_normalize_risk_factors`)
   - Routers directly calling multiple services
   - Action Required: Implement proper dependency injection, respect encapsulation

5. **Limited Test Coverage**
   - Frontend: Only 1 unit test file (`guards.test.ts`)
   - Backend: Only 1 test file (`test_sec_10k_pipeline.py`)
   - Action Required: Establish comprehensive test suites with >80% coverage target

6. **Inconsistent Error Handling**
   - API client mixes null returns and exceptions
   - Action Required: Standardize error handling patterns

7. **Missing Separation of Concerns**
   - `/frontend/components/SummarySections.tsx` (409 lines): data transformation + rendering + state
   - `/frontend/components/CookieConsent.tsx` (322 lines): cookie management + UI + integration
   - Action Required: Extract hooks and sub-components

### 🟢 Medium Priority

8. **Naming Convention Inconsistencies**
   - Frontend: Mix of `PascalCase.tsx` and `kebab-case.ts`
   - Action Required: Document and enforce conventions

9. **Hard-coded Configuration**
   - Magic numbers scattered throughout (e.g., 150000ms timeout)
   - Action Required: Extract to centralized constants

10. **TODO/FIXME Comments**
    - Found in 15+ files
    - Action Required: Resolve or document as technical debt

## Restructuring Objectives

### 1. Module Organization

**Frontend Goals:**
- Clear separation between UI components, business logic, and data fetching
- Domain-driven folder structure for features
- Reusable component library with proper documentation
- Centralized type definitions and API clients

**Backend Goals:**
- Clear layering: routers → services → repositories → models
- Domain-driven service organization
- Dependency injection for testability
- Separation of business logic from framework code

### 2. Code Quality Standards

**Must achieve:**
- No file exceeds 300 lines (500 max for complex components)
- No function exceeds 50 lines
- No code duplication (DRY principle)
- Single Responsibility Principle for all modules
- Clear dependency graph (no circular dependencies)

### 3. Testing Standards

**Requirements:**
- Unit test coverage: >80%
- Integration tests for all API endpoints
- E2E tests for critical user flows
- Component tests for interactive UI
- Mock external dependencies (OpenAI, Stripe, SEC API)

### 4. Developer Experience

**Improvements needed:**
- Clear documentation for architecture decisions
- Consistent code style enforced by linters
- Pre-commit hooks for quality checks
- Clear onboarding documentation
- ADR (Architecture Decision Records) for major changes

## Proposed High-Level Structure

### Frontend Structure Suggestion

```
frontend/
├── app/                          # Next.js App Router (pages only)
├── features/                     # Feature-based organization
│   ├── companies/
│   │   ├── components/          # Feature-specific components
│   │   ├── hooks/               # Feature-specific hooks
│   │   ├── api/                 # Feature-specific API calls
│   │   └── types/               # Feature-specific types
│   ├── filings/
│   ├── summaries/
│   ├── watchlist/
│   ├── auth/
│   └── dashboard/
├── components/                   # Shared/reusable components
│   ├── ui/                      # Base UI components
│   ├── layout/                  # Layout components
│   ├── charts/                  # Chart components
│   └── forms/                   # Form components
├── lib/                         # Utilities and helpers
│   ├── api/                     # API client split by domain
│   ├── utils/                   # Pure utility functions
│   ├── hooks/                   # Shared custom hooks
│   └── constants/               # Centralized constants
├── types/                       # Shared TypeScript types
├── config/                      # Configuration files
└── __tests__/                   # Test files mirroring structure
```

### Backend Structure Suggestion

```
backend/
├── app/
│   ├── api/                     # API layer
│   │   ├── routers/            # Endpoint definitions (thin)
│   │   ├── dependencies.py     # Dependency injection
│   │   └── middleware.py       # Middleware
│   ├── core/                    # Core business logic
│   │   ├── services/           # Business logic services
│   │   ├── domain/             # Domain models
│   │   └── exceptions.py       # Custom exceptions
│   ├── infrastructure/          # External integrations
│   │   ├── database/           # Database layer
│   │   ├── ai/                 # OpenAI service
│   │   ├── sec/                # SEC API client
│   │   ├── payments/           # Stripe
│   │   └── email/              # Resend
│   ├── schemas/                 # Pydantic schemas
│   │   ├── requests/           # Request DTOs
│   │   ├── responses/          # Response DTOs
│   │   └── internal/           # Internal DTOs
│   ├── repositories/            # Data access layer
│   │   ├── companies.py
│   │   ├── filings.py
│   │   └── users.py
│   ├── config/                  # Configuration
│   │   ├── settings.py
│   │   └── constants.py
│   └── utils/                   # Utilities
├── tests/                       # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── scripts/                     # Utility scripts
```

## Your Task

### Phase 1: Analysis & Planning (DO THIS FIRST)

1. **Audit Current Structure**
   - Map all files and their dependencies
   - Identify circular dependencies
   - Analyze code complexity metrics
   - Document current pain points

2. **Create Detailed Migration Plan**
   - New directory structure with complete file mappings
   - Order of operations (what to refactor first)
   - Breaking changes and how to handle them
   - Testing strategy at each step
   - Rollback procedures

3. **Risk Assessment**
   - Identify high-risk changes
   - Determine what requires immediate attention vs. gradual refactoring
   - Estimate effort for each change (S/M/L/XL)
   - Propose validation criteria

4. **Present Plan Document** including:
   ```markdown
   # EarningsNerd Restructuring Plan

   ## Executive Summary
   - Current state assessment
   - Proposed changes overview
   - Expected benefits
   - Risks and mitigations

   ## Detailed Changes
   ### Change 1: [Name]
   - **Current**: [description]
   - **Proposed**: [description]
   - **Rationale**: [why]
   - **Files affected**: [list]
   - **Complexity**: [S/M/L/XL]
   - **Dependencies**: [what must happen first]
   - **Testing**: [validation approach]
   - **Risks**: [potential issues]

   [Repeat for each major change]

   ## Migration Sequence
   1. [First change] - Why this first
   2. [Second change] - Dependencies
   ...

   ## Success Criteria
   - [ ] All tests passing
   - [ ] No functionality regression
   - [ ] Build succeeds
   - [ ] Type checking passes
   - [ ] Linting passes
   - [ ] Performance maintained or improved
   ```

### Phase 2: Execution (ONLY AFTER PLAN APPROVAL)

**Execution Principles:**
- One atomic change at a time
- Run tests after each change
- Commit frequently with clear messages
- Document decisions in code comments
- Keep the application working at each step

**Per-Change Checklist:**
- [ ] Make the change
- [ ] Update imports
- [ ] Update tests
- [ ] Run test suite
- [ ] Update documentation
- [ ] Commit with descriptive message

### Phase 3: Validation

After all changes:
- [ ] Full test suite passes (unit + integration + E2E)
- [ ] No TypeScript errors
- [ ] No ESLint errors
- [ ] Build succeeds for both frontend and backend
- [ ] Manual smoke testing of critical flows
- [ ] Performance benchmarking (no regression)
- [ ] Documentation updated

## Constraints & Guidelines

### DO:
✅ Preserve all existing functionality
✅ Maintain backward compatibility where possible
✅ Write comprehensive tests before refactoring
✅ Use established patterns (don't reinvent the wheel)
✅ Document architectural decisions
✅ Follow existing code style and conventions
✅ Consider performance implications
✅ Think about future maintainability

### DON'T:
❌ Make breaking changes without migration path
❌ Remove code without understanding its purpose
❌ Introduce new dependencies without justification
❌ Over-engineer solutions
❌ Skip testing
❌ Bundle multiple unrelated changes
❌ Ignore edge cases
❌ Create abstractions prematurely

## Success Metrics

After restructuring, the codebase should achieve:

**Measurable Improvements:**
- [ ] Average file size reduced to <300 lines
- [ ] Test coverage >80%
- [ ] Zero circular dependencies
- [ ] Build time not increased by >10%
- [ ] Zero TODO comments (all tracked as issues)
- [ ] Consistent naming conventions (100%)
- [ ] All dependencies properly documented

**Qualitative Improvements:**
- [ ] New developers can understand project structure in <30 minutes
- [ ] Adding new features requires touching <5 files on average
- [ ] Clear separation of concerns throughout
- [ ] Code reviews become faster and more focused
- [ ] Debugging becomes easier with clear error traces

## Questions to Answer in Your Plan

Before executing changes, your plan must answer:

1. **What is the ideal structure for this application's scale and complexity?**
2. **How do we migrate without breaking functionality?**
3. **Which changes provide the most value vs. effort?**
4. **How do we ensure refactoring doesn't introduce bugs?**
5. **What are the long-term maintenance implications?**
6. **How does this support the product roadmap?**
7. **What trade-offs are we making and why?**

## Deliverables

1. **Restructuring Plan Document** (before any code changes)
2. **Updated codebase** with all changes implemented
3. **Migration guide** for developers
4. **Updated documentation** (README, architecture docs)
5. **Test suite** with improved coverage
6. **ADRs** for significant architectural decisions

## Remember

🎯 **Plan first, execute later**
🧪 **Test everything**
📚 **Document decisions**
🔄 **Iterate incrementally**
✅ **Keep it working**

Your goal is not just to reorganize files, but to create a maintainable, scalable foundation that will support this application's growth for years to come. Take your time, think critically, and make decisions that your future self (and other developers) will thank you for.

Begin with the planning phase and present your comprehensive plan before making any changes.
