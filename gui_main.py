#!/usr/bin/env python3
"""Launch the Slipstream desktop application.

    python gui_main.py [--config config/config.yaml]

Equivalent to ``python main.py gui``. The engine CLI (main.py run / wb-info /
init-template) keeps working without any GUI dependencies installed.
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="Slipstream desktop GUI")
    ap.add_argument("--config", default="config/config.yaml",
                    help="Project config to open at startup (default: %(default)s)")
    args = ap.parse_args()
    from gui.app import run_app
    return run_app(config_path=args.config)


if __name__ == "__main__":
    raise SystemExit(main())
