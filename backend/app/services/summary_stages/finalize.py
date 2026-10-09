"""Finalize stage: the shared projection, the quality verdict, persistence, usage, and the terminal events.

Everything after a provider result (or the deterministic fallback) has arrived: the one
persisted/streamed projection, the deterministic quality verdict with its greppable measurement
channels, the partial-verdict refund, the Summary + FilingContentCache write (in-place refresh with
the keep-better gate, or an INSERT that yields to a concurrent writer), the completion-time usage
count for lease-less callers, the funnel event and the chunk → (partial | error | complete) events.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncIterator

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app import database
from app.models import Filing, Summary, User
from app.services import summary_pipeline as pipeline

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.summary_stages.generation_run import GenerationRun

logger = logging.getLogger(pipeline.__name__)


async def finalize(run: GenerationRun) -> AsyncIterator[dict]:
    """Project, assess, persist, count usage and emit the chunk and terminal events."""
    filing_id, user_id, force_regenerate = run.filing_id, run.user_id, run.force_regenerate
    replace_unready_only = run.replace_unready_only

    # The application-prepared degraded source is private and will be popped by the shared
    # finalizer. Retain it separately so the cache owner can preserve the same decoded-text
    # view for later API/export projection when no critical excerpt exists.
    risk_source_for_cache = run.summary_payload.get("_risk_source_grounding")
    markdown, raw_summary, sections_info, normalized_financial_section = (
        pipeline._finalize_summary_projection(
            run.summary_payload,
            run.xbrl_metrics,
            run.summary_status,
            source_text=run.excerpt or run.filing_text,
            filing_document_url=run.filing_document_url,
        )
    )

    section_coverage = (
        raw_summary.get("section_coverage")
        if isinstance(raw_summary, dict)
        else None
    )
    if section_coverage:
        await run.run_sync_db(
            run.record_progress_sync,
            filing_id,
            "summarizing",
            section_coverage=section_coverage,
        )

    risk_section = sections_info.get("risks") or []
    # Legacy compat columns on the Summary row (management_discussion / key_changes) still get
    # the v2-mapped prose (earnings_quality / forward_signals, re-pointed in summarize_filing).
    management_section = run.summary_payload.get("management_discussion")
    guidance_section = run.summary_payload.get("key_changes")

    # The legacy MD&A/guidance wrapper injection is retired under v2: the v2 taxonomy already
    # carries earnings_quality + forward_signals, and the web reads the render_sections output
    # (rendered_sections), not these keys. Injecting management_discussion_insights /
    # guidance_outlook here would only decorate every v2 row with phantom v1 nodes.

    # S4: deterministic quality verdict (always attached as metadata for the UI badge).
    # sic feeds the bank-aware revenue-grounding rule (P0-2) as the flag-independent
    # FI signal alongside component presence.
    # ``excerpt or filing_text``: when excerpt extraction failed (cache miss + section-parse
    # timeout), ``summarize_filing`` still generated from ``filing_text``'s parsed sample — so the
    # gate must ground against the same text, else every filing-copied figure false-flags on
    # exactly the degraded population. The two are complementary (filing_text is emptied only when
    # the excerpt is in use), and ``untraceable_figures`` returns [] if BOTH are empty.
    quality = pipeline.assess_quality(
        run.summary_payload, run.xbrl_metrics, sic=run.company_sic, excerpt=run.excerpt or "",
        trace_excerpt=run.excerpt or run.filing_text
    )
    raw_summary["quality"] = quality
    untraceable = quality.get("figures_untraceable") or []
    if untraceable:
        # T3.2 advisory-phase measurement channel. The gate ships flag-off, so untraceable dollar
        # figures do NOT tier the summary "partial" — this greppable counter (count first, for a
        # log-based metric threshold) is the only push signal for the flag-flip decision and,
        # post-T5, the regression alarm for derived-aggregate reintroduction.
        logger.info(
            "figure_trace_untraceable count=%d flag=%s filing_id=%s sic=%s figures=%s",
            len(untraceable),
            pipeline.settings.AI_FIGURE_TRACE_GATE,
            filing_id,
            run.company_sic or "",
            "|".join(untraceable),
        )
    if quality.get("tier") == "partial":
        # P0-2 detection: greppable counter of partial verdicts by reason + SIC. A
        # bank-heavy spike after any prompt change is the recurrence signal for the
        # bank-blind-grounding incident class.
        logger.info(
            "summary_quality_partial filing_id=%s cik=%s sic=%s reasons=%s",
            filing_id,
            run.company_cik,
            run.company_sic or "",
            "|".join(quality.get("reasons") or []),
        )
    if quality.get("machine_sections_only"):
        # T5.3 detection (#621 staff review): full-tier verdict where machine-authored
        # XBRL sections alone crossed the 4/9 bar — zero model-authored sections covered.
        # A spike after a prompt/model change means generation collapse is being masked
        # by deterministic content (and, under AI_QUALITY_GATE, still charged); the
        # verdict is honest, but the class is watched, not assumed.
        logger.info(
            "summary_quality_full_machine_only filing_id=%s cik=%s sic=%s covered=%s/%s",
            filing_id,
            run.company_cik,
            run.company_sic or "",
            quality.get("covered_count"),
            quality.get("total_count"),
        )
    attribution_audit = (raw_summary or {}).get("attribution_audit") or {}
    if attribution_audit.get("unverified"):
        # #805 path step 4 measurement channel (count-first): causal clauses the filing does
        # not state, emitted flag on OR off; dropped counts only when the gate is armed.
        verification = attribution_audit.get("verification") or {}
        logger.info(
            "attribution_unverified count=%d checked=%d dropped=%d decider=%s decided=%d "
            "verify_error=%s flag=%s filing_id=%s sic=%s slots=%s",
            len(attribution_audit["unverified"]),
            attribution_audit.get("checked", 0),
            len(attribution_audit.get("dropped") or []),
            attribution_audit.get("decider", "none"),
            verification.get("decided", 0),
            verification.get("error") or "",
            pipeline.settings.AI_ATTRIBUTION_GATE,
            filing_id,
            run.company_sic or "",
            "|".join(str(u.get("slot") or "?") for u in attribution_audit["unverified"]),
        )
    unit_audit = (raw_summary or {}).get("table_cell_unit_audit") or {}
    if unit_audit.get("restored_count") or unit_audit.get("unresolved_count"):
        # Declared table-cell scale owner (source_units) measurement channel, count-first:
        # bare model dollar figures whose declared scale was restored, and those left
        # untouched with the abstention reason. Totals are exact even when the audit's
        # detail lists are capped. Unresolved figures stay visible as written.
        logger.info(
            "table_cell_units restored=%d unresolved=%d filing_id=%s sic=%s reasons=%s",
            int(unit_audit.get("restored_count") or 0),
            int(unit_audit.get("unresolved_count") or 0),
            filing_id,
            run.company_sic or "",
            "|".join(sorted({str(u.get("reason") or "?") for u in unit_audit.get("unresolved") or []})),
        )
    quote_audit = (raw_summary or {}).get("forward_quote_audit") or {}
    if quote_audit.get("unverified"):
        # T5.4 measurement channel (count-first, the figure-trace convention): §5 quotes
        # that failed the verbatim check, emitted flag on OR off. near_miss (rapidfuzz
        # ≥92 on normalized text) = lightly-paraphrased population → prompt tuning;
        # the remainder = fabrication-class → the arming signal for the drop gate.
        unverified = quote_audit["unverified"]
        logger.info(
            "forward_quote_unverified count=%d near_miss=%d dropped=%d flag=%s "
            "filing_id=%s sic=%s speakers=%s",
            len(unverified),
            quote_audit.get("near_miss", 0),
            len(quote_audit.get("dropped") or []),
            pipeline.settings.AI_FORWARD_QUOTE_GATE,
            filing_id,
            run.company_sic or "",
            "|".join(str(u.get("speaker") or "?") for u in unverified),
        )
    snap_audit = (raw_summary or {}).get("evidence_snap_audit") or {}
    if snap_audit.get("checked"):
        # Evidence auto-snap measurement channel (post-#631, count-first convention):
        # exact = verified as emitted; would_snap = a confident counterpart exists but
        # the flag is unarmed (the entries carry original + candidate — THE arming
        # forensics); snapped = armed repairs (become read-time Verified badges); left =
        # no confident counterpart, text kept (read-time enrichment suppresses it).
        logger.info(
            "evidence_snap checked=%d exact=%d would_snap=%d snapped=%d left=%d "
            "flag=%s filing_id=%s",
            snap_audit.get("checked", 0),
            snap_audit.get("exact", 0),
            len(snap_audit.get("would_snap") or []),
            len(snap_audit.get("snapped") or []),
            len(snap_audit.get("left") or []),
            pipeline.settings.AI_EVIDENCE_SNAP,
            filing_id,
        )

    # S4 quality gate: the summary is ALWAYS persisted, so the streamed result doesn't
    # vanish when the client refetches and isn't regenerated from scratch on revisit. When
    # a result is assessed "partial", the user is not charged for it (they weren't served a
    # full result): the unit counted at provider start is refunded, and a caller without a
    # lease skips the completion-time count. The UI surfaces it honestly via the quality
    # badge + one-click Regenerate.
    count_usage = not (pipeline.settings.AI_QUALITY_GATE and quality["tier"] == "partial")
    if not count_usage:
        logger.info(
            f"[stream:{filing_id}] Quality gate: tier=partial, not charging usage "
            f"(reasons: {quality['reasons']})"
        )
        await run.refund_charge("partial verdict")

    # DB OP: Persist summary
    def save_summary_sync():
        with database.SessionLocal() as session:
            filing_for_cache = session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()

            if force_regenerate:
                # Admin refresh-stale: UPDATE the existing row IN PLACE (preserve summaries.id so
                # the saved_summaries FK/bookmark survives and UNIQUE(filing_id) holds) instead of
                # delete+insert, guarded by a keep-better gate. The read takes the row lock the
                # UPDATE takes, so the checks below hold until this commit: another instance's save
                # commits first and is read here, never lands between this read and the write.
                # SQLite omits the clause; PostgreSQL emits FOR NO KEY UPDATE (FK key-share safe).
                existing = (
                    session.query(Summary)
                    .filter(Summary.filing_id == filing_id)
                    .with_for_update(key_share=True)
                    .first()
                )
                if existing is not None:
                    stored_raw = existing.raw_summary if isinstance(existing.raw_summary, dict) else {}
                    stored_tier = (stored_raw.get("quality") or {}).get("tier")
                    new_tier = (quality or {}).get("tier")
                    # Keep-better protects only a stored row the filing page shows (the body
                    # the router would replay, by the same rule): failure filler or a stale
                    # in-progress marker never outranks a fresh result.
                    stored_shown = pipeline.is_summary_ready(
                        pipeline.source_safe_business_overview(existing, filing_for_cache),
                        stored_raw.get("writer_error"),
                    )
                    if stored_shown and replace_unready_only:
                        # This run was admitted only to replace a row the page cannot show,
                        # and another run made it ready meanwhile: keep that summary.
                        logger.info(
                            "[stream:%s] unready refresh: the stored summary became ready meanwhile; keeping it",
                            filing_id,
                        )
                        return existing.id
                    if stored_shown and pipeline.quality_tier_rank(new_tier) < pipeline.quality_tier_rank(stored_tier):
                        # Never let a refresh downgrade a stored higher tier (a 75s AI-timeout
                        # XBRL fallback comes back "partial"; keep the stored "full").
                        logger.info(
                            "[stream:%s] refresh keep-better: keeping stored tier=%s over new tier=%s",
                            filing_id, stored_tier, new_tier,
                        )
                        return existing.id
                    existing.business_overview = markdown
                    existing.financial_highlights = normalized_financial_section
                    existing.risk_factors = risk_section
                    existing.management_discussion = management_section
                    existing.key_changes = guidance_section
                    # Reassign a NEW dict so SQLAlchemy marks the JSON column dirty and emits UPDATE.
                    existing.raw_summary = raw_summary
                    existing.schema_version = pipeline.SUMMARY_SCHEMA_VERSION
                    existing.prompt_version = pipeline.SUMMARY_PROMPT_VERSION
                    if filing_for_cache:
                        pipeline.upsert_content_cache(
                            session, filing_id, filing_for_cache.content_cache,
                            excerpt=run.excerpt, sections_payload=sections_info,
                            risk_source_text=(
                                risk_source_for_cache
                                if isinstance(risk_source_for_cache, str)
                                else None
                            ),
                            replace_risk_source=True,
                        )
                    session.commit()
                    return existing.id
                # force on a filing with no stored summary yet: fall through to a normal INSERT.

            summary = Summary(
                filing_id=filing_id,
                business_overview=markdown,
                financial_highlights=normalized_financial_section,
                risk_factors=risk_section,
                management_discussion=management_section,
                key_changes=guidance_section,
                raw_summary=raw_summary,
                schema_version=pipeline.SUMMARY_SCHEMA_VERSION,
                prompt_version=pipeline.SUMMARY_PROMPT_VERSION,
            )
            session.add(summary)

            if filing_for_cache:
                pipeline.upsert_content_cache(
                    session,
                    filing_id,
                    filing_for_cache.content_cache,
                    excerpt=run.excerpt,
                    sections_payload=sections_info,
                    risk_source_text=(
                        risk_source_for_cache
                        if (
                            isinstance(risk_source_for_cache, str)
                            and (force_regenerate or not run.excerpt)
                        )
                        else None
                    ),
                    replace_risk_source=force_regenerate,
                )

            try:
                session.commit()
                return summary.id
            except IntegrityError:
                # A concurrent writer (cron / another instance) persisted this filing's summary
                # first — filing_id is UNIQUE. Serve the winner's row instead of erroring the
                # user's stream (S1 decision #3).
                session.rollback()
                existing = session.query(Summary).filter(Summary.filing_id == filing_id).first()
                if existing is None:
                    raise
                return existing.id

    saved_summary_id = await run.run_sync_db(save_summary_sync)

    run.mark_stage("persist_summary")

    if run.charged_month is not None:
        # The unit counted at provider start is settled by the persisted summary: no later
        # failure refunds it.
        run.charged_month = None
        run.charge_future = None  # nothing left to settle: the unit is owed
    elif user_id and count_usage and run.usage_reservation_token is None:
        # No lease was held (background drain, uncapped Pro): the historical
        # completion-time count, full results only. A lease still held here was left
        # uncharged on purpose (an unsignalled timeout fallback); `release` releases it.
        def track_usage_sync():
            with database.SessionLocal() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    pipeline.increment_user_usage(user.id, pipeline.get_current_month(), session)

        await run.run_sync_db(track_usage_sync)
        run.mark_stage("usage_tracking")

    # DB OP: Record complete
    await run.run_sync_db(run.record_progress_sync, filing_id, "completed")

    run.summary_status = run.summary_payload.get("status", "complete")
    summary_message = run.summary_payload.get("message")

    # A persisted result with status "error" means only fallback content was
    # produced — count it as a failure in the funnel, not a success.
    run.emit_funnel(
        run.telemetry_distinct_id,
        pipeline.EVENT_GENERATION_SUCCEEDED if run.summary_status != "error" else pipeline.EVENT_GENERATION_FAILED,
        duration_ms=run.elapsed_ms(),
        result_type=run.summary_status,
        quality_verdict=quality.get("tier"),
        figures_untraceable_count=len(quality.get("figures_untraceable") or []),
        entry_point=run.telemetry_entry_point,
        **run.telemetry_ctx,
    )

    yield {'type': 'chunk', 'content': markdown}

    if run.summary_status == "partial":
        yield {'type': 'partial', 'message': summary_message or 'Some sections may not have loaded fully.', 'summary_id': saved_summary_id}
    elif run.summary_status == "error":
        yield {'type': 'error', 'message': summary_message or 'Error generating summary', 'summary_id': saved_summary_id}
    else:
        yield {'type': 'complete', 'summary_id': saved_summary_id, 'percent': 100}
