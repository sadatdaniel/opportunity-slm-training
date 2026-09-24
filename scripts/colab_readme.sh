#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
colab readme 2>/dev/null | grep -B5 -A30 -i "colab-cli-oauth-config\|installedappflow\|client secret\|client id" | head -80
