"""Every model module under app/models, imported, so Base.metadata and Base.registry hold every model.

`import app.models` does not import them all: it leaves out app/models/sec_request_gate.py, a table the migrations
create and seed (the app's startup creates it too, once main has imported the gate's service). A test that reads the
metadata or the registry after `import app.models` alone would hold that model only when an earlier test in the same
process had imported it, so it would pass or fail by the order the tests ran in.
"""
from __future__ import annotations

import importlib
from pathlib import Path


def import_every_model() -> None:
    import app.models

    for path in sorted(Path(app.models.__file__).parent.glob("*.py")):
        if path.stem != "__init__":
            importlib.import_module(f"app.models.{path.stem}")
