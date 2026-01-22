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
   - Root `/requirements.txt` lists Flask (unused) instead of FastAPI
   - Backend `/backend/requirements.txt` exists and is correct
   - Action Required: Clean up or remove root requirements.txt to avoid confusion, ensure backend/requirements.txt is complete

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
│   │   ├── api/                 # Domain-specific endpoint definitions
│   │   │   └── companies-api.ts # e.g., getCompany(), searchCompanies()
│   │   └── types/               # Feature-specific types
│   ├── filings/
│   │   └── api/
│   │       └── filings-api.ts   # e.g., getFiling(), getCompanyFilings()
│   ├── summaries/
│   ├── watchlist/
│   ├── auth/
│   │   └── api/
│   │       └── auth-api.ts      # e.g., login(), register(), logout()
│   └── dashboard/
├── components/                   # Shared/reusable components
│   ├── ui/                      # Base UI components
│   ├── layout/                  # Layout components
│   ├── charts/                  # Chart components
│   └── forms/                   # Form components
├── lib/                         # Utilities and helpers
│   ├── api/                     # Shared API infrastructure only
│   │   ├── client.ts            # Axios instance, base configuration
│   │   ├── interceptors.ts      # Request/response interceptors
│   │   └── types.ts             # Shared API types (error handling, etc.)
│   ├── utils/                   # Pure utility functions
│   ├── hooks/                   # Shared custom hooks
│   └── constants/               # Centralized constants
├── types/                       # Shared TypeScript types
├── config/                      # Configuration files
└── __tests__/                   # Test files mirroring structure
```

**Important:** Domain-specific API calls (e.g., `getCompany()`, `getFiling()`) belong in `features/.../api/`. The `lib/api/` directory should contain ONLY shared infrastructure: the Axios client instance, interceptors, and shared types. This prevents confusion and maintains clear separation of concerns.

### Backend Structure Suggestion

```
backend/
├── app/
│   ├── api/                     # API layer (presentation)
│   │   ├── routers/            # Endpoint definitions (thin controllers)
│   │   ├── dependencies.py     # Dependency injection setup
│   │   └── middleware.py       # Middleware
│   ├── core/                    # Core business logic (domain layer)
│   │   ├── services/           # Business logic services
│   │   ├── domain/             # Domain models (entities)
│   │   ├── ports/              # Interface definitions (Clean Architecture)
│   │   │   ├── repositories.py # Repository interfaces (abstract base classes)
│   │   │   ├── ai_service.py   # AI service interface
│   │   │   ├── sec_service.py  # SEC service interface
│   │   │   └── payment_service.py # Payment service interface
│   │   └── exceptions.py       # Custom exceptions
│   ├── infrastructure/          # External integrations (adapters)
│   │   ├── persistence/        # Database implementations
│   │   │   ├── database.py     # SQLAlchemy setup
│   │   │   └── repositories/   # Repository implementations
│   │   │       ├── companies_repository.py
│   │   │       ├── filings_repository.py
│   │   │       └── users_repository.py
│   │   ├── ai/                 # AI service implementation
│   │   │   └── openai_adapter.py # Implements core/ports/ai_service.py
│   │   ├── sec/                # SEC API client implementation
│   │   │   └── sec_edgar_adapter.py
│   │   ├── payments/           # Payment service implementation
│   │   │   └── stripe_adapter.py
│   │   └── email/              # Email service implementation
│   │       └── resend_adapter.py
│   ├── schemas/                 # Pydantic schemas (DTOs)
│   │   ├── requests/           # Request DTOs
│   │   ├── responses/          # Response DTOs
│   │   └── internal/           # Internal DTOs
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

**Architecture Pattern: Clean Architecture (Ports & Adapters)**

This structure follows the **Dependency Inversion Principle**:
- **Core/Ports**: Define interfaces (contracts) for external services - these are abstract base classes
- **Infrastructure**: Implement those interfaces (adapters) - these are concrete implementations
- **Benefits**:
  - Core business logic doesn't depend on external implementations
  - Easy to swap implementations (e.g., switch from OpenAI to another LLM provider)
  - Highly testable - mock interfaces in unit tests
  - Clear separation of concerns

