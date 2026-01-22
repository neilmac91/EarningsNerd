
import os
import sys

# Create structure
os.makedirs("test_pkg/models", exist_ok=True)
with open("test_pkg/__init__.py", "w") as f:
    f.write("")

with open("test_pkg/models.py", "w") as f:
    f.write("print('Loaded models.py')\nMY_VAR = 'file'")

with open("test_pkg/models/__init__.py", "w") as f:
    f.write("print('Loaded models package')\nMY_VAR = 'package'")

# Test import
sys.path.append(os.getcwd())
try:
    import test_pkg.models
    print(f"Imported: {test_pkg.models}")
    print(f"MY_VAR: {test_pkg.models.MY_VAR}")
except ImportError as e:
    print(f"ImportError: {e}")
except AttributeError as e:
    print(f"AttributeError: {e}")
