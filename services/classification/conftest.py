import sys
from pathlib import Path

_SERVICE = Path(__file__).resolve().parent
_ROOT = _SERVICE.parents[1]

sys.path.insert(0, str(_ROOT / "libs" / "shared"))
sys.path.insert(0, str(_SERVICE))