**Example:**
```python
# core/ports/repositories.py (interface)
class ICompanyRepository(ABC):
    @abstractmethod
    async def get_by_ticker(self, ticker: str) -> Optional[Company]:
        pass

# infrastructure/persistence/repositories/companies_repository.py (implementation)
class CompanyRepository(ICompanyRepository):
    async def get_by_ticker(self, ticker: str) -> Optional[Company]:
        # SQLAlchemy implementation
        pass

# core/services/company_service.py (business logic)
class CompanyService:
    def __init__(self, repo: ICompanyRepository):  # Depends on interface
        self.repo = repo
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

**After EACH change (mandatory):**
- [ ] Run affected unit tests
- [ ] Run integration tests for changed modules
- [ ] TypeScript type checking passes
- [ ] ESLint passes
- [ ] Build succeeds
- [ ] Manual testing of affected features

**After all changes (comprehensive validation):**

#### Functional Validation
- [ ] Full test suite passes (unit + integration + E2E)
- [ ] No TypeScript errors (`npm run type-check`)
- [ ] No ESLint errors (`npm run lint`)
- [ ] Build succeeds for both frontend and backend
- [ ] All critical user flows work end-to-end:
  - [ ] User registration and login
  - [ ] Company search and filing view
  - [ ] Summary generation (full flow)
  - [ ] Watchlist CRUD operations
  - [ ] Subscription management
  - [ ] Data export (GDPR)

#### Performance Validation
- [ ] **Build Performance**: Build time ≤ baseline + 5%
- [ ] **Frontend Performance**:
  - [ ] Bundle size ≤ baseline + 10%
  - [ ] Lighthouse performance score ≥ baseline - 5 points
  - [ ] First Contentful Paint ≤ baseline + 10%
  - [ ] Largest Contentful Paint ≤ baseline + 10%
  - [ ] Time to Interactive ≤ baseline + 10%
- [ ] **Backend Performance** (for critical endpoints):
  - [ ] Average response time ≤ baseline + 5%
  - [ ] P95 response time ≤ baseline + 10%
  - [ ] P99 response time ≤ baseline + 15%
  - [ ] Throughput (requests/sec) ≥ baseline - 5%
- [ ] **Test Performance**: Test suite execution time ≤ baseline + 10%
- [ ] **Memory Usage**: No memory leaks detected in long-running processes

#### Code Quality Validation
- [ ] No code duplication (check with `jscpd` or similar)
- [ ] No circular dependencies (check with `madge` for frontend)
- [ ] All imports resolve correctly
- [ ] No dead code (unused exports)
- [ ] Consistent code style throughout

#### Documentation Validation
- [ ] All new modules have docstrings/JSDoc
- [ ] README updated if structure changed
- [ ] Architecture decision records (ADRs) created
- [ ] Migration guide completed
- [ ] API documentation updated (if applicable)

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

## Performance & Functionality Risk Controls

**⚠️ CRITICAL: File size reduction is a MEANS, not an END ⚠️**

The goal is NOT to blindly hit line count targets. The real objectives are:
- Improved maintainability through clear separation of concerns
- Better testability through modular design
- Reduced cognitive load through focused, single-purpose modules

### When NOT to Split Files

**DO NOT split files if:**
1. **Performance-Critical Code**: Hot paths that benefit from being in one place
   - Example: Core rendering logic, tight loops, performance-sensitive calculations
   - Validation: Profile before and after to ensure no regression

2. **Tightly Coupled Logic**: Code where separation would hurt readability
   - Example: State machine implementations, complex algorithms
   - Rule: If you need to constantly jump between files to understand flow, don't split

3. **Already Cohesive**: Code that has a single, clear purpose even if long
   - Example: A configuration file with 500 well-organized constants
   - Rule: High cohesion > arbitrary line limits

4. **Would Create Excessive Indirection**: Too many layers make code harder to follow
   - Anti-pattern: `UserService` → `UserHelper` → `UserUtils` → `UserFormatter`
   - Rule: Maximum 3-4 layers of abstraction

### Mandatory Validation for Each File Split

For EVERY file you split, you MUST validate:

#### 1. Functionality Validation
```markdown
### Pre-Refactor Checklist
- [ ] Write tests for current behavior (if none exist)
- [ ] Document current functionality
- [ ] Identify all dependencies and dependents
- [ ] Run full test suite and document results

