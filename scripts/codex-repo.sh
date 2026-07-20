#!/usr/bin/env bash
# Canonical Phase 6.3 launcher: one or more registered direct-child repositories.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
workspace_root="$(cd -- "${script_dir}/.." && pwd -P)"
python_command="${M8_PYTHON:-python3}"

cd -- "${workspace_root}"
PYTHONPATH="${workspace_root}/scripts${PYTHONPATH:+:${PYTHONPATH}}" \
    exec "${python_command}" -m agent_context.codex_repo_launcher "$@"
