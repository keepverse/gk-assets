"""Build the Earth Shield's short impact response."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from earth_shield_combat import build_effect


result = build_effect("impact")
print("EARTH_SHIELD_COMBAT_RESULT", result)
