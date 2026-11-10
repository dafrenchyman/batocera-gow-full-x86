#!/usr/bin/env python3
"""Run the installed authenticated desktop diagnostic."""

import runpy

if __name__ == "__main__":
    runpy.run_module("batocera_gow.runtime.native_diagnostics", run_name="__main__")
