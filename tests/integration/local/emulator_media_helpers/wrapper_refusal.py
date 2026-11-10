"""Exercise wrapper refusal without starting the stock emulator."""

import sys
from pathlib import Path
from typing import Never
from unittest.mock import patch

from batocera_gow.runtime import duckstation_wrapper as wrapper
from batocera_gow.runtime.duckstation_visual import VisualError


def main() -> None:
    """Run the isolated diagnostic fixture."""
    wrapper.SETTINGS = Path(sys.argv[1])

    def discover() -> Never:
        """Refuse visual discovery without contacting the display."""
        message = "Cannot initialize EGL on the current X11 display"
        raise VisualError(message)

    if sys.argv[2] == "settings":
        wrapper.SETTINGS = wrapper.SETTINGS.with_name("private_absent_settings.ini")
    with patch.object(wrapper, "discover_visual", new=discover):
        raise SystemExit(wrapper.main())


if __name__ == "__main__":
    main()
