#!/usr/bin/env python3
"""Validate W2b1 artifacts or print a canonical injected envelope to stdout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_context import w2b1


VALIDATORS = {
    "registry-v1": w2b1.validate_registry_v1,
    "policy-index-v1": w2b1.validate_policy_index_v1,
    "registry-v2": w2b1.validate_registry_v2,
    "policy-index-v2": w2b1.validate_policy_index_v2,
    "workspace-v2": w2b1.validate_workspace_configuration_v2,
    "policy-unit": w2b1.validate_policy_unit,
    "manifest": w2b1.validate_manifest,
    "session": w2b1.validate_session,
    "receipt": w2b1.validate_receipt,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted((*VALIDATORS, "envelope")))
    parser.add_argument("input", type=Path, help="strict UTF-8 JSON input")
    parser.add_argument("--policy-index", type=Path, help="required for workspace-v2")
    parser.add_argument("--v1-policy-index", type=Path, help="required only to compare transitional v2 compatibility bundles")
    arguments = parser.parse_args()
    try:
        value = w2b1.parse_strict_json(arguments.input.read_bytes())
        if arguments.kind == "envelope":
            envelope, serialized, digest = w2b1.build_envelope(
                manifest_id=value["manifest_id"], generation=value["generation"], entries=value["entries"]
            )
            if envelope != value:
                raise w2b1.AgentContextError("E_SOURCE", "envelope input is not already canonical after exact deduplication")
            sys.stdout.buffer.write(serialized + b"\n")
            print(digest, file=sys.stderr)
            return 0
        if arguments.kind == "workspace-v2":
            if arguments.policy_index is None:
                raise w2b1.AgentContextError("E_USAGE", "--policy-index is required for workspace-v2")
            VALIDATORS[arguments.kind](
                value, w2b1.parse_strict_json(arguments.policy_index.read_bytes())
            )
        elif arguments.kind == "policy-index-v2" and arguments.v1_policy_index:
            VALIDATORS[arguments.kind](value, v1_policy_index=w2b1.parse_strict_json(arguments.v1_policy_index.read_bytes()))
        else:
            VALIDATORS[arguments.kind](value)
        return 0
    except (OSError, KeyError, w2b1.AgentContextError) as error:
        print(str(error), file=sys.stderr)
        return 3 if isinstance(error, w2b1.AgentContextError) and error.code == "E_SCHEMA" else 8


if __name__ == "__main__":
    raise SystemExit(main())