### Post-Refactor Checklist
- [ ] All existing tests pass unchanged
- [ ] New tests for split modules pass
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Manual testing of affected features
```

#### 2. Performance Validation

**Before splitting any file:**
```bash
# Measure current performance
npm run build              # Note build time
npm run test               # Note test time
# For backend
pytest --durations=10      # Note slowest tests
```

**After splitting:**
```bash
# Re-measure and compare
npm run build              # Must not increase >5%
npm run test               # Must not increase >10%
pytest --durations=10      # Must not regress
```

**For frontend components:**
```javascript
// Use React DevTools Profiler
// Measure render time before/after refactoring
// Ensure no performance regression in:
// - Initial render time
// - Re-render performance
// - Bundle size impact
```

**For backend services:**
```python
# Profile API endpoints
# Measure before/after:
# - Response time (p50, p95, p99)
# - Memory usage
# - Database query count
# - External API calls
```

#### 3. Bundle Size Validation (Frontend)

```bash
# Before refactoring
npm run build
# Note: First Load JS, Total Size

# After refactoring
npm run build
# Compare - should not increase significantly

# Analyze bundle
npx next-bundle-analyzer   # Check for duplication
```

**Red flags:**
- Bundle size increases >10%
- Code duplication detected
- Shared dependencies loaded multiple times

#### 4. Type Safety Validation

```bash
# Must pass after every change
npm run type-check         # TypeScript
tsc --noEmit
mypy backend/              # Python (if using mypy)
```

### Risk-Based Refactoring Strategy

Classify each file by risk level before splitting:

#### 🟢 Low Risk (Safe to refactor)
- Utility functions (pure functions, no side effects)
- Type definitions
- Constants and configuration
- Simple presentational components
- Isolated service functions

**Approach:** Refactor confidently with basic test coverage

#### 🟡 Medium Risk (Refactor with caution)
- Complex components with state
- Services with multiple dependencies
- API routes with business logic
- Database models with relationships

**Approach:**
- Comprehensive test coverage BEFORE refactoring
- Incremental changes with validation at each step
- Feature flag the changes if possible

#### 🔴 High Risk (Refactor carefully or defer)
- Authentication/authorization logic
- Payment processing
- Data validation and sanitization
- Performance-critical paths
- Code with known bugs or technical debt

**Approach:**
- Extensive test coverage (>95%)
- Pair programming or code review BEFORE changes
- Canary deployment or feature flags
- Performance benchmarking
- Consider deferring if value is low

### Size Guideline Nuances

**Instead of hard limits, use these principles:**

1. **Cohesion over size**: Keep related code together even if it's long
2. **Complexity over lines**: A 500-line file with simple, repetitive code is fine
3. **Readability over metrics**: Can a developer understand the file in 5 minutes?

**Refined guidelines:**

```python
# Backend Python files
- Simple models/schemas: Any size (could be 1000+ lines of field definitions)
- Services: <400 lines OR <20 public methods (whichever comes first)
- Routers: <300 lines OR <10 endpoints (whichever comes first)
- Utilities: <200 lines per file

# Frontend TypeScript files
- Page components: <500 lines (pages are naturally complex)
- Feature components: <300 lines
- Shared components: <150 lines
- Hooks: <100 lines per hook
- API clients: <200 lines per domain (NOT per file - one file per domain is fine)
```

### Performance Benchmarking Requirements

Before approving the restructuring plan, establish baselines:

#### Frontend Baselines
```bash
# Build performance
npm run build
# Record: Build time, First Load JS, Total Size

# Runtime performance (use Lighthouse)
npm run build && npm start
# Record: Performance score, FCP, LCP, TTI, CLS

# Test performance
npm run test -- --coverage
# Record: Test execution time, coverage %
```

#### Backend Baselines
```bash
# API performance (use wrk, hey, or ab)
wrk -t4 -c100 -d30s http://localhost:8000/api/health
# Record: Requests/sec, Latency (avg, p95, p99)

# Critical endpoints
wrk -t4 -c50 -d30s http://localhost:8000/api/summaries/filing/123
# Record for each critical endpoint

