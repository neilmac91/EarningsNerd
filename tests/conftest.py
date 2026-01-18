import sys
from pathlib import Path

# Add backend directory to path for "from app..." imports
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
backend_str = str(BACKEND)
if backend_str not in sys.path:
    sys.path.insert(0, backend_str)

# Add root directory to path for "from backend..." imports
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(1, root_str)
