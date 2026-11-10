#!/usr/bin/env python3
"""Run the installed capability-free input worker."""

import runpy

if __name__ == "__main__":
    runpy.run_module("batocera_gow.runtime.input_worker", run_name="__main__")
