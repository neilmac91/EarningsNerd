"""The app modules that copy ``app.database.SessionLocal`` into themselves when they are imported (E263).

A module whose top level runs ``from app.database import SessionLocal`` holds the factory it found at its first
import. A test whose fixture patches ``database.SessionLocal`` with a temporary factory, and whose body then imports
such a module for the first time, leaves that module holding the temporary factory for the rest of the process; a
``monkeypatch.setattr(module, "SessionLocal", ...)`` in the same test restores the same captured factory at teardown.
A later test's writes through the module then land in a disposed temporary database: run serially,
``test_data_completeness.py`` followed by ``test_filing_section_service.py``'s operator-script case failed so, through
``job_run_service``.

``tests/conftest.py`` imports every module listed here before the first test, so none is first imported under a
patched factory. ``tests/unit/test_session_local_binders.py`` holds this list to the modules under ``app/`` that bind
the factory at import, and fails a binder missing from it or an entry that no longer binds it.
"""

SESSION_LOCAL_BINDERS: tuple[str, ...] = (
    "app.routers.summaries",
    "app.services.account_mail_service",
    "app.services.background_task_runner",
    "app.services.copilot_tools",
    "app.services.filing_list_service",
    "app.services.job_run_service",
    "app.services.sec_request_gate",
    "app.services.summary_generation_service",
    "app.services.summary_job_store",
    "app.services.universe_seed_service",
)