# Test performance
pytest --durations=20
# Record: Slowest test times
```

### Rollback Criteria

**Automatically rollback if:**
- [ ] Any test fails after refactoring
- [ ] TypeScript/ESLint errors introduced
- [ ] Build time increases >10%
- [ ] Bundle size increases >15%
- [ ] API response time degrades >20% (p95)
- [ ] Memory usage increases >25%
- [ ] Any production functionality breaks

### Incremental Refactoring Protocol

**Never refactor everything at once. Use this protocol:**

1. **Phase 1**: Split ONE large file
   - Run full validation
   - Get it merged
   - Monitor production for 1-2 days

2. **Phase 2**: If Phase 1 successful, split next file
   - Repeat validation
   - Continue monitoring

3. **Phase 3**: After 3-5 successful splits, accelerate
   - But maintain validation discipline

**If ANY split causes issues:**
- Pause the refactoring
- Investigate root cause
- Fix or rollback
- Reassess approach before continuing

## Success Metrics

After restructuring, the codebase should achieve:

**Measurable Improvements:**
- [ ] Average file size reduced to <300 lines (excluding justified exceptions)
- [ ] Test coverage >80%
- [ ] Zero circular dependencies
- [ ] Build time not increased by >5%
- [ ] API performance not degraded by >5% (p95 latency)
- [ ] Bundle size not increased by >10%
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
8. **What are the performance implications and how will we measure them?**
9. **Which files should NOT be split and why?**
10. **What is our rollback plan if issues arise?**

## Validation Tools & Commands

Use these specific tools to validate your refactoring:

### Frontend Validation Tools

#### Performance Measurement
```bash
# Build performance
time npm run build

# Bundle analysis
npm install -g @next/bundle-analyzer
ANALYZE=true npm run build

# Runtime performance (Lighthouse)
npm install -g lighthouse
lighthouse http://localhost:3000 --view

# Check for duplicate code
npx jscpd frontend/

# Check for circular dependencies
npx madge --circular --extensions ts,tsx frontend/
```

#### Type & Code Quality
```bash
# Type checking
npm run type-check
# or
npx tsc --noEmit

# Linting
npm run lint

# Find dead code
npx unimported

# Test coverage
npm run test -- --coverage
```

### Backend Validation Tools

#### Performance Measurement
```bash
# API load testing (install wrk: apt-get install wrk)
wrk -t4 -c100 -d30s http://localhost:8000/api/health

# Alternative: using hey (install: go install github.com/rakyll/hey@latest)
hey -z 30s -c 50 http://localhost:8000/api/health

# Profile Python code
python -m cProfile -o profile.stats backend/main.py
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# Memory profiling
pip install memory-profiler
python -m memory_profiler backend/main.py
```

#### Type & Code Quality
```bash
# Type checking (if using mypy)
pip install mypy
mypy backend/ --ignore-missing-imports

# Linting
pip install flake8 black
flake8 backend/
black --check backend/

# Test coverage
pytest --cov=app --cov-report=html --cov-report=term

# Find dead code
pip install vulture
vulture backend/
```

### Comparative Performance Testing Script

Create this script to automate before/after comparison:

```bash
#!/bin/bash
# performance-comparison.sh

echo "=== Performance Baseline Capture ==="
echo "Timestamp: $(date)" > performance-baseline.txt

echo -e "\n[Frontend Build]" >> performance-baseline.txt
(time npm run build) 2>&1 | grep real >> performance-baseline.txt

echo -e "\n[Frontend Tests]" >> performance-baseline.txt
(time npm run test) 2>&1 | grep real >> performance-baseline.txt

echo -e "\n[Backend Tests]" >> performance-baseline.txt
(cd backend && time pytest) 2>&1 | grep real >> performance-baseline.txt

echo -e "\n[API Performance - Health Check]" >> performance-baseline.txt
wrk -t2 -c10 -d10s http://localhost:8000/api/health | grep "Requests/sec" >> performance-baseline.txt

