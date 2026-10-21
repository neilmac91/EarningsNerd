# Point homepage receipts at the primary filing document and check the destination independently

Date: 2026-10-22 · Area: frontend

**Context.** The homepage emitted twelve anchors to Apple's FY2025 accession directory. The
static samples shared that directory URL, while the live hero discarded the API's `document_url`
and selected `sec_url`. Component tests compared links with those same inputs, so they accepted
the wrong destination. The sample-accuracy gate checked figures and quotes without checking URLs.

**Rule.** Static Apple sample receipts open the verified primary 10-K document. The live hero
uses `originalDocumentUrl`, preferring the chosen filing's `document_url` and retaining the
existing folder fallback only when no usable document URL is supplied. Test the expected
destination independently of the sample constant, and exercise the API-to-rendered-link path.

**Evidence.** `frontend/tests/unit/landingSamplesVerified.spec.ts` checks every static sample URL
(the separate Multi-Period snapshot excepted). `frontend/tests/unit/hero-example-surface.spec.tsx`
checks the static fallback and the live API-to-hero link with a different company's document,
including unavailable-document behavior. `frontend/lib/serverApi.ts` shares the filing page's
document-selection helper.
