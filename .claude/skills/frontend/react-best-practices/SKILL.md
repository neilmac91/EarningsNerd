---
name: react-best-practices
description: Performance optimization rules for React and Next.js applications
version: 1.0.0
author: vercel
source: https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices
---

# React Best Practices

This skill provides 57 performance optimization rules for React and Next.js applications, organized by impact level. Apply these rules when writing components, implementing data fetching, reviewing code, or optimizing bundle sizes.

## Rule Categories by Impact

| Priority | Category | Primary Benefit |
|----------|----------|-----------------|
| CRITICAL | Eliminating Waterfalls | 2-10× speedup via parallelization |
| CRITICAL | Bundle Size | Faster cold starts, reduced TTI |
| HIGH | Server-Side Performance | Eliminates sequential fetching |
| MEDIUM-HIGH | Client Data Fetching | Automatic request deduplication |
| MEDIUM | Re-render Optimization | Prevents wasted computations |
| MEDIUM | Rendering Performance | Browser optimization |
| LOW-MEDIUM | JavaScript Performance | Algorithm efficiency |
| LOW | Advanced Patterns | Edge case patterns |

## Quick Reference

### Most Impactful Rules

1. **Defer await until needed** - Don't await at function start
2. **Avoid barrel imports** - Import directly from source files
3. **Use Promise.all()** - Parallelize independent operations
4. **Dynamic imports** - Lazy-load heavy components
5. **Use React.cache()** - Deduplicate per-request data

See [rules.md](./rules.md) for the complete 57-rule reference with code examples.

## When to Apply

- Writing new React/Next.js components
- Reviewing code for performance issues
- Refactoring existing codebases
- Optimizing bundle size and load times
- Implementing data fetching patterns