echo "Baseline captured in performance-baseline.txt"
```

### Recommended Validation Workflow

1. **Before starting refactoring:**
   ```bash
   # Capture baselines
   ./performance-comparison.sh
   npm run build > build-before.log
   npm run test -- --coverage > test-before.log
   ```

2. **After each significant change:**
   ```bash
   # Quick validation
   npm run type-check && npm run lint && npm run test
   ```

3. **After completing refactoring:**
   ```bash
   # Full comparison
   ./performance-comparison.sh
   npm run build > build-after.log
   npm run test -- --coverage > test-after.log

   # Compare
   diff build-before.log build-after.log
   diff test-before.log test-after.log
   ```

## What to Do When Performance or Functionality Regresses

If validation reveals issues, follow this protocol:

### Minor Regression (5-10% performance degradation or small bugs)

1. **Analyze root cause**
   - Profile the specific slow code path
   - Identify what changed to cause the regression
   - Determine if it's acceptable technical debt

2. **Decision matrix**
   - **If maintainability gain > performance loss**: Document trade-off, add to technical debt backlog
   - **If performance loss unacceptable**: Optimize the new structure OR revert the change
   - **If bug found**: Fix immediately before proceeding

3. **Optimization strategies**
   - Add memoization (React.memo, useMemo, useCallback)
   - Implement lazy loading / code splitting
   - Optimize imports (tree shaking)
   - Cache expensive computations
   - Use performance profiling to find bottlenecks

### Major Regression (>10% performance degradation or critical bugs)

1. **STOP immediately**
2. **Revert the problematic change**
3. **Root cause analysis**
   - What was refactored?
   - What assumption was wrong?
   - Why didn't tests catch it?

4. **Reassess approach**
   - Was the split necessary?
   - Is there a better way to split?
   - Should this file remain as-is?

5. **Document decision**
   - Create ADR explaining why certain files weren't split
   - Add comments in code explaining why large files are acceptable

### Critical Failure (Production broken or data corruption risk)

1. **IMMEDIATE ROLLBACK**
2. **Post-mortem**
   - What broke and why?
   - What validation step failed?
   - How do we prevent this in the future?

3. **Strengthen validation**
   - Add missing tests
   - Add performance regression tests
   - Improve staging environment validation

### Example: When to Accept a Trade-off

```markdown
## ADR: Keep openai_service.py as single 2,471-line file

**Context**: OpenAI service handles prompt loading, AI summarization, validation, and normalization.

**Decision**: Keep as single file despite size.

**Rationale**:
- Splitting would add 15% latency due to increased import overhead in hot path
- Code is highly cohesive - all functions relate to AI summarization
- Splitting would create artificial boundaries (e.g., where does validation end and normalization begin?)
- File is well-organized with clear sections

**Consequences**:
- Accept: Larger file size (2,471 lines)
- Gain: Better performance, easier to understand flow, no artificial boundaries
- Mitigate: Use clear section comments, comprehensive unit tests

**Alternatives Considered**:
1. Split by functionality - rejected due to performance impact
2. Extract only prompts - rejected because prompts are tightly coupled to validation
3. Split by filing type - rejected because logic is shared across types

**Review Date**: Revisit if file grows beyond 3,000 lines
```

## Deliverables

1. **Restructuring Plan Document** (before any code changes)
2. **Performance Baseline Report** (before changes)
3. **Updated codebase** with all changes implemented
4. **Performance Comparison Report** (after changes)
5. **Migration guide** for developers
6. **Updated documentation** (README, architecture docs)
7. **Test suite** with improved coverage
8. **ADRs** for significant architectural decisions
9. **List of files NOT refactored** with justifications

## Remember

🎯 **Plan first, execute later**
🧪 **Test everything**
📊 **Measure before and after**
🔄 **Iterate incrementally**
✅ **Keep it working**
⚖️ **Balance metrics with maintainability**
🚫 **Don't refactor for refactoring's sake**

### Core Principles

1. **Functionality First**: Never sacrifice working code for cleaner structure
2. **Performance Matters**: Measure everything, accept no significant regression
3. **Pragmatism over Purity**: 80/20 rule - focus on changes with highest impact
4. **Reversibility**: Every change should be easily reversible
5. **Evidence-Based**: Make decisions based on data, not assumptions

Your goal is not just to reorganize files or hit arbitrary metrics, but to create a maintainable, scalable foundation that will support this application's growth for years to come. Take your time, think critically, and make decisions that your future self (and other developers) will thank you for.

**If in doubt, err on the side of caution. A working codebase with technical debt is better than a broken codebase with perfect structure.**

Begin with the planning phase and present your comprehensive plan before making any changes.
