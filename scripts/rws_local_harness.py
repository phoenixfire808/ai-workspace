#!/usr/bin/env python3
"""Start the standalone stdlib-only Refactor Workflow Studio harness."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.lightweight_agent import serve  # noqa: E402


if __name__ == "__main__":
    serve()
