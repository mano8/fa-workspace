#!/usr/bin/env bash
set -euo pipefail

readonly CODEX_VERSION="0.144.6"
readonly CODEX_BINARY_SHA256="134063e133f0b4244fa3b251acf973d4fe4b4aeeacbdc135211bf480f59f1477"
readonly CLAUDE_VERSION="2.1.217"
readonly CLAUDE_BINARY_SHA256="2630fc5dc6db61bc03f86b95daf47766e5b61873f7bb7cfea764c5ac5a9ba"
readonly HEADROOM_RECORD_SHA256="f924558152b73d544efb800d9884db709e4856d4a989b47023864c9a2325aa02"
readonly ROOT_TOOLING_LOCK_SHA256="a0da875a5c7c202a95fa7963d2b1b1132a47bb32fa25140aa58a52a95d85b368"
readonly ROOT_TOOLING_LOCK_VERSION="2026-07-21"
readonly NODE_VERSION="24.16.0"
readonly NODE_BINARY_SHA256="b2959781cc5a74c357ffa02367efa8a0330cbb1c9cb347732fdfaaaca381cbcd"
readonly PYTHON_VERSION="3.12.13"
readonly PYTHON_BINARY_SHA256="4dbf3143240288fb2170257ffaa7bd030cdda5d2703d1f5f30b627042267e2e3"
readonly CA_CERTIFICATES_VERSION="20260601~26.04.1"
readonly CURL_VERSION="8.18.0-1ubuntu2.3"
readonly GIT_VERSION="1:2.53.0-1ubuntu1"
readonly JQ_VERSION="1.8.1-4ubuntu2"

echo "[1/8] Mise à jour des outils système..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    "ca-certificates=${CA_CERTIFICATES_VERSION}" \
    "curl=${CURL_VERSION}" \
    "git=${GIT_VERSION}" \
    "jq=${JQ_VERSION}"

test "$(dpkg-query -W -f='${Version}' ca-certificates)" = "${CA_CERTIFICATES_VERSION}"
test "$(dpkg-query -W -f='${Version}' curl)" = "${CURL_VERSION}"
test "$(dpkg-query -W -f='${Version}' git)" = "${GIT_VERSION}"
test "$(dpkg-query -W -f='${Version}' jq)" = "${JQ_VERSION}"
test "$(node --version)" = "v${NODE_VERSION}"
test "$(sha256sum "$(command -v node)" | awk '{print $1}')" = "${NODE_BINARY_SHA256}"
test "$(python3 --version)" = "Python ${PYTHON_VERSION}"
test "$(sha256sum "$(command -v python3)" | awk '{print $1}')" = "${PYTHON_BINARY_SHA256}"

echo "[2/8] Préparation des dossiers persistants..."
mkdir -p \
    "${HOME}/.claude" \
    "${HOME}/.codex" \
    "${HOME}/.venvs"

sudo chown -R "$(id -u):$(id -g)" \
    "${HOME}/.claude" \
    "${HOME}/.codex" \
    "${HOME}/.venvs"

echo "[3/8] Configuration Git safe.directory pour les repos du workspace..."
git config --global --add safe.directory /workspace || true

find /workspace -mindepth 1 -maxdepth 2 -type d -name ".git" \
    -exec dirname {} \; \
    | sort -u \
    | while read -r repo_path; do
        git config --global --add safe.directory "${repo_path}" || true
      done

echo "[4/8] Configuration de l'environnement Python PARTAGÉ..."
cd /workspace

python3 -m venv .shared-venv

test "$(sha256sum /workspace/.github/workflows/root-tooling.requirements.lock | awk '{print $1}')" = "${ROOT_TOOLING_LOCK_SHA256}"
./.shared-venv/bin/pip install \
    --only-binary=:all: \
    --require-hashes \
    --no-deps \
    -r /workspace/.github/workflows/root-tooling.requirements.lock

echo "[5/8] Installation vérifiée de Codex CLI sans sudo..."
npm config delete prefix
codex_path="$(command -v codex || true)"
if [ -z "${codex_path}" ]; then
    npm install -g "@openai/codex@${CODEX_VERSION}"
    codex_path="$(command -v codex)"
fi
test "$(sha256sum "${codex_path}" | awk '{print $1}')" = "${CODEX_BINARY_SHA256}"
test "$(codex --version)" = "codex-cli ${CODEX_VERSION}"

echo "[6/8] Installation vérifiée de Claude Code sans sudo..."
claude_path="$(command -v claude || true)"
if [ -z "${claude_path}" ]; then
    npm install -g "@anthropic-ai/claude-code@${CLAUDE_VERSION}"
    claude_path="$(command -v claude)"
fi
test "$(sha256sum "${claude_path}" | awk '{print $1}')" = "${CLAUDE_BINARY_SHA256}"
test "$(claude --version)" = "${CLAUDE_VERSION} (Claude Code)"

echo "[7/8] Installation verrouillée de Headroom MCP CLI dans un venv isolé..."
python3 -m venv "${HOME}/.venvs/headroom"
"${HOME}/.venvs/headroom/bin/pip" install \
    --only-binary=:all: \
    --require-hashes \
    --no-deps \
    -r /workspace/.devcontainer/headroom.requirements.lock
headroom_record="$(find "${HOME}/.venvs/headroom/lib" -path '*/headroom_ai-0.32.1.dist-info/RECORD' -type f -print -quit)"
test -n "${headroom_record}"
test "$(sha256sum "${headroom_record}" | awk '{print $1}')" = "${HEADROOM_RECORD_SHA256}"

if ! grep -q '.venvs/headroom/bin' "${HOME}/.bashrc"; then
    echo 'export PATH="${HOME}/.venvs/headroom/bin:${PATH}"' >> "${HOME}/.bashrc"
fi

echo "[8/8] Vérification..."
export PATH="${HOME}/.venvs/headroom/bin:${PATH}"

python3 --version
node --version
npm --version
codex --version || true
claude --version
headroom --help >/dev/null
headroom mcp serve --help || true

echo "✨ Configuration terminée avec succès !"
