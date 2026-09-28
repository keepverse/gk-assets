"""Build the actor-free Ice Mirror deflection response."""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ice_mirror_combat import build_effect


def main() -> None:
    print("ICE_MIRROR_DEFLECT_BUILD_COMPLETE", build_effect("deflect"))


if __name__ == "__main__":
    main()
