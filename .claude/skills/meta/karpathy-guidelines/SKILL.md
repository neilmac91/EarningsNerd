---
name: karpathy-guidelines
description: Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.
version: 1.0.0
license: MIT
---

# Karpathy Guidelines

Behavioral guidelines drawn from Andrej Karpathy's observations on LLM coding
pitfalls. They prioritize caution over speed; apply judgment on trivial tasks
rather than enforcing all four rigidly.

## Core Principles

### 1. Think Before Coding
Surface uncertainties rather than concealing them. Articulate your working
assumptions upfront, present multiple interpretations when they exist, and
acknowledge confusion explicitly. Propose simpler alternatives when available.

### 2. Simplicity First
Implement only what's requested. Avoid speculative features, unnecessary
abstractions, or error handling for edge cases unlikely to occur. The standard:
"Would a senior engineer call this overcomplicated?"

### 3. Surgical Changes
Preserve existing code style and structure. Confine modifications to what
directly addresses the request. Remove only the dependencies your changes
create as orphans — leave pre-existing dead code untouched unless instructed
otherwise.

### 4. Goal-Driven Execution
Convert abstract requests into measurable checkpoints. Create tests that
validate the desired outcome, then satisfy them incrementally. State multi-step
plans with verification steps for each phase.

---

## Provenance

Vendored from the upstream project, pinned to a reviewed commit (not tracking `main`):

- **Source:** https://github.com/multica-ai/andrej-karpathy-skills
- **Path:** `skills/karpathy-guidelines/SKILL.md`
- **Pinned commit:** `2c606141936f1eeef17fa3043a72095b4765b9c2` (2026-04-20)
- **License:** MIT

The content above was reviewed before vendoring: it is behavioral guidance only,
with no executable code, network calls, or instructions to alter agent
permissions. Re-review and bump the pinned commit before pulling upstream changes.
