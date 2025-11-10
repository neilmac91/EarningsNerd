import sys
from pathlib import Path

# Add root directory to path for "from backend.pipeline..." imports
# The pydantic directory has been removed to avoid conflicts with the installed package
ROOT = Path(__file__).resolve().parent.parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

# Add backend directory to path for "from app..." imports
# This is added after root so that "from backend..." imports work first
# but "from app..." can still find backend/app/ after root/app.py fails
BACKEND = ROOT / "backend"
backend_str = str(BACKEND)
if backend_str not in sys.path:
    sys.path.insert(1, backend_str)  # Insert at position 1, after root
