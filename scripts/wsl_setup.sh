#!/usr/bin/env bash
# One-time WSL/Ubuntu setup for the Colab CLI training path (brief 24).
# Run from Windows:  wsl -d Ubuntu-24.04 -u root -- bash /mnt/c/.../scripts/wsl_setup.sh
set -euo pipefail

echo "== installing base tools =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl git ca-certificates >/dev/null

echo "== installing uv =="
if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo "== done. Next: drop the GitHub token into ~/.oi_github_token (chmod 600) =="
echo "   then run scripts/colab_train_wsl.sh"
