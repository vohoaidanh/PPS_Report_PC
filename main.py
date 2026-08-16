#!/usr/bin/env python3
"""
Entry point shim — kept at the repo root so `build.spec` (PyInstaller
Analysis(['main.py'])) keeps working unchanged. Actual application code
lives in the pps_report package.
"""

from pps_report.__main__ import main

if __name__ == "__main__":
    main()
