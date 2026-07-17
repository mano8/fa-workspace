#!/usr/bin/env bash
set -euo pipefail

HEADROOM_MCP_URL="${HEADROOM_MCP_URL:-http://headroom-mcp:8787/mcp}"

mkdir -p /home/vscode/.codex /home/vscode/.claude

cat > /home/vscode/.codex/config.toml <<EOF
[mcp_servers.headroom]
url = "${HEADROOM_MCP_URL}"
enabled = true
startup_timeout_sec = 20
tool_timeout_sec = 60
default_tools_approval_mode = "prompt"
EOF

echo "Codex Headroom MCP configured: ${HEADROOM_MCP_URL}"

if command -v headroom >/dev/null 2>&1; then
  headroom mcp install --remote "${HEADROOM_MCP_URL}" --force || true
else
  echo "Headroom CLI not installed in workspace container; Claude MCP can be configured manually."
fi