"""AI summarization internals, split out of ``app.services.openai_service`` (roadmap S2).

Every symbol here is re-exported by ``app.services.openai_service`` so existing callers keep a
single import surface — this package is an organizational split, not a new public API. The split is
behavior-preserving ("pure moves"): leaf helper modules hold standalone functions/constants, and the
``_*Mixin`` classes hold the ``OpenAIService`` method groups that couple through ``self``.

Import discipline (a regression test walks this package): NOTHING here may import ``app.models`` /
the ``User`` model — the AI path is fed filing text + financial metrics only, never app-user PII.
"""
