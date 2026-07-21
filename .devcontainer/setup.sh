#!/usr/bin/env bash
set -euo pipefail

readonly CODEX_VERSION="0.144.6"
readonly CODEX_BINARY_SHA256="134063e133f0b4244fa3b251acf973d4fe4b4aeeacbdc135211bf480f59f1477"
readonly HEADROOM_RECORD_SHA256="f924558152b73d544efb800d9884db709e4856d4a989b47023864c9a2325aa02"

echo "[1/7] Mise à jour des outils système..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    jq \
    python3-venv

echo "[2/7] Préparation des dossiers persistants..."
mkdir -p \
    "${HOME}/.claude" \
    "${HOME}/.codex" \
    "${HOME}/.venvs"

sudo chown -R "$(id -u):$(id -g)" \
    "${HOME}/.claude" \
    "${HOME}/.codex" \
    "${HOME}/.venvs"

echo "[3/7] Configuration Git safe.directory pour les repos du workspace..."
git config --global --add safe.directory /workspace || true

find /workspace -mindepth 1 -maxdepth 2 -type d -name ".git" \
    -exec dirname {} \; \
    | sort -u \
    | while read -r repo_path; do
        git config --global --add safe.directory "${repo_path}" || true
      done

echo "[4/7] Configuration de l'environnement Python PARTAGÉ..."
cd /workspace

python3 -m venv .shared-venv

./.shared-venv/bin/pip install \
    -r /workspace/fa-auth-m8/auth_user_service/requirements_dev.txt \
    -r /workspace/imgtools_m8/requirements.txt \
    -r /workspace/media-service-m8/media_service/requirements_dev.txt

echo "[5/7] Installation vérifiée de Codex CLI sans sudo..."
npm config delete prefix
codex_path="$(command -v codex || true)"
if [ -z "${codex_path}" ]; then
    npm install -g "@openai/codex@${CODEX_VERSION}"
    codex_path="$(command -v codex)"
fi
test "$(sha256sum "${codex_path}" | awk '{print $1}')" = "${CODEX_BINARY_SHA256}"
test "$(codex --version)" = "codex-cli ${CODEX_VERSION}"

echo "[6/7] Installation verrouillée de Headroom MCP CLI dans un venv isolé..."
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

echo "[7/7] Vérification..."
export PATH="${HOME}/.venvs/headroom/bin:${PATH}"

python3 --version
node --version
npm --version
codex --version || true
claude --version || true
headroom --help >/dev/null
headroom mcp serve --help || true

echo "✨ Configuration terminée avec succès !"
