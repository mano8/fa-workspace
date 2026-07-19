#!/usr/bin/env bash
set -euo pipefail

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
./.shared-venv/bin/pip install --upgrade pip

./.shared-venv/bin/pip install \
    -r /workspace/fa-auth-m8/auth_user_service/requirements_dev.txt \
    -r /workspace/imgtools_m8/requirements.txt \
    -r /workspace/media-service-m8/media_service/requirements_dev.txt

echo "[5/7] Installation de Codex CLI sans sudo..."
npm config delete prefix
npm install -g @openai/codex

echo "[6/7] Installation de Headroom MCP CLI dans un venv isolé..."
python3 -m venv "${HOME}/.venvs/headroom"
"${HOME}/.venvs/headroom/bin/pip" install --upgrade pip
"${HOME}/.venvs/headroom/bin/pip" install "headroom-ai[mcp,proxy,code]"

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
