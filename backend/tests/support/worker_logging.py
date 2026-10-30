"""The process logging the task worker's entrypoint configures on its first import, put back afterwards."""
import logging
from contextlib import contextmanager

# The library loggers app/services/logging_service.py::configure_logging quiets.
LIBRARY_LOGGERS = ("httpx", "httpcore", "urllib3", "edgar", "markdown_it")


@contextmanager
def preserved_logging():
    """The root logger's handlers and level, and the library loggers' levels, as they were before the block:
    `task_worker_main`'s first import runs configure_logging, which replaces the one and sets the others, and a later
    test that reads caplog would otherwise miss what the API process logs at DEBUG."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    library_levels = {name: logging.getLogger(name).level for name in LIBRARY_LOGGERS}
    try:
        yield
    finally:
        for handler in root.handlers:
            if handler not in handlers:
                handler.close()
        root.handlers[:] = handlers
        root.setLevel(level)
        for name, previous_level in library_levels.items():
            logging.getLogger(name).setLevel(previous_level)
