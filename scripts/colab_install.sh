#!/usr/bin/env bash
# Install google-colab-cli inside WSL (run via: wsl -d Ubuntu-24.04 -u root -- bash /mnt/c/.../scripts/colab_install.sh)
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
if ! command -v colab >/dev/null 2>&1; then
    uv tool install google-colab-cli
fi
colab version || true
echo "---auth help---"
colab auth --help 2>&1 | head -15 || true
echo "---login help---"
colab auth login --help 2>&1 | head -15 || colab login --help 2>&1 | head -15 || true
