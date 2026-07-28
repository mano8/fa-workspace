#!/usr/bin/env bash
# Canonical Phase 12 launcher: one or more registered direct-child repositories.
# Only the evidenced devcontainer non-interactive Claude rows are canonical, so
# there is deliberately no Windows counterpart to this wrapper.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
workspace_root="$(cd -- "${script_dir}/.." && pwd -P)"
python_command="${M8_PYTHON:-python3}"

cd -- "${workspace_root}"
PYTHONPATH="${workspace_root}/scripts${PYTHONPATH:+:${PYTHONPATH}}" \
    exec "${python_command}" -m agent_context.claude_repo_launcher "$@"
