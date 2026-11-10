#!/usr/bin/env python3
"""Run the installed post-configgen DuckStation wrapper."""

import runpy

if __name__ == "__main__":
    runpy.run_module("batocera_gow.runtime.duckstation_wrapper", run_name="__main__")
