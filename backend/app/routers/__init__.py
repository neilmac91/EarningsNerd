"""Load named API exports lazily so a task-only router stays independent of API startup."""
from importlib import import_module
from types import ModuleType

__all__ = [
    'analysis',
    'auth',
    'companies',
    'contact',
    'email',
    'filings',
    'saved_summaries',
    'sitemap',
    'summaries',
    'subscriptions',
    'users',
    'watchlist',
    'webhooks',
]


def __getattr__(name: str) -> ModuleType:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{name}", __name__)
    globals()[name] = module
    return module
