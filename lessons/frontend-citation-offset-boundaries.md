# Resolve citation starts to the text node containing the first matched character

Date: 2026-09-05   Area: frontend

**Context**: At a text-node boundary, an inclusive upper bound selected the preceding paragraph's
end. The citation range still contained the right text, but the flash and scroll targeted the
preceding paragraph. The old test checked only that some paragraph flashed.

**Rule**: Resolve range starts using a half-open interval and range ends using the preceding
character's node. Empty text nodes own no characters. Pin the actual flashed and scrolled element,
the range's start node, and an excerpt ending at the last character in the document.

**Evidence**: `frontend/features/filings/components/copilot/highlightInDom.ts` and
`frontend/tests/unit/highlightInDom.spec.ts` and `frontend/tests/e2e/copilot-highlight-css.spec.ts`
(PR #691). Restoring the inclusive-start predicate makes the exact-target assertions fail;
removing end affinity fails the terminal and internal-boundary range assertions.
