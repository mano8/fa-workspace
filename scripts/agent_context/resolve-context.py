#!/usr/bin/env python3
# ruff: noqa: N999 - the hyphenated name is the documented CLI entrypoint.
"""CLI entrypoint for the inactive W2b2 scoped resolver."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context.resolve_context import main

if __name__ == "__main__":
    raise SystemExit(main())
