# Admit the complete Copilot answer before publishing any candidate prose

Date: 2026-09-29 · Area: arch / Copilot publication boundary

**Context.** Copilot previously streamed an answer before checking its trailing text citations,
then published failed citations with a label. Replacing the final answer could not retract prose
already read. Duplicate IDs could overwrite failed evidence, and renumbering could attach a
previously unresolved numeric literal to an unrelated source.

**Rule.** Keep candidate prose private until a complete citation array is parsed and every referenced
text declaration passes the existing verifier. Do not repair incomplete declarations or invent IDs.
An absent envelope is incomplete, even when its prose has no markers; an explicit empty array
preserves uncited answers. Provider EOF alone is not evidence that the envelope completed.
Reject conflicting referenced identities, final numbering collisions, contradictory not-disclosed
envelopes, and empty resolved answers. Publish one admitted completion or a safe application error.
Live progress and activity labels must contain only application-owned text. Preserve cancellation,
provider accounting and the router's completion-only quota conversion.

**Evidence.** `backend/tests/unit/test_copilot.py::test_service_publication_boundary` pauses the
provider and inspects the real service→ASGI SSE wire before and after admission, including quota,
valid tool provenance, duplicates, malformed envelopes, numeric literals and Markdown. The existing
disconnect owner now runs the real buffering service. Frontend parser and mounted-rail owners guard
completion-only delivery, terminal states and cancellation. The release's committed early-token
fault/restoration belongs to this same publication gate.

Ready review found the initial legacy no-envelope allowance still completed and consumed quota.
The existing no-declaration ASGI case now requires rejection; its natural failing-before and
fixed-after runs preserve the correction separately from the original early-token mutation.

Source matching does not certify interpretation, causality, entity/period entailment, not-disclosed
truth, or every uncited claim. Containment errors do not turn answerable evaluation failures into
successful answers. Prompts, models, source selection and evaluation criteria remain separate.
