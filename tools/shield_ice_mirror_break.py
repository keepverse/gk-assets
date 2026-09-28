"""Build the actor-free Ice Mirror break response."""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ice_mirror_combat import build_effect


def main() -> None:
    print("ICE_MIRROR_BREAK_BUILD_COMPLETE", build_effect("break"))


if __name__ == "__main__":
    main()
