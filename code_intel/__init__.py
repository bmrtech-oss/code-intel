import os
import sys

# Ensure the project root is in sys.path for robust module resolution
# This is a safety net for containerized environments where PYTHONPATH might be misconfigured
try:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
except Exception:
    pass

__version__ = "0.1.0"
