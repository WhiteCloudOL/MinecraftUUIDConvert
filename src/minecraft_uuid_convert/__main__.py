"""Application entry point."""

from __future__ import annotations

import sys

from minecraft_uuid_convert.cli import run_cli
from minecraft_uuid_convert.gui import run_gui


def main() -> int:
    """Open the GUI when no arguments are supplied; otherwise run the CLI."""
    if len(sys.argv) == 1:
        run_gui()
        return 0
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
