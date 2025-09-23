#!/usr/bin/env python
"""
Convenience script to run tests with coverage reporting.
Usage: python tests/run_coverage.py
"""

import subprocess
import sys
from pathlib import Path

def run_coverage():
    """Run tests with coverage and open HTML report."""

    # Run pytest with coverage
    cmd = [
        "pytest",
        "tests/",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=html",
        "-v"
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        report_path = Path("tests/htmlcov/index.html")
        if report_path.exists():
            print(f"\n✓ Coverage report generated: {report_path}")
            print("  To view: python -m webbrowser tests/htmlcov/index.html")
        else:
            print("\n⚠ Coverage report not found")

    return result.returncode

if __name__ == "__main__":
    sys.exit(run_coverage())