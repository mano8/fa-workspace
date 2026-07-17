#!/usr/bin/env bash
set -euo pipefail

export PATH="${HOME}/.npm-global/bin:${HOME}/.venvs/headroom/bin:${PATH}"

HEADROOM_PROXY_URL="${HEADROOM_PROXY_URL:-http://headroom-proxy:8787}"
HEADROOM_HOST="${HEADROOM_HOST:-headroom-proxy}"
HEADROOM_PORT="${HEADROOM_PORT:-8787}"

HEADROOM_BIN="${HOME}/.venvs/headroom/bin/headroom"
CODEX_CONFIG="${HOME}/.codex/config.toml"

mkdir -p "${HOME}/.codex" "${HOME}/.claude"

echo "[1/5] Checking Headroom proxy backend..."

if python3 - "${HEADROOM_HOST}" "${HEADROOM_PORT}" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])

for _ in range(30):
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)

sys.exit(1)
PY
then
    echo "Headroom proxy backend is reachable: ${HEADROOM_PROXY_URL}"
else
    echo "WARNING: Headroom proxy backend is not reachable at ${HEADROOM_HOST}:${HEADROOM_PORT}."
    echo "Dev Container startup will continue."
    echo "Check with:"
    echo "  docker ps -a --filter name=headroom-proxy-server"
    echo "  docker logs --tail 200 headroom-proxy-server"
fi

echo "[2/5] Checking Headroom MCP CLI..."

if [ ! -x "${HEADROOM_BIN}" ]; then
    echo "WARNING: ${HEADROOM_BIN} not found or not executable."
    echo "Run:"
    echo "  bash .devcontainer/setup.sh"
    exit 0
fi

if ! "${HEADROOM_BIN}" mcp serve --help >/dev/null 2>&1; then
    echo "WARNING: Headroom MCP CLI is installed but not usable."
    echo "Try reinstalling with:"
    echo "  ${HOME}/.venvs/headroom/bin/pip install --upgrade 'headroom-ai[mcp,proxy]'"
    exit 0
fi

echo "[3/5] Configuring Codex MCP as stdio server..."

touch "${CODEX_CONFIG}"

python3 - "${CODEX_CONFIG}" "${HEADROOM_BIN}" "${HEADROOM_PROXY_URL}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
headroom_bin = sys.argv[2]
proxy_url = sys.argv[3]

text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""

block = f"""
[mcp_servers.headroom]
command = "{headroom_bin}"
args = ["mcp", "serve", "--proxy-url", "{proxy_url}"]
enabled = true
startup_timeout_sec = 20
tool_timeout_sec = 60
default_tools_approval_mode = "prompt"
"""

pattern = r"(?ms)^\[mcp_servers\.headroom\]\n.*?(?=^\[|\Z)"

if re.search(pattern, text):
    text = re.sub(pattern, block.strip() + "\n\n", text)
else:
    text = text.rstrip() + "\n\n" + block.strip() + "\n"

config_path.write_text(text, encoding="utf-8")
PY

echo "Codex Headroom MCP configured through stdio:"
echo "  ${HEADROOM_BIN} mcp serve --proxy-url ${HEADROOM_PROXY_URL}"

echo "[4/5] Configuring Claude Code MCP as stdio server..."

if command -v claude >/dev/null 2>&1; then
    claude mcp remove headroom >/dev/null 2>&1 || true

    if claude mcp add headroom --scope user -- "${HEADROOM_BIN}" mcp serve --proxy-url "${HEADROOM_PROXY_URL}" >/dev/null 2>&1; then
        echo "Claude Code Headroom MCP configured."
    else
        echo "WARNING: Claude MCP registration failed."
        echo "Run manually:"
        echo "  claude mcp add headroom --scope user -- ${HEADROOM_BIN} mcp serve --proxy-url ${HEADROOM_PROXY_URL}"
    fi
else
    echo "WARNING: Claude CLI not found yet."
fi

echo "[5/5] MCP summary..."
echo "Headroom proxy URL: ${HEADROOM_PROXY_URL}"
echo "Headroom MCP command: ${HEADROOM_BIN} mcp serve --proxy-url ${HEADROOM_PROXY_URL}"
echo "Codex config: ${CODEX_CONFIG}"

if command -v claude >/dev/null 2>&1; then
    claude mcp list || true
fi

echo "✨ MCP configuration terminée."