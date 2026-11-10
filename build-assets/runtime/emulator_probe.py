#!/usr/bin/env python3
"""Run the installed stock-emulator diagnostic."""

import runpy

if __name__ == "__main__":
    runpy.run_module("batocera_gow.runtime.emulator_probe", run_name="__main__")
