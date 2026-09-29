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
envelopes, and empty resolved answers. A not-disclosed response needs a nonempty reason and its
complete, strictly parsed followups array of two or three nonblank strings. Do not invent a reason,
repair an incomplete array, or discard extra trailing content. Publish one admitted completion or
a safe application error.
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

The second ready review found the same EOF assumption in the separate not-disclosed branch.
The existing ASGI owner now proves rejection and quota release for incomplete verdicts on both
free and Pro paths, and preserves complete verdicts with split chunks. The existing browser stream
owner rejects incomplete not-disclosed completion shapes. Both corrections retain their natural
failing-before/fixed-after evidence; the original committed proofs remain historical evidence.

A separate retained provider response declared tool `F1`/`F2` strings inside the text-citation
array. Output-format step 3 now explicitly requests only positive-integer text IDs and an empty
array for tool-only answers. This aligns the prompt with the existing strict parser without
weakening admission or financial requirements. The earlier failure without a retained raw
candidate is not assigned this cause.

Source matching does not certify interpretation, causality, entity/period entailment, not-disclosed
truth, or every uncited claim. Containment errors do not turn answerable evaluation failures into
successful answers. The prompt correction changes only format step 3; model, source selection,
financial instructions and evaluation criteria remain unchanged. Its measured effect requires
fresh aggregate evidence on the changed candidate.
