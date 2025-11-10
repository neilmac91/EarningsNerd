import sys
from pathlib import Path

# Add root directory to path so imports like "from backend.pipeline..." work
# The pydantic directory has been removed to avoid conflicts with the installed package
ROOT = Path(__file__).resolve().parent.parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

# Also add backend directory to path for imports like "from pipeline..." or "from app..."
BACKEND = ROOT / "backend"
backend_str = str(BACKEND)
if backend_str not in sys.path:
    sys.path.insert(0, backend_str)
