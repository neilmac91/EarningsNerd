import sys
from pathlib import Path

# Add backend directory to path instead of root to avoid conflicts
# with root-level directories that might shadow Python packages
BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    # Remove root if present to avoid conflicts
    ROOT = Path(__file__).resolve().parent.parent
    root_str = str(ROOT)
    if root_str in sys.path:
        sys.path.remove(root_str)
    sys.path.insert(0, str(BACKEND))
