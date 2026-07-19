#!/usr/bin/env python3
"""CLI entrypoint for the inactive W2b2 scoped resolver."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context.resolve_context import main


if __name__ == "__main__":
    raise SystemExit(main())
