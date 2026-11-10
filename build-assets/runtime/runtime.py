#!/usr/bin/env python3
"""Run the installed stock-session adapter at its stable image path."""

import runpy

if __name__ == "__main__":
    runpy.run_module("batocera_gow.runtime.runtime", run_name="__main__")
