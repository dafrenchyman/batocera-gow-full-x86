#!/usr/bin/env python3
"""Run the installed input broker at its stable image path."""

import runpy

if __name__ == "__main__":
    runpy.run_module("batocera_gow.runtime.input_transport", run_name="__main__")
